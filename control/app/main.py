import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import settings
from .db import db
from .publish import publish_to_printify

app = FastAPI(title="Adinkra control service")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> str:
    return _now().strftime("%Y-%m-%d")


class Spend(BaseModel):
    room: str
    amount_usd: float = Field(gt=0)
    item: str


@app.get("/health")
async def health():
    await db.command("ping")
    return {"ok": True}


# Kill switch: one flag that every room must check before doing work.
@app.get("/kill-switch")
async def get_kill_switch():
    doc = await db.state.find_one({"_id": "kill_switch"}) or {}
    return {"paused": doc.get("paused", False), "reason": doc.get("reason", "")}


@app.post("/kill-switch/{action}")
async def set_kill_switch(action: str, reason: str = ""):
    if action not in ("pause", "resume"):
        raise HTTPException(404, "action must be pause or resume")
    await db.state.update_one(
        {"_id": "kill_switch"},
        {"$set": {"paused": action == "pause", "reason": reason, "at": _now()}},
        upsert=True,
    )
    return await get_kill_switch()


# Budget ledger: every external call records its cost here first.
@app.post("/budget/spend")
async def record_spend(s: Spend):
    if (await get_kill_switch())["paused"]:
        raise HTTPException(423, "kill switch active")
    day = _today()
    agg = db.spend.aggregate(
        [{"$match": {"room": s.room, "day": day}}, {"$group": {"_id": None, "t": {"$sum": "$amount_usd"}}}]
    )
    spent = next(iter(await agg.to_list(1)), {"t": 0.0})["t"]
    if spent + s.amount_usd > settings.daily_budget_usd:
        raise HTTPException(402, f"daily cap ${settings.daily_budget_usd} reached for {s.room}")
    await db.spend.insert_one({**s.model_dump(), "day": day, "at": _now()})
    return {"room": s.room, "spent_today": spent + s.amount_usd, "cap": settings.daily_budget_usd}


@app.get("/budget/today")
async def spend_today():
    rows = await db.spend.aggregate(
        [{"$match": {"day": _today()}}, {"$group": {"_id": "$room", "spent": {"$sum": "$amount_usd"}}}]
    ).to_list(100)
    return {
        "day": _today(),
        "cap_per_room_usd": settings.daily_budget_usd,
        "rooms": {r["_id"]: round(r["spent"], 4) for r in rows},
    }


@app.post("/briefs")
async def add_brief(brief: dict):
    brief["created_at"] = _now()
    res = await db.briefs.insert_one(brief)
    return {"id": str(res.inserted_id)}


@app.get("/briefs")
async def list_briefs(status: str = "proposed", limit: int = 50):
    docs = await db.briefs.find({"status": status}).sort("created_at", -1).to_list(limit)
    return [{**{k: v for k, v in d.items() if k != "_id"}, "id": str(d["_id"])} for d in docs]


# Drafts: pending_review -> approved -> publishing -> published | failed (or rejected).
@app.post("/drafts")
async def add_draft(draft: dict):
    did = uuid.uuid4().hex[:8]
    await db.drafts.insert_one({**draft, "_id": did, "status": "pending_review", "created_at": _now()})
    return {"id": did}


@app.get("/drafts")
async def list_drafts(status: str = "pending_review"):
    docs = await db.drafts.find({"status": status}).sort("created_at", 1).to_list(100)
    return [{**{k: v for k, v in d.items() if k != "_id"}, "id": d["_id"]} for d in docs]


async def _draft_or_404(did: str) -> dict:
    d = await db.drafts.find_one({"_id": did})
    if not d:
        raise HTTPException(404, "no such draft")
    return d


@app.post("/drafts/{did}/approve")
async def approve_draft(did: str):
    res = await db.drafts.update_one({"_id": did, "status": "pending_review"},
                                     {"$set": {"status": "approved", "approved_at": _now()}})
    if not res.modified_count:
        raise HTTPException(409, f"draft is {(await _draft_or_404(did))['status']}, not pending_review")
    return {"id": did, "status": "approved"}


@app.post("/drafts/{did}/reject")
async def reject_draft(did: str, reason: str = ""):
    res = await db.drafts.update_one({"_id": did, "status": "pending_review"},
                                     {"$set": {"status": "rejected", "reason": reason}})
    if not res.modified_count:
        raise HTTPException(409, "draft is not pending_review")
    return {"id": did, "status": "rejected"}


@app.post("/drafts/{did}/publish")
async def publish_draft(did: str):
    """Every publish passes here: kill switch, human approval, daily cap. Nothing else may publish."""
    if (await get_kill_switch())["paused"]:
        raise HTTPException(423, "kill switch active")
    today = _today()
    if await db.drafts.count_documents({"published_day": today, "status": {"$in": ["publishing", "published"]}}) >= settings.max_publish_per_day:
        raise HTTPException(429, f"daily publish cap {settings.max_publish_per_day} reached")
    claimed = await db.drafts.find_one_and_update({"_id": did, "status": "approved"},
                                                  {"$set": {"status": "publishing", "published_day": today}})
    if not claimed:
        raise HTTPException(409, f"draft is {(await _draft_or_404(did))['status']}, not approved")
    try:
        await publish_to_printify(claimed["product_id"])
    except Exception as e:
        await db.drafts.update_one({"_id": did}, {"$set": {"status": "failed", "error": type(e).__name__}})
        raise HTTPException(502, f"publish failed: {type(e).__name__}")
    await db.drafts.update_one({"_id": did}, {"$set": {"status": "published", "published_at": _now()}})
    return {"id": did, "status": "published"}


def margin_ok(price: float, cost: float, shipping: float, fee_pct: float = 6.5) -> bool:
    """Policy gate piece: refuse listings under the margin floor."""
    profit = price - cost - shipping - price * fee_pct / 100 - 0.20
    return price > 0 and profit / price * 100 >= settings.margin_floor_pct

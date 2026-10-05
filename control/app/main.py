from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import settings
from .db import db

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


def margin_ok(price: float, cost: float, shipping: float, fee_pct: float = 6.5) -> bool:
    """Policy gate piece: refuse listings under the margin floor."""
    profit = price - cost - shipping - price * fee_pct / 100 - 0.20
    return price > 0 and profit / price * 100 >= settings.margin_floor_pct

"""One factory cycle: briefs -> art -> gate -> copy -> policy -> unpublished draft -> Telegram review.
Symbols without a reference image are queued as `needs_reference`, never auto-approved. Never publishes."""
import asyncio
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from research.briefs import generate_briefs  # noqa: E402
from rooms.etsy_pod.artwork import generate_images, quality_gate, reference_path  # noqa: E402
from rooms.etsy_pod.listing import generate_copy  # noqa: E402
from rooms.etsy_pod.pipeline import Rejected, create_draft  # noqa: E402
from rooms.etsy_pod.printify import PrintifyClient  # noqa: E402
from rooms.etsy_pod.review import submit_for_review  # noqa: E402

MAX_DRAFTS_PER_CYCLE = int(os.environ.get("MAX_DRAFTS_PER_CYCLE", 2))
MAX_PENDING_REVIEW = int(os.environ.get("MAX_PENDING_REVIEW", 5))
MIN_BRIEF_QUEUE = 4
MAX_DROPS_PER_CYCLE = 2  # stop spending when images keep failing the gate
CANDIDATES = 1  # one image per attempt, max two attempts: keeps cost per draft low


def tg(env, text):
    return httpx.post(f"https://api.telegram.org/bot{env['TELEGRAM_BOT_TOKEN']}/sendMessage",
                      json={"chat_id": env["TELEGRAM_CHAT_ID"], "text": text}, timeout=20)


async def run_cycle(env: dict, control_url: str = "http://localhost:8000") -> dict:
    out = {"drafted": [], "dropped": [], "missing_refs": set(), "notes": []}
    async with httpx.AsyncClient(base_url=control_url, timeout=60) as control:
        if (await control.get("/kill-switch")).json()["paused"]:
            out["notes"].append("kill switch active: nothing done"); return out

        async def open_briefs():  # proposed + waiting-for-reference, oldest first
            rows = []
            for st in ("proposed", "needs_reference"):
                rows += (await control.get("/briefs", params={"status": st})).json()
            return sorted(rows, key=lambda b: b["created_at"])

        queue = await open_briefs()
        if len([b for b in queue if reference_path(b["symbol"])]) < MIN_BRIEF_QUEUE and len(queue) < MIN_BRIEF_QUEUE:
            try:
                if env.get("BRIEFS_PROVIDER") == "deepseek" and env.get("DEEPSEEK_API_KEY"):  # cheaper text-only step, opt-in
                    ok, _ = await generate_briefs(5, "https://api.deepseek.com", env["DEEPSEEK_API_KEY"],
                                                  env.get("DEEPSEEK_MODEL") or "deepseek-flash", control, est_cost_usd=0.01)
                else:
                    ok, _ = await generate_briefs(5, env["LLM_BASE_URL"], env["LLM_API_KEY"], env["LLM_MODEL"], control)
                for b in ok:
                    (await control.post("/briefs", json=b.model_dump())).raise_for_status()
                queue = await open_briefs()
            except httpx.HTTPStatusError as e:
                out["notes"].append(f"brief generation stopped: HTTP {e.response.status_code}")

        pending = len((await control.get("/drafts", params={"status": "pending_review"})).json())
        # Never make a second listing for the same symbol + product type (plan: no near-duplicates).
        taken = set()
        for st in ("pending_review", "approved", "publishing", "published"):
            for d in (await control.get("/drafts", params={"status": st})).json():
                if d.get("symbol") and d.get("product_type"):
                    taken.add((d["symbol"].strip().lower(), d["product_type"]))
        printify = PrintifyClient(env["PRINTIFY_API_TOKEN"], env["PRINTIFY_SHOP_ID"], control_url=control_url)
        try:
            for brief in queue:
                key = (brief["symbol"].strip().lower(), brief["product_type"])
                if key in taken:
                    await control.post(f"/briefs/{brief['id']}/status", params={"status": "dropped", "note": "duplicate of an existing draft or listing"})
                    continue
                if reference_path(brief["symbol"]) is None:
                    out["missing_refs"].add(brief["symbol"])  # still produced, but flagged shape-unverified for the owner
                if len(out["drafted"]) >= MAX_DRAFTS_PER_CYCLE or pending + len(out["drafted"]) >= MAX_PENDING_REVIEW:
                    out["notes"].append("draft limit reached for this cycle or review queue is full"); break
                try:
                    winner = None
                    last_note = ""
                    for attempt in range(2):  # plan: retry once, then drop
                        imgs = await generate_images(brief, CANDIDATES, env["OPENAI_API_KEY"], env["IMAGE_MODEL"], control)
                        for img in imgs:
                            gate = await quality_gate(brief, img, env["LLM_BASE_URL"], env["LLM_API_KEY"], env["LLM_MODEL"], control,
                                                      # opt-in: set SECOND_REVIEWER=anthropic in .env once the account has credit
                                                      second_key=(env.get("ANTHROPIC_API_KEY") or None) if env.get("SECOND_REVIEWER") == "anthropic" else None,
                                                      second_model=env.get("ANTHROPIC_MODEL") or "claude-sonnet-5-5")
                            last_note = (gate.get("checks") or {}).get("notes", gate.get("reason", ""))
                            if gate["decision"] in ("pass", "pass_unverified_shape"):
                                winner = (img, gate); break
                        if winner:
                            break
                    if not winner:
                        await control.post(f"/briefs/{brief['id']}/status", params={"status": "dropped", "note": f"no image passed the gate: {last_note}"[:200]})
                        out["dropped"].append(f"{brief['symbol']} ({last_note[:80]})")
                        if len(out["dropped"]) >= MAX_DROPS_PER_CYCLE:
                            out["notes"].append("stopped: images keep failing the gate"); break
                        continue
                    copy = await generate_copy(brief, env["LLM_BASE_URL"], env["LLM_API_KEY"], env["LLM_MODEL"], control)
                    result = await create_draft(brief, copy, winner[0], winner[1], printify)
                    did = await submit_for_review(brief, copy, result, winner[0], control, env["TELEGRAM_BOT_TOKEN"], env["TELEGRAM_CHAT_ID"])
                    await control.post(f"/briefs/{brief['id']}/status", params={"status": "drafted", "note": did})
                    out["drafted"].append(did)
                    taken.add(key)
                except Rejected as e:
                    await control.post(f"/briefs/{brief['id']}/status", params={"status": "dropped", "note": str(e)[:200]})
                    out["dropped"].append(f"{brief['symbol']} ({e})")
                except httpx.HTTPStatusError as e:  # 402/423 from the ledger or kill switch: stop the cycle
                    out["notes"].append(f"stopped on HTTP {e.response.status_code} for {brief['symbol']}"); break
        finally:
            await printify.aclose()
    return out


def summary(out: dict) -> str | None:
    parts = []
    if out["drafted"]:
        parts.append(f"{len(out['drafted'])} new draft(s) sent for your review: {', '.join(out['drafted'])}")
    if out["dropped"]:
        parts.append("Dropped: " + "; ".join(out["dropped"]))
    if out["missing_refs"]:
        parts.append("Shape unverified (no reference image) for: " + ", ".join(sorted(out["missing_refs"]))
                     + " (add research/data/reference/<symbol>.png)")
    parts += out["notes"]
    return "Factory cycle: " + " | ".join(parts) if parts else None


async def main():
    env = {**dict(l.split("=", 1) for l in (Path(__file__).resolve().parent.parent.parent / ".env").read_text().splitlines()
                  if "=" in l and not l.startswith("#"))} if (Path(__file__).resolve().parent.parent.parent / ".env").exists() else {}
    env = {**env, **os.environ}
    control_url = env.get("CONTROL_URL", "http://localhost:8000")
    interval = int(env.get("CYCLE_INTERVAL_HOURS", 6)) * 3600
    once = "--once" in sys.argv
    last_missing = None
    while True:
        try:
            out = await run_cycle(env, control_url)
            text = summary(out)
            # don't repeat the same "need references" message every cycle
            if text and not (not out["drafted"] and not out["dropped"] and not out["notes"] and out["missing_refs"] == last_missing):
                tg(env, text)
            last_missing = out["missing_refs"]
            print(text or "cycle: nothing to do")
        except Exception as e:  # never let one bad cycle kill the loop
            print("cycle error:", type(e).__name__)
            if isinstance(e, httpx.TransportError) and not once:
                await asyncio.sleep(300)  # control service probably restarting: retry soon, not in 6 hours
                continue
        if once:
            break
        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(main())

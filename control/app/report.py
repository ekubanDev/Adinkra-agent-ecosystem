"""Results tracking: sales from Printify orders, spend from the ledger, pipeline counts.
ASSUMPTION (unverified until a real order exists): revenue comes from each order line's metadata.price (retail price,
cents); production cost from line_items[].cost and shipping from line_items[].shipping_cost or total_shipping."""
from datetime import datetime, timedelta, timezone

import httpx

from .config import settings
from .db import db

FEE_PCT = 7.0  # combined Shopify + Paystack, UNVERIFIED


def parse_orders(orders: list[dict]) -> dict:
    revenue = cost = shipping = 0.0
    units = 0
    unparsed = 0
    for o in orders:
        items = o.get("line_items") or []
        rev = sum((li.get("metadata") or {}).get("price", 0) * li.get("quantity", 1) for li in items)
        if not items or rev == 0:
            unparsed += 1
        revenue += rev
        cost += sum(li.get("cost", 0) * li.get("quantity", 1) for li in items)
        shipping += o.get("total_shipping") or sum(li.get("shipping_cost", 0) for li in items)
        units += sum(li.get("quantity", 1) for li in items)
    return {"orders": len(orders), "units": units, "revenue": revenue / 100, "production_cost": cost / 100,
            "shipping_cost": shipping / 100, "orders_missing_price": unparsed}


async def fetch_orders(days: int) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    async with httpx.AsyncClient(timeout=30, headers={"Authorization": f"Bearer {settings.printify_api_token}"}) as http:
        for page in range(1, 11):
            r = await http.get(f"https://api.printify.com/v1/shops/{settings.printify_shop_id}/orders.json",
                               params={"page": page, "limit": 50})
            r.raise_for_status()
            data = r.json().get("data", [])
            out += [o for o in data if (o.get("created_at") or "9999") >= since.strftime("%Y-%m-%d")]
            if len(data) < 50:
                break
    return out


async def build_report(days: int = 30) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    spend_rows = await db.spend.aggregate([{"$match": {"day": {"$gte": since}}},
                                           {"$group": {"_id": "$room", "t": {"$sum": "$amount_usd"}}}]).to_list(50)
    ai_spend = round(sum(r["t"] for r in spend_rows), 2)
    counts = {d["_id"]: d["n"] for d in await db.drafts.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}]).to_list(20)}
    try:
        sales = parse_orders(await fetch_orders(days)); sales_ok = True
    except Exception as e:
        sales = parse_orders([]); sales_ok = False; sales["error"] = type(e).__name__
    fees = round(sales["revenue"] * FEE_PCT / 100, 2)
    net = round(sales["revenue"] - sales["production_cost"] - sales["shipping_cost"] - fees - ai_spend, 2)
    return {"days": days, "sales": sales, "sales_source_ok": sales_ok, "fees_assumed": fees, "ai_spend": ai_spend,
            "ai_spend_by_room": {r["_id"]: round(r["t"], 2) for r in spend_rows}, "net_profit": net,
            "drafts": counts, "briefs_proposed": await db.briefs.count_documents({"status": "proposed"})}


def format_report(r: dict) -> str:
    s = r["sales"]
    lines = [f"Adinkra report, last {r['days']} days",
             f"Orders: {s['orders']} ({s['units']} units)  Revenue: ${s['revenue']:.2f}",
             f"Production+shipping: ${s['production_cost'] + s['shipping_cost']:.2f}  Fees (assumed {FEE_PCT:g}%): ${r['fees_assumed']:.2f}",
             f"AI spend: ${r['ai_spend']:.2f}   NET: ${r['net_profit']:.2f}",
             "Drafts: " + (", ".join(f"{k} {v}" for k, v in sorted(r["drafts"].items())) or "none") + f" | briefs queued: {r['briefs_proposed']}"]
    if not r["sales_source_ok"]:
        lines.append(f"WARNING: could not read Printify orders ({s.get('error')}); sales numbers are incomplete")
    if s["orders_missing_price"]:
        lines.append(f"WARNING: {s['orders_missing_price']} order(s) had no readable price")
    return "\n".join(lines)


async def send_telegram(text: str) -> bool:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return False
    async with httpx.AsyncClient(timeout=20) as http:
        r = await http.post(f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                            json={"chat_id": settings.telegram_chat_id, "text": text})
    return r.status_code == 200

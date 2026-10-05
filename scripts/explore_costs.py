"""Read-only: per blueprint, list print providers with the cheapest variant cost and US shipping (USD)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rooms.etsy_pod.printify import PrintifyClient  # noqa: E402

env = dict(l.split("=", 1) for l in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines()
           if "=" in l and not l.startswith("#"))
BLUEPRINTS = {"poster": 282, "mug": 68, "tee": 145}


async def main():
    c = PrintifyClient(env["PRINTIFY_API_TOKEN"], env["PRINTIFY_SHOP_ID"])
    try:
        for kind, bid in BLUEPRINTS.items():
            print(f"\n== {kind} (blueprint {bid})")
            for p in (await c.print_providers(bid))[:8]:
                try:
                    v = await c.variants(bid, p["id"])
                    sh = await c.shipping(bid, p["id"])
                except Exception as e:
                    print(f"  {p['title']}: skipped ({type(e).__name__})"); continue
                prices = sorted(x.get("price", 0) for x in v if x.get("is_available", True))  # cents? printed raw
                us = next((pr for pr in sh.get("profiles", []) if "US" in pr.get("countries", [])), None)
                first = us["first_item"]["cost"] if us else None
                print(f"  {p['id']:>4} {p['title'][:34]:<34} variants={len(v):>3} cost_min={prices[0] if prices else '-'} cost_max={prices[-1] if prices else '-'} us_ship_first={first}")
    finally:
        await c.aclose()

asyncio.run(main())

"""Read-only: find candidate blueprints for poster/mug/tee and print real production + shipping costs.
Run: CONTROL_URL=http://localhost:8000 .venv/bin/python -m scripts.explore_catalog"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rooms.etsy_pod.printify import PrintifyClient  # noqa: E402

env = dict(l.split("=", 1) for l in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines()
           if "=" in l and not l.startswith("#"))

WANT = {"poster": ["poster", "matte vertical posters"], "mug": ["mug", "11oz"], "tee": ["t-shirt", "unisex"]}


async def main():
    c = PrintifyClient(env["PRINTIFY_API_TOKEN"], env["PRINTIFY_SHOP_ID"])
    try:
        bps = await c.blueprints()
        print(len(bps), "blueprints")
        for kind, words in WANT.items():
            hits = [b for b in bps if all(w in b["title"].lower() for w in words[:1]) and (kind != "tee" or "unisex" in b["title"].lower())]
            print(f"\n== {kind}: {len(hits)} matches")
            for b in hits[:6]:
                print(f"  {b['id']:>5}  {b['title']}  ({b.get('brand')})")
    finally:
        await c.aclose()

asyncio.run(main())

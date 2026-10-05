"""Creates ONE unpublished draft per product type with a placeholder image, prints real production cost
(USD) per variant, then deletes the drafts. Never publishes. Run: .venv/bin/python -m scripts.probe_costs"""
import asyncio
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rooms.etsy_pod.printify import PrintifyClient  # noqa: E402

env = dict(l.split("=", 1) for l in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines()
           if "=" in l and not l.startswith("#"))
# (kind, blueprint, provider)
TARGETS = [("poster", 282, 99), ("mug", 68, 1), ("tee", 145, 50)]


def solid_png(w, h, rgb=(40, 40, 40)):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    def chunk(t, d): c = struct.pack(">I", len(d)) + t + d; return c + struct.pack(">I", zlib.crc32(t + d))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


async def main():
    c = PrintifyClient(env["PRINTIFY_API_TOKEN"], env["PRINTIFY_SHOP_ID"])
    made = []
    try:
        img = await c.upload_image("probe.png", solid_png(2000, 2000))
        print("uploaded image", img["id"])
        for kind, bp, pv in TARGETS:
            vs = await c.variants(bp, pv)
            chosen = vs[:3]
            ids = [v["id"] for v in chosen]
            pos = chosen[0]["placeholders"][0]["position"]
            payload = {
                "title": f"PROBE {kind} (delete me)", "description": "cost probe",
                "blueprint_id": bp, "print_provider_id": pv,
                "variants": [{"id": i, "price": 2000, "is_enabled": True} for i in ids],
                "print_areas": [{"variant_ids": ids, "placeholders": [
                    {"position": pos, "images": [{"id": img["id"], "x": 0.5, "y": 0.5, "scale": 1, "angle": 0}]}]}],
            }
            prod = await c.create_product(payload)
            made.append(prod["id"])
            print(f"\n== {kind} draft {prod['id']} published={prod.get('visible')}")
            for v in prod["variants"]:
                if v["id"] in ids:
                    print(f"   variant {v['id']} {v.get('title')}: cost={v.get('cost')} (cents)")
    finally:
        for pid in made:
            await c.delete_product(pid)
        print("\ndeleted drafts:", made)
        await c.aclose()

asyncio.run(main())

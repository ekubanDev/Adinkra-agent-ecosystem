"""PLUMBING TEST ONLY: fakes a gate pass to exercise copy -> policy -> draft -> pricing, then deletes the draft."""
import asyncio, sys
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rooms.etsy_pod.listing import generate_copy, policy_check  # noqa: E402
from rooms.etsy_pod.pipeline import create_draft  # noqa: E402
from rooms.etsy_pod.printify import PrintifyClient  # noqa: E402
env = dict(l.split("=", 1) for l in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines() if "=" in l and not l.startswith("#"))

async def main(img_path, kind):
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30) as control:
        brief = next(b for b in (await control.get("/briefs")).json() if b["product_type"] == kind)
        print("brief:", brief["symbol"], kind)
        copy = await generate_copy(brief, env["LLM_BASE_URL"], env["LLM_API_KEY"], env["LLM_MODEL"], control)
        print("title:", copy["title"]); print("tags:", copy["tags"]); print("policy problems:", policy_check(copy, brief))
        pc = PrintifyClient(env["PRINTIFY_API_TOKEN"], env["PRINTIFY_SHOP_ID"])
        try:
            res = await create_draft(brief, copy, Path(img_path).read_bytes(), {"decision": "pass"}, pc)
            print("draft", res["product_id"], "published:", res["published"])
            for t, cost, price in res["variants"]:
                print(f"   {t}: cost {cost:.2f} -> price {price:.2f}")
            await pc.delete_product(res["product_id"]); print("draft deleted")
        finally:
            await pc.aclose()

asyncio.run(main(sys.argv[1], sys.argv[2]))

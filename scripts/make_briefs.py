"""Generate briefs, store the valid ones in the control service. Run: .venv/bin/python -m scripts.make_briefs 5"""
import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from research.briefs import generate_briefs  # noqa: E402

env = dict(l.split("=", 1) for l in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines()
           if "=" in l and not l.startswith("#"))


async def main(n):
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=20) as control:
        ok, rejected = await generate_briefs(n, env["LLM_BASE_URL"], env["LLM_API_KEY"], env["LLM_MODEL"], control)
        for b in ok:
            (await control.post("/briefs", json=b.model_dump())).raise_for_status()
        print(f"stored {len(ok)}, rejected {len(rejected)}")
        for item, problems in rejected:
            print(" rejected:", item.get("symbol"), problems)
        for b in ok:
            print(f" - {b.symbol} / {b.product_type}: {b.angle}")

asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 5))

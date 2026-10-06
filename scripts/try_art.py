"""Generate 1 candidate for the first stored brief; save to a scratch dir and run the gate (fails closed without a reference)."""
import asyncio, sys
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rooms.etsy_pod.artwork import generate_images, quality_gate  # noqa: E402
env = dict(l.split("=", 1) for l in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines() if "=" in l and not l.startswith("#"))

async def main(out):
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30) as control:
        brief = (await control.get("/briefs")).json()[-1]  # oldest of the stored briefs
        print("brief:", brief["symbol"], brief["product_type"])
        imgs = await generate_images(brief, 1, env["OPENAI_API_KEY"], env["IMAGE_MODEL"], control)
        p = Path(out) / f"{brief['symbol'].lower().replace(' ','_')}_candidate.png"; p.write_bytes(imgs[0]); print("saved", p, len(imgs[0]), "bytes")
        print("gate:", await quality_gate(brief, imgs[0], env["LLM_BASE_URL"], env["LLM_API_KEY"], env["LLM_MODEL"], control))

asyncio.run(main(sys.argv[1]))

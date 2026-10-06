"""Record a draft in the control service and send it to the owner on Telegram for approval."""
import httpx


async def submit_for_review(brief: dict, copy: dict, result: dict, image: bytes, control: httpx.AsyncClient,
                            bot_token: str, chat_id: str) -> str:
    lines = [f"{t}: ${price:.2f} (cost ${cost:.2f})" for t, cost, price in result["variants"]]
    r = await control.post("/drafts", json={
        "product_id": result["product_id"], "symbol": brief["symbol"], "product_type": brief["product_type"],
        "title": copy["title"], "prices": lines, "shape_verified": result.get("shape_verified", False),
    })
    r.raise_for_status()
    did = r.json()["id"]
    warn = "" if result.get("shape_verified") else (
        f"SHAPE NOT VERIFIED. Compare the drawing with a trusted {brief['symbol']} source first. "
        f"If it is right, reply: approve {did} shape ok\n\n")
    caption = (f"Draft {did}: {copy['title']}\n{brief['symbol']} / {brief['product_type']}\n"
               + "\n".join(lines[:6]) + f"\n\n{warn}Reply: approve {did}  or  reject {did}")[:1000]
    async with httpx.AsyncClient(timeout=60) as http:
        resp = await http.post(f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                               data={"chat_id": chat_id, "caption": caption}, files={"photo": ("draft.png", image, "image/png")})
    resp.raise_for_status()
    return did

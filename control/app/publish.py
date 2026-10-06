"""The only code path that publishes to the storefront. Called by the control service after approval checks."""
import asyncio

import httpx

from .config import settings

BODY = {"title": True, "description": True, "images": True, "variants": True, "tags": True,
        "keyFeatures": True, "shipping_template": True}


async def publish_to_printify(product_id: str, retries: int = 3) -> None:
    url = f"https://api.printify.com/v1/shops/{settings.printify_shop_id}/products/{product_id}/publish.json"
    async with httpx.AsyncClient(timeout=30, headers={"Authorization": f"Bearer {settings.printify_api_token}"}) as http:
        for attempt in range(retries + 1):
            r = await http.post(url, json=BODY)
            if r.status_code == 429 or r.status_code >= 500:
                if attempt == retries:
                    r.raise_for_status()
                await asyncio.sleep(float(r.headers.get("retry-after", 2 ** attempt)))
                continue
            r.raise_for_status()
            return

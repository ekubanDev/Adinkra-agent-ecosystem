"""Listing copy and the policy gate. Disclosures are appended by code, never left to the model."""
import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from research.briefs import load_banned  # noqa: E402

DISCLOSURE = (
    "\n\nAbout this design: the artwork was created by us using AI image tools, directed and reviewed by a human. "
    "Printed and shipped on demand by our production partner, Printify print providers; "
    "ship-from location depends on the provider."
)
MAX_TITLE = 100
COPY_COST_USD = 0.02


async def generate_copy(brief: dict, llm_base_url: str, llm_key: str, model: str, control) -> dict:
    r = await control.post("/budget/spend", json={"room": "etsy_pod", "amount_usd": COPY_COST_USD, "item": "listing copy"})
    r.raise_for_status()
    prompt = (
        "Write a Shopify listing for a print-on-demand product. Reply as JSON: "
        '{"title": str (<=90 chars), "description": str (2 short paragraphs, plain text), "tags": [10 to 13 short search phrases]}.\n'
        f"Product: {brief['product_type']}. Design: Adinkra symbol {brief['symbol']} meaning \"{brief['meaning']}\". "
        f"Angle: {brief['angle']} Buyer: {brief['target_buyer']}. Keywords to work in: {', '.join(brief['keywords'])}.\n"
        "Rules: state the symbol's meaning exactly as given; no brands, characters, celebrities or lyrics; "
        "no claims about materials, sizes or shipping times; do not mention AI (that is added separately)."
    )
    async with httpx.AsyncClient(timeout=120) as http:
        resp = await http.post(f"{llm_base_url.rstrip('/')}/chat/completions", headers={"Authorization": f"Bearer {llm_key}"},
                               json={"model": model, "response_format": {"type": "json_object"},
                                     "messages": [{"role": "user", "content": prompt}]})
    resp.raise_for_status()
    copy = json.loads(resp.json()["choices"][0]["message"]["content"])
    copy["description"] = copy["description"].strip() + DISCLOSURE
    return copy


def policy_check(copy: dict, brief: dict) -> list[str]:
    """Problems that block publishing. Empty list = passes."""
    problems = []
    text = " ".join([copy.get("title", ""), copy.get("description", ""), *copy.get("tags", [])]).lower()
    for term in load_banned():
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text):
            problems.append(f"banned term: '{term}'")
    if not copy.get("title") or len(copy["title"]) > MAX_TITLE:
        problems.append(f"title missing or over {MAX_TITLE} chars")
    if not (10 <= len(copy.get("tags", [])) <= 13):
        problems.append("need 10 to 13 tags")
    if "AI image tools" not in copy.get("description", "") or "Printify" not in copy.get("description", ""):
        problems.append("disclosures missing")
    if brief["meaning"].split(";")[0].lower() not in copy.get("description", "").lower():
        problems.append("description does not state the symbol's meaning")
    return problems

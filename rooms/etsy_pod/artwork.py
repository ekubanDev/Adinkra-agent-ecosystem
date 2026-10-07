"""Artwork generation (GPT Image) and the quality gate. Every paid call is recorded on the budget ledger first."""
import base64
import json
from pathlib import Path

import os

import httpx

from research.briefs import load_shape_notes

REF_DIR = Path(os.environ.get("ADINKRA_REF_DIR") or Path(__file__).resolve().parent.parent.parent / "research" / "data" / "reference")
IMAGE_COST_USD = 0.08  # conservative estimate per image (medium quality); true cost should be read back from usage
GATE_COST_USD = 0.02
SIZES = {"poster": "1024x1536", "mug": "1536x1024", "tee": "1024x1024"}


def reference_path(symbol: str) -> Path | None:
    stem = symbol.strip().lower().replace(" ", "_")
    for ext in ("png", "jpg", "jpeg"):
        for name in (stem, stem.replace("_", "-")):
            p = REF_DIR / f"{name}.{ext}"
            if p.exists():
                return p
    return None


def art_prompt(brief: dict) -> str:
    notes = load_shape_notes().get(brief["symbol"].strip().lower())
    form = f" Required form: {notes}" if notes else ""
    return (
        f"Original print design for a {brief['product_type']}: the Adinkra symbol '{brief['symbol']}' "
        f"({brief['meaning']}), drawn faithfully and recognisably.{form} Style: {brief['style_direction']}. "
        f"Mood/angle: {brief['angle']} "
        "Centered composition, generous margins, flat clean shapes suited to printing, solid single background. "
        "ABSOLUTELY NO TEXT: no letters, words, title, caption, subtitle, numbers or signature anywhere in the image; the symbol is the only subject. "
        "No logos, brands, characters or people. Do not add stands, bases, pedestals, ground lines, borders, frames or extra ornaments: the symbol alone. "
        f"Avoid: {', '.join(brief.get('avoid') or []) or 'nothing special'}."
    )


async def _spend(control, amount: float, item: str):
    r = await control.post("/budget/spend", json={"room": "etsy_pod", "amount_usd": amount, "item": item})
    r.raise_for_status()  # 423 kill switch / 402 cap: stop


async def generate_images(brief: dict, n: int, api_key: str, model: str, control) -> list[bytes]:
    """n candidates. Uses the symbol's reference image as an input when one exists."""
    await _spend(control, IMAGE_COST_USD * n, f"images x{n} {brief['symbol']}")
    ref = reference_path(brief["symbol"])
    headers = {"Authorization": f"Bearer {api_key}"}
    size = SIZES[brief["product_type"]]
    async with httpx.AsyncClient(timeout=300) as http:
        if ref:
            r = await http.post("https://api.openai.com/v1/images/edits", headers=headers,
                                data={"model": model, "prompt": art_prompt(brief), "n": str(n), "size": size, "quality": "medium"},
                                files={"image": (ref.name, ref.read_bytes(), "image/png")})
        else:
            r = await http.post("https://api.openai.com/v1/images/generations", headers=headers,
                                json={"model": model, "prompt": art_prompt(brief), "n": n, "size": size, "quality": "medium"})
    r.raise_for_status()
    return [base64.b64decode(d["b64_json"]) for d in r.json()["data"]]


GATE_PROMPT = """You are the quality gate for a print-on-demand shop. Image 1 is the REFERENCE for the Adinkra symbol '{symbol}' ({meaning}).
Image 2 is a generated design. Reply as JSON: {{"symbol_faithful": bool, "legible": bool, "artifacts": bool, "contains_text_or_logo": bool, "policy_issue": bool, "notes": "one sentence"}}.
symbol_faithful = the symbol in image 2 has the same essential shape as the reference (not distorted, missing or invented parts).
artifacts = visible glitches, malformed shapes or noise. contains_text_or_logo = any letters, words, logos or brand marks.
policy_issue = any brand, character, real person or trademark. Be strict."""


async def quality_gate(brief: dict, image: bytes, llm_base_url: str, llm_key: str, model: str, control) -> dict:
    ref = reference_path(brief["symbol"])
    await _spend(control, GATE_COST_USD, f"gate {brief['symbol']}")
    if ref is None:  # no trusted shape reference: check print quality only; the owner must confirm the shape
        return await _quality_only_gate(brief, image, llm_base_url, llm_key, model)

    def data_url(b: bytes) -> str:
        return "data:image/png;base64," + base64.b64encode(b).decode()

    content = [{"type": "text", "text": GATE_PROMPT.format(symbol=brief["symbol"], meaning=brief["meaning"])},
               {"type": "image_url", "image_url": {"url": data_url(ref.read_bytes())}},
               {"type": "image_url", "image_url": {"url": data_url(image)}}]
    async with httpx.AsyncClient(timeout=180) as http:
        r = await http.post(f"{llm_base_url.rstrip('/')}/chat/completions",
                            headers={"Authorization": f"Bearer {llm_key}"},
                            json={"model": model, "response_format": {"type": "json_object"},
                                  "messages": [{"role": "user", "content": content}]})
    r.raise_for_status()
    v = json.loads(r.json()["choices"][0]["message"]["content"])
    ok = v.get("symbol_faithful") and v.get("legible") and not v.get("artifacts") \
        and not v.get("contains_text_or_logo") and not v.get("policy_issue")
    return {"decision": "pass" if ok else "reject", "checks": v}


QUALITY_ONLY_PROMPT = """You are the quality gate for a print-on-demand shop. The image is a generated design of the Adinkra symbol '{symbol}'.
Reply as JSON: {{"legible": bool, "artifacts": bool, "contains_text_or_logo": bool, "policy_issue": bool, "contradicts_form_notes": bool, "notes": "one sentence"}}.
{form_line}
artifacts = visible glitches, malformed shapes, noise or extra invented decoration. contains_text_or_logo = any letters, words, logos or brand marks.
policy_issue = any brand, character, real person or trademark. You cannot verify the symbol's exact shape: do not judge that. Be strict."""


async def _quality_only_gate(brief: dict, image: bytes, llm_base_url: str, llm_key: str, model: str) -> dict:
    notes = load_shape_notes().get(brief["symbol"].strip().lower())
    form_line = (
        f"Written form notes for this symbol: {notes} Set contradicts_form_notes = true if the image clearly adds or changes "
        "anything these notes rule out (for example a stand or base). Otherwise false."
    ) if notes else "contradicts_form_notes = false (no written notes available)."
    url = "data:image/png;base64," + base64.b64encode(image).decode()
    content = [{"type": "text", "text": QUALITY_ONLY_PROMPT.format(symbol=brief["symbol"], form_line=form_line)},
               {"type": "image_url", "image_url": {"url": url}}]
    async with httpx.AsyncClient(timeout=180) as http:
        r = await http.post(f"{llm_base_url.rstrip('/')}/chat/completions", headers={"Authorization": f"Bearer {llm_key}"},
                            json={"model": model, "response_format": {"type": "json_object"},
                                  "messages": [{"role": "user", "content": content}]})
    r.raise_for_status()
    v = json.loads(r.json()["choices"][0]["message"]["content"])
    ok = (v.get("legible") and not v.get("artifacts") and not v.get("contains_text_or_logo")
          and not v.get("policy_issue") and not v.get("contradicts_form_notes"))
    return {"decision": "pass_unverified_shape" if ok else "reject", "checks": v, "shape_verified": False}

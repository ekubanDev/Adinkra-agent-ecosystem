"""Research Lab: brief model, validation against the niche rules (docs/NICHE.md), and LLM generation."""
import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

DATA = Path(__file__).parent / "data"
PRODUCT_TYPES = {"poster", "mug", "tee"}


def load_symbols() -> dict[str, str]:
    return {s["name"].lower(): s["meaning"] for s in json.loads((DATA / "symbols.json").read_text())["symbols"]}


def load_shape_notes() -> dict[str, str]:
    """Written shape descriptions (only where we have a source). Steers generation and catches contradictions."""
    return {s["name"].lower(): s["shape_notes"]
            for s in json.loads((DATA / "symbols.json").read_text())["symbols"] if s.get("shape_notes")}


def load_banned() -> list[str]:
    return [l.strip().lower() for l in (DATA / "banned_terms.txt").read_text().splitlines()
            if l.strip() and not l.startswith("#")]


class Brief(BaseModel):
    symbol: str                      # must exist in symbols.json
    meaning: str                     # must match the reference meaning
    product_type: str                # poster | mug | tee
    target_buyer: str
    angle: str                       # our take, in one or two sentences
    style_direction: str
    keywords: list[str] = Field(min_length=5, max_length=10)
    avoid: list[str] = []
    status: str = "proposed"


def validate_brief(b: Brief) -> list[str]:
    """Return a list of problems; empty means the brief passes."""
    problems = []
    ref = load_symbols().get(b.symbol.strip().lower())
    if ref is None:
        problems.append(f"unknown symbol '{b.symbol}' (not in reference list)")
    elif b.meaning.strip().lower() != ref.lower():
        problems.append(f"meaning for {b.symbol} does not match reference")
    if b.product_type not in PRODUCT_TYPES:
        problems.append(f"product_type must be one of {sorted(PRODUCT_TYPES)}")
    text = " ".join([b.angle, b.style_direction, b.target_buyer, *b.keywords]).lower()
    for term in load_banned():
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text):
            problems.append(f"banned term: '{term}'")
    return problems


PROMPT = """You are the Research Lab for a print-on-demand shop selling meaning-first Adinkra designs
(one symbol plus its meaning, in a modern style) to diaspora and culture-conscious buyers in the US/UK.

Write {n} design briefs as JSON: {{"briefs": [...]}}. Each brief has exactly these fields:
symbol, meaning, product_type, target_buyer, angle, style_direction, keywords (5 to 10 search phrases), avoid (list).

Hard rules:
- symbol and meaning MUST be copied exactly from this reference list (never invent symbols or meanings):
{symbols}
- product_type is one of: poster, mug, tee. Vary symbols and product types across the briefs.
- No brands, logos, characters, real people, celebrities, team names or song lyrics anywhere.
- Do not reference or describe any other seller's design. Describe our own original angle.
- Keywords are phrases a buyer might search; no brand names.
"""


async def generate_briefs(n: int, llm_base_url: str, llm_key: str, model: str, control, est_cost_usd: float = 0.05):
    """Ask the model for briefs, keep only the ones that pass validation. `control` is an httpx.AsyncClient for the control service."""
    import httpx

    sw = await control.post("/budget/spend", json={"room": "research_lab", "amount_usd": est_cost_usd, "item": f"briefs x{n}"})
    sw.raise_for_status()  # 423 kill switch / 402 budget cap both raise here: do not proceed
    symbols = "\n".join(f"- {k.title()}: {v}" for k, v in load_symbols().items())
    async with httpx.AsyncClient(timeout=180) as http:
        r = await http.post(
            f"{llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {llm_key}"},
            json={"model": model, "response_format": {"type": "json_object"},
                  "messages": [{"role": "user", "content": PROMPT.format(n=n, symbols=symbols)}]},
        )
    r.raise_for_status()
    raw = json.loads(r.json()["choices"][0]["message"]["content"])["briefs"]
    ok, rejected = [], []
    for item in raw:
        try:
            b = Brief(**item)
        except Exception as e:
            rejected.append((item, [f"schema: {e.__class__.__name__}"])); continue
        problems = validate_brief(b)
        (rejected.append((item, problems)) if problems else ok.append(b))
    return ok, rejected

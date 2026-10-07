"""Traffic pack: Pinterest pin text, short captions and a symbol story for a live listing.
Sent to the owner on Telegram to post BY HAND: no platform accounts or posting APIs are used here."""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlencode

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from research.briefs import load_banned, load_symbols  # noqa: E402

PACK_COST_USD = 0.01
PACKS_PER_CYCLE = 2
# Claims we never make: invented scarcity, social proof, guarantees, income or health claims.
FORBIDDEN = ["limited edition", "only a few left", "selling fast", "best seller", "bestseller", "best-selling", "guaranteed",
             "sold out", "hurry", "act now", "5-star", "five star", "reviews say", "customers love", "#1"]

PROMPT = """Write a small social-media pack for a print-on-demand product, as JSON:
{{"pins": [{{"title": str (<=90 chars), "description": str (<=350 chars), "board": str}}, x3],
  "captions": [{{"text": str (<=220 chars), "hashtags": [4 to 6 tags without #]}}, x2],
  "story": str (<=500 chars: the symbol's meaning and why someone might give or keep this)}}
Product: {title}. Symbol: {symbol}, meaning "{meaning}". Product type: {ptype}. Buyer: diaspora and culture-conscious shoppers in the US/UK.
Rules: state the meaning exactly as given. Warm, specific, respectful of the culture; no hype. Do NOT claim scarcity, bestseller status,
reviews, guarantees or shipping times. No brands, celebrities or song lyrics. Do not mention prices. Do not include links."""


def validate_pack(pack: dict, symbol: str) -> list[str]:
    problems = []
    if len(pack.get("pins", [])) != 3 or len(pack.get("captions", [])) != 2 or not pack.get("story"):
        return ["pack must have 3 pins, 2 captions and a story"]
    text = json.dumps(pack, ensure_ascii=False).lower()
    for term in load_banned():
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text):
            problems.append(f"banned term: '{term}'")
    for phrase in FORBIDDEN:
        if phrase in text:
            problems.append(f"forbidden claim: '{phrase}'")
    for pin in pack["pins"]:
        if len(pin.get("title", "")) > 100 or not pin.get("description"):
            problems.append("pin title too long or description missing")
    meaning_head = (load_symbols().get(symbol.strip().lower()) or "").split(";")[0].lower()
    if meaning_head and meaning_head not in pack["story"].lower():
        problems.append("story does not state the symbol's meaning")
    return problems


def tracked_url(product_url: str, source: str, draft_id: str) -> str:
    return product_url + ("&" if "?" in product_url else "?") + urlencode(
        {"utm_source": source, "utm_medium": "social", "utm_campaign": draft_id})


def format_pack(pack: dict, product_url: str, draft_id: str, symbol: str) -> str:
    lines = [f"TRAFFIC PACK: {symbol} ({draft_id})",
             "Post these by hand. Where Pinterest, Instagram or TikTok ask whether content is AI-generated or AI-assisted, say yes: the artwork is.", ""]
    for i, p in enumerate(pack["pins"], 1):
        lines += [f"PIN {i} (board: {p.get('board', 'Adinkra wall art')})", p["title"], p["description"],
                  "Link: " + tracked_url(product_url, "pinterest", draft_id), ""]
    for i, c in enumerate(pack["captions"], 1):
        tags = " ".join("#" + t.lstrip("#").replace(" ", "") for t in c.get("hashtags", []))
        lines += [f"CAPTION {i} (Instagram / TikTok)", c["text"], tags, "Link in bio: " + tracked_url(product_url, "social", draft_id), ""]
    lines += ["STORY (blog or long caption)", pack["story"]]
    return "\n".join(lines)


async def build_pack(title: str, symbol: str, ptype: str, llm_base_url: str, llm_key: str, model: str, control,
                     est_cost_usd: float = PACK_COST_USD) -> tuple[dict | None, list[str]]:
    r = await control.post("/budget/spend", json={"room": "marketing", "amount_usd": est_cost_usd, "item": f"pack {symbol}"})
    r.raise_for_status()  # 423 / 402: stop
    meaning = load_symbols().get(symbol.strip().lower(), "")
    async with httpx.AsyncClient(timeout=180) as http:
        resp = await http.post(f"{llm_base_url.rstrip('/')}/chat/completions", headers={"Authorization": f"Bearer {llm_key}"},
                               json={"model": model, "response_format": {"type": "json_object"},
                                     "messages": [{"role": "user", "content": PROMPT.format(title=title, symbol=symbol, meaning=meaning, ptype=ptype)}]})
    resp.raise_for_status()
    pack = json.loads(resp.json()["choices"][0]["message"]["content"])
    problems = validate_pack(pack, symbol)
    return (None, problems) if problems else (pack, [])


async def marketing_step(env: dict, control, printify) -> list[str]:
    """For live, gate-approved listings with no pack yet: build a pack and send it to the owner. Never posts anything itself."""
    sent = []
    if env.get("BRIEFS_PROVIDER") == "deepseek" and env.get("DEEPSEEK_API_KEY"):
        base, key, model, cost = "https://api.deepseek.com", env["DEEPSEEK_API_KEY"], env.get("DEEPSEEK_MODEL") or "deepseek-flash", 0.01
    else:
        base, key, model, cost = env["LLM_BASE_URL"], env["LLM_API_KEY"], env["LLM_MODEL"], PACK_COST_USD
    drafts = (await control.get("/drafts", params={"status": "published"})).json()
    for d in drafts:
        if len(sent) >= PACKS_PER_CYCLE:
            break
        # skip: already sent, flagged, or published outside the approval gate (those carry a note)
        if d.get("marketing_sent_at") or d.get("no_marketing") or d.get("note") or not d.get("symbol"):
            continue
        product = await printify.get_product(d["product_id"])
        url = (product.get("external") or {}).get("handle")
        if not url:
            continue
        pack, problems = await build_pack(product["title"], d["symbol"], d.get("product_type", ""), base, key, model, control, cost)
        if problems:
            continue  # try again next cycle; nothing is sent
        text = format_pack(pack, url, d["id"], d["symbol"])
        img = (product.get("images") or [{}])[0].get("src")
        async with httpx.AsyncClient(timeout=60) as http:
            tg = f"https://api.telegram.org/bot{env['TELEGRAM_BOT_TOKEN']}"
            if img:
                await http.post(f"{tg}/sendPhoto", json={"chat_id": env["TELEGRAM_CHAT_ID"], "photo": img,
                                                          "caption": f"Traffic pack ready for {d['symbol']} {d.get('product_type', '')}"})
            r = await http.post(f"{tg}/sendMessage", json={"chat_id": env["TELEGRAM_CHAT_ID"], "text": text[:4000]})
        if r.status_code == 200:
            (await control.post(f"/drafts/{d['id']}/marketing-sent")).raise_for_status()
            sent.append(d["id"])
    return sent

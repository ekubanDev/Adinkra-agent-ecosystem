"""Phase 0 smoke test: one cheap call per external service. Run: python scripts/check_keys.py
Reads .env from the repo root. Prints pass/fail only, never key values."""
import os
import sys
from pathlib import Path

import httpx

env = {}
for line in (Path(__file__).resolve().parent.parent / ".env").read_text().splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
env = {**env, **{k: v for k, v in os.environ.items() if k in env and v}}


def need(*names):
    missing = [n for n in names if not env.get(n)]
    if missing:
        raise RuntimeError("missing in .env: " + ", ".join(missing))


def check_llm():
    need("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")
    r = httpx.get(f"{env['LLM_BASE_URL'].rstrip('/')}/models",
                  headers={"Authorization": f"Bearer {env['LLM_API_KEY']}"}, timeout=20)
    r.raise_for_status()
    ids = {m["id"] for m in r.json().get("data", [])}
    # OpenRouter-style endpoints may list differently; report rather than fail hard.
    return f"model {env['LLM_MODEL']} " + ("available" if env["LLM_MODEL"] in ids else "NOT in model list")


def check_images():
    need("OPENAI_API_KEY", "IMAGE_MODEL")
    r = httpx.get("https://api.openai.com/v1/models",
                  headers={"Authorization": f"Bearer {env['OPENAI_API_KEY']}"}, timeout=20)
    r.raise_for_status()
    ids = {m["id"] for m in r.json().get("data", [])}
    return f"model {env['IMAGE_MODEL']} " + ("available" if env["IMAGE_MODEL"] in ids else "NOT in model list")


def check_printify():
    need("PRINTIFY_API_TOKEN", "PRINTIFY_SHOP_ID")
    h = {"Authorization": f"Bearer {env['PRINTIFY_API_TOKEN']}"}
    r = httpx.get("https://api.printify.com/v1/shops.json", headers=h, timeout=20)
    r.raise_for_status()
    shops = {str(s["id"]): s for s in r.json()}
    s = shops.get(env["PRINTIFY_SHOP_ID"])
    if not s:
        raise RuntimeError(f"shop id not found; token sees {len(shops)} shop(s)")
    return f"shop '{s['title']}' ({s.get('sales_channel')})"


def check_telegram():
    need("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
    r = httpx.post(f"https://api.telegram.org/bot{env['TELEGRAM_BOT_TOKEN']}/sendMessage",
                   json={"chat_id": env["TELEGRAM_CHAT_ID"], "text": "Adinkra Overseer: Phase 0 test message"},
                   timeout=20)
    r.raise_for_status()
    return "test message sent"


ok = True
for name, fn in [("LLM", check_llm), ("Images", check_images), ("Printify", check_printify), ("Telegram", check_telegram)]:
    try:
        print(f"PASS {name}: {fn()}")
    except httpx.HTTPStatusError as e:
        ok = False
        print(f"FAIL {name}: HTTP {e.response.status_code}")  # no URL/body: avoids echoing tokens
    except Exception as e:
        ok = False
        print(f"FAIL {name}: {type(e).__name__}: {e}" if not isinstance(e, httpx.HTTPError) else f"FAIL {name}: {type(e).__name__}")
sys.exit(0 if ok else 1)

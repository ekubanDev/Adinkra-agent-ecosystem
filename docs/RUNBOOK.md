# Runbook

## Start / stop
- Start everything: `docker compose up -d --build`   (services: mongo, control, overseer, factory)
- Stop everything: `docker compose down`   (data stays in the `mongo_data` volume and `overseer/data/`)
- Logs: `docker compose logs -f factory` (or `control`, `overseer`)
- Check keys: `.venv/bin/python scripts/check_keys.py`   (Python venv: `python3 -m venv .venv && .venv/bin/pip install httpx pydantic pytest`)

## Daily use (all from Telegram, only your account can talk to the bot)
- `status` - kill switch and spend. `report` - orders, costs, net profit.
- `drafts` - list pending drafts. `approve <id>` - approve and publish. `reject <id> [reason]`.
- `pause` - stops every room. **Resume is deliberately not available to the bot:** run on the server
  `curl -X POST localhost:8000/kill-switch/resume`.
- A daily report is sent automatically at `REPORT_HOUR_UTC` (default 18:00 UTC).
- If the bot answers oddly or drifts, send `/new now` to start a fresh session.

## Feeding the factory
- Add one correct reference image per symbol to `research/data/reference/` (`sankofa.png`, `gye_nyame.png`, ...).
  The next cycle (every `CYCLE_INTERVAL_HOURS`, default 6) picks it up. Trigger one now: `docker compose restart factory`.
- Symbols and meanings live in `research/data/symbols.json` (all `verified: false` until a cultural adviser signs off).
- Extend `research/data/banned_terms.txt` as you learn which phrases to avoid.

## Limits (all in `.env`)
`DAILY_BUDGET_USD` (per room), `MARGIN_FLOOR_PCT`, `MAX_PUBLISH_PER_DAY` (slow ramp), `MAX_DRAFTS_PER_CYCLE`, `MAX_PENDING_REVIEW`.
A failed publish still uses one of the day's publish slots (conservative).

## Safety design
- Only the control service publishes (`POST /drafts/{id}/publish`): kill switch, human approval, atomic daily cap.
- The Overseer has no shell, file or web tools; it uses six MCP tools (`overseer/mcp/adinkra_control.py`).
- Secrets live in `.env` only (git-ignored). Never paste keys into chat; revoke any that were exposed.

## Known gaps
- Fees (7%) are assumed, not verified against the real Shopify plan and Paystack rates.
- Order parsing in the report is unverified until a real order exists.
- Quality gate has only been run against a stand-in reference, never a trusted one.
- No Shopify views/favourites yet (needs a Shopify custom-app access token).
- Do a small real test order (Printify billing from Ghana, Paystack payout) before real sales.

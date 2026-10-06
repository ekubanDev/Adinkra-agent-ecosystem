# adinkra-agent-ecosystem (Tesseract Holdings)

Project context for Claude Code. The full plan is in `docs/PLAN.md` (copy of AI_Agent_Ecosystem_Plan.md). Read it before starting work.

## What we're building
An autonomous AI agent ecosystem, pictured as a "space station":
- **Overseer**: a Hermes Agent (Nous Research) that plans, assigns and checks all work, and enforces budgets, the policy gate and the kill switch.
- **Research Lab**: finds demand (never copies designs) and writes design briefs.
- **Factory Room 1**: Etsy print-on-demand. Brief → GPT Image 2 artwork → quality check → Printify product → listing copy with AI and production-partner disclosures → publish → track.
- Future rooms (Fiverr, game assets, music) come only after Room 1 passes a 30-day hands-off run.

## Stack
- Hermes Agent on a Linux VPS or in Docker (orchestration, sub-agents, schedules, Telegram gateway)
- Reasoning model: GPT-5.5 via an OpenAI-compatible endpoint or OpenRouter (keep it configurable)
- Images: OpenAI GPT Image 2
- Fulfilment: Printify API (600 req/min global, 200 publishes per 30 min, errors under 5%)
- Control service: FastAPI (Python)
- Database: MongoDB
- Reports and alerts: Telegram

## Current phase: 1 Build the loop (Phase 0 done; see docs/RUNBOOK.md)
- [x] Storefront route decided: Shopify + Printify + Paystack, connected (see docs/STOREFRONT_DECISION.md). Etsy Payments isn't available to Ghana-based sellers.
- [x] Accounts and API keys: OpenAI (with a spend cap), Printify, Telegram bot (checked with scripts/check_keys.py)
- [x] Server: Hermes + FastAPI + MongoDB running in docker-compose, Overseer replies on Telegram
- [x] First niche and up to 3 product types chosen: meaning-first Adinkra/African-heritage designs; poster, mug, tee (see docs/NICHE.md)

## Rules for all code
- Keep secrets in `.env` and never commit them.
- Every external call has a budget check, a rate limiter, and retry with backoff.
- Policy gate before publishing: no trademarks, brands, characters or real people; disclosures always included.
- Keep the storefront behind an interface (Etsy-via-Printify or Shopify-via-Printify) so it can be swapped.
- A kill switch pauses all rooms.

## Suggested repo layout
```
/overseer        Hermes config, skills, schedules
/control         FastAPI service: tasks, budget ledger, policy checks
/rooms/etsy_pod  Factory Room 1 pipeline
/research        Research Lab agents
/docs            PLAN.md
docker-compose.yml
.env.example
```

## Phase 1 status
- [x] Control service (kill switch, budget ledger, drafts, approval-gated publish, report), Overseer on Telegram with narrow MCP tools
- [x] Printify client, pricing/margin rule, Research Lab briefs, artwork + quality gate, listing copy + policy gate, draft + Telegram review
- [x] Factory cycle container (reference-aware; queues symbols without a reference image)
- [ ] Reference images for the first symbols (owner) -> first real drafts
- [ ] 20 live listings, no policy strikes; small real test order
- [ ] Shopify views/favourites in the report (needs access token)

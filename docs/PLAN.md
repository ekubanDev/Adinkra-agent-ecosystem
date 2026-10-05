# AI Agent Ecosystem: Architecture & Build Plan

As of 4 Oct 2026 · Cro

## Overview

Phase 1 builds one working loop: a Hermes Overseer runs a Research Lab and one Factory Room that designs, lists and sells print-on-demand products on Etsy with no human steps. Everything else (Fiverr, game assets, music) waits until that loop has made its first sales.

The space station is how we picture and present the system. Underneath, it's a set of agents on one server, sharing a task board, a database and a budget.

- **Overseer:** one Hermes agent that plans the work, assigns it, checks it and stops anything going wrong.
- **Research Lab:** agents that find what buyers want right now and turn it into design briefs.
- **Factory Rooms:** agents that each run one business. Room 1 is Etsy print-on-demand.
- **Long-term goal:** a trillion dollars, which is the story. The phase 1 goal is a loop that runs for 30 days with no human help and earns more than it costs.

## System architecture

```
                 You  (daily summary, alerts, kill switch)
                  ▲▼   Telegram or WhatsApp
Control service ◄──► OVERSEER (Hermes Agent)
(FastAPI + MongoDB:   plans, assigns, checks all work,
 tasks, budgets, logs) enforces budgets and the kill switch
                        │
        ┌───────────────┼────────────────┐
        ▼               ▼                ▼
  Research Lab ──► Factory Room 1:   Future rooms
  (finds demand,     Etsy            (Fiverr, game
   writes briefs)  (designs,          assets, music)
        ▲           products,
        │           listings)
        │               │ products
        │               ▼
        │           Printify ──────► Etsy shop
        │        (prints & ships)   (buyers, orders, payouts)
        │                                 │
        └──────── sales and traffic data ─┘
```

The Overseer sends briefs and tasks down to every room, the Factory hands products to Printify, and Etsy sales flow back to the Research Lab to shape the next briefs. Future rooms plug into the same task bus later.

## The Overseer

The Overseer is one [Hermes Agent](https://hermes-agent.org/) instance (Nous Research, MIT licence) running on your server around the clock. Hermes already has what this role needs: scheduled jobs, parallel sub-agents, persistent memory, saved skills, and a chat gateway (Telegram, WhatsApp, Slack) so it can report to you.

**Its loop, every cycle:**

1. Read the task board and the scoreboard (sales, spend, errors).
2. Ask the Research Lab for new briefs when the queue is low.
3. Hand briefs to the Factory Room agents as sub-agent tasks.
4. Check every output against the quality and policy rules before it goes live.
5. Record results, update its skills, and send you a daily summary.

**Guardrails it enforces:**

- **Budget caps:** a daily spend limit per room for model calls, image generation and listing fees. It stops the room when the cap is hit.
- **Policy gate:** no trademarks, brand names, characters or real people in designs or titles. Every listing gets the AI and production-partner disclosures.
- **Rate limits:** stay under Etsy and Printify API limits with backoff and retries.
- **Kill switch:** one command from you pauses all rooms. It also pauses rooms on its own after repeated errors or a policy strike from Etsy.

**Model:** you named GPT-5.5. Hermes can use any OpenAI-compatible endpoint or OpenRouter, so the model can change later without rebuilding. OpenAI's pricing page now lists the GPT-5.6 family, so compare before you commit.

## Factory Room 1: Etsy print-on-demand

Each design goes from brief to live listing in seven steps. Printify prints and ships every order, so there's no stock and no shipping work.

1. **Take a brief** from the Research Lab: niche, buyer, product type (for example tee, mug or poster), style notes and 5 to 10 keywords.
2. **Generate artwork** with GPT Image 2: several options per brief at print resolution, on a transparent background where the product needs one.
3. **Check quality:** a vision model scores each image for legibility, artifacts, text errors and policy issues. Rejected images are retried once, then dropped.
4. **Create the product** through the [Printify API](https://developers.printify.com/): upload the image, place it on the product blueprint, set variants and price.
5. **Write the listing:** title, 13 tags, description, plus the AI-use and production-partner disclosures.
6. **Publish** to the connected Etsy shop through Printify.
7. **Track results:** views, favourites and sales feed back to the Research Lab. Listings with no traction after a set period are retired or reworked.

**Pricing rule:** price = Printify base cost + shipping + Etsy fees + a target margin. The Overseer refuses any listing whose margin falls under the floor.

## Research Lab

The Research Lab looks for demand (what buyers search for and buy) and turns it into briefs for the Factory. It studies the demand behind a successful design and never copies the design itself.

**Signals it watches:**

- Etsy search suggestions, bestseller tags and seasonal trends
- Upcoming holidays and events, planned 6 to 8 weeks ahead
- Our own shop data: which niches, styles and products convert

**What a brief contains:** niche, target buyer, product type, the angle we take, style direction, keywords, and a short list of words and themes to avoid.

**Originality rules:**

- Never pass another seller's image, wording or layout to the Factory as a reference.
- No brands, logos, characters, celebrities, team names or song lyrics.
- Check every brief's keywords against a banned-terms list, and check new phrases against a trademark search before they're used.

This keeps the shop inside Etsy's rule that the seller is the designer, and it protects the account from IP takedowns.

## Tech stack and integrations

| Layer | Choice | Job |
| --- | --- | --- |
| Orchestration | Hermes Agent on a Linux VPS or in Docker | Overseer, sub-agents, schedules, memory, skills |
| Reasoning model | GPT-5.5 through an OpenAI-compatible endpoint or OpenRouter | Planning, briefs, listing copy, checks |
| Image generation | OpenAI GPT Image 2 | Artwork |
| Production and fulfilment | Printify API | Uploads, products, publishing to Etsy, orders, webhooks |
| Storefront | Etsy shop connected to Printify | Sales |
| Control service | FastAPI | Task board, budget ledger, policy checks, API keys |
| Database | MongoDB | Briefs, designs, listings, sales, spend, agent logs |
| Reporting | Hermes gateway to Telegram or WhatsApp | Daily summary, alerts, kill switch |
| Station view (later) | React dashboard | The space-station picture of live agents and rooms |

**Limits to design around:** Printify allows 600 requests a minute overall and 200 product publishes per 30 minutes, and errors must stay under 5% of requests.

## Platform rules and risks

**The biggest risk is that Etsy Payments isn't available to sellers in Ghana.** Etsy's [eligible countries list](https://help.etsy.com/hc/articles/115015710408) includes only Egypt, Morocco and South Africa in Africa, and opening a shop needs a residential address and a bank account in an eligible country. This has to be solved before anything is built.

| Rule or risk | What it means for us | How we handle it |
| --- | --- | --- |
| Seller eligibility | No Etsy Payments for a Ghana-based seller | Decide the storefront route before phase 1 starts |
| AI disclosure | Etsy's [Creativity Standards](https://www.etsy.com/legal/creativity) allow AI-made items from the seller's own prompts, but the listing must say AI was used | Disclosure text added to every listing automatically |
| Production partner | The partner must be disclosed, with accurate ship-from details | Printify set as production partner in shop settings |
| Human creative input | 2026 guidance expects real creative input; low-effort AI output may fail the originality standard | Our own niches, briefs and art direction; quality gate; no mass-produced near-duplicates |
| IP takedowns | Copied designs or trademarked words get listings removed and shops suspended | Originality rules and banned-terms check |
| Fees | $0.20 per listing, 6.5% transaction fee, 12% Offsite Ads fee above $10,000 a year in sales | Built into the pricing rule |
| Fully autonomous, no human review | One bad batch can get the shop suspended | Policy gate, slow ramp in listings per day, kill switch, alerts to you |

## Costs and unit economics

Each new listing should cost well under $1 to make, so the real costs are fees on each sale and the time listings take to sell. These figures are approximate and need checking against real usage in phase 1.

| Cost item | Approximate cost | Basis |
| --- | --- | --- |
| Artwork, 4 options per listing | $0.10 to $0.50 | GPT Image 2 at $30 per 1M image output tokens |
| Briefs, checks and listing copy | A few cents | Model token usage per listing |
| Etsy listing fee | $0.20 | Per listing |
| Server | Low tens of dollars a month | Small VPS for Hermes, FastAPI and MongoDB |

**On each sale:** Etsy takes 6.5% of the sale price including shipping, plus payment processing, plus 12% on Offsite Ads sales once the shop passes $10,000 a year. Printify charges its base cost and shipping per item.

**Margin check per product:** sale price − Printify cost − shipping − Etsy fees − AI cost spread over expected sales = profit. The Overseer runs this before every publish.

## Phased build plan

Each phase starts only when the gate before it is passed.

| Phase | Work | Gate to move on |
| --- | --- | --- |
| 0 Foundations | Storefront decision, accounts and API keys, server and Hermes | Shop can take payments legally |
| 1 Build the loop | Research Lab, Room 1, control service, first 20 listings | 20 listings live, no policy strikes |
| 2 Go autonomous | Hands-off for 30 days, slow ramp in listings, daily reports | 30 days hands-off, earning more than it costs |
| 3 Expand | Room 2 (Fiverr or digital assets), station dashboard | — |

Dates get set once the storefront decision is made.

## Open decisions

- [ ] **Storefront route:** Etsy needs a seller who meets its address and bank rules in an eligible country. Options are a legitimate business presence in an eligible country, or starting on a storefront you can sell from today, such as Shopify with Printify. Get advice before choosing; don't use a borrowed address or account.
- [ ] **Overseer model:** stay on GPT-5.5, or compare it with the GPT-5.6 family on cost and quality.
- [ ] **First niche:** pick one niche and up to 3 product types for the first 50 listings.
- [ ] **Margin floor and daily budget cap** for Factory Room 1.
- [ ] **Your role:** fully autonomous from day one, or a short period where you approve listings before going hands-off.
- [ ] **Station view:** build the space-station dashboard in phase 1 for content, or wait until the loop works.

## Sources

- [Hermes Agent](https://hermes-agent.org/)
- [Etsy: Countries eligible for Etsy Payments](https://help.etsy.com/hc/articles/115015710408)
- [Etsy: Creativity Standards](https://www.etsy.com/legal/creativity)
- [Listadum: Print-on-demand on Etsy in 2026](https://www.listadum.com/blog/understanding-etsys-rules-for-print-on-demand-sellers)
- [SelfEmployed: Etsy 2026 AI disclosure and fees](https://www.selfemployed.com/news/etsy-seller-ai-disclosure-fees-2026/)
- [Printify API](https://developers.printify.com/)
- [OpenAI API pricing](https://openai.com/api/pricing/)

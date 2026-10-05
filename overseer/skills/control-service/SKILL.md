---
name: control-service
description: "Check the kill switch and record spend with the Adinkra control service before any paid or external action."
version: 1.0.0
metadata:
  hermes:
    tags: [adinkra, budget, kill-switch]
---

# Control service

Base URL: `http://control:8000` (inside the Docker network).

## Before every paid or external action
1. `curl -s http://control:8000/kill-switch` -> if `"paused": true`, stop and tell the owner.
2. Record the cost first:
   `curl -s -X POST http://control:8000/budget/spend -H 'content-type: application/json' -d '{"room":"<room>","amount_usd":<est>,"item":"<what>"}'`
   - HTTP 423 = kill switch active. HTTP 402 = daily cap reached. Either way: do not proceed; report to the owner.

## Owner commands (from Telegram)
- "pause" -> `curl -s -X POST 'http://control:8000/kill-switch/pause?reason=<why>'`
- "resume" -> `curl -s -X POST http://control:8000/kill-switch/resume`
- "status" -> read `/kill-switch` and `curl -s http://control:8000/budget/today`, then summarise pause state and spend per room against the cap.

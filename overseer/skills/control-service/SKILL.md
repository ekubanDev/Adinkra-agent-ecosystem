---
name: control-service
description: "Check the kill switch and spend through the adinkra_control tools before any paid or external action."
version: 2.0.0
metadata:
  hermes:
    tags: [adinkra, budget, kill-switch]
---

# Control service (via the adinkra_control tools)

You have no shell, file or web tools. All control-service access goes through these tools:
`kill_switch_status`, `pause_all`, `spend_today`, `report`, `list_drafts`, `approve_and_publish`, `reject_draft`.

- Before any work, call `kill_switch_status`. If `paused` is true, stop and tell the owner.
- "status" -> call `kill_switch_status` and `spend_today`; summarise pause state and spend per room against the cap.
- "report" / "how are we doing" -> call `report` (default 30 days) and give the owner the key numbers; flag any WARNING lines.
- "pause" (or repeated errors / a platform policy warning) -> call `pause_all` with a short reason, then tell the owner.
- "resume" -> you cannot resume. Tell the owner to run: `curl -X POST localhost:8000/kill-switch/resume` on the server.
- Paid actions (model calls, images) are budgeted by the room code itself, not by you.

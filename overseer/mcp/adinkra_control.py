"""Narrow MCP tool surface for the Overseer: the ONLY way it touches the control service.
Deliberately absent: resume (the agent may stop the system, never restart it), budget writes, raw HTTP, shell."""
import os

import httpx
from mcp.server.mcpserver import MCPServer

BASE = os.environ.get("CONTROL_URL", "http://control:8000")
mcp = MCPServer("adinkra-control")


def _call(method: str, path: str, **kw) -> str:
    try:
        r = httpx.request(method, BASE + path, timeout=60, **kw)
    except httpx.HTTPError as e:
        return f"ERROR: control service unreachable ({type(e).__name__}). Do not proceed."
    meaning = {423: "kill switch active", 409: "draft not in the right state", 429: "daily publish cap reached", 428: "symbol shape unverified: ask the owner to confirm with 'shape ok'",
               402: "budget cap reached", 502: "storefront (Printify) call failed", 404: "not found"}.get(r.status_code, "")
    return f"HTTP {r.status_code}{' (' + meaning + ')' if meaning else ''}: {r.text[:1500]}"


@mcp.tool()
def kill_switch_status() -> str:
    """Is the system paused? Check before any work."""
    return _call("GET", "/kill-switch")


@mcp.tool()
def pause_all(reason: str) -> str:
    """Pause every room (kill switch ON). Use on repeated errors, policy warnings or the owner's 'pause'. Cannot be undone by the agent."""
    return _call("POST", "/kill-switch/pause", params={"reason": reason[:200]})


@mcp.tool()
def spend_today() -> str:
    """Today's spend per room against the daily cap."""
    return _call("GET", "/budget/today")


@mcp.tool()
def report(days: int = 30) -> str:
    """Results: orders, revenue, costs, AI spend, net profit and draft counts over the last N days (read-only)."""
    return _call("GET", "/report", params={"days": max(1, min(days, 365))})


@mcp.tool()
def list_drafts(status: str = "pending_review") -> str:
    """List drafts by status: pending_review, approved, published, failed, rejected."""
    return _call("GET", "/drafts", params={"status": status})


@mcp.tool()
def approve_and_publish(draft_id: str, shape_confirmed: bool = False) -> str:
    """ONLY when the owner's own Telegram message says 'approve <id>'. Set shape_confirmed=true ONLY if that same message
    explicitly says the shape is ok (e.g. 'approve <id> shape ok'). Never set it on your own."""
    a = _call("POST", f"/drafts/{draft_id}/approve")
    # 409 on approve is fine when the draft was already approved earlier (e.g. awaiting shape confirmation):
    # the publish endpoint itself enforces the real state, so always attempt it unless approve failed otherwise.
    if not (a.startswith("HTTP 200") or a.startswith("HTTP 409")):
        return "approve: " + a
    return "approve: " + a + "\npublish: " + _call("POST", f"/drafts/{draft_id}/publish", params={"shape_confirmed": str(shape_confirmed).lower()})


@mcp.tool()
def reject_draft(draft_id: str, reason: str = "") -> str:
    """ONLY when the owner says 'reject <id>'."""
    return _call("POST", f"/drafts/{draft_id}/reject", params={"reason": reason[:200]})


if __name__ == "__main__":
    mcp.run()

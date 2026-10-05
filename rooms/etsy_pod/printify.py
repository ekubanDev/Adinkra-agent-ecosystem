"""Printify API client: rate limited, retried with backoff, kill-switch aware.

Printify calls are free, so they are not charged to the budget ledger, but every call
still checks the kill switch first (CLAUDE.md rule). Limits: 600 req/min overall.
"""
import asyncio
import os
import time

import httpx

BASE = "https://api.printify.com/v1"
CONTROL_URL = os.environ.get("CONTROL_URL", "http://localhost:8000")


class KillSwitchActive(RuntimeError):
    pass


class RateLimiter:
    """Simple spacing limiter: at most `per_minute` calls, evenly spread."""

    def __init__(self, per_minute: int = 400):  # headroom under Printify's 600
        self.interval = 60.0 / per_minute
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def wait(self):
        async with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next - now)
            self._next = max(now, self._next) + self.interval
        if delay:
            await asyncio.sleep(delay)


class PrintifyClient:
    def __init__(self, token: str, shop_id: str, per_minute: int = 400, retries: int = 4):
        self.shop_id = shop_id
        self.retries = retries
        self.limiter = RateLimiter(per_minute)
        self.http = httpx.AsyncClient(
            base_url=BASE, headers={"Authorization": f"Bearer {token}"}, timeout=30
        )
        self.control = httpx.AsyncClient(base_url=CONTROL_URL, timeout=10)

    async def aclose(self):
        await self.http.aclose()
        await self.control.aclose()

    async def _check_kill_switch(self):
        r = await self.control.get("/kill-switch")  # fail closed: any error stops the call
        r.raise_for_status()
        if r.json()["paused"]:
            raise KillSwitchActive(r.json().get("reason") or "kill switch active")

    async def _get(self, path: str, **params):
        await self._check_kill_switch()
        for attempt in range(self.retries + 1):
            await self.limiter.wait()
            try:
                r = await self.http.get(path, params=params)
                if r.status_code == 429 or r.status_code >= 500:
                    raise httpx.HTTPStatusError("retryable", request=r.request, response=r)
                r.raise_for_status()
                return r.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as e:
                retryable = isinstance(e, httpx.TransportError) or e.response.status_code in (429,) or e.response.status_code >= 500
                if not retryable or attempt == self.retries:
                    raise
                retry_after = e.response.headers.get("retry-after") if isinstance(e, httpx.HTTPStatusError) else None
                await asyncio.sleep(float(retry_after) if retry_after else 2 ** attempt)

    # --- catalog (read-only) ---
    async def shops(self):
        return await self._get("/shops.json")

    async def blueprints(self):
        return await self._get("/catalog/blueprints.json")

    async def print_providers(self, blueprint_id: int):
        return await self._get(f"/catalog/blueprints/{blueprint_id}/print_providers.json")

    async def variants(self, blueprint_id: int, provider_id: int):
        return (await self._get(
            f"/catalog/blueprints/{blueprint_id}/print_providers/{provider_id}/variants.json"
        ))["variants"]

    async def shipping(self, blueprint_id: int, provider_id: int):
        return await self._get(
            f"/catalog/blueprints/{blueprint_id}/print_providers/{provider_id}/shipping.json"
        )

"""MockPartnerProvider: simulates a remote retailer REST API over local data.

Proves the adapter pattern: paginated fetch, artificial latency, injected
5xx failures with retry+backoff, per-key rate limiting, and a circuit breaker.
Deterministic when seeded (tests) via the injected random generator.
"""

import asyncio
import random
import time
from typing import Any

from app.catalog.provider import CandidateQuery, CatalogProvider, ProductCandidate
from app.catalog.providers.dataset import DatasetProvider
from app.core.logging import get_logger
from app.db import models

log = get_logger()


class CircuitOpen(Exception):
    pass


class MockPartnerProvider:
    name = "mock-partner"

    def __init__(
        self,
        inner: DatasetProvider,
        latency_ms: tuple[int, int] = (50, 200),
        fail_rate: float = 0.0,
        rate_limit_per_min: int = 600,
        breaker_threshold: int = 5,
        breaker_cooldown_s: float = 30.0,
        rng: random.Random | None = None,
    ) -> None:
        self.inner = inner
        self.latency_ms = latency_ms
        self.fail_rate = fail_rate
        self.rate_limit_per_min = rate_limit_per_min
        self.breaker_threshold = breaker_threshold
        self.breaker_cooldown_s = breaker_cooldown_s
        self.rng = rng or random.Random()
        self._calls: list[float] = []
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    def _check_breaker(self) -> None:
        if self._opened_at is None:
            return
        if time.monotonic() - self._opened_at >= self.breaker_cooldown_s:
            self._opened_at = None
            self._consecutive_failures = 0
            log.info("partner circuit half-open", provider=self.name)
        else:
            raise CircuitOpen(f"{self.name} circuit open")

    def _check_rate_limit(self) -> None:
        now = time.monotonic()
        self._calls = [t for t in self._calls if now - t < 60]
        if len(self._calls) >= self.rate_limit_per_min:
            raise RuntimeError(f"{self.name} rate limit exceeded")
        self._calls.append(now)

    async def _remote_fetch(self, query: CandidateQuery) -> list[ProductCandidate]:
        self._check_breaker()
        self._check_rate_limit()
        await asyncio.sleep(self.rng.uniform(*self.latency_ms) / 1000)
        if self.rng.random() < self.fail_rate:
            raise RuntimeError(f"{self.name} simulated 5xx")
        # Paginated remote read, page size 100.
        all_cands = await self.inner.search_candidates(query)
        out: list[ProductCandidate] = []
        for i in range(0, len(all_cands), 100):
            await asyncio.sleep(0)
            out.extend(all_cands[i:i + 100])
        return out

    async def search_candidates(self, query: CandidateQuery) -> list[ProductCandidate]:
        last: Exception | None = None
        for attempt in range(3):
            try:
                res = await self._remote_fetch(query)
                self._consecutive_failures = 0
                return res
            except CircuitOpen:
                raise
            except Exception as exc:
                last = exc
                self._consecutive_failures += 1
                if self._consecutive_failures >= self.breaker_threshold:
                    self._opened_at = time.monotonic()
                    log.warning("partner circuit opened", provider=self.name)
                await asyncio.sleep(0.1 * (2**attempt) + self.rng.uniform(0, 0.05))
        assert last is not None
        raise last

    async def get_product(self, sku: str) -> models.Product | None:
        await asyncio.sleep(self.rng.uniform(*self.latency_ms) / 1000)
        return await self.inner.get_product(sku)

    async def check_availability(self, sku: str, size: str) -> bool:
        await asyncio.sleep(self.rng.uniform(*self.latency_ms) / 1000)
        return await self.inner.check_availability(sku, size)


async def fanout(
    providers: list[CatalogProvider], query: CandidateQuery, timeout_s: float = 2.0
) -> list[ProductCandidate]:
    """Query providers in parallel; merge by product id keeping best sims."""
    merged: dict[str, ProductCandidate] = {}
    results: list[Any] = await asyncio.gather(
        *(p.search_candidates(query) for p in providers), return_exceptions=True
    )
    for provider, res in zip(providers, results):
        if isinstance(res, Exception):
            log.warning("provider failed", provider=provider.name, error=str(res))
            continue
        for cand in res:
            cur = merged.setdefault(cand.product_id, ProductCandidate(product_id=cand.product_id))
            cur.img_sim = max(cur.img_sim, cand.img_sim)
            cur.text_sim = max(cur.text_sim, cand.text_sim)
    return list(merged.values())

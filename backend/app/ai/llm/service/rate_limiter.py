"""Token-bucket rate limiter (injectable clock for deterministic tests)."""
from __future__ import annotations

import time


class RateLimiter:
    def __init__(
        self, rate_per_sec: float = 0.0, capacity: float | None = None, clock=time.monotonic
    ) -> None:
        # rate_per_sec <= 0 disables limiting.
        self.rate = rate_per_sec
        self.capacity = capacity if capacity is not None else max(1.0, rate_per_sec)
        self._clock = clock
        self._tokens = self.capacity
        self._last = clock()

    def _refill(self) -> None:
        now = self._clock()
        elapsed = now - self._last
        self._last = now
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)

    def try_acquire(self, amount: float = 1.0) -> bool:
        if self.rate <= 0:
            return True
        self._refill()
        if self._tokens >= amount:
            self._tokens -= amount
            return True
        return False

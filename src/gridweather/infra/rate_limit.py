from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class RateLimitDecision:
    allowed: bool
    remaining: float
    retry_after_seconds: float


class TokenBucketRateLimiter:
    """Token bucket limiter for API and Agent tool calls."""

    def __init__(self, capacity: float, refill_rate_per_sec: float) -> None:
        if capacity <= 0 or refill_rate_per_sec <= 0:
            raise ValueError("capacity and refill_rate_per_sec must be positive")
        self.capacity = float(capacity)
        self.refill_rate_per_sec = float(refill_rate_per_sec)
        self.tokens = float(capacity)
        self.updated_at = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.updated_at
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate_per_sec)
        self.updated_at = now

    def allow(self, cost: float = 1.0) -> RateLimitDecision:
        if cost <= 0:
            raise ValueError("cost must be positive")
        self._refill()
        if self.tokens >= cost:
            self.tokens -= cost
            return RateLimitDecision(True, self.tokens, 0.0)
        deficit = cost - self.tokens
        retry_after = deficit / self.refill_rate_per_sec
        return RateLimitDecision(False, self.tokens, retry_after)


from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    recovery_timeout_seconds: float = 5.0
    state: CircuitState = CircuitState.CLOSED
    failures: int = 0
    opened_at: float = 0.0

    def call(self, fn: Callable[..., T], *args, **kwargs) -> T:
        now = time.monotonic()
        if self.state == CircuitState.OPEN:
            if now - self.opened_at < self.recovery_timeout_seconds:
                raise RuntimeError("circuit breaker is open")
            self.state = CircuitState.HALF_OPEN
        try:
            result = fn(*args, **kwargs)
        except Exception:
            self.failures += 1
            if self.failures >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.opened_at = time.monotonic()
            raise
        self.failures = 0
        self.state = CircuitState.CLOSED
        return result


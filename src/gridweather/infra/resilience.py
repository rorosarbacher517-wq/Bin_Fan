from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry(
    attempts: int = 3,
    base_delay_seconds: float = 0.2,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry transient failures with exponential backoff."""

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> T:
            last_exc: BaseException | None = None
            for idx in range(attempts):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if idx == attempts - 1:
                        break
                    time.sleep(base_delay_seconds * (2 ** idx))
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


def with_fallback(fn: Callable[..., T], fallback: Callable[..., T]) -> Callable[..., T]:
    """Return fallback output when the primary tool fails."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs) -> T:
        try:
            return fn(*args, **kwargs)
        except Exception:
            return fallback(*args, **kwargs)

    return wrapper


from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class SingleFlight:
    """Prevent cache stampede by making concurrent identical calls share work."""

    def __init__(self) -> None:
        self._locks: dict[str, threading.Lock] = {}
        self._global = threading.Lock()

    def do(self, key: str, fn: Callable[[], T]) -> T:
        with self._global:
            lock = self._locks.setdefault(key, threading.Lock())
        with lock:
            try:
                return fn()
            finally:
                with self._global:
                    self._locks.pop(key, None)


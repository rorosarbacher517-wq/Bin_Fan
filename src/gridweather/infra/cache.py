from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Generic, Hashable, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


class TTLLRUCache(Generic[K, V]):
    """Small dependency-free TTL + LRU cache.

    Interview notes:
    - get/set are O(1) average because OrderedDict gives hash lookup and move_to_end.
    - TTL prevents stale weather/model answers.
    - LRU prevents memory blow-up under high-cardinality requests.
    """

    def __init__(self, max_size: int = 1024, ttl_seconds: float = 300.0) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._data: OrderedDict[K, tuple[float, V]] = OrderedDict()
        self.stats = CacheStats()

    def get(self, key: K) -> V | None:
        item = self._data.get(key)
        if item is None:
            self.stats.misses += 1
            return None
        expires_at, value = item
        if expires_at < time.monotonic():
            self._data.pop(key, None)
            self.stats.misses += 1
            return None
        self._data.move_to_end(key)
        self.stats.hits += 1
        return value

    def set(self, key: K, value: V) -> None:
        expires_at = time.monotonic() + self.ttl_seconds
        if key in self._data:
            self._data[key] = (expires_at, value)
            self._data.move_to_end(key)
            return
        self._data[key] = (expires_at, value)
        if len(self._data) > self.max_size:
            self._data.popitem(last=False)
            self.stats.evictions += 1

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)


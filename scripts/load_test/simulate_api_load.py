from __future__ import annotations

import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from gridweather.infra.cache import TTLLRUCache
from gridweather.infra.rate_limit import TokenBucketRateLimiter


def fake_predict(tower_id: str) -> dict:
    time.sleep(random.uniform(0.002, 0.008))
    return {"tower_id": tower_id, "risk_score": random.random() * 100}


def main(n_requests: int = 1000) -> None:
    cache = TTLLRUCache[str, dict](max_size=200, ttl_seconds=60)
    limiter = TokenBucketRateLimiter(capacity=80, refill_rate_per_sec=120)
    latencies = []
    rejected = 0
    for idx in range(n_requests):
        tower_id = f"L{random.randint(0, 3):02d}_T{random.randint(0, 34):03d}"
        decision = limiter.allow()
        if not decision.allowed:
            rejected += 1
            continue
        start = time.perf_counter()
        result = cache.get(tower_id)
        if result is None:
            result = fake_predict(tower_id)
            cache.set(tower_id, result)
        latencies.append((time.perf_counter() - start) * 1000)
    p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies)
    print(
        {
            "requests": n_requests,
            "served": len(latencies),
            "rejected": rejected,
            "cache_hit_rate": round(cache.stats.hit_rate, 3),
            "p50_ms": round(statistics.median(latencies), 3),
            "p95_ms": round(p95, 3),
        }
    )


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    main(n)


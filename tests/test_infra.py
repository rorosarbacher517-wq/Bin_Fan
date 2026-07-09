from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gridweather.agent.memory import BudgetedConversationMemory
from gridweather.infra.cache import TTLLRUCache
from gridweather.infra.circuit_breaker import CircuitBreaker, CircuitState
from gridweather.infra.rate_limit import TokenBucketRateLimiter
from gridweather.retrieval.hybrid import HybridRetriever, simple_rerank
from gridweather.retrieval.bm25 import BM25Retriever
from gridweather.retrieval.chunking import fixed_window_chunks, paragraph_chunks


def test_ttl_lru_cache_expires_and_evicts() -> None:
    cache = TTLLRUCache[str, int](max_size=2, ttl_seconds=0.02)
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("a") == 1
    cache.set("c", 3)
    assert cache.get("b") is None
    time.sleep(0.12)
    assert cache.get("a") is None


def test_token_bucket_rejects_when_empty() -> None:
    limiter = TokenBucketRateLimiter(capacity=2, refill_rate_per_sec=0.1)
    assert limiter.allow().allowed
    assert limiter.allow().allowed
    assert not limiter.allow().allowed


def test_retrieval_finds_relevant_chunk() -> None:
    text = "DLR uses wind and temperature.\n\nIcing risk uses humidity and precipitation."
    chunks = paragraph_chunks(text)
    retriever = BM25Retriever(chunks)
    results = retriever.search("humidity precipitation")
    assert results
    assert "Icing" in results[0].chunk.text
    assert fixed_window_chunks(text, size=5, overlap=1)


def test_budgeted_memory_stays_under_budget() -> None:
    mem = BudgetedConversationMemory(max_tokens=80, recent_turns=3)
    for idx in range(10):
        mem.add("user", "This is a long engineering discussion about cache rate limit retrieval and fallback " * 3)
    assert mem.total_tokens() <= 80
    assert len(mem.state.recent) <= 3


def test_circuit_breaker_opens_after_failures() -> None:
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=100)

    def fail():
        raise ValueError("boom")

    for _ in range(2):
        try:
            breaker.call(fail)
        except ValueError:
            pass
    assert breaker.state == CircuitState.OPEN
    try:
        breaker.call(lambda: 1)
    except RuntimeError:
        assert True
    else:
        assert False


def test_hybrid_retriever_and_reranker() -> None:
    chunks = paragraph_chunks("DLR uses wind.\n\nAgent memory avoids context overflow.")
    results = simple_rerank("context overflow memory", HybridRetriever(chunks).search("context overflow memory"))
    assert results
    assert "memory" in results[0].chunk.text

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from gridweather.retrieval.chunking import fixed_window_chunks, paragraph_chunks
from gridweather.retrieval.hybrid import HybridRetriever, simple_rerank


CORPUS = """
Dynamic line rating uses weather variables such as ambient temperature, wind speed, wind direction, solar radiation, conductor temperature limit, and conductor type to estimate transmission ampacity.

Icing risk increases under low temperature, high humidity, precipitation, and suitable wind. Mountain terrain, high elevation, slope, and windward exposure can increase transmission corridor risk.

RAG production systems require chunking strategy evaluation. Fixed windows improve recall for unstructured logs, while paragraph chunks preserve semantic boundaries in operational guidelines.

Agent memory should keep stable user preferences and confirmed decisions, summarize old context, retain recent turns, and avoid putting raw evidence tables into the prompt.

API production services require cache, rate limiting, fallback, circuit breaker, queue smoothing, privacy controls, and latency monitoring.
"""

QUERIES = [
    ("dynamic line rating wind temperature ampacity", "Dynamic line rating"),
    ("icing risk humidity precipitation mountain", "Icing risk"),
    ("agent memory context overflow summary", "Agent memory"),
    ("cache rate limiting fallback latency", "API production"),
]


def evaluate(chunks):
    retriever = HybridRetriever(chunks)
    hits = 0
    reciprocal = 0.0
    for query, expected in QUERIES:
        results = simple_rerank(query, retriever.search(query, top_k=5))
        rank = None
        for idx, result in enumerate(results, start=1):
            if expected.lower() in result.chunk.text.lower():
                rank = idx
                break
        if rank is not None:
            hits += 1
            reciprocal += 1 / rank
    return {"recall_at_5": hits / len(QUERIES), "mrr": reciprocal / len(QUERIES), "chunks": len(chunks)}


def main() -> None:
    out_dir = ROOT / "artifacts" / "retrieval_eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    configs = {
        "paragraph_120": paragraph_chunks(CORPUS, max_tokens=120),
        "fixed_40_10": fixed_window_chunks(CORPUS, size=40, overlap=10),
        "fixed_70_20": fixed_window_chunks(CORPUS, size=70, overlap=20),
    }
    rows = {name: evaluate(chunks) for name, chunks in configs.items()}
    (out_dir / "chunking_eval.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(rows)


if __name__ == "__main__":
    main()


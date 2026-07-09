from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from gridweather.retrieval.chunking import Chunk, tokenize


@dataclass
class SearchResult:
    chunk: Chunk
    score: float


class BM25Retriever:
    """Tiny BM25 retriever for interview-visible RAG basics."""

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.doc_tokens = [tokenize(c.text) for c in chunks]
        self.doc_lens = [len(toks) for toks in self.doc_tokens]
        self.avgdl = sum(self.doc_lens) / max(len(self.doc_lens), 1)
        self.term_freqs = [Counter(toks) for toks in self.doc_tokens]
        df = Counter()
        for toks in self.doc_tokens:
            df.update(set(toks))
        n = len(chunks)
        self.idf = {term: math.log(1 + (n - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()}

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        terms = tokenize(query)
        scored: list[SearchResult] = []
        for chunk, tf, doc_len in zip(self.chunks, self.term_freqs, self.doc_lens):
            score = 0.0
            for term in terms:
                if term not in tf:
                    continue
                idf = self.idf.get(term, 0.0)
                freq = tf[term]
                denom = freq + self.k1 * (1 - self.b + self.b * doc_len / max(self.avgdl, 1e-9))
                score += idf * (freq * (self.k1 + 1)) / denom
            if score > 0:
                scored.append(SearchResult(chunk, score))
        return sorted(scored, key=lambda x: x.score, reverse=True)[:top_k]


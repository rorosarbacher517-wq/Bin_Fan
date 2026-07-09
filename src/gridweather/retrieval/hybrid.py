from __future__ import annotations

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from gridweather.retrieval.bm25 import BM25Retriever, SearchResult
from gridweather.retrieval.chunking import Chunk, tokenize


@dataclass
class HybridSearchResult:
    chunk: Chunk
    score: float
    bm25_score: float
    vector_score: float


class HybridRetriever:
    """BM25 + TF-IDF vector hybrid retriever.

    In production this can be replaced by BM25 + dense embeddings + reranker.
    """

    def __init__(self, chunks: list[Chunk], alpha: float = 0.55) -> None:
        self.chunks = chunks
        self.alpha = alpha
        self.bm25 = BM25Retriever(chunks)
        self.vectorizer = TfidfVectorizer(token_pattern=r"(?u)[\w\u4e00-\u9fff]+")
        self.matrix = self.vectorizer.fit_transform([c.text for c in chunks])

    def search(self, query: str, top_k: int = 5) -> list[HybridSearchResult]:
        bm25_results = self.bm25.search(query, top_k=max(top_k * 3, 10))
        bm25_map = {r.chunk.chunk_id: r.score for r in bm25_results}
        max_bm25 = max(bm25_map.values(), default=1.0)
        q_vec = self.vectorizer.transform([query])
        vector_scores = cosine_similarity(q_vec, self.matrix).ravel()
        scored = []
        for idx, chunk in enumerate(self.chunks):
            bm25_norm = bm25_map.get(chunk.chunk_id, 0.0) / max_bm25
            vec = float(vector_scores[idx])
            score = self.alpha * bm25_norm + (1 - self.alpha) * vec
            if score > 0:
                scored.append(HybridSearchResult(chunk, score, bm25_map.get(chunk.chunk_id, 0.0), vec))
        return sorted(scored, key=lambda x: x.score, reverse=True)[:top_k]


def simple_rerank(query: str, results: list[HybridSearchResult]) -> list[HybridSearchResult]:
    q_terms = set(tokenize(query))

    def rerank_score(item: HybridSearchResult) -> float:
        c_terms = set(tokenize(item.chunk.text))
        coverage = len(q_terms & c_terms) / max(len(q_terms), 1)
        return item.score + 0.2 * coverage

    return sorted(results, key=rerank_score, reverse=True)


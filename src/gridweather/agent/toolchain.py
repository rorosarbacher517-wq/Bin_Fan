from __future__ import annotations

from pathlib import Path

import pandas as pd

from gridweather.retrieval.chunking import paragraph_chunks
from gridweather.retrieval.hybrid import HybridRetriever, simple_rerank


class OpsGuidelineRetriever:
    def __init__(self, corpus_path: Path | None = None) -> None:
        if corpus_path is None:
            corpus_path = Path(__file__).parent / "guidelines" / "icing_ops_guidelines.md"
        text = corpus_path.read_text(encoding="utf-8")
        self.retriever = HybridRetriever(paragraph_chunks(text, max_tokens=120))

    def search(self, query: str, top_k: int = 3) -> list[str]:
        return [r.chunk.text for r in simple_rerank(query, self.retriever.search(query, top_k=top_k))]


def query_tower(prediction_csv: Path, tower_id: str) -> pd.DataFrame:
    df = pd.read_csv(prediction_csv, parse_dates=["time"])
    return df[df["tower_id"] == tower_id].sort_values("time")


def build_evidence_packet(prediction_csv: Path, tower_id: str) -> dict:
    tower = query_tower(prediction_csv, tower_id)
    if tower.empty:
        return {"tower_id": tower_id, "error": "tower not found"}
    peak = tower.sort_values("pred_risk_score", ascending=False).iloc[0]
    retriever = OpsGuidelineRetriever()
    guidelines = retriever.search(f"risk level {peak['pred_risk_level']} dlr margin {peak.get('dlr_margin_pct', 0)}")
    return {
        "tower_id": tower_id,
        "peak_time": str(peak["time"]),
        "risk_score": float(peak["pred_risk_score"]),
        "risk_level": int(peak["pred_risk_level"]),
        "dlr_margin_pct": float(peak.get("dlr_margin_pct", 0.0)),
        "weather": {
            "temperature_c": float(peak["temperature_c"]),
            "relative_humidity": float(peak["relative_humidity"]),
            "wind_speed_ms": float(peak["wind_speed_ms"]),
            "precip_mm": float(peak["precip_mm"]),
        },
        "guidelines": guidelines,
    }


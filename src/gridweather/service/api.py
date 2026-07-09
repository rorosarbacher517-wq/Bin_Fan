from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

from gridweather.agent.explain import attach_explanations
from gridweather.infra.cache import TTLLRUCache
from gridweather.infra.rate_limit import TokenBucketRateLimiter

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
except ImportError as exc:  # pragma: no cover - optional dependency
    raise RuntimeError("FastAPI service requires: pip install fastapi uvicorn") from exc


ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = ROOT / "artifacts" / "models_real_era5" / "risk_model.joblib"
TABLE_PATH = ROOT / "data" / "real" / "features" / "training_table.csv"

app = FastAPI(title="GridWeather-Agent API", version="0.1.0")
cache = TTLLRUCache[str, dict](max_size=2048, ttl_seconds=300)
limiter = TokenBucketRateLimiter(capacity=100, refill_rate_per_sec=50)
bundle = joblib.load(MODEL_PATH) if MODEL_PATH.exists() else None


class PredictRequest(BaseModel):
    tower_id: str
    horizon_hours: int = 24


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_loaded": bundle is not None}


@app.post("/predict")
def predict(req: PredictRequest) -> dict:
    decision = limiter.allow()
    if not decision.allowed:
        raise HTTPException(status_code=429, detail={"retry_after_seconds": decision.retry_after_seconds})
    key = f"{req.tower_id}:{req.horizon_hours}:{MODEL_PATH.stat().st_mtime if MODEL_PATH.exists() else 0}"
    cached = cache.get(key)
    if cached:
        return {**cached, "cache": "hit"}
    if bundle is None:
        raise HTTPException(status_code=503, detail="model is not available")
    df = pd.read_csv(TABLE_PATH, parse_dates=["time"])
    target = df[df["tower_id"] == req.tower_id].sort_values("time").tail(req.horizon_hours).copy()
    if target.empty:
        raise HTTPException(status_code=404, detail="tower_id not found")
    features = bundle["feature_columns"]
    target["pred_risk_level"] = bundle["classifier"].predict(target[features])
    target["pred_risk_score"] = bundle["regressor"].predict(target[features]).clip(0, 100)
    explained = attach_explanations(target)
    peak = explained.sort_values("pred_risk_score", ascending=False).iloc[0]
    result = {
        "tower_id": req.tower_id,
        "peak_time": str(peak["time"]),
        "risk_level": int(peak["pred_risk_level"]),
        "risk_score": float(peak["pred_risk_score"]),
        "dlr_margin_pct": float(peak.get("dlr_margin_pct", 0.0)),
        "explanation": str(peak["agent_explanation"]),
        "recommended_action": str(peak["recommended_action"]),
        "cache": "miss",
    }
    cache.set(key, result)
    return result


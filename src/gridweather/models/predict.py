from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd


def predict_latest(table_path: Path, model_path: Path, output_dir: Path, horizon_hours: int = 24) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(table_path, parse_dates=["time"])
    latest_start = df["time"].max() - pd.Timedelta(hours=horizon_hours - 1)
    pred_df = df[df["time"] >= latest_start].copy()
    bundle = joblib.load(model_path)
    features = bundle["feature_columns"]
    pred_df["pred_risk_level"] = bundle["classifier"].predict(pred_df[features])
    pred_df["pred_risk_score"] = bundle["regressor"].predict(pred_df[features]).clip(0, 100)
    output_path = output_dir / "latest_predictions.csv"
    pred_df.to_csv(output_path, index=False)
    return output_path


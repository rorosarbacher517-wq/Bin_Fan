from __future__ import annotations

import numpy as np
import pandas as pd


def compute_icing_risk_score(df: pd.DataFrame) -> pd.Series:
    temp = df["temperature_c"].astype(float)
    rh = df["relative_humidity"].astype(float)
    wind = df["wind_speed_ms"].astype(float)
    precip = df["precip_mm"].astype(float)
    elevation = df["elevation_m"].astype(float)
    slope = df["slope_deg"].astype(float)

    temp_window = np.exp(-((temp + 2.5) / 4.0) ** 2)
    moisture = np.clip((rh - 0.72) / 0.25, 0, 1)
    precip_factor = np.clip(precip / 1.5, 0, 1)
    wind_factor = np.exp(-((wind - 5.5) / 4.0) ** 2)
    terrain_factor = np.clip((elevation - 450) / 850, 0, 1) * 0.7 + np.clip(slope / 35, 0, 1) * 0.3

    score = 100 * (0.45 * temp_window + 0.2 * moisture + 0.15 * precip_factor + 0.1 * wind_factor + 0.1 * terrain_factor)
    score = np.where((temp > 2.0) | (rh < 0.55), score * 0.25, score)
    score = np.where((temp < -12.0) & (precip < 0.1), score * 0.55, score)
    return pd.Series(np.clip(score, 0, 100), index=df.index, name="risk_score")


def risk_level_from_score(score: pd.Series) -> pd.Series:
    bins = [-0.1, 35, 55, 72, 100.1]
    labels = [0, 1, 2, 3]
    return pd.cut(score, bins=bins, labels=labels).astype(int).rename("risk_level")


def add_physics_labels(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["risk_score"] = compute_icing_risk_score(out)
    out["risk_level"] = risk_level_from_score(out["risk_score"])
    out["icing_trigger"] = (
        (out["temperature_c"].between(-8, 1.5))
        & (out["relative_humidity"] > 0.78)
        & ((out["precip_mm"] > 0.05) | (out["wind_speed_ms"] > 4.0))
    )
    return out


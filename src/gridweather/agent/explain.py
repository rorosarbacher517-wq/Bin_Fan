from __future__ import annotations

import pandas as pd


def explain_row(row: pd.Series) -> str:
    reasons: list[str] = []
    if -8 <= row["temperature_c"] <= 1.5:
        reasons.append(f"temperature is in icing window ({row['temperature_c']:.1f} C)")
    if row["relative_humidity"] >= 0.78:
        reasons.append(f"humidity is high ({row['relative_humidity']:.0%})")
    if row["precip_mm"] > 0.05:
        reasons.append(f"precipitation is present ({row['precip_mm']:.2f} mm/h)")
    if row["wind_speed_ms"] >= 4:
        reasons.append(f"wind supports droplet collision ({row['wind_speed_ms']:.1f} m/s)")
    if row["elevation_m"] >= 700:
        reasons.append(f"high-elevation tower ({row['elevation_m']:.0f} m)")
    if row["slope_deg"] >= 20:
        reasons.append(f"steep terrain exposure ({row['slope_deg']:.1f} deg)")
    if "dlr_margin_pct" in row and row["dlr_margin_pct"] < 10:
        reasons.append(f"limited dynamic line rating headroom ({row['dlr_margin_pct']:.1f}%)")
    if not reasons:
        reasons.append("no major icing trigger is active")
    return "; ".join(reasons)


def recommend_action(row: pd.Series) -> str:
    level = int(row.get("pred_risk_level", row.get("risk_level", 0)))
    margin = float(row.get("dlr_margin_pct", 999))
    if level >= 3:
        return "Escalate: inspect critical span, prepare de-icing/anti-icing response, and verify nearby weather observations."
    if level >= 2 and margin < 10:
        return "Operate conservatively: monitor loading, prioritize patrol, and review transfer capability."
    if level >= 2:
        return "Watch: increase patrol priority and refresh forecast in the next cycle."
    if margin < 0:
        return "Capacity watch: weather reduces line headroom even without severe icing risk."
    return "Normal monitoring."


def attach_explanations(predictions: pd.DataFrame) -> pd.DataFrame:
    out = predictions.copy()
    out["agent_explanation"] = out.apply(explain_row, axis=1)
    out["recommended_action"] = out.apply(recommend_action, axis=1)
    return out

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gridweather.features.physics_labels import add_physics_labels


def test_icing_conditions_rank_above_warm_dry_conditions() -> None:
    df = pd.DataFrame(
        [
            {
                "temperature_c": -2.0,
                "relative_humidity": 0.92,
                "wind_speed_ms": 5.5,
                "precip_mm": 0.8,
                "elevation_m": 850,
                "slope_deg": 22,
            },
            {
                "temperature_c": 8.0,
                "relative_humidity": 0.45,
                "wind_speed_ms": 2.0,
                "precip_mm": 0.0,
                "elevation_m": 200,
                "slope_deg": 5,
            },
        ]
    )
    out = add_physics_labels(df)
    assert out.loc[0, "risk_score"] > out.loc[1, "risk_score"]
    assert out.loc[0, "risk_level"] >= 2
    assert out.loc[1, "risk_level"] == 0


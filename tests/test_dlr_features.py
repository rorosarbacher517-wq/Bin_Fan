from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gridweather.features.dlr import add_dynamic_line_rating_features


def test_cold_windy_weather_has_more_ampacity_than_hot_still_weather() -> None:
    df = pd.DataFrame(
        [
            {"temperature_c": -5.0, "wind_speed_ms": 6.0, "crosswind_factor": 1.0},
            {"temperature_c": 35.0, "wind_speed_ms": 0.2, "crosswind_factor": 0.2},
        ]
    )
    out = add_dynamic_line_rating_features(df)
    assert out.loc[0, "dlr_ampacity_a"] > out.loc[1, "dlr_ampacity_a"]
    assert out.loc[0, "dlr_margin_pct"] > out.loc[1, "dlr_margin_pct"]


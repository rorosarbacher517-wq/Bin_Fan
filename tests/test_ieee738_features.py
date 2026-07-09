from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gridweather.features.ieee738 import add_ieee738_like_dlr


def test_ieee738_like_dlr_responds_to_weather() -> None:
    df = pd.DataFrame(
        [
            {"temperature_c": -5, "wind_speed_ms": 8, "crosswind_factor": 1, "pressure_hpa": 850},
            {"temperature_c": 35, "wind_speed_ms": 0.1, "crosswind_factor": 0.1, "pressure_hpa": 850},
        ]
    )
    out = add_ieee738_like_dlr(df)
    assert out.loc[0, "ieee738_ampacity_a"] > out.loc[1, "ieee738_ampacity_a"]


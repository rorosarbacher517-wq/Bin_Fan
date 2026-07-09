from __future__ import annotations

import numpy as np
import pandas as pd


def add_dynamic_line_rating_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add approximate weather-aware line capacity features.

    This is an interview/project-level dynamic line rating proxy, not a certified
    IEEE 738/CIGRE thermal rating implementation. It captures the key physics:
    colder air and stronger crosswind increase cooling, while hot still air
    reduces ampacity headroom.
    """
    out = df.copy()
    temp_c = out["temperature_c"].astype(float)
    wind_speed = out["wind_speed_ms"].astype(float).clip(lower=0.05)
    crosswind = out.get("crosswind_factor", pd.Series(1.0, index=out.index)).astype(float).abs().clip(0, 1)

    conductor_max_c = 75.0
    static_rating_a = 1800.0
    conductor_diameter_m = 0.028
    resistance_ohm_m = 8.5e-5
    emissivity = 0.5
    sigma = 5.670374419e-8

    delta_t = (conductor_max_c - temp_c).clip(lower=1.0)
    effective_wind = (0.25 + 0.75 * crosswind) * wind_speed
    convective_w_m = 5.5 * np.power(effective_wind, 0.6) * delta_t
    radiative_w_m = np.pi * conductor_diameter_m * emissivity * sigma * (
        np.power(conductor_max_c + 273.15, 4) - np.power(temp_c + 273.15, 4)
    )
    cooling_w_m = np.maximum(convective_w_m + radiative_w_m, 1.0)
    ampacity_a = np.sqrt(cooling_w_m / resistance_ohm_m)

    out["dlr_ampacity_a"] = ampacity_a.clip(100, 2500)
    out["static_rating_a"] = static_rating_a
    out["dlr_margin_pct"] = (out["dlr_ampacity_a"] - static_rating_a) / static_rating_a * 100
    out["thermal_stress_index"] = (100 - out["dlr_margin_pct"]).clip(lower=0, upper=100)
    out["weather_capacity_state"] = pd.cut(
        out["dlr_margin_pct"],
        bins=[-1000, -10, 10, 35, 1000],
        labels=["constrained", "watch", "normal", "high_headroom"],
    ).astype(str)
    return out

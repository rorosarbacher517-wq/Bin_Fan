from __future__ import annotations

import numpy as np
import pandas as pd


def air_density_kg_m3(pressure_hpa: pd.Series, temp_c: pd.Series) -> pd.Series:
    r_d = 287.05
    return (pressure_hpa.astype(float) * 100) / (r_d * (temp_c.astype(float) + 273.15))


def add_ieee738_like_dlr(
    df: pd.DataFrame,
    conductor_max_c: float = 75.0,
    conductor_diameter_m: float = 0.028,
    resistance_ohm_m: float = 8.5e-5,
    absorptivity: float = 0.5,
    emissivity: float = 0.5,
    solar_w_m2: float = 650.0,
    static_rating_a: float = 1800.0,
) -> pd.DataFrame:
    """Approximate IEEE 738/CIGRE-style thermal balance features.

    Includes ambient temperature, wind, air density, solar gain, convection,
    radiation, and Joule heating. It is still a simplified study model because
    certified DLR needs conductor-specific parameters and field validation.
    """
    out = df.copy()
    temp = out["temperature_c"].astype(float)
    wind = out["wind_speed_ms"].astype(float).clip(lower=0.05)
    pressure = out.get("pressure_hpa", pd.Series(1013.25, index=out.index)).astype(float)
    crosswind = out.get("crosswind_factor", pd.Series(1.0, index=out.index)).astype(float).abs().clip(0, 1)
    rho = air_density_kg_m3(pressure, temp)
    delta_t = (conductor_max_c - temp).clip(lower=1)
    effective_wind = wind * (0.25 + 0.75 * crosswind)

    forced_convection_w_m = 3.8 * np.power(rho / 1.225, 0.5) * np.power(effective_wind, 0.6) * delta_t
    natural_convection_w_m = 0.8 * np.power(delta_t, 1.25)
    convection_w_m = np.maximum(forced_convection_w_m, natural_convection_w_m)

    sigma = 5.670374419e-8
    radiation_w_m = (
        np.pi
        * conductor_diameter_m
        * emissivity
        * sigma
        * (np.power(conductor_max_c + 273.15, 4) - np.power(temp + 273.15, 4))
    )
    solar_gain_w_m = absorptivity * solar_w_m2 * conductor_diameter_m
    net_cooling_w_m = np.maximum(convection_w_m + radiation_w_m - solar_gain_w_m, 1.0)
    ampacity = np.sqrt(net_cooling_w_m / resistance_ohm_m)

    out["air_density_kg_m3"] = rho
    out["solar_gain_w_m"] = solar_gain_w_m
    out["convective_cooling_w_m"] = convection_w_m
    out["radiative_cooling_w_m"] = radiation_w_m
    out["ieee738_ampacity_a"] = ampacity.clip(100, 3000)
    out["ieee738_margin_pct"] = (out["ieee738_ampacity_a"] - static_rating_a) / static_rating_a * 100
    return out


from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from gridweather.config import ensure_dirs
from gridweather.features.dlr import add_dynamic_line_rating_features
from gridweather.features.ieee738 import add_ieee738_like_dlr
from gridweather.features.physics_labels import add_physics_labels


def _nearest_weather_for_towers(towers: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    grid = weather[["lat", "lon"]].drop_duplicates().reset_index(drop=True)
    tower_xy = towers[["lat", "lon"]].to_numpy()
    grid_xy = grid[["lat", "lon"]].to_numpy()
    nearest = ((tower_xy[:, None, :] - grid_xy[None, :, :]) ** 2).sum(axis=2).argmin(axis=1)
    mapped = towers.copy()
    mapped["weather_lat"] = grid.iloc[nearest]["lat"].to_numpy()
    mapped["weather_lon"] = grid.iloc[nearest]["lon"].to_numpy()
    return mapped


def build_training_table(raw_dir: Path, feature_dir: Path) -> Path:
    ensure_dirs(feature_dir)
    towers = pd.read_csv(raw_dir / "towers.csv")
    weather = pd.read_csv(raw_dir / "weather_hourly.csv", parse_dates=["time"])
    towers = _nearest_weather_for_towers(towers, weather)

    merged = weather.merge(
        towers,
        left_on=["lat", "lon"],
        right_on=["weather_lat", "weather_lon"],
        suffixes=("_weather", ""),
    )
    merged["hour"] = merged["time"].dt.hour
    merged["dayofyear"] = merged["time"].dt.dayofyear
    merged["wind_line_angle"] = np.abs(((merged["wind_dir_deg"] - merged["line_heading_deg"] + 180) % 360) - 180)
    merged["crosswind_factor"] = np.sin(np.deg2rad(merged["wind_line_angle"]))
    merged["temp_dewpoint_spread_proxy"] = (1 - merged["relative_humidity"]) * 12
    merged = add_dynamic_line_rating_features(merged)
    merged = add_ieee738_like_dlr(merged)
    merged = add_physics_labels(merged)

    cols = [
        "time",
        "tower_id",
        "line_id",
        "lat",
        "lon",
        "temperature_c",
        "relative_humidity",
        "wind_speed_ms",
        "wind_dir_deg",
        "precip_mm",
        "pressure_hpa",
        "elevation_m",
        "slope_deg",
        "ndvi",
        "ndwi",
        "ndbi",
        "line_heading_deg",
        "wind_line_angle",
        "crosswind_factor",
        "temp_dewpoint_spread_proxy",
        "dlr_ampacity_a",
        "static_rating_a",
        "dlr_margin_pct",
        "thermal_stress_index",
        "air_density_kg_m3",
        "solar_gain_w_m",
        "convective_cooling_w_m",
        "radiative_cooling_w_m",
        "ieee738_ampacity_a",
        "ieee738_margin_pct",
        "weather_capacity_state",
        "hour",
        "dayofyear",
        "risk_score",
        "risk_level",
        "icing_trigger",
    ]
    out = merged[cols].sort_values(["time", "line_id", "tower_id"])
    output_path = feature_dir / "training_table.csv"
    out.to_csv(output_path, index=False)
    return output_path

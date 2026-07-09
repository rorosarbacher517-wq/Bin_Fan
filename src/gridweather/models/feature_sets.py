from __future__ import annotations


WEATHER = [
    "temperature_c",
    "relative_humidity",
    "wind_speed_ms",
    "wind_dir_deg",
    "precip_mm",
    "pressure_hpa",
    "hour",
    "dayofyear",
]

DEM = ["elevation_m", "slope_deg"]
SENTINEL = ["ndvi", "ndwi", "ndbi"]
LINE_GEOMETRY = ["line_heading_deg", "wind_line_angle", "crosswind_factor", "line_id"]
DLR = ["dlr_ampacity_a", "dlr_margin_pct", "thermal_stress_index"]
IEEE738 = [
    "air_density_kg_m3",
    "convective_cooling_w_m",
    "radiative_cooling_w_m",
    "ieee738_ampacity_a",
    "ieee738_margin_pct",
]
PHYSICS_PROXY = ["temp_dewpoint_spread_proxy"]

FEATURE_SETS = {
    "weather_only": WEATHER,
    "weather_dem": WEATHER + DEM,
    "weather_dem_sentinel": WEATHER + DEM + SENTINEL,
    "weather_dem_sentinel_line": WEATHER + DEM + SENTINEL + LINE_GEOMETRY,
    "weather_dem_sentinel_line_dlr": WEATHER + DEM + SENTINEL + LINE_GEOMETRY + DLR,
    "weather_dem_sentinel_line_ieee738": WEATHER + DEM + SENTINEL + LINE_GEOMETRY + IEEE738,
    "full_with_physics_prior": WEATHER + DEM + SENTINEL + LINE_GEOMETRY + DLR + IEEE738 + PHYSICS_PROXY,
}

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from gridweather.config import load_config, project_path


def _read_service_account(args: argparse.Namespace) -> tuple[str, str]:
    key_file = args.service_account_file or os.getenv("GEE_SERVICE_ACCOUNT_FILE")
    email = args.service_account_email or os.getenv("GEE_SERVICE_ACCOUNT_EMAIL")
    if args.service_account_email_file and not email:
        email = Path(args.service_account_email_file).read_text(encoding="utf-8").strip()
    if not key_file or not email:
        raise ValueError(
            "Provide --service-account-file and --service-account-email, or set "
            "GEE_SERVICE_ACCOUNT_FILE/GEE_SERVICE_ACCOUNT_EMAIL."
        )
    return email, key_file


def _apply_proxy(proxy_url: str) -> None:
    if not proxy_url:
        return
    os.environ["HTTP_PROXY"] = proxy_url
    os.environ["HTTPS_PROXY"] = proxy_url
    os.environ["http_proxy"] = proxy_url
    os.environ["https_proxy"] = proxy_url
    import requests

    original_request = requests.sessions.Session.request

    def proxied_request(self, method, url, **kwargs):
        kwargs.setdefault("proxies", {"http": proxy_url, "https": proxy_url})
        return original_request(self, method, url, **kwargs)

    requests.sessions.Session.request = proxied_request


def _init_ee(auth_mode: str, email: str, key_file: str, ee_project: str = "") -> None:
    import ee

    if auth_mode == "user":
        if ee_project:
            ee.Initialize(project=ee_project)
        else:
            ee.Initialize()
    else:
        credentials = ee.ServiceAccountCredentials(email, key_file)
        if ee_project:
            ee.Initialize(credentials, project=ee_project)
        else:
            ee.Initialize(credentials)


def _tower_feature_collection(towers: pd.DataFrame, buffer_m: int):
    import ee

    features = []
    required = {"tower_id", "lat", "lon"}
    missing = required - set(towers.columns)
    if missing:
        raise ValueError(f"Tower CSV is missing required columns: {sorted(missing)}")
    for row in towers.itertuples(index=False):
        props = {
            "tower_id": str(getattr(row, "tower_id")),
            "line_id": str(getattr(row, "line_id", "")),
            "lat": float(getattr(row, "lat")),
            "lon": float(getattr(row, "lon")),
        }
        geom = ee.Geometry.Point([props["lon"], props["lat"]]).buffer(buffer_m)
        features.append(ee.Feature(geom, props))
    return ee.FeatureCollection(features)


def export_static_features(
    tower_csv: Path,
    output_csv: Path,
    buffer_m: int,
    start_date: str,
    end_date: str,
    scale: int,
) -> Path:
    import ee

    towers = pd.read_csv(tower_csv)
    fc = _tower_feature_collection(towers, buffer_m)
    region = fc.geometry().bounds()

    dem = ee.Image("NASA/NASADEM_HGT/001").select("elevation").rename("elevation_m")
    terrain = ee.Terrain.products(dem)
    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(region)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 35))
        .median()
    )
    ndvi = s2.normalizedDifference(["B8", "B4"]).rename("ndvi")
    ndwi = s2.normalizedDifference(["B3", "B8"]).rename("ndwi")
    ndbi = s2.normalizedDifference(["B11", "B8"]).rename("ndbi")
    stack = (
        dem.addBands(terrain.select("slope").rename("slope_deg"))
        .addBands(terrain.select("aspect").rename("aspect_deg"))
        .addBands(ndvi)
        .addBands(ndwi)
        .addBands(ndbi)
    )

    reduced = stack.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=scale)
    info = reduced.getInfo()
    rows = []
    for feature in info["features"]:
        props = feature["properties"]
        rows.append(
            {
                "tower_id": props.get("tower_id"),
                "line_id": props.get("line_id"),
                "lat": props.get("lat"),
                "lon": props.get("lon"),
                "elevation_m": props.get("elevation_m"),
                "slope_deg": props.get("slope_deg"),
                "aspect_deg": props.get("aspect_deg"),
                "ndvi": props.get("ndvi"),
                "ndwi": props.get("ndwi"),
                "ndbi": props.get("ndbi"),
            }
        )
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output_csv, index=False)
    return output_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract tower-level DEM and Sentinel-2 static features from GEE.")
    parser.add_argument("--config", default=str(ROOT / "configs" / "project.yaml"))
    parser.add_argument("--tower-csv", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--service-account-file", default="")
    parser.add_argument("--service-account-email", default="")
    parser.add_argument("--service-account-email-file", default="")
    parser.add_argument("--auth-mode", choices=["service-account", "user"], default="service-account")
    parser.add_argument("--proxy-url", default="", help="Optional proxy URL, for example http://127.0.0.1:7890.")
    parser.add_argument("--ee-project", default="", help="Registered Earth Engine Cloud project id, for example nmcproductivity.")
    parser.add_argument("--buffer-m", type=int, default=500)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2023-12-31")
    parser.add_argument("--scale", type=int, default=30)
    args = parser.parse_args()

    cfg = load_config(args.config)
    _apply_proxy(args.proxy_url)
    email, key_file = ("", "")
    if args.auth_mode == "service-account":
        email, key_file = _read_service_account(args)
    _init_ee(args.auth_mode, email, key_file, args.ee_project)

    tower_csv = Path(args.tower_csv) if args.tower_csv else project_path(cfg, cfg["paths"]["data_dir"], "raw", "towers.csv")
    output_csv = Path(args.output) if args.output else project_path(cfg, cfg["paths"]["data_dir"], "features", "tower_static_features_gee.csv")
    out = export_static_features(
        tower_csv=tower_csv,
        output_csv=output_csv,
        buffer_m=args.buffer_m,
        start_date=args.start_date,
        end_date=args.end_date,
        scale=args.scale,
    )
    print(out)


if __name__ == "__main__":
    main()

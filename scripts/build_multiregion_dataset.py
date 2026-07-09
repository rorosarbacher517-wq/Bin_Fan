from __future__ import annotations

import argparse
import sys
from copy import deepcopy
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gridweather.config import ensure_dirs, load_config, project_path
from gridweather.data.era5_to_weather import convert_era5_folder
from gridweather.data.synthetic import generate_demo_data, generate_synthetic_towers
from gridweather.features.build_dataset import build_training_table


def _region_cfg(base_cfg: dict, region: dict, region_dir: Path) -> dict:
    cfg = deepcopy(base_cfg)
    cfg["paths"]["data_dir"] = str(region_dir)
    cfg["region"] = {"name": region["region_id"], "area": region["area"]}
    return cfg


def _prefix_region_ids(table: pd.DataFrame, region_id: str, province_hint: str) -> pd.DataFrame:
    out = table.copy()
    out["region_id"] = region_id
    out["province_hint"] = province_hint
    out["line_id"] = region_id + "__" + out["line_id"].astype(str)
    out["tower_id"] = region_id + "__" + out["tower_id"].astype(str)
    cols = ["region_id", "province_hint"] + [c for c in out.columns if c not in {"region_id", "province_hint"}]
    return out[cols]


def _build_region_demo(base_cfg: dict, region: dict, region_dir: Path) -> Path:
    cfg = _region_cfg(base_cfg, region, region_dir)
    generate_demo_data(cfg, region_dir)
    return build_training_table(region_dir / "raw", region_dir / "features")


def _build_region_real(base_cfg: dict, region: dict, region_dir: Path) -> Path:
    raw_dir = region_dir / "raw"
    feature_dir = region_dir / "features"
    ensure_dirs(raw_dir, feature_dir)
    tower_path = raw_dir / "towers.csv"
    if not tower_path.exists():
        cfg = _region_cfg(base_cfg, region, region_dir)
        generate_synthetic_towers(cfg, region_dir)
    weather_path = raw_dir / "weather_hourly.csv"
    if not weather_path.exists():
        era5_dir = raw_dir / "era5_land"
        if not era5_dir.exists():
            raise FileNotFoundError(f"Missing ERA5 folder for {region['region_id']}: {era5_dir}")
        convert_era5_folder(era5_dir, weather_path)
    return build_training_table(raw_dir, feature_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a multi-region China benchmark training table.")
    parser.add_argument("--config", default=str(ROOT / "configs" / "regions_china.yaml"))
    parser.add_argument("--mode", choices=["demo", "real"], default="demo")
    parser.add_argument("--regions", nargs="*", default=[], help="Optional region_id filter.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    selected = set(args.regions)
    data_dir = project_path(cfg, cfg["paths"]["data_dir"])
    feature_dir = data_dir / "features"
    ensure_dirs(data_dir, feature_dir)

    tables = []
    manifest_rows = []
    for region in cfg["regions"]:
        region_id = region["region_id"]
        if selected and region_id not in selected:
            continue
        region_dir = data_dir / region_id
        table_path = _build_region_demo(cfg, region, region_dir) if args.mode == "demo" else _build_region_real(cfg, region, region_dir)
        table = pd.read_csv(table_path, parse_dates=["time"])
        table = _prefix_region_ids(table, region_id, region.get("province_hint", ""))
        tables.append(table)
        manifest_rows.append(
            {
                "region_id": region_id,
                "province_hint": region.get("province_hint", ""),
                "area": region["area"],
                "rows": len(table),
                "n_towers": table["tower_id"].nunique(),
                "start": table["time"].min(),
                "end": table["time"].max(),
                "mode": args.mode,
            }
        )

    if not tables:
        raise SystemExit("No regions selected.")
    combined = pd.concat(tables, ignore_index=True).sort_values(["region_id", "time", "line_id", "tower_id"])
    out_path = feature_dir / f"training_table_multiregion_{args.mode}.csv"
    manifest_path = feature_dir / f"benchmark_manifest_{args.mode}.csv"
    combined.to_csv(out_path, index=False)
    pd.DataFrame(manifest_rows).to_csv(manifest_path, index=False)
    print(out_path)
    print(manifest_path)


if __name__ == "__main__":
    main()

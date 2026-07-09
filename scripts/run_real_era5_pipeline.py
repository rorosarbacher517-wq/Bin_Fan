from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gridweather.agent.report import build_html_report
from gridweather.config import ensure_dirs, load_config, project_path
from gridweather.data.synthetic import generate_synthetic_towers
from gridweather.features.build_dataset import build_training_table
from gridweather.models.predict import predict_latest
from gridweather.models.train import train_risk_model


def main() -> None:
    cfg = load_config(ROOT / "configs" / "project.yaml")
    real_dir = project_path(cfg, "data", "real")
    raw_dir = real_dir / "raw"
    feature_dir = real_dir / "features"
    artifact_dir = project_path(cfg, cfg["paths"]["artifact_dir"])
    ensure_dirs(raw_dir, feature_dir, artifact_dir)

    weather_path = raw_dir / "weather_hourly.csv"
    if not weather_path.exists():
        raise FileNotFoundError(
            f"Missing {weather_path}. Run scripts/download_era5_land.py and scripts/prepare_era5_weather.py first."
        )

    print("[1/4] Creating non-sensitive synthetic transmission lines inside the Guizhou study region...")
    tower_path = generate_synthetic_towers(cfg, real_dir)
    gee_static_path = feature_dir / "tower_static_features_gee.csv"
    if gee_static_path.exists():
        print("      Using GEE DEM/Sentinel static features for towers...")
        towers = pd.read_csv(tower_path)
        static = pd.read_csv(gee_static_path)
        replace_cols = ["lat", "lon", "elevation_m", "slope_deg", "ndvi", "ndwi", "ndbi"]
        static_cols = ["tower_id"] + [c for c in replace_cols if c in static.columns]
        merged = towers.drop(columns=[c for c in replace_cols if c in towers.columns and c not in ["lat", "lon"]]).merge(
            static[static_cols], on="tower_id", how="left", suffixes=("", "_gee")
        )
        for coord in ["lat", "lon"]:
            gee_col = f"{coord}_gee"
            if gee_col in merged.columns:
                merged[coord] = merged[gee_col].combine_first(merged[coord])
                merged = merged.drop(columns=[gee_col])
        merged.to_csv(tower_path, index=False)

    print("[2/4] Building training table with real ERA5-Land weather and physics-guided weak labels...")
    table_path = build_training_table(raw_dir, feature_dir)

    print("[3/4] Training risk model on real weather plus line and static terrain/remote-sensing features...")
    model_dir = artifact_dir / "models_real_era5"
    result = train_risk_model(
        table_path=table_path,
        artifact_dir=model_dir,
        test_days=int(cfg["model"]["test_days"]),
        random_state=int(cfg["model"]["random_state"]),
    )
    print(f"      metrics: accuracy={result['accuracy']:.3f}, macro_f1={result['macro_f1']:.3f}, score_mae={result['score_mae']:.3f}")

    print("[4/4] Predicting latest 24h risk and building report...")
    pred_path = predict_latest(table_path, result["model"], artifact_dir / "predictions_real_era5")
    report_path = build_html_report(pred_path, artifact_dir / "reports_real_era5")
    latest_report = artifact_dir / "reports" / "gridweather_real_era5_report.html"
    latest_report.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(report_path, latest_report)
    print(f"Done. Report: {latest_report}")


if __name__ == "__main__":
    main()

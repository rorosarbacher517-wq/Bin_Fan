from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gridweather.agent.report import build_html_report
from gridweather.config import ensure_dirs, load_config, project_path
from gridweather.data.synthetic import generate_demo_data
from gridweather.features.build_dataset import build_training_table
from gridweather.models.predict import predict_latest
from gridweather.models.train import train_risk_model


def main() -> None:
    cfg = load_config(ROOT / "configs" / "project.yaml")
    data_dir = project_path(cfg, cfg["paths"]["data_dir"])
    artifact_dir = project_path(cfg, cfg["paths"]["artifact_dir"])
    ensure_dirs(data_dir, artifact_dir)

    print("[1/5] Generating demo weather, towers, terrain, and remote-sensing features...")
    generate_demo_data(cfg, data_dir)

    print("[2/5] Building training table and physics-guided weak labels...")
    table_path = build_training_table(data_dir / "raw", data_dir / "features")

    print("[3/5] Training risk model...")
    result = train_risk_model(
        table_path=table_path,
        artifact_dir=artifact_dir / "models",
        test_days=int(cfg["model"]["test_days"]),
        random_state=int(cfg["model"]["random_state"]),
    )
    print(f"      metrics: accuracy={result['accuracy']:.3f}, macro_f1={result['macro_f1']:.3f}, score_mae={result['score_mae']:.3f}")

    print("[4/5] Predicting latest 24h risk...")
    prediction_path = predict_latest(table_path, result["model"], artifact_dir / "predictions")

    print("[5/5] Building HTML report with agent explanations...")
    report_path = build_html_report(prediction_path, artifact_dir / "reports")
    print(f"Done. Report: {report_path}")


if __name__ == "__main__":
    main()


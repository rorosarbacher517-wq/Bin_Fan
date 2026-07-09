from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from gridweather.models.feature_sets import FEATURE_SETS
from gridweather.models.train import train_with_features


def main() -> None:
    table_path = ROOT / "data" / "real" / "features" / "training_table.csv"
    out_dir = ROOT / "artifacts" / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(table_path, parse_dates=["time"])
    rows = []
    for name, features in FEATURE_SETS.items():
        metrics, _, _ = train_with_features(df, features, test_days=5, random_state=42)
        rows.append({"feature_set": name, "n_features": len(features), **metrics})
        print(rows[-1])
    result = pd.DataFrame(rows).sort_values("macro_f1", ascending=False)
    result.to_csv(out_dir / "ablation_results.csv", index=False)
    (out_dir / "ablation_results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(out_dir / "ablation_results.csv")


if __name__ == "__main__":
    main()


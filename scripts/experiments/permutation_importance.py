from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from sklearn.inspection import permutation_importance

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from gridweather.models.train import FEATURE_COLUMNS, temporal_split, train_with_features


def _read_training_table(table_path: Path) -> pd.DataFrame:
    if not table_path.exists() or table_path.stat().st_size == 0:
        raise FileNotFoundError(f"Training table is missing or empty: {table_path}")
    df = pd.read_csv(table_path, parse_dates=["time"])
    if df.empty:
        raise ValueError(f"Training table has no rows: {table_path}")
    missing = [col for col in FEATURE_COLUMNS + ["risk_level"] if col not in df.columns]
    if missing:
        raise ValueError(f"Training table is missing required columns: {missing}")
    return df


def main() -> None:
    table_path = ROOT / "data" / "real" / "features" / "training_table.csv"
    out_dir = ROOT / "artifacts" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    df = _read_training_table(table_path)
    _, clf, _ = train_with_features(df, FEATURE_COLUMNS, test_days=5, random_state=42)
    _, test_df = temporal_split(df, 5)
    sample = test_df.sample(min(5000, len(test_df)), random_state=42)
    result = permutation_importance(
        clf,
        sample[FEATURE_COLUMNS],
        sample["risk_level"],
        n_repeats=5,
        random_state=42,
        scoring="f1_macro",
    )
    imp = pd.DataFrame({"feature": FEATURE_COLUMNS, "importance": result.importances_mean}).sort_values("importance", ascending=False)
    imp.to_csv(out_dir / "permutation_importance.csv", index=False)
    top = imp.head(15).sort_values("importance")
    plt.figure(figsize=(8, 5))
    plt.barh(top["feature"], top["importance"], color="#2E74B5")
    plt.xlabel("Permutation importance (macro-F1 drop)")
    plt.title("GridWeather-Agent feature importance")
    plt.tight_layout()
    plt.savefig(out_dir / "permutation_importance.png", dpi=180)
    print(out_dir / "permutation_importance.png")


if __name__ == "__main__":
    main()

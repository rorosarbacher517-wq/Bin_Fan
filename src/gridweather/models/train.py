from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import accuracy_score, classification_report, f1_score, mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from gridweather.models.feature_sets import FEATURE_SETS


FEATURE_COLUMNS = [
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
    "dlr_margin_pct",
    "thermal_stress_index",
    "air_density_kg_m3",
    "convective_cooling_w_m",
    "radiative_cooling_w_m",
    "ieee738_ampacity_a",
    "ieee738_margin_pct",
    "hour",
    "dayofyear",
    "line_id",
]

NUMERIC_COLUMNS = [c for c in FEATURE_COLUMNS if c != "line_id"]
CATEGORICAL_COLUMNS = ["line_id"]


def temporal_split(df: pd.DataFrame, test_days: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    df["time"] = pd.to_datetime(df["time"])
    cutoff = df["time"].max() - pd.Timedelta(days=test_days)
    return df[df["time"] <= cutoff], df[df["time"] > cutoff]


def train_with_features(
    df: pd.DataFrame,
    feature_columns: list[str],
    test_days: int = 14,
    random_state: int = 42,
) -> tuple[dict, object, object]:
    train_df, test_df = temporal_split(df, test_days)
    categorical = [c for c in feature_columns if c == "line_id"]
    numeric = [c for c in feature_columns if c not in categorical]
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
        ],
        remainder="drop",
    )
    clf = Pipeline(
        steps=[
            ("pre", preprocessor),
            (
                "model",
                HistGradientBoostingClassifier(max_iter=180, learning_rate=0.07, l2_regularization=0.03, random_state=random_state),
            ),
        ]
    )
    reg = Pipeline(
        steps=[
            ("pre", preprocessor),
            (
                "model",
                HistGradientBoostingRegressor(max_iter=160, learning_rate=0.07, l2_regularization=0.03, random_state=random_state),
            ),
        ]
    )
    clf.fit(train_df[feature_columns], train_df["risk_level"])
    reg.fit(train_df[feature_columns], train_df["risk_score"])
    pred_level = clf.predict(test_df[feature_columns])
    pred_score = reg.predict(test_df[feature_columns])
    metrics = {
        "accuracy": float(accuracy_score(test_df["risk_level"], pred_level)),
        "macro_f1": float(f1_score(test_df["risk_level"], pred_level, average="macro")),
        "score_mae": float(mean_absolute_error(test_df["risk_score"], pred_score)),
    }
    return metrics, clf, reg


def train_risk_model(table_path: Path, artifact_dir: Path, test_days: int = 14, random_state: int = 42) -> dict[str, Path | float]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(table_path, parse_dates=["time"])
    train_df, test_df = temporal_split(df, test_days)
    metrics, clf, reg = train_with_features(df, FEATURE_COLUMNS, test_days, random_state)
    pred_level = clf.predict(test_df[FEATURE_COLUMNS])
    pred_score = reg.predict(test_df[FEATURE_COLUMNS])

    report = classification_report(test_df["risk_level"], pred_level, zero_division=0)
    model_bundle = {
        "classifier": clf,
        "regressor": reg,
        "feature_columns": FEATURE_COLUMNS,
        "metrics": metrics,
        "classification_report": report,
    }
    model_path = artifact_dir / "risk_model.joblib"
    metrics_path = artifact_dir / "metrics.txt"
    joblib.dump(model_bundle, model_path)
    metrics_path.write_text(str(metrics) + "\n\n" + report, encoding="utf-8")
    return {"model": model_path, "metrics": metrics_path, **metrics}

from __future__ import annotations

from sklearn.ensemble import HistGradientBoostingClassifier


def make_classifier(model_name: str = "histgb", random_state: int = 42):
    """Optional model factory for interview experiments.

    LightGBM/XGBoost are used only when installed. The default dependency-free
    fallback remains sklearn HistGradientBoostingClassifier.
    """
    name = model_name.lower()
    if name == "xgboost":
        try:
            from xgboost import XGBClassifier

            return XGBClassifier(
                n_estimators=300,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.9,
                objective="multi:softprob",
                eval_metric="mlogloss",
                random_state=random_state,
            )
        except ImportError:
            pass
    if name == "lightgbm":
        try:
            from lightgbm import LGBMClassifier

            return LGBMClassifier(
                n_estimators=300,
                learning_rate=0.05,
                num_leaves=31,
                subsample=0.9,
                colsample_bytree=0.9,
                random_state=random_state,
            )
        except ImportError:
            pass
    return HistGradientBoostingClassifier(max_iter=180, learning_rate=0.07, l2_regularization=0.03, random_state=random_state)


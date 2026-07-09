from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "experiments"))

from graph_smooth_predictions import smooth_line_graph


def test_graph_smoothing_adds_expected_columns() -> None:
    df = pd.DataFrame(
        {
            "line_id": ["L00", "L00", "L00"],
            "time": ["2023-01-01"] * 3,
            "tower_id": ["T0", "T1", "T2"],
            "pred_risk_score": [10.0, 90.0, 10.0],
        }
    )
    out = smooth_line_graph(df, alpha=0.5)
    assert "graph_smoothed_score" in out
    assert out.loc[1, "graph_smoothed_score"] < 90.0


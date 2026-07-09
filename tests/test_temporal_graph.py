from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gridweather.models.feature_sets import DEM, DLR, IEEE738, PHYSICS_PROXY, SENTINEL, WEATHER
from gridweather.models.temporal_graph import NODE_FEATURES, build_line_edges, build_temporal_graph_snapshots


def _toy_table() -> pd.DataFrame:
    rows = []
    for line_id in ["L00"]:
        for tower_num in range(3):
            tower_id = f"{line_id}_T{tower_num:03d}"
            for hour in range(8):
                row = {
                    "time": pd.Timestamp("2023-01-01") + pd.Timedelta(hours=hour),
                    "tower_id": tower_id,
                    "line_id": line_id,
                    "risk_level": tower_num % 4,
                    "line_heading_deg": 30.0,
                    "wind_line_angle": 40.0,
                    "crosswind_factor": 0.7,
                }
                row.update({col: float(hour + 1) for col in WEATHER})
                row.update({col: 1.0 for col in DEM + SENTINEL + DLR + IEEE738 + PHYSICS_PROXY})
                rows.append(row)
    return pd.DataFrame(rows)


def test_build_line_edges_path_graph() -> None:
    tower_ids, edge_index = build_line_edges(_toy_table())
    assert tower_ids == ["L00_T000", "L00_T001", "L00_T002"]
    assert edge_index.shape == (2, 4)


def test_build_temporal_graph_snapshots_shapes() -> None:
    snapshots = build_temporal_graph_snapshots(_toy_table(), window=4, stride=2)
    assert snapshots
    first = snapshots[0]
    assert first.x_seq.shape == (3, 4, len(WEATHER))
    assert first.x_node.shape == (3, len(NODE_FEATURES))
    assert first.y.shape == (3,)

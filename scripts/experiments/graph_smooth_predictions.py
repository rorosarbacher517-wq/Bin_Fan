from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def smooth_line_graph(pred: pd.DataFrame, alpha: float = 0.8) -> pd.DataFrame:
    out = pred.copy()
    smoothed = []
    for (_, time), group in out.groupby(["line_id", "time"], sort=False):
        ordered = group.sort_values("tower_id").reset_index()
        graph = nx.path_graph(len(ordered))
        values = ordered["pred_risk_score"].to_numpy(dtype=float)
        new_values = values.copy()
        for node in graph.nodes:
            neigh = list(graph.neighbors(node))
            if neigh:
                new_values[node] = alpha * values[node] + (1 - alpha) * values[neigh].mean()
        ordered["graph_smoothed_score"] = new_values
        smoothed.append(ordered.set_index("index"))
    merged = pd.concat(smoothed).sort_index()
    out["graph_smoothed_score"] = merged["graph_smoothed_score"]
    out["graph_smoothed_level"] = pd.cut(out["graph_smoothed_score"], bins=[-0.1, 35, 55, 72, 100.1], labels=[0, 1, 2, 3]).astype(int)
    return out


def main() -> None:
    path = ROOT / "artifacts" / "predictions_real_era5" / "latest_predictions.csv"
    out_path = ROOT / "artifacts" / "predictions_real_era5" / "latest_predictions_graph_smoothed.csv"
    pred = pd.read_csv(path, parse_dates=["time"])
    smooth_line_graph(pred).to_csv(out_path, index=False)
    print(out_path)


if __name__ == "__main__":
    main()


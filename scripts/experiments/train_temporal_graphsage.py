from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from gridweather.models.feature_sets import WEATHER
from gridweather.models.temporal_graph import NODE_FEATURES, build_line_edges, build_temporal_graph_snapshots, make_temporal_graph_model


def _write_metrics(metrics: dict) -> None:
    out_dir = ROOT / "artifacts" / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "patchtst_graphsage_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(metrics)


def main() -> None:
    try:
        import torch
    except Exception as exc:  # pragma: no cover - environment-specific
        _write_metrics({"status": "skipped", "reason": f"PyTorch import failed: {exc!r}"})
        return

    table_path = ROOT / "data" / "real" / "features" / "training_table.csv"
    if not table_path.exists() or table_path.stat().st_size == 0:
        _write_metrics({"status": "skipped", "reason": f"Missing real training table: {table_path}"})
        return

    df = pd.read_csv(table_path, parse_dates=["time"])
    cutoff = df["time"].max() - pd.Timedelta(days=5)
    train_df = df[df["time"] <= cutoff].copy()
    test_df = df[df["time"] > cutoff].copy()

    weather_scaler = StandardScaler().fit(train_df[WEATHER])
    node_scaler = StandardScaler().fit(train_df[NODE_FEATURES])
    for part in [train_df, test_df]:
        part[WEATHER] = weather_scaler.transform(part[WEATHER])
        part[NODE_FEATURES] = node_scaler.transform(part[NODE_FEATURES])

    train_snapshots = build_temporal_graph_snapshots(train_df, window=24, stride=12, max_snapshots=80)
    test_snapshots = build_temporal_graph_snapshots(test_df, window=24, stride=12, max_snapshots=30)
    if not train_snapshots or not test_snapshots:
        _write_metrics({"status": "skipped", "reason": "Not enough temporal graph snapshots after train/test split."})
        return

    _, edge_np = build_line_edges(train_df[["tower_id", "line_id"]])
    edge_index = torch.tensor(edge_np, dtype=torch.long)
    model = make_temporal_graph_model(n_weather=len(WEATHER), n_node=len(NODE_FEATURES))
    optimizer = torch.optim.AdamW(model.parameters(), lr=8e-4, weight_decay=1e-3)
    loss_fn = torch.nn.CrossEntropyLoss()

    rng = np.random.default_rng(42)
    model.train()
    for _ in range(4):
        for snap_idx in rng.permutation(len(train_snapshots)):
            snap = train_snapshots[int(snap_idx)]
            x_seq = torch.tensor(snap.x_seq, dtype=torch.float32)
            x_node = torch.tensor(snap.x_node, dtype=torch.float32)
            y = torch.tensor(snap.y, dtype=torch.long)
            logits = model(x_seq, x_node, edge_index)
            loss = loss_fn(logits, y)
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

    y_true: list[int] = []
    y_pred: list[int] = []
    model.eval()
    with torch.no_grad():
        for snap in test_snapshots:
            logits = model(torch.tensor(snap.x_seq), torch.tensor(snap.x_node), edge_index)
            y_true.extend(snap.y.tolist())
            y_pred.extend(logits.argmax(dim=1).cpu().numpy().tolist())

    metrics = {
        "status": "ok",
        "model": "PatchTST weather encoder + IEEE738 priors + GraphSAGE topology",
        "window_hours": 24,
        "train_snapshots": len(train_snapshots),
        "test_snapshots": len(test_snapshots),
        "nodes": len(train_snapshots[0].tower_ids),
        "edges": int(edge_np.shape[1]),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
    }
    out_dir = ROOT / "artifacts" / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out_dir / "patchtst_graphsage.pt")
    _write_metrics(metrics)


if __name__ == "__main__":
    main()

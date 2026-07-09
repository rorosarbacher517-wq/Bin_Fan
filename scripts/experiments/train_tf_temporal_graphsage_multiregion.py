from __future__ import annotations

import argparse
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
from gridweather.models.temporal_graph import NODE_FEATURES, build_line_edges, build_temporal_graph_snapshots
from gridweather.models.tf_temporal_graph import make_tf_patchtst_graphsage_model


def _prepare_snapshots(train_df: pd.DataFrame, test_df: pd.DataFrame, window: int, stride: int):
    weather_scaler = StandardScaler().fit(train_df[WEATHER])
    node_scaler = StandardScaler().fit(train_df[NODE_FEATURES])
    train_df = train_df.copy()
    test_df = test_df.copy()
    train_df[WEATHER] = weather_scaler.transform(train_df[WEATHER])
    test_df[WEATHER] = weather_scaler.transform(test_df[WEATHER])
    train_df[NODE_FEATURES] = node_scaler.transform(train_df[NODE_FEATURES])
    test_df[NODE_FEATURES] = node_scaler.transform(test_df[NODE_FEATURES])
    return (
        build_temporal_graph_snapshots(train_df, window=window, stride=stride),
        build_temporal_graph_snapshots(test_df, window=window, stride=stride),
        build_line_edges(train_df[["tower_id", "line_id"]])[1],
        build_line_edges(test_df[["tower_id", "line_id"]])[1],
    )


def _train_one_region(tf, df: pd.DataFrame, heldout_region: str, window: int, stride: int, epochs: int) -> dict:
    train_df = df[df["region_id"] != heldout_region].copy()
    test_df = df[df["region_id"] == heldout_region].copy()
    train_snapshots, test_snapshots, train_edges_np, test_edges_np = _prepare_snapshots(train_df, test_df, window, stride)
    if not train_snapshots or not test_snapshots:
        return {"heldout_region": heldout_region, "status": "skipped", "reason": "not enough snapshots"}

    train_edge_index = tf.constant(train_edges_np, dtype=tf.int32)
    test_edge_index = tf.constant(test_edges_np, dtype=tf.int32)
    model = make_tf_patchtst_graphsage_model(n_weather=len(WEATHER), n_node=len(NODE_FEATURES), window=window)
    optimizer = tf.keras.optimizers.Adam(learning_rate=8e-4)
    loss_fn = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True)
    train_labels = np.concatenate([snap.y for snap in train_snapshots])
    counts = np.bincount(train_labels, minlength=4).astype(np.float32)
    class_weight = tf.constant(counts.sum() / np.maximum(counts * len(counts), 1.0), dtype=tf.float32)
    rng = np.random.default_rng(42)

    @tf.function
    def train_step(x_seq, x_node, edge_index, y):
        with tf.GradientTape() as tape:
            logits = model((x_seq, x_node, edge_index), training=True)
            weights = tf.gather(class_weight, y)
            loss = loss_fn(y, logits, sample_weight=weights)
        grads = tape.gradient(loss, model.trainable_variables)
        grads, _ = tf.clip_by_global_norm(grads, 1.0)
        optimizer.apply_gradients(zip(grads, model.trainable_variables))
        return loss

    for _ in range(epochs):
        for snap_idx in rng.permutation(len(train_snapshots)):
            snap = train_snapshots[int(snap_idx)]
            train_step(
                tf.constant(snap.x_seq, dtype=tf.float32),
                tf.constant(snap.x_node, dtype=tf.float32),
                train_edge_index,
                tf.constant(snap.y, dtype=tf.int64),
            )

    y_true: list[int] = []
    y_pred: list[int] = []
    for snap in test_snapshots:
        logits = model(
            (tf.constant(snap.x_seq, dtype=tf.float32), tf.constant(snap.x_node, dtype=tf.float32), test_edge_index),
            training=False,
        )
        y_true.extend(snap.y.tolist())
        y_pred.extend(tf.argmax(logits, axis=1).numpy().tolist())

    return {
        "heldout_region": heldout_region,
        "status": "ok",
        "train_regions": sorted(train_df["region_id"].unique().tolist()),
        "window_hours": window,
        "epochs": epochs,
        "train_snapshots": len(train_snapshots),
        "test_snapshots": len(test_snapshots),
        "train_nodes": len(train_snapshots[0].tower_ids),
        "test_nodes": len(test_snapshots[0].tower_ids),
        "train_edges": int(train_edges_np.shape[1]),
        "test_edges": int(test_edges_np.shape[1]),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Leave-one-region-out TensorFlow PatchTST-GraphSAGE benchmark.")
    parser.add_argument("--table", default=str(ROOT / "data" / "china_benchmark" / "features" / "training_table_multiregion_demo.csv"))
    parser.add_argument("--heldout-region", default="", help="If empty, evaluate every region.")
    parser.add_argument("--window", type=int, default=24)
    parser.add_argument("--stride", type=int, default=12)
    parser.add_argument("--epochs", type=int, default=8)
    args = parser.parse_args()

    try:
        import tensorflow as tf
    except Exception as exc:  # pragma: no cover - environment-specific
        raise RuntimeError(f"TensorFlow import failed: {exc!r}") from exc

    table_path = Path(args.table)
    if not table_path.exists():
        raise FileNotFoundError(f"Missing multiregion table: {table_path}. Run scripts/build_multiregion_dataset.py first.")
    df = pd.read_csv(table_path, parse_dates=["time"])
    if "region_id" not in df.columns:
        raise ValueError("Multiregion table must include region_id.")

    regions = [args.heldout_region] if args.heldout_region else sorted(df["region_id"].unique().tolist())
    rows = [_train_one_region(tf, df, region, args.window, args.stride, args.epochs) for region in regions]
    out_dir = ROOT / "artifacts" / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "tf_patchtst_graphsage_multiregion.json"
    out_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(out_path)
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()

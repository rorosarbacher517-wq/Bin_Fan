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
from gridweather.models.temporal_graph import NODE_FEATURES, build_line_edges, build_temporal_graph_snapshots
from gridweather.models.tf_temporal_graph import make_tf_patchtst_graphsage_model


def _write_metrics(metrics: dict) -> None:
    out_dir = ROOT / "artifacts" / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "tf_patchtst_graphsage_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(metrics)


def main() -> None:
    try:
        import tensorflow as tf
    except Exception as exc:  # pragma: no cover - environment-specific
        _write_metrics({"status": "skipped", "reason": f"TensorFlow import failed: {exc!r}"})
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

    train_snapshots = build_temporal_graph_snapshots(train_df, window=24, stride=12, max_snapshots=50)
    test_snapshots = build_temporal_graph_snapshots(test_df, window=24, stride=12, max_snapshots=20)
    if not train_snapshots or not test_snapshots:
        _write_metrics({"status": "skipped", "reason": "Not enough temporal graph snapshots after train/test split."})
        return

    _, edge_np = build_line_edges(train_df[["tower_id", "line_id"]])
    edge_index = tf.constant(edge_np, dtype=tf.int32)
    model = make_tf_patchtst_graphsage_model(n_weather=len(WEATHER), n_node=len(NODE_FEATURES), window=24)
    optimizer = tf.keras.optimizers.Adam(learning_rate=8e-4)
    loss_fn = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True)
    rng = np.random.default_rng(42)
    train_labels = np.concatenate([snap.y for snap in train_snapshots])
    counts = np.bincount(train_labels, minlength=4).astype(np.float32)
    class_weight = counts.sum() / np.maximum(counts * len(counts), 1.0)
    class_weight = tf.constant(class_weight, dtype=tf.float32)

    @tf.function
    def train_step(x_seq, x_node, y):
        with tf.GradientTape() as tape:
            logits = model((x_seq, x_node, edge_index), training=True)
            weights = tf.gather(class_weight, y)
            loss = loss_fn(y, logits, sample_weight=weights)
        grads = tape.gradient(loss, model.trainable_variables)
        grads, _ = tf.clip_by_global_norm(grads, 1.0)
        optimizer.apply_gradients(zip(grads, model.trainable_variables))
        return loss

    epochs = 20
    for _ in range(epochs):
        for snap_idx in rng.permutation(len(train_snapshots)):
            snap = train_snapshots[int(snap_idx)]
            train_step(
                tf.constant(snap.x_seq, dtype=tf.float32),
                tf.constant(snap.x_node, dtype=tf.float32),
                tf.constant(snap.y, dtype=tf.int64),
            )

    y_true: list[int] = []
    y_pred: list[int] = []
    for snap in test_snapshots:
        logits = model((tf.constant(snap.x_seq, dtype=tf.float32), tf.constant(snap.x_node, dtype=tf.float32), edge_index), training=False)
        y_true.extend(snap.y.tolist())
        y_pred.extend(tf.argmax(logits, axis=1).numpy().tolist())

    out_dir = ROOT / "artifacts" / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_weights(str(out_dir / "tf_patchtst_graphsage_weights"))
    _write_metrics(
        {
            "status": "ok",
            "framework": "TensorFlow/Keras",
            "model": "PatchTST weather encoder + IEEE738 priors + GraphSAGE topology",
            "window_hours": 24,
            "epochs": epochs,
            "train_snapshots": len(train_snapshots),
            "test_snapshots": len(test_snapshots),
            "nodes": len(train_snapshots[0].tower_ids),
            "edges": int(edge_np.shape[1]),
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
        }
    )


if __name__ == "__main__":
    main()

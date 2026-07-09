from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from gridweather.models.feature_sets import DEM, DLR, IEEE738, PHYSICS_PROXY, SENTINEL, WEATHER


NODE_FEATURES = [
    *DEM,
    *SENTINEL,
    "line_heading_deg",
    "wind_line_angle",
    "crosswind_factor",
    *DLR,
    *IEEE738,
    *PHYSICS_PROXY,
]


@dataclass
class TemporalGraphSnapshot:
    time: pd.Timestamp
    tower_ids: list[str]
    x_seq: np.ndarray
    x_node: np.ndarray
    y: np.ndarray


def build_line_edges(towers: pd.DataFrame) -> tuple[list[str], np.ndarray]:
    """Build an undirected path graph for towers on each line."""
    tower_table = towers[["tower_id", "line_id"]].drop_duplicates().sort_values(["line_id", "tower_id"])
    tower_ids = tower_table["tower_id"].tolist()
    idx = {tower_id: pos for pos, tower_id in enumerate(tower_ids)}
    edges: list[tuple[int, int]] = []
    for _, group in tower_table.groupby("line_id", sort=False):
        ordered = group["tower_id"].tolist()
        for left, right in zip(ordered, ordered[1:]):
            a, b = idx[left], idx[right]
            edges.append((a, b))
            edges.append((b, a))
    if not edges:
        return tower_ids, np.empty((2, 0), dtype=np.int64)
    return tower_ids, np.asarray(edges, dtype=np.int64).T


def build_temporal_graph_snapshots(
    df: pd.DataFrame,
    window: int = 24,
    stride: int = 6,
    max_snapshots: int | None = None,
) -> list[TemporalGraphSnapshot]:
    """Create graph snapshots with PatchTST weather windows and IEEE738 node priors."""
    missing = [col for col in ["time", "tower_id", "risk_level", *WEATHER, *NODE_FEATURES] if col not in df.columns]
    if missing:
        raise ValueError(f"Training table is missing columns required by temporal graph model: {missing}")

    work = df.sort_values(["tower_id", "time"]).copy()
    work["time"] = pd.to_datetime(work["time"])
    tower_ids, _ = build_line_edges(work[["tower_id", "line_id"]])
    tower_set = set(tower_ids)
    time_index = sorted(work["time"].unique())
    candidate_times = time_index[window::stride]
    snapshots: list[TemporalGraphSnapshot] = []

    by_tower = {tower_id: group.reset_index(drop=True) for tower_id, group in work.groupby("tower_id", sort=False)}
    for target_time in candidate_times:
        seq_rows = []
        node_rows = []
        labels = []
        valid = True
        for tower_id in tower_ids:
            if tower_id not in tower_set:
                valid = False
                break
            group = by_tower[tower_id]
            pos = group.index[group["time"] == target_time]
            if len(pos) != 1 or int(pos[0]) < window:
                valid = False
                break
            idx = int(pos[0])
            seq_rows.append(group.loc[idx - window : idx - 1, WEATHER].to_numpy(dtype=np.float32))
            node_rows.append(group.loc[idx, NODE_FEATURES].to_numpy(dtype=np.float32))
            labels.append(int(group.loc[idx, "risk_level"]))
        if valid:
            snapshots.append(
                TemporalGraphSnapshot(
                    time=pd.Timestamp(target_time),
                    tower_ids=tower_ids,
                    x_seq=np.stack(seq_rows).astype(np.float32),
                    x_node=np.stack(node_rows).astype(np.float32),
                    y=np.asarray(labels, dtype=np.int64),
                )
            )
        if max_snapshots is not None and len(snapshots) >= max_snapshots:
            break
    return snapshots


def require_torch():
    try:
        import torch
        from torch import nn
    except Exception as exc:  # pragma: no cover - environment-specific
        raise RuntimeError(f"PyTorch is required for PatchTST-GraphSAGE training: {exc!r}") from exc
    return torch, nn


def make_temporal_graph_model(n_weather: int, n_node: int, n_classes: int = 4):
    torch, nn = require_torch()

    class PatchTemporalEncoder(nn.Module):
        def __init__(self, patch_len: int = 6, d_model: int = 64, n_heads: int = 4) -> None:
            super().__init__()
            self.patch_len = patch_len
            self.proj = nn.Linear(n_weather * patch_len, d_model)
            layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=n_heads, dim_feedforward=128, batch_first=True)
            self.encoder = nn.TransformerEncoder(layer, num_layers=2)

        def forward(self, x):
            nodes, steps, feats = x.shape
            pad = (-steps) % self.patch_len
            if pad:
                x = torch.cat([x, x[:, -1:, :].repeat(1, pad, 1)], dim=1)
            patches = x.reshape(nodes, -1, self.patch_len * feats)
            return self.encoder(self.proj(patches)).mean(dim=1)

    class GraphSAGELayer(nn.Module):
        def __init__(self, in_dim: int, out_dim: int) -> None:
            super().__init__()
            self.self_proj = nn.Linear(in_dim, out_dim)
            self.neigh_proj = nn.Linear(in_dim, out_dim)

        def forward(self, h, edge_index):
            src, dst = edge_index
            neigh = torch.zeros_like(h)
            degree = torch.zeros((h.shape[0], 1), dtype=h.dtype, device=h.device)
            neigh.index_add_(0, dst, h[src])
            degree.index_add_(0, dst, torch.ones((len(dst), 1), dtype=h.dtype, device=h.device))
            neigh = neigh / degree.clamp_min(1.0)
            return torch.relu(self.self_proj(h) + self.neigh_proj(neigh))

    class PatchTSTGraphSAGE(nn.Module):
        """PatchTST weather encoder + IEEE738 node priors + GraphSAGE propagation."""

        def __init__(self, d_model: int = 64, hidden: int = 96) -> None:
            super().__init__()
            self.temporal = PatchTemporalEncoder(d_model=d_model)
            self.node_proj = nn.Sequential(nn.Linear(n_node, d_model), nn.ReLU(), nn.LayerNorm(d_model))
            self.sage1 = GraphSAGELayer(d_model * 2, hidden)
            self.sage2 = GraphSAGELayer(hidden, hidden)
            self.head = nn.Sequential(nn.LayerNorm(hidden), nn.Linear(hidden, n_classes))

        def forward(self, x_seq, x_node, edge_index):
            z_time = self.temporal(x_seq)
            z_node = self.node_proj(x_node)
            h = torch.cat([z_time, z_node], dim=-1)
            h = self.sage1(h, edge_index)
            h = self.sage2(h, edge_index)
            return self.head(h)

    return PatchTSTGraphSAGE()

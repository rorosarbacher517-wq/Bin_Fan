from __future__ import annotations

import torch
from torch import nn


class PatchTSTLite(nn.Module):
    """Small PatchTST-style classifier for weather windows.

    Input shape: [batch, time, features]. It patches the time axis, encodes
    patches with a Transformer encoder, and classifies risk level.
    """

    def __init__(self, n_features: int, n_classes: int = 4, patch_len: int = 6, d_model: int = 64, n_heads: int = 4) -> None:
        super().__init__()
        self.patch_len = patch_len
        self.proj = nn.Linear(n_features * patch_len, d_model)
        layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=n_heads, dim_feedforward=128, batch_first=True)
        self.encoder = nn.TransformerEncoder(layer, num_layers=2)
        self.head = nn.Sequential(nn.LayerNorm(d_model), nn.Linear(d_model, n_classes))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        bsz, steps, feats = x.shape
        pad = (-steps) % self.patch_len
        if pad:
            x = torch.cat([x, x[:, -1:, :].repeat(1, pad, 1)], dim=1)
        patches = x.reshape(bsz, -1, self.patch_len * feats)
        z = self.encoder(self.proj(patches))
        return self.head(z.mean(dim=1))


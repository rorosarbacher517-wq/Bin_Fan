from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

try:
    import torch
    from gridweather.models.patchtst_lite import PatchTSTLite
    TORCH_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - environment-specific
    torch = None
    PatchTSTLite = None
    TORCH_IMPORT_ERROR = repr(exc)

from gridweather.models.feature_sets import WEATHER


def build_windows(df: pd.DataFrame, window: int = 24):
    df = df.sort_values(["tower_id", "time"])
    xs, ys = [], []
    for _, group in df.groupby("tower_id"):
        arr = group[WEATHER].to_numpy(dtype=np.float32)
        labels = group["risk_level"].to_numpy(dtype=np.int64)
        for idx in range(window, len(group), 12):
            xs.append(arr[idx - window : idx])
            ys.append(labels[idx])
    return np.stack(xs), np.array(ys)


def main() -> None:
    out_dir = ROOT / "artifacts" / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)
    if torch is None or PatchTSTLite is None:
        metrics = {"status": "skipped", "reason": TORCH_IMPORT_ERROR}
        (out_dir / "patchtst_lite_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print(metrics)
        return
    df = pd.read_csv(ROOT / "data" / "real" / "features" / "training_table.csv", parse_dates=["time"])
    cutoff = df["time"].max() - pd.Timedelta(days=5)
    train_df, test_df = df[df["time"] <= cutoff], df[df["time"] > cutoff]
    scaler = StandardScaler().fit(train_df[WEATHER])
    train_df = train_df.copy()
    test_df = test_df.copy()
    train_df[WEATHER] = scaler.transform(train_df[WEATHER])
    test_df[WEATHER] = scaler.transform(test_df[WEATHER])
    x_train, y_train = build_windows(train_df)
    x_test, y_test = build_windows(test_df)
    model = PatchTSTLite(n_features=x_train.shape[-1])
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    loss_fn = torch.nn.CrossEntropyLoss()
    x = torch.tensor(x_train)
    y = torch.tensor(y_train)
    for _ in range(3):
        model.train()
        perm = torch.randperm(len(x))
        for start in range(0, len(x), 128):
            idx = perm[start : start + 128]
            loss = loss_fn(model(x[idx]), y[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        pred = model(torch.tensor(x_test)).argmax(dim=1).numpy()
    metrics = {"macro_f1": float(f1_score(y_test, pred, average="macro")), "windows_train": int(len(x_train)), "windows_test": int(len(x_test))}
    (out_dir / "patchtst_lite_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    torch.save(model.state_dict(), out_dir / "patchtst_lite.pt")
    print(metrics)


if __name__ == "__main__":
    main()

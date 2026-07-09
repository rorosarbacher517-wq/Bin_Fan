from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    cfg_path = Path(path)
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    base = cfg_path.parent.parent
    cfg["_base_dir"] = str(base.resolve())
    return cfg


def project_path(cfg: dict[str, Any], *parts: str) -> Path:
    return Path(cfg["_base_dir"]).joinpath(*parts)


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


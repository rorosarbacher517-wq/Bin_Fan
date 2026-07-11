from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


class EventLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, **payload: Any) -> None:
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    @contextmanager
    def span(self, event: str, **payload: Any) -> Iterator[None]:
        start = time.perf_counter()
        self.emit(f"{event}.start", **payload)
        try:
            yield
        except Exception as exc:
            self.emit(f"{event}.error", elapsed_seconds=time.perf_counter() - start, error=repr(exc), **payload)
            raise
        self.emit(f"{event}.end", elapsed_seconds=time.perf_counter() - start, **payload)

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TaskRecord:
    task_id: str
    user_message: str
    status: str = "created"
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    plan: dict[str, Any] = field(default_factory=dict)
    graph_trace: list[str] = field(default_factory=list)
    used_tools: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    guidelines: list[str] = field(default_factory=list)
    guardrail_flags: list[str] = field(default_factory=list)
    error: str | None = None

    @classmethod
    def create(cls, user_message: str) -> "TaskRecord":
        return cls(task_id=f"task_{uuid.uuid4().hex[:12]}", user_message=user_message)


class TaskStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, user_message: str) -> TaskRecord:
        record = TaskRecord.create(user_message)
        self.save(record)
        return record

    def save(self, record: TaskRecord) -> None:
        record.updated_at = utc_now_iso()
        self.path(record.task_id).write_text(json.dumps(asdict(record), indent=2, ensure_ascii=False), encoding="utf-8")

    def load(self, task_id: str) -> TaskRecord:
        data = json.loads(self.path(task_id).read_text(encoding="utf-8"))
        return TaskRecord(**data)

    def path(self, task_id: str) -> Path:
        return self.root / f"{task_id}.json"

    def evidence_path(self, task_id: str) -> Path:
        return self.root / f"{task_id}.evidence.json"

    def save_evidence_packet(self, task_id: str, packet: dict[str, Any]) -> Path:
        path = self.evidence_path(task_id)
        path.write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    permissions: list[str] = field(default_factory=list)
    timeout_seconds: float = 10.0
    side_effect: bool = False
    status: str = "implemented"


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def list(self) -> list[ToolSpec]:
        return [self._tools[name] for name in sorted(self._tools)]

    def as_dict(self) -> dict[str, dict[str, Any]]:
        return {tool.name: tool.__dict__ for tool in self.list()}


def default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="risk_summary",
            description="Summarize tower-level risk records in the latest available prediction window.",
            input_schema={"type": "object", "properties": {"time_range": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"tower_count": {"type": "integer"}, "high_risk_records": {"type": "integer"}}},
            permissions=["risk:read"],
        )
    )
    registry.register(
        ToolSpec(
            name="top_risk_ranker",
            description="Rank towers by peak predicted risk score.",
            input_schema={"type": "object", "properties": {"top_k": {"type": "integer", "default": 5}}},
            output_schema={"type": "object", "properties": {"top_risks": {"type": "array"}}},
            permissions=["risk:read"],
        )
    )
    registry.register(
        ToolSpec(
            name="tower_lookup",
            description="Query tower-level peak risk and evidence by tower id.",
            input_schema={"type": "object", "required": ["tower_id"], "properties": {"tower_id": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"tower_id": {"type": "string"}, "risk_score": {"type": "number"}}},
            permissions=["risk:read", "asset:read"],
        )
    )
    registry.register(
        ToolSpec(
            name="line_risk_aggregator",
            description="Aggregate tower risk by transmission line id.",
            input_schema={"type": "object", "required": ["line_id"], "properties": {"line_id": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"line_id": {"type": "string"}, "high_risk_tower_count": {"type": "integer"}}},
            permissions=["risk:read", "asset:read"],
        )
    )
    registry.register(
        ToolSpec(
            name="capacity_margin_checker",
            description="Find low DLR or capacity-margin towers.",
            input_schema={"type": "object", "properties": {"top_k": {"type": "integer", "default": 5}}},
            output_schema={"type": "object", "properties": {"capacity_watch": {"type": "array"}}},
            permissions=["risk:read"],
        )
    )
    registry.register(
        ToolSpec(
            name="rag_guideline_retriever",
            description="Retrieve operation guideline snippets for grounding recommendations.",
            input_schema={"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"guidelines": {"type": "array"}}},
            permissions=["kb:read"],
        )
    )
    registry.register(
        ToolSpec(
            name="weather_forecast_reader",
            description="Read future weather forecasts. Currently implemented as a mock adapter.",
            input_schema={"type": "object", "properties": {"line_id": {"type": "string"}, "horizon_hours": {"type": "integer"}}},
            output_schema={"type": "object", "properties": {"forecast": {"type": "array"}}},
            permissions=["weather:read"],
            status="mock",
        )
    )
    registry.register(
        ToolSpec(
            name="scada_load_reader",
            description="Read real-time line load/current from SCADA. Currently implemented as a mock adapter.",
            input_schema={"type": "object", "properties": {"line_id": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"current_a": {"type": "number"}, "load_rate": {"type": "number"}}},
            permissions=["scada:read"],
            status="mock",
        )
    )
    registry.register(
        ToolSpec(
            name="maintenance_ticket_writer",
            description="Create an inspection or maintenance ticket. Currently implemented as a mock adapter.",
            input_schema={"type": "object", "required": ["title"], "properties": {"title": {"type": "string"}, "priority": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"ticket_id": {"type": "string"}, "status": {"type": "string"}}},
            permissions=["ticket:write"],
            side_effect=True,
            status="mock",
        )
    )
    return registry

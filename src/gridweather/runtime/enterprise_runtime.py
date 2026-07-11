from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from gridweather.agent.operator_graph import answer_operator_question
from gridweather.runtime.connectors import ConnectorHub
from gridweather.runtime.observability import EventLogger
from gridweather.runtime.task_state import TaskStore
from gridweather.runtime.tool_registry import ToolRegistry, default_tool_registry


class EnterpriseAgentRuntime:
    """Enterprise runtime wrapper around the operator Agent graph.

    This class adds task ids, tool registry, evidence persistence, event logs,
    and mock enterprise connectors around the current runnable Agent.
    """

    def __init__(
        self,
        predictions: pd.DataFrame,
        artifact_dir: Path,
        registry: ToolRegistry | None = None,
        connectors: ConnectorHub | None = None,
    ) -> None:
        self.predictions = predictions
        self.artifact_dir = artifact_dir
        self.registry = registry or default_tool_registry()
        self.connectors = connectors or ConnectorHub.mock()
        self.tasks = TaskStore(artifact_dir / "runtime" / "tasks")
        self.events = EventLogger(artifact_dir / "runtime" / "events.jsonl")

    def ask(self, message: str) -> dict[str, Any]:
        task = self.tasks.create(message)
        self.events.emit("task.created", task_id=task.task_id, message=message)
        try:
            with self.events.span("agent.invoke", task_id=task.task_id):
                response = answer_operator_question(self.predictions, message)
            response = self._attach_mock_connector_context(response)
            evidence_packet = self._build_evidence_packet(response)
            evidence_path = self.tasks.save_evidence_packet(task.task_id, evidence_packet)

            task.status = "completed"
            task.plan = response.get("plan", {})
            task.graph_trace = response.get("graph_trace", [])
            task.used_tools = response.get("used_tools", [])
            task.evidence = response.get("evidence", {})
            task.guidelines = response.get("guidelines", [])
            task.guardrail_flags = response.get("guardrail_flags", [])
            self.tasks.save(task)
            self.events.emit(
                "task.completed",
                task_id=task.task_id,
                intent=response.get("intent"),
                used_tools=task.used_tools,
                guardrail_flags=task.guardrail_flags,
            )
            return {
                **response,
                "task_id": task.task_id,
                "task_status": task.status,
                "evidence_packet_path": str(evidence_path),
                "tool_registry": self._used_tool_specs(task.used_tools + response.get("unsupported_tools", [])),
            }
        except Exception as exc:
            task.status = "failed"
            task.error = repr(exc)
            self.tasks.save(task)
            self.events.emit("task.failed", task_id=task.task_id, error=repr(exc))
            raise

    def _attach_mock_connector_context(self, response: dict[str, Any]) -> dict[str, Any]:
        unsupported = set(response.get("unsupported_tools", []))
        connector_context: dict[str, Any] = {}
        line_id = response.get("plan", {}).get("target", {}).get("line_id") or "L00"

        if "weather_forecast_reader" in unsupported:
            connector_context["weather_forecast_reader_mock"] = self.connectors.weather.read_forecast(line_id=line_id)
        if "scada_load_reader" in unsupported or "scenario_risk_simulator" in unsupported:
            connector_context["scada_load_reader_mock"] = self.connectors.scada.read_line_load(line_id=line_id)
        if "maintenance_ticket_writer" in unsupported:
            connector_context["maintenance_ticket_writer_mock"] = self.connectors.tickets.create_ticket(
                title="High-risk inspection draft",
                priority="high",
                description="Mock draft created for Agent capability demonstration.",
            )
        if connector_context:
            response = dict(response)
            response["mock_connector_context"] = connector_context
        return response

    def _build_evidence_packet(self, response: dict[str, Any]) -> dict[str, Any]:
        return {
            "intent": response.get("intent"),
            "plan": response.get("plan", {}),
            "graph_trace": response.get("graph_trace", []),
            "used_tools": response.get("used_tools", []),
            "evidence": response.get("evidence", {}),
            "guidelines": response.get("guidelines", []),
            "guardrail_flags": response.get("guardrail_flags", []),
            "missing_info": response.get("missing_info", []),
            "unsupported_tools": response.get("unsupported_tools", []),
            "mock_connector_context": response.get("mock_connector_context", {}),
        }

    def _used_tool_specs(self, used_tools: list[str]) -> dict[str, Any]:
        specs: dict[str, Any] = {}
        for tool in used_tools:
            if tool in {"planner", "clarify", "guardrails", "unsupported_capability", "report_generator"}:
                continue
            try:
                specs[tool] = self.registry.get(tool).__dict__
            except KeyError:
                specs[tool] = {"name": tool, "status": "unregistered"}
        return specs

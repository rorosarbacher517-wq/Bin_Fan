from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from gridweather.agent.explain import attach_explanations, explain_row, recommend_action
from gridweather.agent.report import build_html_report
from gridweather.agent.toolchain import build_evidence_packet


@dataclass
class ToolCall:
    name: str
    success: bool
    latency_seconds: float
    error: str | None = None


@dataclass
class EvalTask:
    task_id: str
    task_type: str
    prompt: str
    expected_tools: list[str]
    requires_recovery: bool = False
    calls: list[ToolCall] = field(default_factory=list)
    success: bool = False
    unsupported_claims: int = 0
    total_claims: int = 0
    traceable_items: int = 0
    total_trace_items: int = 0
    human_intervention_required: bool = False
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def latency_seconds(self) -> float:
        return sum(call.latency_seconds for call in self.calls)

    @property
    def called_tools(self) -> list[str]:
        return [call.name for call in self.calls]


class AgentWorkflowEvaluator:
    def __init__(self, prediction_csv: Path, output_dir: Path, top_k_towers: int = 5) -> None:
        self.prediction_csv = prediction_csv
        self.output_dir = output_dir
        self.top_k_towers = top_k_towers
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def call_tool(self, task: EvalTask, name: str, fn: Callable[[], Any]) -> Any:
        start = time.perf_counter()
        try:
            result = fn()
        except Exception as exc:
            task.calls.append(ToolCall(name=name, success=False, latency_seconds=time.perf_counter() - start, error=repr(exc)))
            raise
        task.calls.append(ToolCall(name=name, success=True, latency_seconds=time.perf_counter() - start))
        return result

    def build_tasks(self) -> list[EvalTask]:
        df = pd.read_csv(self.prediction_csv, parse_dates=["time"])
        peak = (
            df.sort_values("pred_risk_score", ascending=False)
            .groupby("tower_id", as_index=False)
            .head(1)
            .sort_values("pred_risk_score", ascending=False)
            .head(self.top_k_towers)
        )

        tasks = [
            EvalTask(
                task_id="report_latest_risk",
                task_type="report_generation",
                prompt="Generate a tower-level risk report from the latest prediction table.",
                expected_tools=["read_predictions", "attach_explanations", "build_report"],
            )
        ]
        for idx, tower_id in enumerate(peak["tower_id"].astype(str), start=1):
            tasks.append(
                EvalTask(
                    task_id=f"tower_evidence_{idx}",
                    task_type="evidence_query",
                    prompt=f"Explain the peak risk and supporting evidence for tower {tower_id}.",
                    expected_tools=["build_evidence_packet"],
                    output={"tower_id": tower_id},
                )
            )
        tasks.append(
            EvalTask(
                task_id="missing_tower_recovery",
                task_type="failure_recovery",
                prompt="Query a tower id that does not exist and recover gracefully.",
                expected_tools=["build_evidence_packet", "fallback_missing_tower"],
                requires_recovery=True,
                output={"tower_id": "__MISSING_TOWER__"},
            )
        )
        return tasks

    def run(self) -> dict[str, Any]:
        tasks = self.build_tasks()
        for task in tasks:
            try:
                if task.task_type == "report_generation":
                    self._run_report_task(task)
                elif task.task_type == "evidence_query":
                    self._run_evidence_task(task, str(task.output["tower_id"]))
                elif task.task_type == "failure_recovery":
                    self._run_recovery_task(task, str(task.output["tower_id"]))
                else:
                    raise ValueError(f"Unsupported task type: {task.task_type}")
            except Exception as exc:
                task.success = False
                task.error = repr(exc)
                task.human_intervention_required = True

        metrics = self._summarize(tasks)
        self._write_outputs(tasks, metrics)
        return metrics

    def _run_report_task(self, task: EvalTask) -> None:
        df = self.call_tool(task, "read_predictions", lambda: pd.read_csv(self.prediction_csv, parse_dates=["time"]))
        explained = self.call_tool(task, "attach_explanations", lambda: attach_explanations(df))
        report_path = self.call_tool(
            task,
            "build_report",
            lambda: build_html_report(self.prediction_csv, self.output_dir / "reports"),
        )

        sample = explained.sort_values("pred_risk_score", ascending=False).head(30)
        unsupported = 0
        total = 0
        for _, row in sample.iterrows():
            expected_explanation = explain_row(row)
            expected_action = recommend_action(row)
            explanation_parts = [part for part in str(row["agent_explanation"]).split("; ") if part]
            total += max(1, len(explanation_parts)) + 1
            if row["agent_explanation"] != expected_explanation:
                unsupported += max(1, len(explanation_parts))
            if row["recommended_action"] != expected_action:
                unsupported += 1

        task.total_claims = total
        task.unsupported_claims = unsupported
        required_columns = {
            "tower_id",
            "time",
            "pred_risk_level",
            "pred_risk_score",
            "temperature_c",
            "relative_humidity",
            "wind_speed_ms",
            "precip_mm",
            "agent_explanation",
            "recommended_action",
        }
        task.total_trace_items = 3
        task.traceable_items = int(self.prediction_csv.exists()) + int(required_columns.issubset(explained.columns)) + int(report_path.exists())
        task.success = task.traceable_items == task.total_trace_items and unsupported == 0
        task.output.update({"report_path": str(report_path), "sampled_rows": int(len(sample))})

    def _run_evidence_task(self, task: EvalTask, tower_id: str) -> None:
        packet = self.call_tool(task, "build_evidence_packet", lambda: build_evidence_packet(self.prediction_csv, tower_id))
        required_keys = {"tower_id", "peak_time", "risk_score", "risk_level", "weather", "guidelines"}
        task.total_trace_items = len(required_keys)
        task.traceable_items = sum(1 for key in required_keys if key in packet and packet.get(key) not in (None, "", []))
        task.total_claims = 4
        task.unsupported_claims = 0 if task.traceable_items == task.total_trace_items else 1
        task.success = "error" not in packet and task.traceable_items == task.total_trace_items
        task.output.update({"evidence_packet": packet})

    def _run_recovery_task(self, task: EvalTask, tower_id: str) -> None:
        packet = self.call_tool(task, "build_evidence_packet", lambda: build_evidence_packet(self.prediction_csv, tower_id))

        def fallback() -> dict[str, Any]:
            return {
                "status": "recovered",
                "reason": packet.get("error", "unknown error"),
                "next_action": "ask user to provide a valid tower_id or choose one from latest_predictions.csv",
            }

        recovered = self.call_tool(task, "fallback_missing_tower", fallback)
        task.total_trace_items = 2
        task.traceable_items = int(packet.get("error") == "tower not found") + int(recovered["status"] == "recovered")
        task.total_claims = 1
        task.unsupported_claims = 0
        task.success = task.traceable_items == task.total_trace_items
        task.output.update({"tool_packet": packet, "fallback": recovered})

    def _summarize(self, tasks: list[EvalTask]) -> dict[str, Any]:
        expected_tool_count = sum(len(task.expected_tools) for task in tasks)
        matched_tool_count = sum(sum(1 for tool in task.expected_tools if tool in task.called_tools) for task in tasks)
        unexpected_tool_count = sum(sum(1 for tool in task.called_tools if tool not in task.expected_tools) for task in tasks)
        recovery_tasks = [task for task in tasks if task.requires_recovery]
        total_claims = sum(task.total_claims for task in tasks)
        unsupported_claims = sum(task.unsupported_claims for task in tasks)
        total_trace_items = sum(task.total_trace_items for task in tasks)
        traceable_items = sum(task.traceable_items for task in tasks)
        total_latency = sum(task.latency_seconds for task in tasks)

        return {
            "evaluation_scope": "Agent-ready deterministic workflow evaluation; model accuracy is reported separately.",
            "prediction_csv": str(self.prediction_csv),
            "num_tasks": len(tasks),
            "task_success_rate": _ratio(sum(task.success for task in tasks), len(tasks)),
            "tool_call_accuracy": _ratio(matched_tool_count, expected_tool_count),
            "unexpected_tool_calls": unexpected_tool_count,
            "average_steps": statistics.mean(len(task.calls) for task in tasks) if tasks else 0.0,
            "recovery_rate": _ratio(sum(task.success for task in recovery_tasks), len(recovery_tasks)) if recovery_tasks else None,
            "hallucination_rate": _ratio(unsupported_claims, total_claims),
            "latency_seconds_total": total_latency,
            "latency_seconds_avg_per_task": total_latency / len(tasks) if tasks else 0.0,
            "human_intervention_rate": _ratio(sum(task.human_intervention_required for task in tasks), len(tasks)),
            "cost_per_task": {
                "llm_api_calls": 0,
                "estimated_llm_cost_usd": 0.0,
                "local_runtime_seconds_avg": total_latency / len(tasks) if tasks else 0.0,
            },
            "traceability_rate": _ratio(traceable_items, total_trace_items),
            "claim_counts": {
                "total_claims_checked": total_claims,
                "unsupported_claims": unsupported_claims,
            },
            "traceability_counts": {
                "traceable_items": traceable_items,
                "total_trace_items": total_trace_items,
            },
        }

    def _write_outputs(self, tasks: list[EvalTask], metrics: dict[str, Any]) -> None:
        serializable_tasks = []
        for task in tasks:
            serializable_tasks.append(
                {
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "prompt": task.prompt,
                    "expected_tools": task.expected_tools,
                    "called_tools": task.called_tools,
                    "success": task.success,
                    "latency_seconds": task.latency_seconds,
                    "unsupported_claims": task.unsupported_claims,
                    "total_claims": task.total_claims,
                    "traceable_items": task.traceable_items,
                    "total_trace_items": task.total_trace_items,
                    "human_intervention_required": task.human_intervention_required,
                    "error": task.error,
                    "calls": [call.__dict__ for call in task.calls],
                    "output": task.output,
                }
            )

        (self.output_dir / "agent_eval_metrics.json").write_text(
            json.dumps({"metrics": metrics, "tasks": serializable_tasks}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (self.output_dir / "agent_eval_report.md").write_text(_format_markdown(metrics, serializable_tasks), encoding="utf-8")


def _ratio(numerator: int | float, denominator: int | float) -> float:
    if denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)


def _pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def _format_markdown(metrics: dict[str, Any], tasks: list[dict[str, Any]]) -> str:
    lines = [
        "# GridWeatherAgent Workflow Evaluation",
        "",
        "This evaluation measures the deterministic Agent-ready workflow layer. It does not treat the risk model's classification accuracy as an Agent metric.",
        "",
        "## Summary Metrics",
        "",
        f"- Task Success Rate: {_pct(metrics['task_success_rate'])}",
        f"- Tool Call Accuracy: {_pct(metrics['tool_call_accuracy'])}",
        f"- Average Steps: {metrics['average_steps']:.2f}",
        f"- Recovery Rate: {_pct(metrics['recovery_rate'])}",
        f"- Hallucination Rate: {_pct(metrics['hallucination_rate'])}",
        f"- Average Latency: {metrics['latency_seconds_avg_per_task']:.3f} seconds/task",
        f"- Human Intervention Rate: {_pct(metrics['human_intervention_rate'])}",
        f"- Cost per Task: {metrics['cost_per_task']['estimated_llm_cost_usd']:.2f} USD LLM cost; {metrics['cost_per_task']['local_runtime_seconds_avg']:.3f} local runtime seconds",
        f"- Traceability Rate: {_pct(metrics['traceability_rate'])}",
        "",
        "## Task Details",
        "",
        "| Task | Type | Success | Tools | Latency (s) |",
        "|---|---|---:|---|---:|",
    ]
    for task in tasks:
        lines.append(
            f"| {task['task_id']} | {task['task_type']} | {task['success']} | {', '.join(task['called_tools'])} | {task['latency_seconds']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `Task Success Rate` checks whether report generation, tower evidence query, and graceful failure recovery finish with required outputs.",
            "- `Tool Call Accuracy` checks whether the workflow used the expected registered tools for each task.",
            "- `Hallucination Rate` checks deterministic report/explanation claims against source prediction columns and rule outputs.",
            "- `Traceability Rate` checks whether task outputs can be traced back to prediction CSV, evidence packet fields, and generated report artifacts.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate GridWeatherAgent Agent-ready workflow metrics.")
    parser.add_argument(
        "--prediction-csv",
        type=Path,
        default=ROOT / "artifacts" / "predictions" / "latest_predictions.csv",
        help="Path to latest_predictions.csv.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "artifacts" / "agent_eval",
        help="Directory for agent_eval_metrics.json and agent_eval_report.md.",
    )
    parser.add_argument("--top-k-towers", type=int, default=5, help="Number of high-risk tower evidence tasks.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.prediction_csv.exists():
        raise FileNotFoundError(f"Prediction CSV not found: {args.prediction_csv}")
    metrics = AgentWorkflowEvaluator(args.prediction_csv, args.output_dir, args.top_k_towers).run()
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

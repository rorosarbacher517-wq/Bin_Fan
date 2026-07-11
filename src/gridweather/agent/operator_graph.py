from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from gridweather.retrieval.chunking import paragraph_chunks
from gridweather.retrieval.hybrid import HybridRetriever, simple_rerank


SUGGESTED_QUESTIONS = [
    "当前总体风险怎么样？",
    "最高风险杆塔有哪些？",
    "L02_T034 为什么危险？",
    "L00 线路风险如何？",
    "哪些杆塔容量裕度不足？",
    "帮我生成一份今天的值班简报",
]


HELP_TEXT = """我是 GridWeatherAgent 的运维试用版。你可以把我当成电网气象风险诊断助手。

当前可处理：
1. 总体风险概览；
2. 最高风险杆塔排序；
3. 单杆塔风险诊断；
4. 单线路风险汇总；
5. 容量裕度/DLR 风险检查；
6. 基于运维规程片段给出处置建议；
7. 缺少参数时主动反问；
8. 超出当前能力时说明需要接入的工具。

当前还没有接入实时天气预报、SCADA 负荷、历史故障库和工单系统。"""


@dataclass
class OperatorAgentState:
    message: str
    predictions: pd.DataFrame
    intent: str = "unknown"
    plan: dict[str, Any] = field(default_factory=dict)
    tower_id: str | None = None
    line_id: str | None = None
    missing_info: list[str] = field(default_factory=list)
    unsupported_tools: list[str] = field(default_factory=list)
    answer: str = ""
    used_tools: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    guidelines: list[str] = field(default_factory=list)
    suggested_questions: list[str] = field(default_factory=lambda: list(SUGGESTED_QUESTIONS))
    guardrail_flags: list[str] = field(default_factory=list)
    graph_trace: list[str] = field(default_factory=list)

    def to_response(self) -> dict[str, Any]:
        response = {
            "intent": self.intent,
            "plan": self.plan,
            "answer": self.answer,
            "used_tools": self.used_tools,
            "suggested_questions": self.suggested_questions,
            "graph_trace": self.graph_trace,
        }
        if self.evidence:
            response["evidence"] = self.evidence
        if self.guidelines:
            response["guidelines"] = self.guidelines
        if self.missing_info:
            response["missing_info"] = self.missing_info
        if self.unsupported_tools:
            response["unsupported_tools"] = self.unsupported_tools
        if self.guardrail_flags:
            response["guardrail_flags"] = self.guardrail_flags
        return response


class GuidelineRetriever:
    def __init__(self, corpus_path: Path | None = None) -> None:
        if corpus_path is None:
            corpus_path = Path(__file__).parent / "guidelines" / "icing_ops_guidelines.md"
        text = corpus_path.read_text(encoding="utf-8")
        self.retriever = HybridRetriever(paragraph_chunks(text, max_tokens=120))

    def search(self, query: str, top_k: int = 2) -> list[str]:
        return [r.chunk.text for r in simple_rerank(query, self.retriever.search(query, top_k=top_k))]


class OperatorAgentGraph:
    """Dependency-light LangGraph-style graph for operator questions.

    Graph path:
    planner -> clarify / unsupported / task node -> rag_guideline -> guardrails
    """

    def __init__(self) -> None:
        self.guidelines = GuidelineRetriever()
        self.nodes: dict[str, Callable[[OperatorAgentState], OperatorAgentState]] = {
            "planner": self.planner,
            "clarify": self.clarify,
            "unsupported_capability": self.unsupported_capability,
            "risk_summary": self.risk_summary,
            "top_risk_ranker": self.top_risk_ranker,
            "tower_diagnosis": self.tower_diagnosis,
            "line_diagnosis": self.line_diagnosis,
            "capacity_watch": self.capacity_watch,
            "briefing": self.briefing,
            "help": self.help,
            "rag_guideline": self.rag_guideline,
            "guardrails": self.guardrails,
        }

    def invoke(self, predictions: pd.DataFrame, message: str) -> dict[str, Any]:
        state = OperatorAgentState(message=message, predictions=predictions)
        state = self._run_node("planner", state)
        task_node = self._route_after_planner(state)
        state = self._run_node(task_node, state)
        if task_node not in {"clarify", "unsupported_capability", "help"}:
            state = self._run_node("rag_guideline", state)
        state = self._run_node("guardrails", state)
        return state.to_response()

    def _run_node(self, name: str, state: OperatorAgentState) -> OperatorAgentState:
        state.graph_trace.append(name)
        return self.nodes[name](state)

    def _route_after_planner(self, state: OperatorAgentState) -> str:
        if state.missing_info:
            return "clarify"
        if state.unsupported_tools:
            return "unsupported_capability"
        return {
            "risk_summary": "risk_summary",
            "top_risks": "top_risk_ranker",
            "tower_diagnosis": "tower_diagnosis",
            "line_diagnosis": "line_diagnosis",
            "capacity_watch": "capacity_watch",
            "briefing": "briefing",
            "help": "help",
        }.get(state.intent, "unsupported_capability")

    def planner(self, state: OperatorAgentState) -> OperatorAgentState:
        message = state.message
        normalized = message.lower()
        tower_match = re.search(r"\bL\d{2}_T\d{3}\b", message, flags=re.IGNORECASE)
        line_match = re.search(r"\bL\d{2}\b", message, flags=re.IGNORECASE)
        state.used_tools.append("planner")

        if tower_match:
            state.tower_id = tower_match.group(0).upper()
        if line_match:
            state.line_id = line_match.group(0).upper()

        if any(word in normalized for word in ["help", "帮助", "怎么用", "能问什么"]):
            return self._set_plan(state, "help", [])

        if any(word in message for word in ["明天", "未来", "后天", "预报", "寒潮来了", "未来24", "未来 24"]):
            return self._set_unsupported(state, "future_weather_risk", ["weather_forecast_reader", "risk_model_runner"])

        if any(word in message for word in ["负荷增加", "电流", "SCADA", "scada", "实时负荷", "运行状态"]):
            return self._set_unsupported(state, "load_scenario_analysis", ["scada_load_reader", "scenario_risk_simulator"])

        if any(word in message for word in ["历史", "故障", "相似案例", "像不像"]):
            return self._set_unsupported(state, "historical_case_comparison", ["case_retriever", "fault_record_reader"])

        if any(word in message for word in ["工单", "派单", "巡检单", "生成任务"]):
            return self._set_unsupported(state, "maintenance_ticket", ["maintenance_ticket_writer", "human_confirmation_gate"])

        if any(word in message for word in ["日报", "简报", "报告", "值班"]):
            return self._set_plan(state, "briefing", ["risk_summary", "top_risk_ranker", "capacity_margin_checker", "rag_guideline_retriever"])

        if state.tower_id:
            return self._set_plan(state, "tower_diagnosis", ["tower_lookup", "risk_explainer", "rag_guideline_retriever"])

        if state.line_id:
            return self._set_plan(state, "line_diagnosis", ["line_risk_aggregator", "risk_explainer", "rag_guideline_retriever"])

        if any(word in message for word in ["哪条线路", "哪些线路", "线路风险", "这条线路"]):
            if "这条线路" in message or "该线路" in message or "线路风险" in message:
                state.missing_info.append("line_id")
                return self._set_plan(state, "line_diagnosis", ["line_risk_aggregator"])
            return self._set_plan(state, "top_risks", ["top_risk_ranker"])

        if any(word in message for word in ["哪个杆塔", "某个杆塔", "这个杆塔", "杆塔为什么", "为什么危险"]):
            state.missing_info.append("tower_id")
            return self._set_plan(state, "tower_diagnosis", ["tower_lookup"])

        if any(word in message for word in ["最高", "最危险", "高风险", "优先巡检", "top"]):
            return self._set_plan(state, "top_risks", ["top_risk_ranker", "risk_explainer", "rag_guideline_retriever"])

        if any(word in message for word in ["容量", "裕度", "载流", "DLR", "dlr", "余量"]):
            return self._set_plan(state, "capacity_watch", ["capacity_margin_checker", "rag_guideline_retriever"])

        if any(word in message for word in ["总体", "概览", "今天", "当前", "风险", "汇总", "情况"]):
            return self._set_plan(state, "risk_summary", ["risk_summary", "top_risk_ranker"])

        return self._set_unsupported(state, "unknown_question", ["llm_planner", "domain_tool_selector"])

    def _set_plan(self, state: OperatorAgentState, intent: str, tools: list[str]) -> OperatorAgentState:
        state.intent = intent
        state.plan = {
            "intent": intent,
            "target": {"tower_id": state.tower_id, "line_id": state.line_id},
            "time_range": "latest_available_window",
            "required_tools": tools,
            "missing_info": list(state.missing_info),
            "unsupported_tools": list(state.unsupported_tools),
            "need_human_confirmation": False,
        }
        return state

    def _set_unsupported(self, state: OperatorAgentState, intent: str, tools: list[str]) -> OperatorAgentState:
        state.intent = intent
        state.unsupported_tools.extend(tools)
        return self._set_plan(state, intent, tools)

    def clarify(self, state: OperatorAgentState) -> OperatorAgentState:
        state.used_tools.append("clarify")
        questions = {
            "tower_id": "请提供杆塔编号，例如 L02_T034，这样我才能做单杆塔诊断。",
            "line_id": "请提供线路编号，例如 L00，这样我才能做线路风险汇总。",
            "time_range": "请提供时间范围，例如当前窗口、未来 24 小时或某一天。",
        }
        prompts = [questions.get(item, f"请补充 {item}。") for item in state.missing_info]
        state.answer = "\n".join(prompts)
        state.suggested_questions = ["L02_T034 为什么危险？", "L00 线路风险如何？", "当前总体风险怎么样？"]
        state.guardrail_flags.append("clarification_required")
        return state

    def unsupported_capability(self, state: OperatorAgentState) -> OperatorAgentState:
        state.used_tools.append("unsupported_capability")
        tools = "、".join(state.unsupported_tools or ["对应业务工具"])
        state.answer = (
            "这个问题超出了当前本地试用版能力，不能直接编造答案。\n"
            f"需要接入的能力/工具：{tools}。\n"
            "当前我可以基于已有预测结果回答总体风险、最高风险杆塔、单杆塔诊断、线路汇总、容量裕度和运维规程建议。"
        )
        state.suggested_questions = list(SUGGESTED_QUESTIONS)
        state.guardrail_flags.append("unsupported_capability")
        return state

    def risk_summary(self, state: OperatorAgentState) -> OperatorAgentState:
        state.used_tools.extend(["risk_summary", "top_risk_ranker"])
        df = state.predictions
        peak = _peak_by_tower(df)
        high = int((df["pred_risk_level"] >= 2).sum())
        severe_towers = int((peak["pred_risk_level"] >= 3).sum())
        max_row = peak.iloc[0]
        state.answer = (
            f"当前预测窗口共覆盖 {df['tower_id'].nunique()} 个杆塔、{len(df)} 条时序预测记录。"
            f"较高及以上风险记录 {high} 条，严重风险杆塔 {severe_towers} 个。"
            f"最高风险点是 {max_row['tower_id']}，风险等级 {int(max_row['pred_risk_level'])}"
            f"（{_risk_label(int(max_row['pred_risk_level']))}），风险分数 {float(max_row['pred_risk_score']):.1f}，"
            f"峰值时间 {max_row['time']}。建议先查看最高风险杆塔和容量裕度不足点。"
        )
        state.evidence = {
            "tower_count": int(df["tower_id"].nunique()),
            "prediction_records": int(len(df)),
            "high_risk_records": high,
            "severe_risk_towers": severe_towers,
            "top_tower_id": str(max_row["tower_id"]),
            "top_risk_score": float(max_row["pred_risk_score"]),
        }
        state.suggested_questions = ["最高风险杆塔有哪些？", f"{max_row['tower_id']} 为什么危险？", "哪些杆塔容量裕度不足？"]
        return state

    def top_risk_ranker(self, state: OperatorAgentState) -> OperatorAgentState:
        state.used_tools.extend(["top_risk_ranker", "risk_explainer", "action_recommender"])
        rows = _peak_by_tower(state.predictions).head(5)
        lines = ["当前最高风险杆塔如下："]
        evidence_rows = []
        for idx, row in enumerate(rows.itertuples(index=False), start=1):
            lines.append(
                f"{idx}. {row.tower_id}：等级 {int(row.pred_risk_level)}（{_risk_label(int(row.pred_risk_level))}），"
                f"分数 {float(row.pred_risk_score):.1f}，时间 {row.time}，建议：{row.recommended_action}"
            )
            evidence_rows.append(
                {
                    "tower_id": str(row.tower_id),
                    "risk_level": int(row.pred_risk_level),
                    "risk_score": float(row.pred_risk_score),
                    "peak_time": str(row.time),
                }
            )
        state.answer = "\n".join(lines)
        state.evidence = {"top_risks": evidence_rows}
        state.suggested_questions = [f"{str(rows.iloc[0]['tower_id'])} 为什么危险？", "哪些杆塔容量裕度不足？"]
        return state

    def tower_diagnosis(self, state: OperatorAgentState) -> OperatorAgentState:
        state.used_tools.extend(["tower_lookup", "risk_explainer", "action_recommender"])
        tower_id = state.tower_id or ""
        tower = state.predictions[state.predictions["tower_id"].astype(str).str.upper() == tower_id].sort_values("time")
        if tower.empty:
            state.answer = f"没有找到杆塔 {tower_id}。你可以先问“最高风险杆塔有哪些？”获取可用杆塔编号。"
            state.suggested_questions = ["最高风险杆塔有哪些？"]
            state.guardrail_flags.append("tower_id_not_found")
            return state
        peak = tower.sort_values("pred_risk_score", ascending=False).iloc[0]
        state.answer = (
            f"{tower_id} 的峰值风险出现在 {peak['time']}，风险等级 {int(peak['pred_risk_level'])}"
            f"（{_risk_label(int(peak['pred_risk_level']))}），风险分数 {float(peak['pred_risk_score']):.1f}。\n"
            f"主要原因：{peak['agent_explanation']}。\n"
            f"容量裕度：{float(peak.get('dlr_margin_pct', 0.0)):.1f}%。\n"
            f"建议处置：{peak['recommended_action']}"
        )
        state.evidence = {
            "tower_id": tower_id,
            "peak_time": str(peak["time"]),
            "risk_level": int(peak["pred_risk_level"]),
            "risk_score": float(peak["pred_risk_score"]),
            "temperature_c": float(peak["temperature_c"]),
            "relative_humidity": float(peak["relative_humidity"]),
            "wind_speed_ms": float(peak["wind_speed_ms"]),
            "precip_mm": float(peak["precip_mm"]),
            "dlr_margin_pct": float(peak.get("dlr_margin_pct", 0.0)),
        }
        state.suggested_questions = ["这条线路整体风险如何？", "哪些杆塔容量裕度不足？"]
        return state

    def line_diagnosis(self, state: OperatorAgentState) -> OperatorAgentState:
        state.used_tools.extend(["line_risk_aggregator", "risk_explainer"])
        line_id = state.line_id or ""
        line = state.predictions[state.predictions["line_id"].astype(str).str.upper() == line_id]
        if line.empty:
            state.answer = f"没有找到线路 {line_id}。你可以问“最高风险杆塔有哪些？”查看当前数据覆盖范围。"
            state.suggested_questions = ["最高风险杆塔有哪些？"]
            state.guardrail_flags.append("line_id_not_found")
            return state
        peak = _peak_by_tower(line)
        high_towers = int((peak["pred_risk_level"] >= 2).sum())
        top = peak.head(3)
        details = "；".join(f"{r.tower_id} 分数 {float(r.pred_risk_score):.1f}" for r in top.itertuples(index=False))
        state.answer = (
            f"{line_id} 线路覆盖 {line['tower_id'].nunique()} 个杆塔，其中较高及以上风险杆塔 {high_towers} 个。"
            f"前三个风险点：{details}。建议优先巡检这些杆塔，并结合现场覆冰、导线负荷和微气象观测复核。"
        )
        state.evidence = {
            "line_id": line_id,
            "tower_count": int(line["tower_id"].nunique()),
            "high_risk_tower_count": high_towers,
            "top_towers": [
                {"tower_id": str(r.tower_id), "risk_score": float(r.pred_risk_score)}
                for r in top.itertuples(index=False)
            ],
        }
        state.suggested_questions = [f"{str(top.iloc[0]['tower_id'])} 为什么危险？", "当前总体风险怎么样？"]
        return state

    def capacity_watch(self, state: OperatorAgentState) -> OperatorAgentState:
        state.used_tools.extend(["capacity_margin_checker", "risk_explainer"])
        watch = _peak_by_tower(state.predictions).sort_values("dlr_margin_pct", ascending=True).head(5)
        lines = ["容量裕度最低的杆塔如下，建议优先关注导线热稳定和负荷转供空间："]
        evidence_rows = []
        for idx, row in enumerate(watch.itertuples(index=False), start=1):
            lines.append(
                f"{idx}. {row.tower_id}：DLR 裕度 {float(row.dlr_margin_pct):.1f}%，"
                f"风险等级 {int(row.pred_risk_level)}，风险分数 {float(row.pred_risk_score):.1f}。"
            )
            evidence_rows.append(
                {
                    "tower_id": str(row.tower_id),
                    "dlr_margin_pct": float(row.dlr_margin_pct),
                    "risk_level": int(row.pred_risk_level),
                    "risk_score": float(row.pred_risk_score),
                }
            )
        state.answer = "\n".join(lines)
        state.evidence = {"capacity_watch": evidence_rows}
        state.suggested_questions = [f"{str(watch.iloc[0]['tower_id'])} 为什么危险？", "最高风险杆塔有哪些？"]
        return state

    def briefing(self, state: OperatorAgentState) -> OperatorAgentState:
        state.used_tools.extend(["risk_summary", "top_risk_ranker", "capacity_margin_checker", "report_generator"])
        df = state.predictions
        peak = _peak_by_tower(df)
        top = peak.head(3)
        capacity = peak.sort_values("dlr_margin_pct", ascending=True).head(3)
        high = int((df["pred_risk_level"] >= 2).sum())
        state.answer = (
            "值班风险简报：\n"
            f"1. 当前窗口覆盖 {df['tower_id'].nunique()} 个杆塔、{len(df)} 条预测记录，较高及以上风险记录 {high} 条。\n"
            "2. 最高风险点："
            + "；".join(f"{r.tower_id} 分数 {float(r.pred_risk_score):.1f}" for r in top.itertuples(index=False))
            + "。\n"
            "3. 容量裕度关注点："
            + "；".join(f"{r.tower_id} 裕度 {float(r.dlr_margin_pct):.1f}%" for r in capacity.itertuples(index=False))
            + "。\n"
            "4. 建议：优先复核最高风险杆塔附近观测，安排重点巡检，并关注容量裕度偏低线路。"
        )
        state.evidence = {
            "high_risk_records": high,
            "top_towers": [{"tower_id": str(r.tower_id), "risk_score": float(r.pred_risk_score)} for r in top.itertuples(index=False)],
            "capacity_watch": [{"tower_id": str(r.tower_id), "dlr_margin_pct": float(r.dlr_margin_pct)} for r in capacity.itertuples(index=False)],
        }
        state.suggested_questions = ["最高风险杆塔有哪些？", "哪些杆塔容量裕度不足？"]
        return state

    def help(self, state: OperatorAgentState) -> OperatorAgentState:
        state.answer = HELP_TEXT
        return state

    def rag_guideline(self, state: OperatorAgentState) -> OperatorAgentState:
        state.used_tools.append("rag_guideline_retriever")
        intent_queries = {
            "risk_summary": "high icing risk operation patrol observation de-icing",
            "top_risks": "high icing risk tower patrol priority de-icing windward exposure",
            "tower_diagnosis": "high icing risk weather triggers terrain model score DLR margin",
            "line_diagnosis": "high icing risk critical spans patrol priority line operation",
            "capacity_watch": "dynamic line rating margin low current loading transfer capability",
            "briefing": "high icing risk dynamic line rating watch operation briefing patrol priority",
        }
        query = f"{intent_queries.get(state.intent, state.intent)} {state.evidence}"
        state.guidelines = self.guidelines.search(query, top_k=2)
        if state.guidelines:
            state.answer += "\n\n运维规程参考：\n" + "\n".join(f"- {item}" for item in state.guidelines)
        return state

    def guardrails(self, state: OperatorAgentState) -> OperatorAgentState:
        state.used_tools.append("guardrails")
        if state.intent not in {"help"} and not state.evidence and not state.missing_info and not state.unsupported_tools:
            state.guardrail_flags.append("missing_evidence")
            state.answer += "\n\n注意：当前回答缺少结构化证据，建议人工复核后再用于处置。"
        if any(keyword in state.message for keyword in ["立即断电", "跳闸", "停运", "切负荷"]):
            state.guardrail_flags.append("human_confirmation_required")
            state.answer += "\n\n高风险操作需要调度/运维负责人确认，Agent 仅提供辅助诊断建议。"
            state.plan["need_human_confirmation"] = True
        return state


def answer_operator_question(df: pd.DataFrame, message: str) -> dict[str, Any]:
    return OperatorAgentGraph().invoke(df, message)


def _peak_by_tower(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.sort_values("pred_risk_score", ascending=False)
        .groupby("tower_id", as_index=False)
        .head(1)
        .sort_values("pred_risk_score", ascending=False)
    )


def _risk_label(level: int) -> str:
    if level >= 3:
        return "严重风险"
    if level >= 2:
        return "较高风险"
    if level >= 1:
        return "关注风险"
    return "低风险"

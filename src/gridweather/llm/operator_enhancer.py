from __future__ import annotations

import json
from typing import Any

from gridweather.llm.base import LLMClient, LLMMessage


SYSTEM_PROMPT = """你是面向中国电网输电线路运维的气象风险辅助 Agent。
你只能基于给定的工具输出、结构化证据和规程片段组织答案，不得编造实时天气、SCADA、故障记录或调度指令。
回答必须保留：结论、关键证据、建议动作、不确定性/人工复核提醒。
涉及停运、跳闸、切负荷、派单等高风险动作时，必须强调需要人工确认。
语言要求：中文，简洁，适合值班/运维人员快速阅读。"""


def enhance_operator_response(response: dict[str, Any], llm: LLMClient | None) -> dict[str, Any]:
    """Use an optional LLM to rewrite deterministic tool output.

    The deterministic answer remains the source of truth. If the provider is not
    configured or the API call fails, the original response is returned with a
    guardrail flag instead of breaking the local demo workflow.
    """

    if llm is None:
        return response
    if response.get("missing_info"):
        return response

    payload = {
        "intent": response.get("intent"),
        "plan": response.get("plan", {}),
        "deterministic_answer": response.get("answer", ""),
        "used_tools": response.get("used_tools", []),
        "evidence": response.get("evidence", {}),
        "guidelines": response.get("guidelines", []),
        "guardrail_flags": response.get("guardrail_flags", []),
        "unsupported_tools": response.get("unsupported_tools", []),
    }
    messages = [
        LLMMessage(role="system", content=SYSTEM_PROMPT),
        LLMMessage(
            role="user",
            content=(
                "请将以下确定性 Agent 输出改写成更清晰的中文运维回答。"
                "不要增加未给出的事实；如果能力不支持，要明确说明需要接入的工具。\n\n"
                + json.dumps(payload, ensure_ascii=False, indent=2)
            ),
        ),
    ]
    try:
        completion = llm.chat(messages)
    except Exception as exc:  # pragma: no cover - external API failures are runtime-dependent.
        updated = dict(response)
        flags = list(updated.get("guardrail_flags", []))
        flags.append("llm_enhancement_failed")
        updated["guardrail_flags"] = flags
        updated["llm_error"] = repr(exc)
        return updated

    updated = dict(response)
    updated["deterministic_answer"] = response.get("answer", "")
    updated["answer"] = completion.content or response.get("answer", "")
    updated["llm_provider"] = completion.provider
    updated["llm_model"] = completion.model
    updated["used_tools"] = list(response.get("used_tools", [])) + ["llm_answer_enhancer"]
    return updated

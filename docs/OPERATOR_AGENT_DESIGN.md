# GridWeatherAgent Operator-Facing Design

This document defines the first user-facing design for GridWeatherAgent as an operations assistant for power plant and grid operation staff.

## Target Users

Primary users:

- Power plant operation staff
- Grid dispatch and inspection coordinators
- Transmission-line maintenance teams
- Weather-risk duty engineers

These users usually do not want raw CSV tables. They want fast answers to:

- Where is the risk?
- Why is it risky?
- What should I do first?
- Which line or tower needs priority inspection?
- Is the model result traceable?
- Is there capacity headroom pressure?

## Core User Needs

| Need | User question | Agent response |
|---|---|---|
| Situation awareness | What is the current overall risk? | Summarize total records, high-risk count, severe-risk towers, and the top risk point. |
| Priority ranking | Which towers have the highest risk? | Return top risky towers with score, level, time, and recommended action. |
| Tower diagnosis | Why is tower L02_T034 risky? | Explain peak time, risk score, weather triggers, DLR margin, and action. |
| Line-level diagnosis | What is the risk on line L00? | Aggregate line-level tower risk and highlight top towers. |
| Capacity watch | Which towers have insufficient capacity margin? | Rank towers by DLR margin and recommend capacity monitoring. |
| Traceability | What evidence supports this conclusion? | Return tool names, evidence fields, and graph trace. |

## Current Architecture

The current Agent is implemented as a LangGraph-style state graph:

```text
operator question
  -> planner
  -> clarify / unsupported_capability / routed tool node
      -> risk_summary
      -> top_risk_ranker
      -> tower_diagnosis
      -> line_diagnosis
      -> capacity_watch
      -> briefing
      -> help / fallback
  -> rag_guideline
  -> guardrails
  -> answer + plan + used_tools + evidence + guidelines + graph_trace
```

The runnable graph is implemented in:

```text
src/gridweather/agent/operator_graph.py
```

The local web/API wrapper is implemented in:

```text
scripts/service/local_demo_server.py
```

## Tool / Skill Design

Current local tools:

| Tool / Skill | Responsibility | Current status |
|---|---|---|
| `planner` | Parse free-form operator questions into structured plans. | Implemented with deterministic rules. |
| `clarify` | Ask follow-up questions when tower id, line id, or time range is missing. | Implemented. |
| `unsupported_capability` | Explain missing tools when a request cannot be handled. | Implemented. |
| `risk_summary` | Summarize overall risk. | Implemented. |
| `top_risk_ranker` | Rank high-risk towers. | Implemented. |
| `tower_lookup` | Query one tower by `tower_id`. | Implemented. |
| `line_risk_aggregator` | Aggregate one transmission line. | Implemented. |
| `capacity_margin_checker` | Check DLR/capacity margin pressure. | Implemented. |
| `briefing` | Generate a duty briefing from risk and capacity evidence. | Implemented. |
| `rag_guideline_retriever` | Retrieve operation guideline snippets. | Implemented with local hybrid retrieval. |
| `risk_explainer` | Explain weather/terrain/capacity triggers. | Implemented through rule explanations. |
| `action_recommender` | Generate operational recommendations. | Implemented through rule recommendations. |
| `guardrails` | Add evidence and human-confirmation warnings. | Implemented. |

Future tools:

| Tool / Skill | Why it matters |
|---|---|
| `weather_forecast_reader` | Use future weather forecast rather than only existing prediction artifacts. |
| `scada_load_reader` | Connect risk to actual load/current and operational constraints. |
| `maintenance_ticket_writer` | Convert diagnosis into inspection or maintenance tasks. |
| `human_confirmation_gate` | Require human approval for high-risk operational actions. |
| `rag_guideline_retriever` | Retrieve internal operation procedures and emergency plans. |
| `feedback_collector` | Let users mark answers as useful/wrong and improve evaluation. |

## Product Form

The current first usable interface is a local web app:

```bash
python scripts/service/local_demo_server.py
```

Open:

```text
http://127.0.0.1:8765/app
```

The app supports Chinese operator questions and returns:

- Intent
- Structured plan
- Answer
- Used tools
- Retrieved guideline snippets
- Graph trace
- Key evidence for tower-level diagnosis
- Suggested follow-up questions

## Current Boundary

Current version:

- Uses existing prediction artifacts.
- Uses deterministic routing and rule-based explanation.
- Uses a LangGraph-style state object and graph nodes.
- Supports Planner, Clarify, Unsupported Capability, RAG Guideline, and Guardrail nodes.
- Does not call an external LLM API.
- Does not connect to live SCADA, real-time forecast, or internal dispatch systems.

This is intentional for the first testable version: it proves the operator workflow before adding a full LLM Planner.

## Next Upgrade

After user testing, the next version should add:

1. LLM Planner for flexible intent understanding.
2. RAG over operation manuals and emergency guidelines.
3. Real-time forecast and SCADA connectors.
4. Feedback buttons in the UI.
5. Agent evaluation logs for task success, tool-call accuracy, hallucination, recovery, and traceability.
6. Persistent checkpoint/resume support through LangGraph or an equivalent state store.

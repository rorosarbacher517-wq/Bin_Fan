# LangGraph-Style Operator Agent

GridWeatherAgent now separates the operator-facing Agent logic into a state-graph module:

- `src/gridweather/agent/operator_graph.py`
- `scripts/service/local_demo_server.py`

The current environment does not require the external `langgraph` dependency. Instead, the project implements a dependency-light LangGraph-style graph so the demo remains runnable on a clean machine.

## Current Architecture

```text
User question
  -> planner
      -> structured plan
      -> missing_info
      -> unsupported_tools
  -> clarify / unsupported_capability / routed tool node
      -> risk_summary
      -> top_risk_ranker
      -> tower_diagnosis
      -> line_diagnosis
      -> capacity_watch
      -> briefing
      -> help
  -> rag_guideline
  -> guardrails
  -> response with answer + plan + used_tools + evidence + guidelines + graph_trace
```

## Why This Fits Power-Grid Operations

Power-grid operation is a high-risk workflow. The first version should be:

- deterministic,
- evidence-grounded,
- auditable,
- easy to test,
- easy to recover from failure.

Therefore, this version uses a state-graph workflow rather than an open-ended autonomous multi-Agent system.

## State Object

`OperatorAgentState` carries:

- user message,
- prediction table,
- intent,
- tower id / line id,
- answer,
- used tools,
- evidence,
- suggested questions,
- guardrail flags,
- graph trace.

This mirrors the state object normally passed between LangGraph nodes.

## Node Design

| Node | Role |
|---|---|
| `planner` | Parse operator question into a structured task plan. |
| `clarify` | Ask for missing tower id, line id, or time range. |
| `unsupported_capability` | Explain missing tools instead of hallucinating. |
| `risk_summary` | Summarize overall risk. |
| `top_risk_ranker` | Rank highest-risk towers. |
| `tower_diagnosis` | Explain one tower's peak risk. |
| `line_diagnosis` | Aggregate risk by line. |
| `capacity_watch` | Find low DLR/capacity margin towers. |
| `briefing` | Generate a duty briefing from risk and capacity evidence. |
| `rag_guideline` | Retrieve operation guideline snippets for response grounding. |
| `guardrails` | Add evidence/safety checks and human-confirmation warnings. |

## Migration to Real LangGraph

When `langgraph` is installed, the current node functions can be attached to a real `StateGraph`:

```python
from langgraph.graph import END, StateGraph

workflow = StateGraph(OperatorAgentState)
workflow.add_node("planner", graph.planner)
workflow.add_node("clarify", graph.clarify)
workflow.add_node("unsupported_capability", graph.unsupported_capability)
workflow.add_node("risk_summary", graph.risk_summary)
workflow.add_node("top_risk_ranker", graph.top_risk_ranker)
workflow.add_node("tower_diagnosis", graph.tower_diagnosis)
workflow.add_node("line_diagnosis", graph.line_diagnosis)
workflow.add_node("capacity_watch", graph.capacity_watch)
workflow.add_node("briefing", graph.briefing)
workflow.add_node("rag_guideline", graph.rag_guideline)
workflow.add_node("guardrails", graph.guardrails)

workflow.set_entry_point("planner")
workflow.add_conditional_edges("planner", route_after_planner)
workflow.add_edge("risk_summary", "rag_guideline")
workflow.add_edge("top_risk_ranker", "rag_guideline")
workflow.add_edge("tower_diagnosis", "rag_guideline")
workflow.add_edge("line_diagnosis", "rag_guideline")
workflow.add_edge("capacity_watch", "rag_guideline")
workflow.add_edge("briefing", "rag_guideline")
workflow.add_edge("rag_guideline", "guardrails")
workflow.add_edge("clarify", "guardrails")
workflow.add_edge("unsupported_capability", "guardrails")
workflow.add_edge("guardrails", END)
app = workflow.compile()
```

## Next Upgrade

The next production version should add:

1. LLM Planner node for flexible natural-language understanding.
2. RAG retrieval node for operation guidelines and emergency plans.
3. Forecast data connector node.
4. SCADA/load connector node.
5. Human confirmation node for high-risk operation suggestions.
6. Persistent checkpoint store for resume/replay.

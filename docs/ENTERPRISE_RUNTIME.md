# Enterprise Runtime Layer

This document records what has been implemented now and what is intentionally kept as a connector or adapter interface for future enterprise integration.

## Current Scope

The v0 Agent is no longer only a static Q&A demo. It now has a lightweight enterprise runtime around the operator Agent graph:

1. **Task identity and checkpoint**: every `/api/chat` request receives a `task_id`, task status, graph trace, used tools, evidence, guideline snippets, and guardrail flags.
2. **Evidence packet**: each answer writes a replayable evidence JSON file under `artifacts/runtime/tasks/`.
3. **Event logging**: runtime events are appended to `artifacts/runtime/events.jsonl`.
4. **Tool registry**: each tool has a name, description, input schema, output schema, permission tags, timeout, side-effect flag, and implementation status.
5. **Mock enterprise connectors**: weather forecast, SCADA load, asset registry, and ticket writing have typed adapter interfaces and mock implementations.
6. **Web test entry**: `/app` remains the user-facing chat surface; `/api/chat` now returns runtime metadata in addition to the answer.
7. **Task replay API**: `/api/tasks?task_id=<task_id>` returns the saved task record and evidence packet.

## Implemented Tools

| Tool | Current status | Business use |
|---|---|---|
| `risk_summary` | implemented | Summarize current tower-level risk state |
| `top_risk_ranker` | implemented | Rank highest-risk towers |
| `tower_lookup` | implemented | Diagnose one tower |
| `line_risk_aggregator` | implemented | Aggregate risk by line |
| `capacity_margin_checker` | implemented | Identify low DLR/capacity-margin towers |
| `rag_guideline_retriever` | implemented | Retrieve operation guideline snippets |
| `weather_forecast_reader` | mock | Future weather forecast adapter |
| `scada_load_reader` | mock | Real-time load/current adapter |
| `maintenance_ticket_writer` | mock | Work-order/ticket adapter |

## Connector Interfaces

The current code defines adapter contracts in `src/gridweather/runtime/connectors.py`:

- `WeatherForecastConnector`: future NWP or weather API access.
- `ScadaLoadConnector`: real-time line load/current from SCADA/EMS.
- `AssetConnector`: line, tower, voltage, ownership, and criticality metadata.
- `MaintenanceTicketConnector`: inspection or maintenance ticket creation.

These interfaces let the Agent design stay stable while the real enterprise systems are connected later.

## Runtime Artifacts

After calling `/api/chat`, the runtime writes:

```text
artifacts/runtime/events.jsonl
artifacts/runtime/tasks/<task_id>.json
artifacts/runtime/tasks/<task_id>.evidence.json
```

The evidence packet is designed for traceability: it records the intent, plan, graph nodes, tools, risk evidence, retrieved guidelines, missing information, unsupported tools, mock connector context, and guardrail flags.

## How to Test

Start the local server:

```powershell
python scripts/service/local_demo_server.py --port 8770
```

Open:

```text
http://127.0.0.1:8770/app
```

Inspect tool registry and task records:

```text
http://127.0.0.1:8770/api/tools
http://127.0.0.1:8770/api/tasks?task_id=<task_id>
```

Useful test questions:

```text
当前总体风险怎么样？
L00 线路风险如何？
L02_T034 为什么危险？
未来24小时 L00 哪些线路最危险？
如果 L00 负荷增加20%，风险会怎样？
```

The future-risk and load-increase questions are expected to trigger unsupported capability handling plus mock connector payloads. This is intentional: the Agent is showing what production connector is missing instead of hallucinating a real enterprise data source.

## Production Replacement Plan

To turn the mock adapters into production connectors:

1. Replace `MockWeatherForecastConnector` with NWP/weather API access and forecast version metadata.
2. Replace `MockScadaLoadConnector` with read-only SCADA/EMS access, permission checks, timeout, and data freshness checks.
3. Replace `MockAssetConnector` with GIS/equipment registry APIs.
4. Replace `MockMaintenanceTicketConnector` with a human-confirmed work-order API.
5. Add per-tool auth, audit logs, rate limits, retry policy, and circuit breaker behavior.
6. Add regression evaluation for task success, tool-call accuracy, recovery rate, hallucination rate, cost, latency, and traceability.

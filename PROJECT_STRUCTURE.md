# GridWeatherAgent Project Structure

This document summarizes the current repository layout and the role of each major file or directory. It is intended as a quick orientation guide for development, deployment, documentation, and future multimodal Agent expansion.

```text
GridWeatherAgent/
├── README.md                          # Project overview, quick start, interfaces, and usage notes
├── requirements.txt                   # Python dependency list
├── .gitignore                         # Git ignore rules
├── .gitattributes                     # Git file attribute configuration
├── .env.example                       # Example environment variables for optional LLM providers
├── GITHUB_SYNC.md                     # GitHub synchronization and update notes
├── docs_data_sources.md               # Data source notes and provenance summary
├── PROJECT_STRUCTURE.md               # This repository structure guide
│
├── configs/                           # Project configuration files
│   ├── project.yaml                   # Main project config: data, model, runtime, and LLM provider settings
│   ├── project_smoke.yaml             # Lightweight smoke-test configuration
│   ├── regions_china.yaml             # China-region and grid-adaptation configuration
│   └── harness_rules.json             # Agent Harness validation, safety, and runtime rules
│
├── src/
│   └── gridweather/                   # Main Python package
│       ├── __init__.py
│       ├── config.py                  # Configuration loading and project parameter handling
│       │
│       ├── service/
│       │   └── api.py                 # API service entry points and interface wrappers
│       │
│       ├── agent/                     # Operator-facing Agent logic
│       │   ├── operator_graph.py      # Operator Agent state graph and Q&A workflow
│       │   ├── toolchain.py           # Agent tool orchestration
│       │   ├── report.py              # Risk report generation
│       │   ├── explain.py             # Risk explanation and action recommendation generation
│       │   ├── memory.py              # Agent memory and context handling
│       │   └── guidelines/
│       │       └── icing_ops_guidelines.md # Icing/weather-risk operation guideline knowledge
│       │
│       ├── llm/                       # Optional LLM provider layer
│       │   ├── __init__.py            # LLM module exports
│       │   ├── base.py                # Common LLM client, message, and response abstractions
│       │   ├── openai_compatible.py   # OpenAI-compatible HTTP API client wrapper
│       │   ├── router.py              # Provider routing for DeepSeek, Zhipu, Qwen, OpenAI, etc.
│       │   └── operator_enhancer.py   # LLM enhancement for operator-facing answers
│       │
│       ├── runtime/                   # Enterprise Agent Runtime
│       │   ├── enterprise_runtime.py  # Main enterprise runtime entry point
│       │   ├── task_state.py          # Task IDs, task state, and evidence packet management
│       │   ├── tool_registry.py       # Tool registry, schemas, and permission metadata
│       │   ├── validation.py          # Output validation, evidence checks, and safety checks
│       │   ├── recovery.py            # Clarification, connector-required, and human-review recovery strategies
│       │   ├── observability.py       # Logs, traces, and runtime observability
│       │   ├── feedback.py            # User feedback capture and evaluation-sample accumulation
│       │   ├── connectors.py          # External-system and mock connector integration
│       │   └── rules.py               # Runtime rule definitions
│       │
│       ├── features/                  # Weather, grid, and physics feature engineering
│       │   ├── build_dataset.py       # Training and prediction dataset construction
│       │   ├── dlr.py                 # Dynamic Line Rating and capacity-margin features
│       │   ├── ieee738.py             # IEEE 738 conductor thermal-balance and ampacity calculations
│       │   └── physics_labels.py      # Physics-informed labels and risk labels
│       │
│       ├── models/                    # Spatiotemporal forecasting models
│       │   ├── train.py               # Model training entry point
│       │   ├── predict.py             # Model prediction entry point
│       │   ├── model_zoo.py           # Model registry and model selection
│       │   ├── feature_sets.py        # Feature-set definitions
│       │   ├── temporal_graph.py      # Temporal graph model implementation
│       │   ├── tf_temporal_graph.py   # TensorFlow temporal graph model implementation
│       │   └── patchtst_lite.py       # Lightweight PatchTST-style time-series model
│       │
│       ├── retrieval/                 # RAG and knowledge retrieval
│       │   ├── bm25.py                # BM25 retrieval
│       │   ├── chunking.py            # Document chunking utilities
│       │   └── hybrid.py              # Hybrid retrieval pipeline
│       │
│       └── infra/                     # Engineering infrastructure utilities
│           ├── cache.py               # Cache utilities
│           ├── circuit_breaker.py     # Circuit breaker implementation
│           ├── rate_limit.py          # Rate limiting
│           ├── resilience.py          # Retry and fault-tolerance helpers
│           └── singleflight.py        # Request coalescing to avoid duplicate work
│
├── scripts/                           # Data, model, evaluation, and service scripts
│   ├── run_demo_pipeline.py           # Demo data pipeline
│   ├── run_real_era5_pipeline.py      # Real ERA5 weather-data pipeline
│   ├── prepare_era5_weather.py        # ERA5 weather data preprocessing
│   ├── download_era5_land.py          # ERA5-Land download script
│   ├── download_era5_land_regions.py  # Multi-region ERA5-Land download script
│   ├── build_multiregion_dataset.py   # Multi-region dataset construction
│   ├── export_gee_static_features.py  # Google Earth Engine static feature export
│   ├── gee_export_static_features.js  # GEE JavaScript export helper
│   │
│   ├── service/
│   │   ├── local_demo_server.py       # Local web/API demo service with Chinese/English UI toggle
│   │   └── scheduled_refresh.py       # Scheduled refresh and background update jobs
│   │
│   ├── experiments/                   # Model experiment scripts
│   │   ├── train_patchtst_lite.py     # PatchTST-lite experiment training
│   │   ├── train_temporal_graphsage.py # Temporal GraphSAGE training
│   │   ├── train_tf_temporal_graphsage.py # TensorFlow Temporal GraphSAGE training
│   │   ├── train_tf_temporal_graphsage_multiregion.py # Multi-region TensorFlow graph training
│   │   ├── graph_smooth_predictions.py # Graph-based prediction smoothing
│   │   ├── permutation_importance.py   # Feature importance analysis
│   │   └── run_ablation.py             # Ablation experiments
│   │
│   ├── agent_eval/
│   │   └── evaluate_agent_workflow.py # Agent workflow evaluation
│   │
│   ├── retrieval_eval/
│   │   └── evaluate_chunking.py       # Retrieval chunking evaluation
│   │
│   ├── load_test/
│   │   └── simulate_api_load.py       # API load-test simulation
│   │
│   └── doc_build/
│       └── build_interview_manual.py  # Documentation/manual generation helper
│
├── docs/                              # Architecture, design, and implementation documents
│   ├── OPERATOR_AGENT_DESIGN.md       # Multimodal research and reporting Agent design
│   ├── LLM_PROVIDER_SETUP.md          # DeepSeek, Zhipu, Qwen, and OpenAI provider setup guide
│   ├── ENTERPRISE_RUNTIME.md          # Enterprise runtime documentation
│   ├── ENTERPRISE_AGENT_ARCHITECTURE_MAPPING.md # Enterprise Agent architecture mapping
│   ├── TECHNICAL_IMPLEMENTATION_GUIDE.md # Technical implementation guide
│   ├── LANGGRAPH_MIGRATION.md         # LangGraph migration plan
│   ├── AGENT_EVAL.md                  # Agent evaluation plan
│   └── industry_need_research.md      # Industry need and market research notes
│
├── knowledge-base/                    # RAG knowledge base and research notes
│   ├── README.md
│   ├── 00_knowledge_framework/        # Knowledge map, usage rules, naming rules, and source index
│   ├── 01_theory/                     # Theory foundations
│   ├── 02_understanding/              # Core research questions and conceptual understanding
│   ├── 03_data_and_technology/        # ERA5, HLS, FLUXNET, and related data-technology notes
│   ├── 04_methods/                    # Method notes: validation, matching, aggregation, etc.
│   ├── 05_policy_and_regulation/      # Policy, regulation, and standards source tracking
│   ├── 06_applications/               # Application scenarios and use cases
│   ├── 07_projects_and_cases/         # Project cases and reusable experience
│   ├── 08_career_mapping/             # Capability matrix and career mapping notes
│   ├── papers/                        # Paper index and literature notes
│   ├── policies/                      # Policy document index
│   └── reports/                       # Research report index
│
├── tests/                             # Automated tests
│   ├── test_enterprise_runtime.py     # Enterprise Runtime tests
│   ├── test_temporal_graph.py         # Temporal graph model tests
│   ├── test_graph_smoothing.py        # Graph smoothing tests
│   ├── test_ieee738_features.py       # IEEE 738 feature tests
│   ├── test_dlr_features.py           # DLR feature tests
│   ├── test_physics_labels.py         # Physics label tests
│   ├── test_infra.py                  # Cache, limiter, breaker, and resilience tests
│   └── test_llm_router.py             # LLM provider routing tests
│
├── deploy/                            # Deployment configuration
│   ├── Dockerfile                     # Docker image definition
│   └── docker-compose.yml             # Local/server compose configuration
│
├── data/                              # Local raw and intermediate data directory
├── artifacts/                         # Model outputs, predictions, reports, logs, and evidence packets
└── GridWeather-Agent-source.zip       # Local source archive backup
```

## Main Workflows

```text
Data pipeline:
ERA5 / static grid data
  -> scripts/prepare_era5_weather.py
  -> src/gridweather/features/
  -> artifacts/

Model pipeline:
features + labels
  -> src/gridweather/models/train.py
  -> src/gridweather/models/predict.py
  -> risk predictions

Agent pipeline:
risk predictions + knowledge base
  -> src/gridweather/runtime/enterprise_runtime.py
  -> src/gridweather/agent/operator_graph.py
  -> local/API response + evidence packet + report

Local demo:
scripts/service/local_demo_server.py
  -> http://127.0.0.1:8765/app
  -> /api/chat, /api/towers, /api/tools, /api/tasks, /api/predict

Optional LLM enhancement:
GRIDWEATHER_LLM_ENABLED=1
  -> src/gridweather/llm/router.py
  -> DeepSeek / Zhipu / Qwen / OpenAI-compatible providers
```

## Notes

- `data/` and `artifacts/` are usually local runtime directories and may contain large files or generated outputs.
- `knowledge-base/` is designed to support future RAG, research, report generation, and domain-specific evidence retrieval.
- `src/gridweather/runtime/` and `src/gridweather/agent/` together form the enterprise-facing Agent layer.
- `src/gridweather/llm/` is optional. The system can run deterministically without an LLM, then add LLM enhancement when provider keys are configured.

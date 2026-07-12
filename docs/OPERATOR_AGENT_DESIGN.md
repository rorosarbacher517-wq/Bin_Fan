# GridWeatherAgent Product and Operator-Facing Design

This document defines the user-facing design for GridWeatherAgent. The project should remain anchored in its strongest differentiator: weather-to-grid resilience analysis for transmission corridors. Around that domain core, the product can grow into a multimodal research and report Agent that supports file understanding, structured planning, technical writing, presentation generation, and evidence-grounded operator assistance.

## Product Positioning

GridWeatherAgent is not intended to be a generic ChatGPT clone. Its target product identity is:

```text
A multimodal weather-grid research and operation Agent for power-system risk analysis, file understanding, evidence-grounded writing, and report generation.
```

The product should combine three layers:

1. **Grid-weather domain core**: tower-level risk prediction, DLR capacity margin, line-level diagnosis, risk explanations, and operation recommendations.
2. **General AI workbench**: question answering, document/image/PDF parsing, summarization, writing, PPT generation, and optional image generation.
3. **Agent workflow layer**: plan-first execution, tool routing, evidence packets, guardrails, task logs, and human confirmation for operational actions.

This positioning keeps the project credible as an engineering portfolio project: the current implementation proves a vertical risk workflow, while the proposed extensions show a practical path toward a broader AI assistant.

## Target Users

Primary users:

- Power plant operation staff
- Grid dispatch and inspection coordinators
- Transmission-line maintenance teams
- Weather-risk duty engineers
- Power-system researchers and graduate students
- Technical report and presentation authors working with weather, grid, and risk-analysis materials

These users usually do not want raw CSV tables. They want fast, traceable answers to:

- Where is the risk?
- Why is it risky?
- What should I do first?
- Which line or tower needs priority inspection?
- Is the model result traceable?
- Is there capacity headroom pressure?
- What does this PDF, image, table, or report say?
- Can this analysis be turned into a summary, report, or PPT?

## Core User Needs

| Need | User question | Agent response |
|---|---|---|
| Situation awareness | What is the current overall risk? | Summarize total records, high-risk count, severe-risk towers, and the top risk point. |
| Priority ranking | Which towers have the highest risk? | Return top risky towers with score, level, time, and recommended action. |
| Tower diagnosis | Why is tower L02_T034 risky? | Explain peak time, risk score, weather triggers, DLR margin, and action. |
| Line-level diagnosis | What is the risk on line L00? | Aggregate line-level tower risk and highlight top towers. |
| Capacity watch | Which towers have insufficient capacity margin? | Rank towers by DLR margin and recommend capacity monitoring. |
| Traceability | What evidence supports this conclusion? | Return tool names, evidence fields, and graph trace. |
| File understanding | Summarize this PDF/image/table. | Parse uploaded files, extract text/tables/figures, and produce a structured summary. |
| Research writing | Write a research brief about weather-grid risk. | Search or retrieve evidence, organize claims, cite sources, and draft a report. |
| PPT generation | Create a presentation from this analysis. | Build a slide outline, generate page content, and export a `.pptx` file. |
| Problem solving | Explain this technical question step by step. | Use LLM reasoning and domain tools when relevant; show steps and assumptions. |
| Plan-first tasks | Analyze this PDF and make a PPT. | Produce an execution plan first, wait for confirmation when needed, then run tools. |

## Current Implemented Scope

The current repository already implements a deterministic, local, Agent-ready workflow for the weather-grid domain.

Implemented capabilities:

- Synthetic demo pipeline for towers, weather, training data, model training, predictions, and HTML report generation.
- ERA5-Land/GEE-oriented real-data pipeline design.
- Physics-guided risk labeling and DLR-like capacity features.
- Tabular risk model and deep temporal-graph research path.
- Local web/API wrapper.
- LangGraph-style operator state graph.
- Chinese operator questions for risk summary, top-risk ranking, tower diagnosis, line diagnosis, capacity watch, and duty briefing.
- Evidence, graph trace, guideline retrieval, and guardrail flags.

Not implemented yet:

- General LLM chat and open-ended problem solving.
- File upload and parsing for PDF, Word, PowerPoint, Excel, image, or audio files.
- OCR and image understanding.
- PPT generation.
- Image generation.
- Web research and citation-backed writing.
- Voice transcription, music generation, video generation, or podcast generation.
- Live SCADA, real-time forecast, ticketing, or dispatch-system integration.

The current boundary is important: the project can answer domain questions from existing prediction artifacts, but it should not claim to be a finished general multimodal assistant.

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

## Target Architecture

The recommended next architecture keeps the current deterministic operator graph as a trusted domain sub-agent and adds a higher-level task router.

```text
user input + uploaded files
  -> session manager
  -> mode selector
      -> normal mode
      -> plan mode
  -> task router / LLM planner
      -> grid-weather operator tools
      -> file parsing tools
      -> research and retrieval tools
      -> writing tools
      -> PPT/report generation tools
      -> image generation tools
  -> evidence manager
  -> guardrails and human confirmation
  -> final answer + artifacts + trace
```

### Modes

| Mode | Purpose | Behavior |
|---|---|---|
| `normal` | Simple chat, summary, explanation, or one-step domain question. | Answer directly and cite available evidence. |
| `plan` | Multi-step tasks such as file analysis, research, report writing, or PPT generation. | Generate a plan first, ask for confirmation when appropriate, then execute steps. |

Plan mode should be used when a request involves multiple tools, multiple files, external retrieval, artifact generation, or irreversible operational actions.

Example plan-mode request:

```text
User: Analyze this PDF and generate a 12-slide presentation.

Agent plan:
1. Parse the PDF text, tables, and figures.
2. Identify the paper's objective, method, data, results, and limitations.
3. Generate a Chinese structured summary.
4. Select slide-worthy claims and figures.
5. Build a 12-slide PPTX with speaker notes.
6. Return the PPTX and a Markdown summary.

Ask for confirmation before execution if the task is expensive, uses external APIs, or produces long artifacts.
```

## Tool / Skill Design

### Implemented Local Tools

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

### Recommended New Tools

| Tool / Skill | Responsibility | Priority |
|---|---|---:|
| `llm_planner` | Route open-ended user requests to one or more tools. | P0 |
| `plan_mode_manager` | Create, confirm, execute, and resume multi-step plans. | P0 |
| `file_upload_manager` | Store uploaded files, assign file IDs, and track parsed outputs. | P0 |
| `pdf_parser` | Extract text, tables, page images, metadata, and section structure from PDFs. | P0 |
| `image_ocr_reader` | Read screenshots, scanned documents, charts, and handwritten content when possible. | P0 |
| `document_parser` | Parse `.docx`, `.pptx`, `.xlsx`, `.csv`, `.txt`, and Markdown files. | P1 |
| `summarizer` | Produce short, structured, and domain-specific summaries from parsed content. | P0 |
| `qa_solver` | Answer general and technical questions with step-by-step reasoning. | P1 |
| `research_agent` | Search, retrieve, compare, and synthesize evidence for deeper research. | P1 |
| `citation_manager` | Track sources, URLs, document anchors, and citation metadata. | P1 |
| `writing_agent` | Draft reports, abstracts, research briefs, and operation summaries. | P1 |
| `ppt_generator` | Generate `.pptx` decks from outlines, documents, and analysis results. | P1 |
| `image_generator` | Generate illustrative images from prompts where appropriate. | P2 |
| `weather_forecast_reader` | Use future weather forecast rather than only existing prediction artifacts. | P1 |
| `scada_load_reader` | Connect risk to actual load/current and operational constraints. | P2 |
| `maintenance_ticket_writer` | Convert diagnosis into inspection or maintenance tasks. | P2 |
| `human_confirmation_gate` | Require human approval for high-risk operational actions. | P0 |
| `feedback_collector` | Let users mark answers as useful/wrong and improve evaluation. | P1 |

## File Upload and Parsing Design

The upload system should treat each file as an evidence source, not just as raw input.

Supported target formats:

| Format | Parser behavior | Output |
|---|---|---|
| `.pdf` | Extract text, metadata, tables, page images, and OCR fallback for scanned pages. | Page-aware text blocks, table JSON/CSV, figure thumbnails, summary. |
| `.png`, `.jpg`, `.jpeg`, `.webp` | OCR and multimodal image description; detect charts, tables, screenshots, and equations. | Extracted text, visual summary, detected objects/tables/equations. |
| `.docx` | Extract headings, paragraphs, tables, images, and comments if available. | Structured document tree and summary. |
| `.pptx` | Extract slide text, images, notes, and layout hints. | Slide-by-slide summary and reusable outline. |
| `.xlsx`, `.csv` | Infer schema, preview rows, compute descriptive statistics, detect missing values. | Data profile, tables, charts, and analysis notes. |
| `.txt`, `.md` | Parse text and headings. | Structured text chunks and summary. |

Every parsed file should produce an evidence packet:

```json
{
  "file_id": "file_001",
  "filename": "example.pdf",
  "file_type": "pdf",
  "parser": "pdf_parser",
  "chunks": [],
  "tables": [],
  "figures": [],
  "summary": "...",
  "warnings": []
}
```

The Agent should cite `file_id`, page number, slide number, sheet name, or table name when answering questions based on uploaded files.

## Research and Writing Design

Research/writing should be evidence-grounded and traceable.

Recommended workflow:

```text
research question
  -> clarify scope and output type
  -> retrieve sources or parse uploaded files
  -> extract claims and evidence
  -> build outline
  -> draft content
  -> attach citations/evidence anchors
  -> self-check unsupported claims
  -> export Markdown / Word / PDF / PPT
```

Supported outputs:

- Short summary
- Structured research memo
- Literature-style comparison table
- Technical report
- Operation briefing
- Manuscript-style section draft
- PPT outline
- `.pptx` presentation

The writing layer should distinguish between:

- **Domain-grounded writing**: based on GridWeather risk outputs and evidence packets.
- **File-grounded writing**: based on uploaded PDFs, images, tables, and documents.
- **Web-grounded writing**: based on retrieved sources with citations.
- **Creative or illustrative writing**: clearly labeled as model-generated and not evidence-backed.

## PPT Generation Design

PPT generation should be a downstream artifact workflow, not just a text response.

Recommended PPT pipeline:

```text
input topic/files/analysis
  -> determine audience and slide count
  -> create slide outline
  -> select evidence and figures
  -> generate slide text
  -> create charts/images if needed
  -> build `.pptx`
  -> run layout checks
  -> return file + summary
```

Typical deck types:

- Grid weather risk operation briefing
- Research paper presentation
- Project demo presentation
- Model evaluation presentation
- Incident review presentation

## Image Generation Design

Image generation should be optional and scoped. It is useful for:

- Concept illustrations for presentations.
- Architecture diagrams when code-native diagrams are insufficient.
- Report cover images.
- Scenario illustrations for weather-grid risk communication.

It should not replace factual plots, maps, model outputs, satellite data, or evidence figures. Those should come from real data or deterministic visualization code.

## Product Form

The current first usable interface is a local web app:

```bash
python scripts/service/local_demo_server.py
```

Open:

```text
http://127.0.0.1:8765/app
```

The current app supports Chinese operator questions and returns:

- Intent
- Structured plan
- Answer
- Used tools
- Retrieved guideline snippets
- Graph trace
- Key evidence for tower-level diagnosis
- Suggested follow-up questions

Recommended UI upgrades:

- Left navigation for `Chat`, `Files`, `Research`, `Reports`, `Grid Risk`, and `Tasks`.
- Message composer with file upload, plan-mode toggle, and domain-tool shortcuts.
- Artifact panel for generated Markdown, PDF, Word, PPT, charts, and evidence packets.
- Task timeline showing plan steps, tool calls, status, and warnings.
- Evidence drawer showing source files, pages, tables, prediction rows, and model outputs.
- Feedback buttons for answer quality and evidence usefulness.

## Guardrails and Human Confirmation

The system should not present unsupported generated content as factual evidence.

Guardrail rules:

- For grid operation actions, always show evidence and uncertainty.
- For high-risk recommendations, require human confirmation before ticketing or dispatch-like actions.
- For file-based answers, cite source file anchors where possible.
- For web research, cite source URLs and retrieval dates.
- For image generation, label outputs as generated illustrations.
- For missing tools, return `unsupported_capability` instead of fabricating results.
- For unavailable live data, say that the answer is based on existing artifacts only.

## Evaluation Design

The existing Agent workflow evaluation should be kept and extended.

Current metrics:

- Task success rate
- Tool-call accuracy
- Average steps
- Recovery rate
- Hallucination rate
- Latency
- Human intervention rate
- Cost per task
- Traceability rate

New evaluation sets:

| Evaluation set | Example tasks | Metrics |
|---|---|---|
| Grid operation QA | Risk summary, tower diagnosis, capacity watch. | Accuracy, traceability, unsupported-claim rate. |
| File understanding | Parse PDF/image/table and summarize. | Extraction quality, citation accuracy, summary coverage. |
| Plan mode | Multi-step research and artifact tasks. | Plan validity, completion rate, recovery rate. |
| PPT generation | Generate slides from a report or PDF. | Slide completeness, layout quality, evidence coverage. |
| Research writing | Produce a cited memo from sources. | Citation correctness, claim support, structure quality. |
| Safety boundary | Ask for unsupported live SCADA/forecast actions. | Refusal/clarification correctness. |

## Phased Roadmap

### Phase 0: Current Baseline

Status: implemented.

- Deterministic operator graph.
- Local risk predictions and reports.
- Domain-specific Chinese Q&A.
- Evidence and graph trace.

### Phase 1: Plan Mode and File Understanding

Goal: make the system useful for uploaded PDFs, images, and reports.

Deliverables:

- `plan_mode_manager`
- `file_upload_manager`
- `pdf_parser`
- `image_ocr_reader`
- `summarizer`
- Evidence packets for uploaded files
- UI upload area and task timeline

### Phase 2: LLM Planner, Writing, and PPT

Goal: turn parsed evidence and grid-risk outputs into user-facing artifacts.

Deliverables:

- LLM planner and tool router
- Research/writing workflow
- PPT outline and `.pptx` generation
- Markdown/HTML/PDF report export
- Evaluation cases for plan mode and artifact quality

### Phase 3: Research and Domain Connectors

Goal: connect the assistant to external and domain-specific evidence.

Deliverables:

- Web/literature research connector
- Citation manager
- Forecast reader
- Optional SCADA/load adapter interface
- Expanded RAG over operation manuals and emergency plans

### Phase 4: Operationalization

Goal: prepare for realistic enterprise operation.

Deliverables:

- User/session permissions
- Persistent task storage
- Human confirmation gates
- Feedback collection
- Audit logs
- Monitoring dashboard
- Deployment documentation

## Recommended Next Upgrade

The next practical upgrade should be Phase 1, not a full general assistant all at once.

Recommended implementation order:

1. Add plan mode to the existing chat API and UI.
2. Add file upload and local file registry.
3. Implement PDF parsing and image OCR/vision parsing.
4. Add file-grounded summarization with source anchors.
5. Extend the planner so it can route between grid-risk questions and file-analysis questions.
6. Add evaluation cases for uploaded-file summarization and unsupported requests.

This path preserves the project's current credibility while moving it toward the requested multimodal assistant capabilities.

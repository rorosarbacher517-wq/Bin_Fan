# Domestic-First LLM Provider Setup

GridWeatherAgent can now run in two modes:

1. **Offline deterministic mode**: the default. No external LLM API is called, and the demo remains reproducible without network access.
2. **LLM-enhanced mode**: deterministic grid-weather tools still produce the source evidence, then an optional LLM rewrites the answer into a clearer Chinese operator-facing response.

The recommended production direction for China grid scenarios is domestic-first:

```text
Default text/planning: DeepSeek
Domestic multimodal fallback: Zhipu GLM or Qwen-VL
Optional overseas fallback: OpenAI
```

## Why Domestic-First

Power-grid operation scenarios in China need Chinese language quality, domestic network reliability, local compliance options, and the ability to deploy with providers commonly available in Chinese enterprise environments. The LLM should not replace the weather-risk model. It should route tools, explain evidence, summarize files, and generate reports.

## Environment Variables

Copy `.env.example` into your deployment environment and set the variables there. Do not commit real API keys.

### DeepSeek Default

```powershell
$env:GRIDWEATHER_LLM_ENABLED="1"
$env:GRIDWEATHER_LLM_PROVIDER="deepseek"
$env:GRIDWEATHER_LLM_MODEL="deepseek-chat"
$env:DEEPSEEK_API_KEY="<your-deepseek-key>"
```

Use `deepseek-chat` for ordinary operator answers and report drafting. Use a reasoning model only for expensive planning, complex code, or research workflows.

### Zhipu GLM

```powershell
$env:GRIDWEATHER_LLM_ENABLED="1"
$env:GRIDWEATHER_LLM_PROVIDER="zhipu"
$env:GRIDWEATHER_LLM_MODEL="glm-4-plus"
$env:ZHIPU_API_KEY="<your-zhipu-key>"
```

Zhipu is a good domestic fallback for Chinese enterprise deployment and future multimodal tasks.

### Qwen / DashScope Compatible Mode

```powershell
$env:GRIDWEATHER_LLM_ENABLED="1"
$env:GRIDWEATHER_LLM_PROVIDER="qwen"
$env:GRIDWEATHER_LLM_MODEL="qwen-plus"
$env:DASHSCOPE_API_KEY="<your-dashscope-key>"
```

Qwen is useful when the project is deployed in the Alibaba Cloud ecosystem.

### Optional OpenAI Fallback

```powershell
$env:GRIDWEATHER_LLM_ENABLED="1"
$env:GRIDWEATHER_LLM_PROVIDER="openai"
$env:GRIDWEATHER_LLM_MODEL="gpt-4.1-mini"
$env:OPENAI_API_KEY="<your-openai-key>"
```

OpenAI can be kept as an optional fallback for multimodal research/report workflows, but it is not required for the core grid-weather demo.

## Runtime Behavior

When LLM enhancement is enabled:

```text
operator question
  -> deterministic GridWeatherAgent tools
  -> structured evidence and guideline retrieval
  -> optional LLM answer enhancer
  -> answer + deterministic_answer + evidence + guardrails + LLM metadata
```

The deterministic answer remains available in the API response as `deterministic_answer`. The LLM-enhanced response includes:

- `llm_provider`
- `llm_model`
- `llm_answer_enhancer` in `used_tools`

If the LLM call fails, the runtime returns the original deterministic answer and adds:

```text
llm_enhancement_failed
```

to `guardrail_flags`.

## Guardrail Rules

The LLM enhancer must not invent weather, SCADA, failure, or dispatch information. It only rewrites evidence produced by deterministic tools.

Every operator-facing answer should preserve:

- conclusion
- key evidence
- operational recommendation
- uncertainty or manual-review reminder
- human confirmation requirement for high-risk actions

High-risk instructions such as switching, tripping, load shedding, dispatch orders, and ticket creation must remain human-confirmed.

## Next Implementation Steps

The current implementation adds the provider layer and answer enhancement. The next practical steps are:

1. Add an LLM planner that can route between grid-risk questions, file analysis, and report generation.
2. Add PDF/image parsers and pass extracted evidence into the LLM summarizer.
3. Add provider fallback logic: DeepSeek first, then Zhipu/Qwen if configured.
4. Add evaluation tasks for LLM-enhanced answers, including unsupported-request and hallucination checks.
5. Add future weather tools for GFS/CMA forecast ingestion so the LLM can answer future-risk questions through real tool evidence.

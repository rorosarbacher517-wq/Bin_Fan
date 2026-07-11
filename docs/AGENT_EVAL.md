# Agent Workflow Evaluation

This note defines the evaluation scope for GridWeatherAgent's Agent-ready workflow.

## What These Metrics Measure

The current evaluation measures a deterministic tool-using workflow:

1. Build a tower-level risk report from prediction artifacts.
2. Query high-risk tower evidence packets.
3. Recover gracefully from a missing tower id.
4. Check whether generated explanations and recommendations are supported by source columns and rules.
5. Check whether outputs can be traced back to prediction CSV files, evidence packet fields, and report artifacts.

It does not claim that the risk model's classification accuracy is an Agent task success rate.

## Run

Demo predictions:

```bash
python scripts/agent_eval/evaluate_agent_workflow.py
```

ERA5 real-weather predictions:

```bash
python scripts/agent_eval/evaluate_agent_workflow.py \
  --prediction-csv artifacts/predictions_real_era5/latest_predictions.csv \
  --output-dir artifacts/agent_eval_real_era5
```

Outputs:

- `artifacts/agent_eval/agent_eval_metrics.json`
- `artifacts/agent_eval/agent_eval_report.md`
- `artifacts/agent_eval_real_era5/agent_eval_metrics.json`
- `artifacts/agent_eval_real_era5/agent_eval_report.md`

## Metric Definitions

| Metric | Definition in this project |
|---|---|
| Task Success Rate | Completed workflow tasks / all evaluation tasks. |
| Tool Call Accuracy | Expected tool calls observed / expected tool calls. |
| Average Steps | Average number of registered tool calls per task. |
| Recovery Rate | Successful recovery tasks / injected failure tasks. |
| Hallucination Rate | Unsupported deterministic report claims / checked report claims. |
| Latency | Wall-clock execution time for the local workflow. |
| Human Intervention Rate | Tasks requiring manual repair / all tasks. |
| Cost per Task | LLM API cost is 0 for this deterministic evaluation; local runtime is reported. |
| Traceability Rate | Traceable output items / required traceability items. |

## Current Results

On the checked artifacts, the workflow-level metrics are high because the current system is a deterministic, local Agent-ready toolchain rather than an open-ended autonomous Agent benchmark.

Demo artifact result:

- Task Success Rate: 100.0%
- Tool Call Accuracy: 100.0%
- Recovery Rate: 100.0%
- Hallucination Rate: 0.0%
- Human Intervention Rate: 0.0%
- Traceability Rate: 100.0%

ERA5 real-weather artifact result:

- Task Success Rate: 100.0%
- Tool Call Accuracy: 100.0%
- Recovery Rate: 100.0%
- Hallucination Rate: 0.0%
- Human Intervention Rate: 0.0%
- Traceability Rate: 100.0%

These numbers should be presented as workflow reliability metrics, not as open-ended Agent intelligence metrics.

## Resume Wording

Recommended wording:

```text
构建 GridWeatherAgent 的小规模 Agent workflow 评测集，覆盖报告生成、杆塔证据查询和缺失参数恢复等场景；统计任务完成率、工具调用正确率、失败恢复率、幻觉率和结果可追溯率。当前评测面向确定性 Agent-ready 工具链，demo 与 ERA5 真实气象产物均实现 100% 任务完成率、100% 工具调用正确率、100% 失败恢复率和 0% 规则解释幻觉率；底层风险识别模型指标单独评估，demo Accuracy 94.1%、Macro-F1 93.5%，ERA5 实验 Accuracy 90.9%、Macro-F1 87.9%。
```

Shorter wording:

```text
补充 Agent workflow 评测集，覆盖报告生成、证据查询和异常恢复；在确定性工具链评测中实现 100% 任务完成率、100% 工具调用正确率、100% 失败恢复率和 0% 规则解释幻觉率，并将底层风险模型 Accuracy/Macro-F1 与 Agent 指标分开报告。
```

## Interview Explanation

If asked whether 94.1% is the Agent accuracy:

```text
不是。94.1% 是底层风险等级识别模型的分类 Accuracy，不是 Agent 指标。Agent 层我单独构建了 workflow eval，评估任务完成率、工具调用正确率、失败恢复率、幻觉率、耗时和结果可追溯率。当前项目是确定性 Agent-ready 工具链，所以 workflow 指标较高；如果扩展到开放式 LLM Planner，我会进一步加入更复杂的任务集、错误注入、工具误选场景和人工评审。
```

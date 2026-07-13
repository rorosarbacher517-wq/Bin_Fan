from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from gridweather.agent.explain import attach_explanations
from gridweather.runtime.enterprise_runtime import EnterpriseAgentRuntime


class GridWeatherDemoHandler(BaseHTTPRequestHandler):
    prediction_csv: Path
    report_html: Path
    _predictions: pd.DataFrame | None = None
    _runtime: EnterpriseAgentRuntime | None = None

    def log_message(self, format: str, *args) -> None:
        return

    @classmethod
    def predictions(cls) -> pd.DataFrame:
        if cls._predictions is None:
            df = pd.read_csv(cls.prediction_csv, parse_dates=["time"])
            cls._predictions = attach_explanations(df)
        return cls._predictions

    @classmethod
    def runtime(cls) -> EnterpriseAgentRuntime:
        if cls._runtime is None:
            cls._runtime = EnterpriseAgentRuntime(cls.predictions(), ROOT / "artifacts")
        return cls._runtime

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/app"}:
            self._send_html(build_app_html())
            return
        if parsed.path == "/report":
            self._send_html(self.report_html.read_text(encoding="utf-8"))
            return
        if parsed.path == "/api/towers":
            self._handle_towers()
            return
        if parsed.path == "/api/tools":
            self._send_json({"tools": [spec.__dict__ for spec in self.runtime().registry.list()]})
            return
        if parsed.path == "/api/tasks":
            params = parse_qs(parsed.query)
            self._handle_task(params.get("task_id", [""])[0])
            return
        if parsed.path == "/api/predict":
            params = parse_qs(parsed.query)
            self._handle_predict(params.get("tower_id", [""])[0])
            return
        self._send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/chat":
            self._send_json({"error": "not found"}, status=404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send_json({"error": "invalid json"}, status=400)
            return
        message = str(payload.get("message", "")).strip()
        language = str(payload.get("language", "zh")).lower()
        if language not in {"zh", "en"}:
            language = "zh"
        if not message:
            self._send_json({"error": "missing message"}, status=400)
            return
        response = self.runtime().ask(message)
        response["language"] = language
        self._send_json(response)

    def _handle_towers(self) -> None:
        df = self.predictions()
        peak = (
            df.sort_values("pred_risk_score", ascending=False)
            .groupby("tower_id", as_index=False)
            .head(1)
            .sort_values("pred_risk_score", ascending=False)
            .head(20)
        )
        towers = [
            {
                "tower_id": str(row["tower_id"]),
                "risk_level": int(row["pred_risk_level"]),
                "risk_score": float(row["pred_risk_score"]),
                "peak_time": str(row["time"]),
            }
            for _, row in peak.iterrows()
        ]
        self._send_json({"count": len(towers), "towers": towers})

    def _handle_predict(self, tower_id: str) -> None:
        if not tower_id:
            self._send_json({"error": "missing tower_id"}, status=400)
            return
        df = self.predictions()
        tower = df[df["tower_id"].astype(str) == tower_id].sort_values("time")
        if tower.empty:
            self._send_json({"error": "tower_id not found", "tower_id": tower_id}, status=404)
            return
        peak = tower.sort_values("pred_risk_score", ascending=False).iloc[0]
        self._send_json(
            {
                "tower_id": tower_id,
                "peak_time": str(peak["time"]),
                "risk_level": int(peak["pred_risk_level"]),
                "risk_score": float(peak["pred_risk_score"]),
                "dlr_margin_pct": float(peak.get("dlr_margin_pct", 0.0)),
                "explanation": str(peak["agent_explanation"]),
                "recommended_action": str(peak["recommended_action"]),
            }
        )

    def _handle_task(self, task_id: str) -> None:
        if not task_id:
            self._send_json({"error": "missing task_id"}, status=400)
            return
        try:
            task = self.runtime().tasks.load(task_id)
            evidence_path = self.runtime().tasks.evidence_path(task_id)
            payload = task.__dict__ | {"evidence_packet_path": str(evidence_path)}
            if evidence_path.exists():
                payload["evidence_packet"] = json.loads(evidence_path.read_text(encoding="utf-8"))
            self._send_json(payload)
        except FileNotFoundError:
            self._send_json({"error": "task_id not found", "task_id": task_id}, status=404)

    def _send_html(self, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def build_app_html() -> str:
    i18n_json = json.dumps(
        {
            "zh": {
                "title": "GridWeatherAgent 运维试用版",
                "aside": "面向电厂/电网运维人员的气象风险诊断 Agent。当前采用 LangGraph-style 状态图，并增加企业级运行时：任务 ID、工具注册、证据包、执行日志和 mock connector。",
                "topbar": "运维问答试用台",
                "report": "打开完整风险报告",
                "hello": "你好，我是 GridWeatherAgent。你可以问我：当前总体风险怎么样？最高风险杆塔有哪些？L02_T034 为什么危险？L00 线路风险如何？哪些杆塔容量裕度不足？也可以测试尚未真实接入的能力，例如未来 24 小时风险或负荷增加 20% 的影响。",
                "placeholder": "输入运维问题，例如：L02_T034 为什么危险？",
                "send": "发送",
                "intent": "意图",
                "tools": "使用工具",
                "trace": "图节点",
                "task": "任务ID",
                "mock": "已附 mock connector 结果",
                "failed": "请求失败：",
                "toolsList": [
                    "planner：意图识别与任务计划",
                    "risk_summary：总体风险概览",
                    "top_risk_ranker：最高风险排序",
                    "tower_lookup：单杆塔诊断",
                    "line_risk_aggregator：线路风险汇总",
                    "capacity_margin_checker：容量裕度检查",
                    "rag_guideline_retriever：运维规程检索",
                    "guardrails：证据与安全护栏"
                ],
                "suggestions": [
                    "当前总体风险怎么样？",
                    "最高风险杆塔有哪些？",
                    "L02_T034 为什么危险？",
                    "L00 线路风险如何？",
                    "哪些杆塔容量裕度不足？",
                    "帮我生成一份今天的值班简报"
                ]
            },
            "en": {
                "title": "GridWeatherAgent Operator Demo",
                "aside": "A weather-risk diagnostic Agent for power-grid operators. It uses a LangGraph-style state graph with task IDs, tool registry, evidence packets, event logs, and mock connectors.",
                "topbar": "Operator Q&A Console",
                "report": "Open Full Risk Report",
                "hello": "Hello, I am GridWeatherAgent. You can ask: What is the current overall risk? Which towers have the highest risk? Why is L02_T034 risky? What is the risk on line L00? Which towers have low DLR margin?",
                "placeholder": "Ask an operation question, e.g. Why is L02_T034 risky?",
                "send": "Send",
                "intent": "Intent",
                "tools": "Tools",
                "trace": "Graph trace",
                "task": "Task ID",
                "mock": "mock connector context attached",
                "failed": "Request failed: ",
                "toolsList": [
                    "planner: intent parsing and task planning",
                    "risk_summary: overall risk summary",
                    "top_risk_ranker: highest-risk tower ranking",
                    "tower_lookup: single-tower diagnosis",
                    "line_risk_aggregator: line-level risk aggregation",
                    "capacity_margin_checker: DLR margin watch",
                    "rag_guideline_retriever: operation guideline retrieval",
                    "guardrails: evidence and safety checks"
                ],
                "suggestions": [
                    "What is the current overall risk?",
                    "Which towers have the highest risk?",
                    "Why is L02_T034 risky?",
                    "What is the risk on line L00?",
                    "Which towers have low DLR margin?",
                    "Generate today's operation briefing."
                ]
            }
        },
        ensure_ascii=False,
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GridWeatherAgent</title>
<style>
body {{ margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; background: #f6f7f9; color: #172033; }}
.app {{ display: grid; grid-template-columns: 320px 1fr; min-height: 100vh; }}
aside {{ background: #101827; color: #e6edf7; padding: 24px; }}
aside h1 {{ font-size: 22px; margin: 0 0 10px; }}
aside p {{ color: #b8c4d6; line-height: 1.6; font-size: 14px; }}
.tool {{ border: 1px solid #31415c; border-radius: 8px; padding: 10px 12px; margin: 10px 0; font-size: 13px; background: #162238; }}
main {{ display: flex; flex-direction: column; min-width: 0; }}
.topbar {{ padding: 18px 24px; border-bottom: 1px solid #e1e5eb; background: white; display: flex; justify-content: space-between; gap: 16px; align-items: center; }}
.topbar strong {{ font-size: 18px; }}
.topbar a {{ color: #1d65d8; text-decoration: none; font-size: 14px; }}
.actions {{ display: flex; align-items: center; gap: 10px; }}
.lang-toggle {{ display: inline-flex; border: 1px solid #cfd7e3; border-radius: 8px; overflow: hidden; background: #fff; }}
.lang-toggle button {{ border: 0; background: transparent; padding: 7px 10px; cursor: pointer; color: #475569; }}
.lang-toggle button.active {{ background: #1769e0; color: white; }}
.chat {{ flex: 1; padding: 24px; overflow: auto; }}
.msg {{ max-width: 900px; border-radius: 8px; padding: 14px 16px; margin: 0 0 14px; line-height: 1.65; white-space: pre-wrap; }}
.user {{ background: #dbeafe; margin-left: auto; }}
.agent {{ background: white; border: 1px solid #e1e5eb; }}
.meta {{ margin-top: 10px; color: #64748b; font-size: 13px; }}
.composer {{ background: white; border-top: 1px solid #e1e5eb; padding: 16px 24px; }}
.chips {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }}
.chips button {{ border: 1px solid #cfd7e3; background: #fff; border-radius: 999px; padding: 7px 11px; cursor: pointer; }}
.inputrow {{ display: flex; gap: 10px; }}
input {{ flex: 1; border: 1px solid #cfd7e3; border-radius: 8px; padding: 12px 14px; font-size: 15px; }}
.send {{ border: 0; background: #1769e0; color: white; border-radius: 8px; padding: 0 20px; font-size: 15px; cursor: pointer; }}
@media (max-width: 800px) {{ .app {{ grid-template-columns: 1fr; }} aside {{ display: none; }} .topbar {{ align-items: flex-start; flex-direction: column; }} }}
</style>
</head>
<body>
<div class="app">
<aside>
<h1>GridWeatherAgent</h1>
<p id="asideText"></p>
<div id="toolList"></div>
</aside>
<main>
<div class="topbar">
<strong id="topbarTitle"></strong>
<div class="actions">
<div class="lang-toggle" aria-label="Language">
<button id="langZh" onclick="setLanguage('zh')">中文</button>
<button id="langEn" onclick="setLanguage('en')">EN</button>
</div>
<a id="reportLink" href="/report" target="_blank"></a>
</div>
</div>
<div id="chat" class="chat"></div>
<div class="composer">
<div class="chips" id="chips"></div>
<div class="inputrow">
<input id="input">
<button id="sendButton" class="send" onclick="sendMessage()"></button>
</div>
</div>
</main>
</div>
<script>
const I18N = {i18n_json};
let currentLanguage = localStorage.getItem("gridweather_language") || "zh";
function t(key) {{ return I18N[currentLanguage][key]; }}
function setLanguage(lang) {{
  currentLanguage = lang;
  localStorage.setItem("gridweather_language", lang);
  document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  document.title = t("title");
  document.getElementById("asideText").textContent = t("aside");
  document.getElementById("topbarTitle").textContent = t("topbar");
  document.getElementById("reportLink").textContent = t("report");
  document.getElementById("input").placeholder = t("placeholder");
  document.getElementById("sendButton").textContent = t("send");
  document.getElementById("langZh").classList.toggle("active", lang === "zh");
  document.getElementById("langEn").classList.toggle("active", lang === "en");
  renderTools();
  renderChips();
  if (!document.getElementById("chat").children.length) {{
    addMsg(t("hello"), "agent");
  }}
}}
function renderTools() {{
  const toolList = document.getElementById("toolList");
  toolList.innerHTML = "";
  for (const item of t("toolsList")) {{
    const div = document.createElement("div");
    div.className = "tool";
    div.textContent = item;
    toolList.appendChild(div);
  }}
}}
function renderChips() {{
  const chips = document.getElementById("chips");
  chips.innerHTML = "";
  for (const q of t("suggestions")) {{
    const btn = document.createElement("button");
    btn.textContent = q;
    btn.onclick = () => {{ document.getElementById("input").value = q; sendMessage(); }};
    chips.appendChild(btn);
  }}
}}
function addMsg(text, cls, meta) {{
  const div = document.createElement("div");
  div.className = "msg " + cls;
  div.textContent = text;
  if (meta) {{
    const m = document.createElement("div");
    m.className = "meta";
    m.textContent = meta;
    div.appendChild(m);
  }}
  document.getElementById("chat").appendChild(div);
  div.scrollIntoView({{behavior: "smooth", block: "end"}});
}}
function buildMeta(data) {{
  const parts = [];
  if (data.intent) parts.push(t("intent") + "：" + data.intent);
  if (data.used_tools) parts.push(t("tools") + "：" + data.used_tools.join(", "));
  if (data.graph_trace) parts.push(t("trace") + "：" + data.graph_trace.join(" -> "));
  if (data.task_id) parts.push(t("task") + "：" + data.task_id);
  if (data.mock_connector_context) parts.push(t("mock"));
  return parts.join("；");
}}
async function sendMessage() {{
  const input = document.getElementById("input");
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  addMsg(message, "user");
  try {{
    const res = await fetch("/api/chat", {{
      method: "POST",
      headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify({{message, language: currentLanguage}})
    }});
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "request failed");
    addMsg(data.answer, "agent", buildMeta(data));
  }} catch (err) {{
    addMsg(t("failed") + err.message, "agent");
  }}
}}
document.getElementById("input").addEventListener("keydown", e => {{
  if (e.key === "Enter") sendMessage();
}});
setLanguage(currentLanguage);
</script>
</body>
</html>"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a dependency-light local GridWeatherAgent demo server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--prediction-csv",
        type=Path,
        default=ROOT / "artifacts" / "predictions_real_era5" / "latest_predictions.csv",
    )
    parser.add_argument(
        "--report-html",
        type=Path,
        default=ROOT / "artifacts" / "reports_real_era5" / "gridweather_report.html",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.prediction_csv.exists():
        raise FileNotFoundError(f"Prediction CSV not found: {args.prediction_csv}")
    if not args.report_html.exists():
        raise FileNotFoundError(f"Report HTML not found: {args.report_html}")
    GridWeatherDemoHandler.prediction_csv = args.prediction_csv
    GridWeatherDemoHandler.report_html = args.report_html
    server = ThreadingHTTPServer((args.host, args.port), GridWeatherDemoHandler)
    print(f"GridWeatherAgent demo server: http://{args.host}:{args.port}")
    print(f"Chat app: http://{args.host}:{args.port}/app")
    print(f"Report: http://{args.host}:{args.port}/report")
    print(f"Towers API: http://{args.host}:{args.port}/api/towers")
    server.serve_forever()


if __name__ == "__main__":
    main()

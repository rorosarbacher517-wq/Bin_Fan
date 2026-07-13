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
                "docLang": "zh-CN",
                "pageTitle": "GridWeatherAgent \u8fd0\u884c\u63a7\u5236\u53f0",
                "aside": "\u9762\u5411\u7535\u7f51\u8fd0\u7ef4\u7684\u6c14\u8c61\u98ce\u9669 Agent\uff0c\u63d0\u4f9b\u8ba1\u5212\u3001\u5de5\u5177\u8c03\u7528\u3001\u8bc1\u636e\u5305\u3001\u6062\u590d\u5efa\u8bae\u548c\u53cd\u9988\u95ed\u73af\u3002",
                "cards": [
                    "\u8ba1\u5212\u5668\uff1a\u610f\u56fe\u8bc6\u522b\u4e0e\u4efb\u52a1\u8ba1\u5212",
                    "\u5de5\u5177\u6ce8\u518c\u8868\uff1a\u6a21\u5f0f\u3001\u6743\u9650\u4e0e\u53ef\u7528\u6027",
                    "\u9a8c\u8bc1\u5668\uff1a\u72b6\u6001\u56fe\u3001\u8bc1\u636e\u548c\u5b89\u5168\u62a4\u680f\u68c0\u67e5",
                    "\u6062\u590d\u7b56\u7565\uff1a\u6f84\u6e05\u95ee\u9898\u3001\u63a5\u53e3\u7f3a\u5931\u548c\u4eba\u5de5\u590d\u6838",
                    "\u5b66\u4e60\u95ed\u73af\uff1a\u628a\u53cd\u9988\u7d2f\u79ef\u4e3a\u8bc4\u6d4b\u6837\u672c"
                ],
                "console": "\u8fd0\u884c\u63a7\u5236\u53f0",
                "harness": "Harness JSON",
                "report": "\u98ce\u9669\u62a5\u544a",
                "hello": "\u8bf7\u8f93\u5165\u8fd0\u7ef4\u95ee\u9898\uff0c\u4f8b\u5982\uff1a\u5f53\u524d\u603b\u4f53\u98ce\u9669\u5982\u4f55\uff1f\u54ea\u4e9b\u6746\u5854\u98ce\u9669\u6700\u9ad8\uff1fL00 \u7ebf\u8def\u98ce\u9669\u600e\u6837\uff1f\u4e5f\u53ef\u4ee5\u8be2\u95ee\u672a\u6765\u98ce\u9669\u3001\u5bb9\u91cf\u88d5\u5ea6\u6216\u8fd0\u7ef4\u7b80\u62a5\u3002",
                "placeholder": "\u4f8b\u5982\uff1aL00 \u7ebf\u8def\u98ce\u9669",
                "send": "\u53d1\u9001",
                "failed": "\u8bf7\u6c42\u5931\u8d25\uff1a",
                "intent": "\u610f\u56fe",
                "tools": "\u5de5\u5177",
                "graph": "\u56fe\u8ffd\u8e2a",
                "task": "\u4efb\u52a1",
                "valid": "\u9a8c\u8bc1",
                "recovery": "\u6062\u590d",
                "suggestions": [
                    "\u5f53\u524d\u603b\u4f53\u98ce\u9669\u5982\u4f55\uff1f",
                    "\u54ea\u4e9b\u6746\u5854\u98ce\u9669\u6700\u9ad8\uff1f",
                    "L02_T034 \u4e3a\u4ec0\u4e48\u98ce\u9669\u9ad8\uff1f",
                    "L00 \u7ebf\u8def\u98ce\u9669\u600e\u6837\uff1f",
                    "\u54ea\u4e9b\u6746\u5854 DLR \u88d5\u5ea6\u4f4e\uff1f",
                    "\u751f\u6210\u4eca\u5929\u7684\u8fd0\u7ef4\u7b80\u62a5\u3002"
                ]
            },
            "en": {
                "docLang": "en",
                "pageTitle": "GridWeatherAgent Runtime",
                "aside": "Operator-facing weather-risk Agent with a lightweight Harness: planner, tool registry, validation loop, evidence packet, recovery plan, and feedback capture.",
                "cards": [
                    "planner: intent and task plan",
                    "tool registry: schemas and permissions",
                    "validator: graph, evidence, and guardrail checks",
                    "recovery: clarify, connector-required, review",
                    "learning: feedback to eval candidates"
                ],
                "console": "Runtime Console",
                "harness": "Harness JSON",
                "report": "Risk report",
                "hello": "Ask an operation question, such as current risk, top risky towers, L00 line risk, or future-risk capabilities that require mock connectors.",
                "placeholder": "Example: L00 line risk",
                "send": "Send",
                "failed": "Request failed: ",
                "intent": "intent",
                "tools": "tools",
                "graph": "graph",
                "task": "task",
                "valid": "valid",
                "recovery": "recovery",
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
        ensure_ascii=True,
    )
    html = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GridWeatherAgent</title>
<style>
body { margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; background: #f6f7f9; color: #172033; }
.app { display: grid; grid-template-columns: 330px 1fr; min-height: 100vh; }
aside { background: #101827; color: #e6edf7; padding: 24px; }
aside h1 { font-size: 22px; margin: 0 0 10px; }
aside p { color: #b8c4d6; line-height: 1.6; font-size: 14px; }
.tool { border: 1px solid #31415c; border-radius: 8px; padding: 10px 12px; margin: 10px 0; font-size: 13px; background: #162238; }
main { display: flex; flex-direction: column; min-width: 0; }
.topbar { padding: 18px 24px; border-bottom: 1px solid #e1e5eb; background: white; display: flex; justify-content: space-between; gap: 16px; align-items: center; }
.topbar strong { font-size: 18px; }
.topbar a { color: #1d65d8; text-decoration: none; font-size: 14px; }
.actions { display: flex; align-items: center; gap: 10px; }
.lang-toggle { display: inline-flex; border: 1px solid #cfd7e3; border-radius: 8px; overflow: hidden; background: #fff; }
.lang-toggle button { border: 0; background: transparent; padding: 7px 10px; cursor: pointer; color: #475569; }
.lang-toggle button.active { background: #1769e0; color: white; }
.chat { flex: 1; padding: 24px; overflow: auto; }
.msg { max-width: 900px; border-radius: 8px; padding: 14px 16px; margin: 0 0 14px; line-height: 1.65; white-space: pre-wrap; }
.user { background: #dbeafe; margin-left: auto; }
.agent { background: white; border: 1px solid #e1e5eb; }
.meta { margin-top: 10px; color: #64748b; font-size: 13px; }
.composer { background: white; border-top: 1px solid #e1e5eb; padding: 16px 24px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.chips button { border: 1px solid #cfd7e3; background: #fff; border-radius: 999px; padding: 7px 11px; cursor: pointer; }
.inputrow { display: flex; gap: 10px; }
input { flex: 1; border: 1px solid #cfd7e3; border-radius: 8px; padding: 12px 14px; font-size: 15px; }
.send { border: 0; background: #1769e0; color: white; border-radius: 8px; padding: 0 20px; font-size: 15px; cursor: pointer; }
@media (max-width: 800px) { .app { grid-template-columns: 1fr; } aside { display: none; } .topbar { align-items: flex-start; flex-direction: column; } }
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
<strong id="consoleTitle"></strong>
<div class="actions">
<div class="lang-toggle" aria-label="Language">
<button id="langZh" onclick="setLanguage('zh')">&#20013;&#25991;</button>
<button id="langEn" onclick="setLanguage('en')">EN</button>
</div>
<span><a id="harnessLink" href="/api/harness" target="_blank"></a> | <a id="reportLink" href="/report" target="_blank"></a></span>
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
const I18N = __I18N__;
let currentLanguage = localStorage.getItem("gridweather_language") || "zh";
function t(key) { return I18N[currentLanguage][key]; }
function setLanguage(lang) {
  currentLanguage = lang;
  localStorage.setItem("gridweather_language", lang);
  document.documentElement.lang = t("docLang");
  document.title = t("pageTitle");
  document.getElementById("asideText").textContent = t("aside");
  document.getElementById("consoleTitle").textContent = t("console");
  document.getElementById("harnessLink").textContent = t("harness");
  document.getElementById("reportLink").textContent = t("report");
  document.getElementById("input").placeholder = t("placeholder");
  document.getElementById("sendButton").textContent = t("send");
  document.getElementById("langZh").classList.toggle("active", lang === "zh");
  document.getElementById("langEn").classList.toggle("active", lang === "en");
  renderCards();
  renderChips();
  if (!document.getElementById("chat").children.length) addMsg(t("hello"), "agent");
}
function renderCards() {
  const toolList = document.getElementById("toolList");
  toolList.innerHTML = "";
  for (const item of t("cards")) {
    const div = document.createElement("div");
    div.className = "tool";
    div.textContent = item;
    toolList.appendChild(div);
  }
}
function renderChips() {
  const chips = document.getElementById("chips");
  chips.innerHTML = "";
  for (const q of t("suggestions")) {
    const btn = document.createElement("button");
    btn.textContent = q;
    btn.onclick = () => { document.getElementById("input").value = q; sendMessage(); };
    chips.appendChild(btn);
  }
}
function addMsg(text, cls, meta) {
  const div = document.createElement("div");
  div.className = "msg " + cls;
  div.textContent = text;
  if (meta) {
    const m = document.createElement("div");
    m.className = "meta";
    m.textContent = meta;
    div.appendChild(m);
  }
  document.getElementById("chat").appendChild(div);
  div.scrollIntoView({behavior: "smooth", block: "end"});
}
function buildMeta(data) {
  const parts = [];
  if (data.intent) parts.push(t("intent") + "=" + data.intent);
  if (data.used_tools) parts.push(t("tools") + "=" + data.used_tools.join(", "));
  if (data.graph_trace) parts.push(t("graph") + "=" + data.graph_trace.join(" -> "));
  if (data.task_id) parts.push(t("task") + "=" + data.task_id);
  if (data.validation) parts.push(t("valid") + "=" + data.validation.passed);
  if (data.recovery_plan) parts.push(t("recovery") + "=" + data.recovery_plan.strategy);
  return parts.join("; ");
}
async function sendMessage() {
  const input = document.getElementById("input");
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  addMsg(message, "user");
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message, language: currentLanguage})
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "request failed");
    addMsg(data.answer, "agent", buildMeta(data));
  } catch (err) {
    addMsg(t("failed") + err.message, "agent");
  }
}
document.getElementById("input").addEventListener("keydown", e => {
  if (e.key === "Enter") sendMessage();
});
setLanguage(currentLanguage);
</script>
</body>
</html>"""
    return html.replace("__I18N__", i18n_json)


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

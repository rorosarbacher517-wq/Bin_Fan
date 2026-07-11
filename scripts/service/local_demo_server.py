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
from gridweather.agent.operator_graph import SUGGESTED_QUESTIONS
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
        if not message:
            self._send_json({"error": "missing message"}, status=400)
            return
        self._send_json(self.runtime().ask(message))

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
    suggestions_json = json.dumps(SUGGESTED_QUESTIONS, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GridWeatherAgent 运维试用版</title>
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
@media (max-width: 800px) {{ .app {{ grid-template-columns: 1fr; }} aside {{ display: none; }} }}
</style>
</head>
<body>
<div class="app">
<aside>
<h1>GridWeatherAgent</h1>
<p>面向电厂/电网运维人员的气象风险诊断 Agent。当前采用 LangGraph-style 状态图：意图路由、工具节点、证据汇总、护栏校验。</p>
<div class="tool">intent_router：意图路由</div>
<div class="tool">risk_summary：总体风险概览</div>
<div class="tool">top_risk_ranker：最高风险排序</div>
<div class="tool">tower_lookup：单杆塔诊断</div>
<div class="tool">line_risk_aggregator：线路汇总</div>
<div class="tool">capacity_margin_checker：容量裕度检查</div>
<div class="tool">guardrails：证据与安全护栏</div>
</aside>
<main>
<div class="topbar">
<strong>运维问答试用台</strong>
<a href="/report" target="_blank">打开完整风险报告</a>
</div>
<div id="chat" class="chat">
<div class="msg agent">你好，我是 GridWeatherAgent。你可以问我：当前总体风险怎么样？最高风险杆塔有哪些？L02_T034 为什么危险？L00 线路风险如何？哪些杆塔容量裕度不足？</div>
</div>
<div class="composer">
<div class="chips" id="chips"></div>
<div class="inputrow">
<input id="input" placeholder="输入运维问题，例如：L02_T034 为什么危险？">
<button class="send" onclick="sendMessage()">发送</button>
</div>
</div>
</main>
</div>
<script>
const suggestions = {suggestions_json};
const chips = document.getElementById("chips");
for (const q of suggestions) {{
  const btn = document.createElement("button");
  btn.textContent = q;
  btn.onclick = () => {{ document.getElementById("input").value = q; sendMessage(); }};
  chips.appendChild(btn);
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
      body: JSON.stringify({{message}})
    }});
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "request failed");
    const trace = data.graph_trace ? "；图节点：" + data.graph_trace.join(" -> ") : "";
    addMsg(data.answer, "agent", "意图：" + data.intent + "；使用工具：" + (data.used_tools || []).join(", ") + trace);
  }} catch (err) {{
    addMsg("请求失败：" + err.message, "agent");
  }}
}}
document.getElementById("input").addEventListener("keydown", e => {{
  if (e.key === "Enter") sendMessage();
}});
</script>
</body>
</html>"""


def build_app_html() -> str:
    suggestions_json = json.dumps(SUGGESTED_QUESTIONS, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GridWeatherAgent 运维试用版</title>
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
@media (max-width: 800px) {{ .app {{ grid-template-columns: 1fr; }} aside {{ display: none; }} }}
</style>
</head>
<body>
<div class="app">
<aside>
<h1>GridWeatherAgent</h1>
<p>面向电厂/电网运维人员的气象风险诊断 Agent。当前采用 LangGraph-style 状态图，并增加企业级运行时：任务 ID、工具注册、证据包、执行日志和 mock connector。</p>
<div class="tool">planner：意图识别与任务计划</div>
<div class="tool">risk_summary：总体风险概览</div>
<div class="tool">top_risk_ranker：最高风险排序</div>
<div class="tool">tower_lookup：单杆塔诊断</div>
<div class="tool">line_risk_aggregator：线路风险汇总</div>
<div class="tool">capacity_margin_checker：容量裕度检查</div>
<div class="tool">rag_guideline_retriever：运维规程检索</div>
<div class="tool">guardrails：证据与安全护栏</div>
</aside>
<main>
<div class="topbar">
<strong>运维问答试用台</strong>
<a href="/report" target="_blank">打开完整风险报告</a>
</div>
<div id="chat" class="chat">
<div class="msg agent">你好，我是 GridWeatherAgent。你可以问我：当前总体风险怎么样？最高风险杆塔有哪些？L02_T034 为什么危险？L00 线路风险如何？哪些杆塔容量裕度不足？也可以测试尚未真实接入的能力，例如未来 24 小时风险或负荷增加 20% 的影响。</div>
</div>
<div class="composer">
<div class="chips" id="chips"></div>
<div class="inputrow">
<input id="input" placeholder="输入运维问题，例如：L02_T034 为什么危险？">
<button class="send" onclick="sendMessage()">发送</button>
</div>
</div>
</main>
</div>
<script>
const suggestions = {suggestions_json};
const chips = document.getElementById("chips");
for (const q of suggestions) {{
  const btn = document.createElement("button");
  btn.textContent = q;
  btn.onclick = () => {{ document.getElementById("input").value = q; sendMessage(); }};
  chips.appendChild(btn);
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
      body: JSON.stringify({{message}})
    }});
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "request failed");
    const trace = data.graph_trace ? "；图节点：" + data.graph_trace.join(" -> ") : "";
    const task = data.task_id ? "；任务ID：" + data.task_id : "";
    const mock = data.mock_connector_context ? "；已附 mock connector 结果" : "";
    addMsg(data.answer, "agent", "意图：" + data.intent + "；使用工具：" + (data.used_tools || []).join(", ") + trace + task + mock);
  }} catch (err) {{
    addMsg("请求失败：" + err.message, "agent");
  }}
}}
document.getElementById("input").addEventListener("keydown", e => {{
  if (e.key === "Enter") sendMessage();
}});
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

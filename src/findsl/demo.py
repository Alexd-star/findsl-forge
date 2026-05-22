from __future__ import annotations

import json
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List

from .compiler import Compiler
from .equivalence import verify_sql_equivalence
from .evaluation import load_cases


DEFAULT_DEMO_DSL = (
    'then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), '
    'rank(indicator("turnover_rate"), desc, top=100))'
)


def analyze_dsl(
    dsl: str,
    data_dir: Path = Path("data/samples"),
    enable_prefix_sum: bool = True,
    verify: bool = True,
) -> Dict[str, Any]:
    compiler = Compiler(enable_prefix_sum=enable_prefix_sum)
    compiled = compiler.compile(dsl)
    payload: Dict[str, Any] = {
        "ok": True,
        "dsl": dsl,
        "compile": {
            "elapsed_ms": compiled.elapsed_ms,
            "ast": compiled.ast,
            "sql": compiled.sql,
            "trace": compiled.trace,
            "explain": compiled.explain,
            "prefix_sum_enabled": enable_prefix_sum,
        },
        "verification": None,
    }
    if verify:
        verification = verify_sql_equivalence(dsl, Path(data_dir), compiler=compiler)
        payload["verification"] = {
            "passed": verification.passed,
            "sql_row_count": verification.sql_row_count,
            "reference_row_count": verification.reference_row_count,
            "missing_keys": verification.missing_keys,
            "extra_keys": verification.extra_keys,
            "result_keys": verification.sql_keys[:50],
        }
    return payload


def demo_examples(cases_path: Path = Path("data/samples/queries.jsonl")) -> List[Dict[str, str]]:
    try:
        cases = load_cases(Path(cases_path))
    except FileNotFoundError:
        return [{"name": "Default", "dsl": DEFAULT_DEMO_DSL}]
    examples = [{"name": case.get("name", "Example"), "dsl": case["dsl"]} for case in cases if case.get("dsl")]
    return examples or [{"name": "Default", "dsl": DEFAULT_DEMO_DSL}]


def make_demo_handler(data_dir: Path, cases_path: Path = Path("data/samples/queries.jsonl")):
    data_dir = Path(data_dir)
    cases_path = Path(cases_path)

    class DemoHandler(BaseHTTPRequestHandler):
        server_version = "FinDSLDemo/0.1"

        def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler.
            if self.path in {"/", "/index.html"}:
                self._send_text(render_demo_html(), "text/html; charset=utf-8")
                return
            if self.path == "/api/examples":
                self._send_json({"ok": True, "examples": demo_examples(cases_path)})
                return
            self._send_json({"ok": False, "error": {"message": "Not found"}}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler.
            if self.path != "/api/analyze":
                self._send_json({"ok": False, "error": {"message": "Not found"}}, HTTPStatus.NOT_FOUND)
                return
            try:
                request = self._read_json()
                dsl = str(request.get("dsl", "")).strip()
                if not dsl:
                    raise ValueError("DSL is required")
                result = analyze_dsl(
                    dsl=dsl,
                    data_dir=data_dir,
                    enable_prefix_sum=bool(request.get("enable_prefix_sum", True)),
                    verify=bool(request.get("verify", True)),
                )
                self._send_json(result)
            except Exception as exc:  # noqa: BLE001 - demo API returns structured diagnostics.
                self._send_json(
                    {
                        "ok": False,
                        "error": {
                            "type": type(exc).__name__,
                            "message": str(exc),
                            "trace": traceback.format_exc(limit=3).strip().splitlines(),
                        },
                    },
                    HTTPStatus.BAD_REQUEST,
                )

        def log_message(self, format: str, *args: object) -> None:
            return

        def _read_json(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            raw = self.rfile.read(min(length, 128 * 1024))
            return json.loads(raw.decode("utf-8"))

        def _send_json(self, payload: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_text(self, body: str, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return DemoHandler


def run_demo_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    data_dir: Path = Path("data/samples"),
    cases_path: Path = Path("data/samples/queries.jsonl"),
) -> None:
    handler = make_demo_handler(data_dir=data_dir, cases_path=cases_path)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"FinDSL Forge demo listening on http://{host}:{port}")
    server.serve_forever()


def render_demo_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FinDSL Forge Demo</title>
  <style>
    :root {
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #172026;
      --muted: #65717b;
      --line: #d8dee4;
      --accent: #0f766e;
      --accent-2: #7c3aed;
      --danger: #b42318;
      --ok: #137333;
      --warn: #a15c00;
      --code: #111827;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 0 24px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    h1 { font-size: 18px; margin: 0; font-weight: 700; }
    main { padding: 18px 24px 24px; }
    .shell {
      display: grid;
      grid-template-columns: minmax(320px, 0.85fr) minmax(420px, 1.15fr);
      gap: 16px;
      align-items: start;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    .panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
    }
    .panel-head h2 { font-size: 14px; margin: 0; }
    .section { padding: 14px; }
    label { display: block; color: var(--muted); font-size: 12px; margin-bottom: 6px; }
    select, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      font: inherit;
    }
    select { height: 36px; padding: 0 10px; }
    textarea {
      min-height: 168px;
      resize: vertical;
      padding: 10px;
      font-family: Consolas, "SFMono-Regular", monospace;
      line-height: 1.45;
    }
    .controls {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-top: 12px;
    }
    .checks { display: flex; gap: 12px; color: var(--muted); font-size: 13px; }
    .checks label { display: inline-flex; align-items: center; gap: 6px; margin: 0; color: inherit; }
    button {
      border: 0;
      border-radius: 6px;
      background: var(--accent);
      color: #fff;
      height: 36px;
      padding: 0 14px;
      font-weight: 700;
      cursor: pointer;
    }
    button:disabled { opacity: 0.65; cursor: default; }
    .metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }
    .metric {
      border-left: 3px solid var(--accent);
      padding: 4px 8px;
      min-height: 48px;
    }
    .metric strong { display: block; font-size: 16px; }
    .metric span { color: var(--muted); font-size: 12px; }
    .status-ok { color: var(--ok); }
    .status-fail { color: var(--danger); }
    .tabs {
      display: flex;
      gap: 6px;
      padding: 10px 10px 0;
      border-bottom: 1px solid var(--line);
      background: #fbfcfd;
    }
    .tab {
      height: 32px;
      padding: 0 10px;
      color: var(--muted);
      background: transparent;
      border: 1px solid transparent;
      border-bottom: 0;
      border-radius: 6px 6px 0 0;
      font-weight: 600;
    }
    .tab.active {
      color: var(--ink);
      background: var(--panel);
      border-color: var(--line);
    }
    pre {
      margin: 0;
      min-height: 420px;
      overflow: auto;
      padding: 14px;
      background: var(--code);
      color: #e5e7eb;
      font: 12px/1.55 Consolas, "SFMono-Regular", monospace;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .rows {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    .rows th, .rows td {
      border-bottom: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
    }
    .rows th { color: var(--muted); font-weight: 600; }
    .error {
      border-left: 3px solid var(--danger);
      color: var(--danger);
      padding: 10px 12px;
      background: #fff7f5;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      height: 26px;
      padding: 0 8px;
      border-radius: 999px;
      background: #edf7f5;
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
    }
    @media (max-width: 960px) {
      header { padding: 0 14px; }
      main { padding: 14px; }
      .shell { grid-template-columns: 1fr; }
      .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      pre { min-height: 280px; }
    }
  </style>
</head>
<body>
  <header>
    <h1>FinDSL Forge</h1>
    <span class="badge" id="buildState">Ready</span>
  </header>
  <main>
    <div class="shell">
      <section class="panel">
        <div class="panel-head">
          <h2>DSL Workbench</h2>
          <span class="badge">Doris SQL</span>
        </div>
        <div class="section">
          <label for="exampleSelect">Sample</label>
          <select id="exampleSelect"></select>
          <label for="dslInput" style="margin-top:12px;">DSL</label>
          <textarea id="dslInput" spellcheck="false"></textarea>
          <div class="controls">
            <div class="checks">
              <label><input id="prefixToggle" type="checkbox" checked> Prefix sum</label>
              <label><input id="verifyToggle" type="checkbox" checked> Verify</label>
            </div>
            <button id="runButton">Run</button>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>Result</h2>
          <span id="resultState" class="badge">Waiting</span>
        </div>
        <div class="section metrics">
          <div class="metric"><strong id="metricStatus">-</strong><span>verification</span></div>
          <div class="metric"><strong id="metricLatency">-</strong><span>compile latency</span></div>
          <div class="metric"><strong id="metricRows">-</strong><span>SQL rows</span></div>
          <div class="metric"><strong id="metricPrefix">-</strong><span>optimizer</span></div>
        </div>
        <div class="tabs">
          <button class="tab active" data-tab="sql">SQL</button>
          <button class="tab" data-tab="ast">AST</button>
          <button class="tab" data-tab="explain">Explain</button>
          <button class="tab" data-tab="rows">Rows</button>
        </div>
        <div id="errorBox" class="error" hidden></div>
        <pre id="outputPane"></pre>
      </section>
    </div>
  </main>
  <script>
    const sampleSelect = document.getElementById("exampleSelect");
    const dslInput = document.getElementById("dslInput");
    const runButton = document.getElementById("runButton");
    const outputPane = document.getElementById("outputPane");
    const errorBox = document.getElementById("errorBox");
    const resultState = document.getElementById("resultState");
    const buildState = document.getElementById("buildState");
    const prefixToggle = document.getElementById("prefixToggle");
    const verifyToggle = document.getElementById("verifyToggle");
    let currentResult = null;
    let currentTab = "sql";

    function setState(text, ok) {
      resultState.textContent = text;
      resultState.style.color = ok ? "var(--ok)" : "var(--danger)";
      buildState.textContent = text;
    }

    function pretty(value) {
      return JSON.stringify(value, null, 2);
    }

    function render() {
      errorBox.hidden = true;
      if (!currentResult || !currentResult.ok) {
        outputPane.textContent = "";
        return;
      }
      const compiled = currentResult.compile;
      if (currentTab === "sql") outputPane.textContent = compiled.sql;
      if (currentTab === "ast") outputPane.textContent = pretty(compiled.ast);
      if (currentTab === "explain") outputPane.textContent = pretty({ trace: compiled.trace, explain: compiled.explain });
      if (currentTab === "rows") outputPane.textContent = pretty(currentResult.verification ? currentResult.verification.result_keys : []);
    }

    function updateMetrics(result) {
      const verification = result.verification;
      const passed = verification ? verification.passed : null;
      document.getElementById("metricStatus").textContent = passed === null ? "Skipped" : passed ? "PASS" : "FAIL";
      document.getElementById("metricStatus").className = passed === false ? "status-fail" : "status-ok";
      document.getElementById("metricLatency").textContent = result.compile.elapsed_ms.toFixed(3) + " ms";
      document.getElementById("metricRows").textContent = verification ? verification.sql_row_count : "-";
      const applied = result.compile.explain.some(step => step.rule === "PREFIX_SUM" && step.status === "applied");
      document.getElementById("metricPrefix").textContent = applied ? "Applied" : "Skipped";
    }

    async function loadExamples() {
      const res = await fetch("/api/examples");
      const data = await res.json();
      sampleSelect.innerHTML = "";
      data.examples.forEach((item, idx) => {
        const option = document.createElement("option");
        option.value = item.dsl;
        option.textContent = item.name;
        sampleSelect.appendChild(option);
        if (idx === 0) dslInput.value = item.dsl;
      });
    }

    async function run() {
      runButton.disabled = true;
      setState("Running", true);
      try {
        const res = await fetch("/api/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            dsl: dslInput.value,
            enable_prefix_sum: prefixToggle.checked,
            verify: verifyToggle.checked
          })
        });
        const data = await res.json();
        if (!data.ok) {
          throw new Error(data.error.type + ": " + data.error.message);
        }
        currentResult = data;
        updateMetrics(data);
        setState(data.verification && !data.verification.passed ? "Failed" : "Passed", !(data.verification && !data.verification.passed));
        render();
      } catch (err) {
        currentResult = null;
        errorBox.hidden = false;
        errorBox.textContent = err.message;
        outputPane.textContent = "";
        setState("Error", false);
      } finally {
        runButton.disabled = false;
      }
    }

    document.querySelectorAll(".tab").forEach(button => {
      button.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach(item => item.classList.remove("active"));
        button.classList.add("active");
        currentTab = button.dataset.tab;
        render();
      });
    });
    sampleSelect.addEventListener("change", () => { dslInput.value = sampleSelect.value; });
    runButton.addEventListener("click", run);
    loadExamples().then(run);
  </script>
</body>
</html>"""

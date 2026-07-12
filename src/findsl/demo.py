from __future__ import annotations

import json
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List

from .compiler import Compiler
from .diagnostics import diagnose_exception
from .equivalence import verify_sql_equivalence
from .evaluation import load_cases
from .nl2dsl import suggest_dsl
from .official.pipeline import compile_official
from .official_suite import DEFAULT_NEGATIVE_CASES, DEFAULT_POSITIVE_CASES


DEFAULT_DEMO_DSL = (
    'then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), '
    'rank(indicator("turnover_rate"), desc, top=100))'
)
DEFAULT_NL_REQUEST = "筛选A股连续3天主力净流入为正的股票，并按换手率从高到低排名前100"
DEMO_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REAL_MARKET_CASES = DEMO_REPO_ROOT / "data/real_samples/eastmoney_a_share_sample/queries.jsonl"
DEFAULT_REAL_MARKET_DATA_DIR = DEMO_REPO_ROOT / "data/real_samples/eastmoney_a_share_sample"


def doris_evidence_summary(report_path: Path = Path("reports/doris_cluster_evidence.md")) -> Dict[str, Any]:
    report_path = Path(report_path)
    if not report_path.exists():
        return {
            "available": False,
            "path": str(report_path),
            "message": "Doris evidence report is not available yet.",
        }
    content = report_path.read_text(encoding="utf-8")
    metrics: Dict[str, str] = {}
    for line in content.splitlines():
        if not line.startswith("- ") or ": " not in line:
            continue
        key, value = line[2:].split(": ", 1)
        metrics[_metric_key(key)] = value.strip()
    return {
        "available": True,
        "path": str(report_path),
        "metrics": metrics,
        "headline": {
            "passed": metrics.get("evidence_passed", "<unknown>"),
            "speedup": metrics.get("doris_cluster_speedup", "<unknown>"),
            "baseline_avg_ms": metrics.get("baseline_avg_execute_ms", "<unknown>"),
            "optimized_avg_ms": metrics.get("optimized_avg_execute_ms", "<unknown>"),
            "row_counts_match": metrics.get("row_counts_match", "<unknown>"),
        },
    }


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


def analyze_official_dsl(dsl: str) -> Dict[str, Any]:
    payload = compile_official(dsl).to_dict()
    payload["pipeline"] = "official-antlr-ir-sqlglot"
    return payload


def demo_examples(
    cases_path: Path = Path("data/samples/queries.jsonl"),
    official_positive_path: Path = DEFAULT_POSITIVE_CASES,
    official_negative_path: Path = DEFAULT_NEGATIVE_CASES,
    real_market_cases_path: Path = DEFAULT_REAL_MARKET_CASES,
) -> List[Dict[str, str]]:
    examples: List[Dict[str, str]] = []
    for case in _safe_load_cases(_resolve_demo_path(cases_path)):
        if case.get("dsl"):
            examples.append(
                {
                    "name": str(case.get("name", "Example")),
                    "dsl": str(case["dsl"]),
                    "kind": "baseline",
                    "scenario": "evaluation",
                    "dataset": "default",
                    "dataset_label": "sample fixtures",
                }
            )
    for case in _safe_load_cases(_resolve_demo_path(official_positive_path)):
        if case.get("dsl"):
            examples.append(
                {
                    "name": f"Official positive: {case.get('name', 'Example')}",
                    "dsl": str(case["dsl"]),
                    "kind": "official_positive",
                    "scenario": str(case.get("scenario", "")),
                    "dataset": "default",
                    "dataset_label": "sample fixtures",
                }
            )
    for case in _safe_load_cases(_resolve_demo_path(official_negative_path)):
        if case.get("dsl"):
            examples.append(
                {
                    "name": f"Diagnostic negative: {case.get('name', 'Example')}",
                    "dsl": str(case["dsl"]),
                    "kind": "official_negative",
                    "scenario": "diagnostic",
                    "expected_code": str(case.get("expected_code", "")),
                    "dataset": "default",
                    "dataset_label": "sample fixtures",
                }
            )
    for case in _safe_load_cases(_resolve_demo_path(real_market_cases_path)):
        if case.get("dsl"):
            examples.append(
                {
                    "name": f"Real market: {case.get('name', 'Example')}",
                    "dsl": str(case["dsl"]),
                    "kind": "real_market",
                    "scenario": str(case.get("scenario", "")),
                    "dataset": "real_market",
                    "dataset_label": "Eastmoney A-share sample",
                }
            )
    return examples or [
        {
            "name": "Default",
            "dsl": DEFAULT_DEMO_DSL,
            "kind": "baseline",
            "scenario": "fallback",
            "dataset": "default",
            "dataset_label": "sample fixtures",
        }
    ]


def suggest_from_text(
    text: str,
    data_dir: Path = Path("data/samples"),
    enable_prefix_sum: bool = True,
    verify: bool = True,
) -> Dict[str, Any]:
    suggestion = suggest_dsl(text)
    candidates = []
    for candidate in suggestion.candidates:
        item = candidate.to_dict()
        try:
            analysis = analyze_dsl(
                candidate.dsl,
                data_dir=data_dir,
                enable_prefix_sum=enable_prefix_sum,
                verify=verify,
            )
            verification = analysis.get("verification") or {}
            item["analysis"] = analysis
            item["validated"] = bool(analysis.get("ok")) and (
                not verify or bool(verification.get("passed"))
            )
        except Exception as exc:  # noqa: BLE001 - candidate validation is diagnostic evidence.
            item["validated"] = False
            item["error"] = _error_payload(exc)
        candidates.append(item)
    return {
        "ok": True,
        "text": text,
        "warnings": suggestion.warnings,
        "candidates": candidates,
    }


def make_demo_handler(data_dir: Path, cases_path: Path = Path("data/samples/queries.jsonl")):
    data_dir = _resolve_demo_path(data_dir)
    cases_path = _resolve_demo_path(cases_path)
    dataset_paths = {
        "default": data_dir,
        "real_market": DEFAULT_REAL_MARKET_DATA_DIR,
    }

    class DemoHandler(BaseHTTPRequestHandler):
        server_version = "FinDSLDemo/0.1"

        def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler.
            if self.path in {"/", "/index.html"}:
                self._send_text(render_demo_html(), "text/html; charset=utf-8")
                return
            if self.path == "/api/examples":
                self._send_json({"ok": True, "examples": demo_examples(cases_path)})
                return
            if self.path == "/api/evidence":
                self._send_json({"ok": True, "evidence": doris_evidence_summary()})
                return
            self._send_json({"ok": False, "error": {"message": "Not found"}}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler.
            if self.path not in {"/api/analyze", "/api/suggest", "/api/official/analyze"}:
                self._send_json({"ok": False, "error": {"message": "Not found"}}, HTTPStatus.NOT_FOUND)
                return
            try:
                request = self._read_json()
                if self.path == "/api/official/analyze":
                    dsl = str(request.get("dsl", "")).strip()
                    if not dsl:
                        raise ValueError("Official DSL is required")
                    self._send_json(analyze_official_dsl(dsl))
                    return
                if self.path == "/api/suggest":
                    text = str(request.get("text", "")).strip()
                    if not text:
                        raise ValueError("Natural-language request is required")
                    result = suggest_from_text(
                        text=text,
                        data_dir=data_dir,
                        enable_prefix_sum=bool(request.get("enable_prefix_sum", True)),
                        verify=bool(request.get("verify", True)),
                    )
                    self._send_json(result)
                    return
                dsl = str(request.get("dsl", "")).strip()
                if not dsl:
                    raise ValueError("DSL is required")
                result = analyze_dsl(
                    dsl=dsl,
                    data_dir=_resolve_demo_dataset(str(request.get("dataset", "default")), dataset_paths),
                    enable_prefix_sum=bool(request.get("enable_prefix_sum", True)),
                    verify=bool(request.get("verify", True)),
                )
                self._send_json(result)
            except Exception as exc:  # noqa: BLE001 - demo API returns structured diagnostics.
                self._send_json(
                    {"ok": False, "error": _error_payload(exc)},
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


def _error_payload(exc: Exception) -> Dict[str, Any]:
    if hasattr(exc, "to_dict"):
        payload = dict(exc.to_dict())
        payload["type"] = type(exc).__name__
        payload["trace"] = traceback.format_exc(limit=3).strip().splitlines()
        return payload
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "diagnostics": [item.to_dict() for item in diagnose_exception(exc)],
        "trace": traceback.format_exc(limit=3).strip().splitlines(),
    }


def _safe_load_cases(path: Path) -> List[Dict[str, Any]]:
    try:
        return load_cases(path)
    except FileNotFoundError:
        return []


def _resolve_demo_path(path: Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    cwd_candidate = Path.cwd() / candidate
    if cwd_candidate.exists():
        return cwd_candidate
    repo_candidate = DEMO_REPO_ROOT / candidate
    if repo_candidate.exists():
        return repo_candidate
    return candidate


def _resolve_demo_dataset(dataset: str, dataset_paths: Dict[str, Path]) -> Path:
    if dataset not in dataset_paths:
        raise ValueError(f"Unsupported demo dataset: {dataset}")
    return dataset_paths[dataset]


def _metric_key(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
    )


def render_demo_html() -> str:
    html = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FinDSL Forge Demo</title>
  <style>
    :root {
      --bg: #f4f7f8;
      --panel: #ffffff;
      --panel-2: #f8fbfb;
      --ink: #162124;
      --muted: #607075;
      --line: #cad7da;
      --soft: #d9e3e5;
      --accent: #0f766e;
      --accent-deep: #0b4f4a;
      --accent-soft: #e4f3f1;
      --blue: #1d4f73;
      --danger: #b42318;
      --danger-soft: #fff0ed;
      --ok: #137333;
      --ok-soft: #eaf6ee;
      --warn: #9a5a00;
      --warn-soft: #fff3d9;
      --code: #101820;
      --shadow: 0 8px 24px rgba(18, 36, 42, 0.08);
    }
    * { box-sizing: border-box; min-width: 0; }
    html {
      width: 100%;
      max-width: 100%;
      overflow-x: hidden;
    }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.55 "Segoe UI", "Microsoft YaHei", system-ui, sans-serif;
      width: 100%;
      max-width: 100%;
      overflow-x: hidden;
    }
    main, .topbar, .hero-strip, .shell, .panel, .brief, .metric, .panel-head, .section {
      min-width: 0;
    }
    .topbar {
      min-height: 70px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 24px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
      position: sticky;
      top: 0;
      z-index: 10;
    }
    .brand { display: flex; flex-direction: column; gap: 2px; min-width: 260px; }
    h1 { font-size: 20px; margin: 0; font-weight: 800; letter-spacing: -0.01em; }
    .brand p { margin: 0; color: var(--muted); font-size: 12px; }
    .top-metrics { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
    main { padding: 18px 24px 24px; max-width: 1600px; margin: 0 auto; }
    .hero-strip {
      display: grid;
      grid-template-columns: minmax(260px, 1.2fr) minmax(280px, 0.8fr);
      gap: 14px;
      margin-bottom: 16px;
    }
    .brief {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 14px 16px;
      box-shadow: var(--shadow);
    }
    .brief h2 { margin: 0 0 6px; font-size: 16px; }
    .brief p { margin: 0; color: var(--muted); max-width: 84ch; overflow-wrap: anywhere; }
    .evidence-ribbon { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
    .shell {
      display: grid;
      grid-template-columns: minmax(360px, 0.82fr) minmax(520px, 1.18fr);
      gap: 16px;
      align-items: start;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      overflow: hidden;
      box-shadow: var(--shadow);
    }
    .panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 13px 15px;
      border-bottom: 1px solid var(--line);
      background: var(--panel-2);
    }
    .panel-title { display: flex; flex-direction: column; gap: 2px; }
    .panel-head h2 { font-size: 15px; margin: 0; }
    .panel-head p { margin: 0; color: var(--muted); font-size: 12px; }
    .panel-actions {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
    }
    .section { padding: 14px 15px 16px; }
    .field { margin-bottom: 12px; }
    label {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 6px;
    }
    select, textarea {
      width: 100%;
      min-width: 0;
      max-width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      font: inherit;
      outline: none;
      word-break: break-word;
      transition: border-color 0.16s ease, box-shadow 0.16s ease;
    }
    select:focus, textarea:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.14);
    }
    select {
      height: 36px;
      padding: 0 10px;
      text-overflow: ellipsis;
    }
    textarea {
      min-height: 168px;
      resize: vertical;
      padding: 10px;
      font-family: Consolas, "SFMono-Regular", monospace;
      line-height: 1.45;
      overflow-wrap: anywhere;
      white-space: pre-wrap;
      overflow-x: hidden;
    }
    #nlInput {
      min-height: 84px;
      font-family: inherit;
    }
    .controls {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-top: 12px;
      min-width: 0;
    }
    .checks { display: flex; flex-wrap: wrap; gap: 12px; color: var(--muted); font-size: 13px; }
    .checks label { display: inline-flex; align-items: center; gap: 6px; margin: 0; color: inherit; }
    button {
      border: 0;
      border-radius: 8px;
      background: var(--accent);
      color: #fff;
      height: 36px;
      padding: 0 14px;
      font-weight: 700;
      cursor: pointer;
      min-width: 0;
      transition: transform 0.14s ease, background 0.14s ease, box-shadow 0.14s ease;
    }
    button:hover { background: var(--accent-deep); }
    button:active { transform: translateY(1px); }
    button:focus-visible { outline: 3px solid rgba(15, 118, 110, 0.28); outline-offset: 2px; }
    .secondary { background: var(--blue); }
    .ghost {
      background: #eff5f6;
      color: #172026;
      border: 1px solid var(--line);
    }
    .ghost:hover { background: #e2ecee; color: var(--ink); }
    button:disabled { opacity: 0.65; cursor: default; }
    .candidates {
      display: grid;
      gap: 8px;
      margin-top: 10px;
      margin-bottom: 12px;
    }
    .candidate {
      width: 100%;
      max-width: 100%;
      height: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      padding: 8px 10px;
      text-align: left;
      font-weight: 500;
    }
    .candidate strong {
      display: block;
      font-size: 13px;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    .candidate span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-top: 2px;
      overflow-wrap: anywhere;
      word-break: break-all;
      white-space: normal;
    }
    .candidate.validated {
      background: var(--ok-soft);
      border-color: #b9dfc6;
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-2);
      padding: 9px 10px;
      min-height: 60px;
    }
    .metric strong { display: block; font-size: 16px; line-height: 1.2; }
    .metric span { color: var(--muted); font-size: 12px; }
    .status-ok { color: var(--ok); }
    .status-fail { color: var(--danger); }
    .status-warn { color: var(--warn); }
    .tabs {
      display: flex;
      gap: 6px;
      padding: 10px 10px 0;
      border-bottom: 1px solid var(--line);
      background: #fbfcfd;
      overflow-x: auto;
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
      flex: 0 0 auto;
    }
    .tab.active {
      color: var(--ink);
      background: var(--panel);
      border-color: var(--line);
    }
    .output { min-height: 500px; background: #fff; }
    pre {
      margin: 0;
      min-height: 500px;
      overflow: auto;
      padding: 14px;
      background: var(--code);
      color: #e5e7eb;
      font: 12px/1.55 Consolas, "SFMono-Regular", monospace;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .structured { min-height: 500px; padding: 14px; background: #fff; overflow: auto; }
    .timeline { display: grid; gap: 10px; }
    .step-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
      background: var(--panel-2);
    }
    .step-card header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 6px;
    }
    .step-card h3 { margin: 0; font-size: 13px; }
    .step-card p { margin: 0 0 8px; color: var(--muted); }
    .kv {
      display: grid;
      grid-template-columns: minmax(120px, 0.38fr) 1fr;
      gap: 6px 10px;
      font-size: 12px;
      border-top: 1px solid var(--soft);
      padding-top: 8px;
      overflow-wrap: anywhere;
    }
    .kv dt { color: var(--muted); }
    .kv dd { margin: 0; font-family: Consolas, "SFMono-Regular", monospace; }
    .data-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    .data-table th, .data-table td {
      border-bottom: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }
    .data-table th { color: var(--muted); font-weight: 700; background: var(--panel-2); }
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
      color: var(--danger);
      padding: 12px 14px;
      background: var(--danger-soft);
      white-space: pre-wrap;
      border-bottom: 1px solid #ffd1c9;
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
      white-space: nowrap;
      max-width: 100%;
    }
    .badge.ok { background: var(--ok-soft); color: var(--ok); }
    .badge.warn { background: var(--warn-soft); color: var(--warn); }
    .badge.fail { background: var(--danger-soft); color: var(--danger); }
    .small-note { color: var(--muted); font-size: 12px; margin-top: 8px; }
    .empty { color: var(--muted); padding: 36px 18px; text-align: center; }
    .diagnostic-list { display: grid; gap: 10px; }
    .diagnostic-card {
      border: 1px solid #f2c5bc;
      background: var(--danger-soft);
      border-radius: 8px;
      padding: 10px 12px;
    }
    .diagnostic-card h3 { margin: 0 0 6px; font-size: 13px; color: var(--danger); }
    .diagnostic-card p { margin: 0 0 8px; color: #6f2c23; }
    .suggestion-list { margin: 6px 0 0; padding-left: 18px; color: var(--ink); }
    @media (prefers-reduced-motion: reduce) {
      * { scroll-behavior: auto !important; transition: none !important; }
    }
    @media (max-width: 960px) {
      .topbar { padding: 12px 14px; align-items: flex-start; flex-direction: column; }
      .brand { min-width: 0; }
      .top-metrics { justify-content: flex-start; width: 100%; }
      main { padding: 14px; }
      .hero-strip, .shell { grid-template-columns: 1fr; }
      .evidence-ribbon, .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      pre { min-height: 280px; }
      .structured { min-height: 320px; }
    }
    @media (max-width: 640px) {
      .evidence-ribbon, .metrics { grid-template-columns: 1fr; }
      .panel-head { align-items: flex-start; flex-direction: column; }
      .panel-actions { width: 100%; justify-content: space-between; }
      .controls { flex-direction: column; align-items: stretch; }
      .controls button { width: 100%; }
      label { flex-direction: column; align-items: flex-start; gap: 2px; }
      .checks { width: 100%; justify-content: space-between; }
      .checks label { flex-direction: row; align-items: center; }
      .badge { white-space: normal; height: auto; min-height: 26px; padding-top: 4px; padding-bottom: 4px; }
      .top-metrics .badge { white-space: nowrap; }
      .tab { padding: 0 10px; }
      .kv { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="topbar">
    <div class="brand">
      <h1>FinDSL Forge</h1>
      <p>金融选股 DSL 到 Apache Doris SQL 的确定性编译与证据工作台</p>
    </div>
    <div class="top-metrics">
      <span class="badge ok" id="buildState">Ready</span>
      <span class="badge" id="evidenceSpeed">Doris evidence loading</span>
      <span class="badge" id="evidenceRows">Row parity unknown</span>
    </div>
  </div>
  <main>
    <section class="hero-strip">
      <div class="brief">
        <h2>评审演示主线</h2>
        <p>中文需求生成候选 DSL，候选表达式经过编译器、SQL 安全检查和 SQL/reference 等价验证，再展示 Doris evidence。页面不会执行 LLM 直接 SQL。</p>
      </div>
      <div class="evidence-ribbon">
        <div class="metric"><strong id="metricEvidence">-</strong><span>Doris evidence</span></div>
        <div class="metric"><strong id="metricSpeedup">-</strong><span>cluster speedup</span></div>
        <div class="metric"><strong id="metricParity">-</strong><span>row counts</span></div>
      </div>
    </section>
    <div class="shell">
      <section class="panel">
        <div class="panel-head">
          <div class="panel-title">
            <h2>DSL Workbench</h2>
            <p>输入中文需求、选择样例或直接编辑 FinDSL。</p>
          </div>
          <span class="badge">Doris SQL</span>
        </div>
        <div class="section">
          <div class="field">
            <label for="nlInput">Natural language <span>NL2DSL candidate source</span></label>
            <textarea id="nlInput" spellcheck="false"></textarea>
          </div>
          <div class="controls">
            <span class="badge" id="suggestState">NL2DSL ready</span>
            <button class="secondary" id="suggestButton">Suggest DSL</button>
          </div>
          <div class="candidates" id="candidateList"></div>
          <div class="field">
            <label for="exampleSelect">Sample <span>official, negative, real_market</span></label>
            <select id="exampleSelect"></select>
          </div>
          <div class="field">
            <label for="dslInput">DSL <span>compiler-controlled input</span></label>
            <textarea id="dslInput" spellcheck="false"></textarea>
          </div>
          <div class="controls">
            <div class="checks">
              <label><input id="prefixToggle" type="checkbox" checked> Prefix sum</label>
              <label><input id="verifyToggle" type="checkbox" checked> Verify</label>
            </div>
            <button id="runButton">Run analysis</button>
          </div>
          <p class="small-note">负例样例会展示 Diagnostic，不会绕过 DSL 编译器直接执行 SQL。</p>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div class="panel-title">
            <h2>Result</h2>
            <p>SQL、AST、Explain、Rows、Evidence 和 Diagnostic 统一展示。</p>
          </div>
          <div class="panel-actions">
            <button class="ghost" id="copyButton" type="button">Copy SQL</button>
            <span id="resultState" class="badge">Waiting</span>
          </div>
        </div>
        <div class="section metrics">
          <div class="metric"><strong id="metricStatus">-</strong><span>verification</span></div>
          <div class="metric"><strong id="metricLatency">-</strong><span>compile latency</span></div>
          <div class="metric"><strong id="metricRows">-</strong><span>SQL rows</span></div>
          <div class="metric"><strong id="metricPrefix">-</strong><span>optimizer</span></div>
          <div class="metric"><strong id="metricDataset">-</strong><span>dataset</span></div>
        </div>
        <div class="tabs">
          <button class="tab active" data-tab="sql">SQL</button>
          <button class="tab" data-tab="ast">AST</button>
          <button class="tab" data-tab="explain">Explain</button>
          <button class="tab" data-tab="rows">Rows</button>
          <button class="tab" data-tab="evidence">Evidence</button>
          <button class="tab" data-tab="diagnostic">Diagnostic</button>
        </div>
        <div id="errorBox" class="error" hidden></div>
        <div id="outputPane" class="output"></div>
      </section>
    </div>
  </main>
  <script>
    const sampleSelect = document.getElementById("exampleSelect");
    const nlInput = document.getElementById("nlInput");
    const suggestButton = document.getElementById("suggestButton");
    const suggestState = document.getElementById("suggestState");
    const candidateList = document.getElementById("candidateList");
    const dslInput = document.getElementById("dslInput");
    const runButton = document.getElementById("runButton");
    const outputPane = document.getElementById("outputPane");
    const copyButton = document.getElementById("copyButton");
    const errorBox = document.getElementById("errorBox");
    const resultState = document.getElementById("resultState");
    const buildState = document.getElementById("buildState");
    const prefixToggle = document.getElementById("prefixToggle");
    const verifyToggle = document.getElementById("verifyToggle");
    const evidenceSpeed = document.getElementById("evidenceSpeed");
    const evidenceRows = document.getElementById("evidenceRows");
    let currentResult = null;
    let currentEvidence = null;
    let currentError = null;
    let currentTab = "sql";
    let currentExample = null;
    const defaultNlRequest = "__DEFAULT_NL_REQUEST__";

    function setState(text, ok) {
      resultState.textContent = text;
      buildState.textContent = text;
      resultState.className = "badge " + (ok ? "ok" : "fail");
      buildState.className = "badge " + (ok ? "ok" : "fail");
    }

    function pretty(value) {
      return JSON.stringify(value, null, 2);
    }

    function render() {
      errorBox.hidden = true;
      if (!currentResult || !currentResult.ok) {
        if (currentTab === "diagnostic" && currentError) {
          renderDiagnostic(currentError);
          return;
        }
        outputPane.replaceChildren(emptyState("Run an example to see compiler output."));
        return;
      }
      const compiled = currentResult.compile;
      if (currentTab === "sql") renderCode(compiled.sql);
      if (currentTab === "ast") renderCode(pretty(compiled.ast));
      if (currentTab === "explain") renderExplain(compiled.trace, compiled.explain);
      if (currentTab === "rows") renderRows(currentResult.verification);
      if (currentTab === "evidence") renderEvidence(currentEvidence);
      if (currentTab === "diagnostic") renderDiagnostic(currentError);
    }

    function renderCode(text) {
      const pre = document.createElement("pre");
      pre.textContent = text || "";
      outputPane.replaceChildren(pre);
    }

    function emptyState(text) {
      const wrap = document.createElement("div");
      wrap.className = "structured";
      const p = document.createElement("p");
      p.className = "empty";
      p.textContent = text;
      wrap.appendChild(p);
      return wrap;
    }

    function kvList(obj) {
      const dl = document.createElement("dl");
      dl.className = "kv";
      Object.entries(obj || {}).forEach(([key, value]) => {
        const dt = document.createElement("dt");
        const dd = document.createElement("dd");
        dt.textContent = key;
        dd.textContent = typeof value === "object" ? JSON.stringify(value) : String(value);
        dl.appendChild(dt);
        dl.appendChild(dd);
      });
      return dl;
    }

    function renderExplain(trace, explain) {
      const wrap = document.createElement("div");
      wrap.className = "structured timeline";
      if (!explain || !explain.length) {
        wrap.appendChild(emptyState("No explain records.").firstChild);
      } else {
        explain.forEach((step, index) => {
          const card = document.createElement("article");
          card.className = "step-card";
          const head = document.createElement("header");
          const title = document.createElement("h3");
          const badge = document.createElement("span");
          title.textContent = (index + 1) + ". " + step.rule;
          badge.className = "badge " + (step.status === "applied" || step.status === "passed" ? "ok" : "warn");
          badge.textContent = step.status;
          head.appendChild(title);
          head.appendChild(badge);
          const message = document.createElement("p");
          message.textContent = step.message || "";
          card.appendChild(head);
          card.appendChild(message);
          if (step.evidence) card.appendChild(kvList(step.evidence));
          wrap.appendChild(card);
        });
      }
      if (trace && trace.length) {
        const card = document.createElement("article");
        card.className = "step-card";
        const title = document.createElement("h3");
        title.textContent = "Trace";
        card.appendChild(title);
        card.appendChild(kvList(Object.fromEntries(trace.map((item, idx) => [String(idx + 1), item]))));
        wrap.appendChild(card);
      }
      outputPane.replaceChildren(wrap);
    }

    function renderRows(verification) {
      const wrap = document.createElement("div");
      wrap.className = "structured";
      if (!verification) {
        wrap.appendChild(emptyState("Verification skipped. Enable Verify and run again.").firstChild);
        outputPane.replaceChildren(wrap);
        return;
      }
      wrap.appendChild(kvList({
        passed: verification.passed,
        sql_row_count: verification.sql_row_count,
        reference_row_count: verification.reference_row_count,
        missing_keys: verification.missing_keys.length,
        extra_keys: verification.extra_keys.length
      }));
      const table = document.createElement("table");
      table.className = "data-table";
      table.innerHTML = "<thead><tr><th>#</th><th>Result key</th></tr></thead>";
      const tbody = document.createElement("tbody");
      (verification.result_keys || []).forEach((key, idx) => {
        const tr = document.createElement("tr");
        const c1 = document.createElement("td");
        const c2 = document.createElement("td");
        c1.textContent = String(idx + 1);
        c2.textContent = JSON.stringify(key);
        tr.appendChild(c1);
        tr.appendChild(c2);
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      wrap.appendChild(table);
      outputPane.replaceChildren(wrap);
    }

    function renderEvidence(evidence) {
      const wrap = document.createElement("div");
      wrap.className = "structured";
      if (!evidence || !evidence.available) {
        wrap.appendChild(emptyState("Doris evidence report is not available yet.").firstChild);
        outputPane.replaceChildren(wrap);
        return;
      }
      wrap.appendChild(kvList({
        report_path: evidence.path,
        evidence_passed: evidence.headline.passed,
        doris_speedup: evidence.headline.speedup,
        baseline_avg_ms: evidence.headline.baseline_avg_ms,
        optimized_avg_ms: evidence.headline.optimized_avg_ms,
        row_counts_match: evidence.headline.row_counts_match
      }));
      const details = document.createElement("pre");
      details.textContent = pretty(evidence.metrics || {});
      details.style.marginTop = "12px";
      wrap.appendChild(details);
      outputPane.replaceChildren(wrap);
    }

    function renderDiagnostic(error) {
      const wrap = document.createElement("div");
      wrap.className = "structured diagnostic-list";
      if (!error) {
        wrap.appendChild(emptyState("No diagnostic for the latest successful run.").firstChild);
        outputPane.replaceChildren(wrap);
        return;
      }
      const diagnostics = error.diagnostics || [];
      if (!diagnostics.length) {
        const card = document.createElement("article");
        card.className = "diagnostic-card";
        const title = document.createElement("h3");
        const p = document.createElement("p");
        title.textContent = error.type || "Error";
        p.textContent = error.message || "Unknown error";
        card.appendChild(title);
        card.appendChild(p);
        wrap.appendChild(card);
      }
      diagnostics.forEach(item => {
        const card = document.createElement("article");
        card.className = "diagnostic-card";
        const title = document.createElement("h3");
        const p = document.createElement("p");
        title.textContent = item.code || "DIAGNOSTIC";
        p.textContent = item.message || error.message || "";
        card.appendChild(title);
        card.appendChild(p);
        if (item.suggestions && item.suggestions.length) {
          const ul = document.createElement("ul");
          ul.className = "suggestion-list";
          item.suggestions.forEach(text => {
            const li = document.createElement("li");
            li.textContent = text;
            ul.appendChild(li);
          });
          card.appendChild(ul);
        }
        wrap.appendChild(card);
      });
      if (currentExample && currentExample.expected_code) {
        const card = document.createElement("article");
        card.className = "step-card";
        card.appendChild(kvList({
          "Expected diagnostic": currentExample.expected_code,
          "Actual diagnostic": diagnostics.map(item => item.code).filter(Boolean).join(", ") || "<none>"
        }));
        wrap.appendChild(card);
      }
      outputPane.replaceChildren(wrap);
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
      document.getElementById("metricPrefix").className = applied ? "status-ok" : "status-warn";
      document.getElementById("metricDataset").textContent = currentExample && currentExample.dataset_label ? currentExample.dataset_label : "sample fixtures";
    }

    function resetMetrics(status) {
      document.getElementById("metricStatus").textContent = status;
      document.getElementById("metricStatus").className = status === "ERROR" ? "status-fail" : "";
      document.getElementById("metricLatency").textContent = "-";
      document.getElementById("metricRows").textContent = "-";
      document.getElementById("metricPrefix").textContent = "-";
      document.getElementById("metricDataset").textContent = currentExample && currentExample.dataset_label ? currentExample.dataset_label : "-";
    }

    function selectExample(index) {
      currentExample = sampleSelect.options[index] ? JSON.parse(sampleSelect.options[index].dataset.example) : null;
      if (!currentExample) return;
      sampleSelect.value = String(index);
      dslInput.value = currentExample.dsl;
      candidateList.replaceChildren();
      currentResult = null;
      currentError = null;
      currentTab = "sql";
      setActiveTab("sql");
      resetMetrics("READY");
      setState("Ready", true);
      render();
      if (currentExample.kind === "official_negative") {
        suggestState.textContent = "Diagnostic preset";
        verifyToggle.checked = false;
      } else if (currentExample.kind === "real_market") {
        suggestState.textContent = currentExample.dataset_label || "Real-market sample";
        verifyToggle.checked = true;
      } else if (currentExample.kind === "official_positive") {
        suggestState.textContent = currentExample.scenario || "Official preset";
        verifyToggle.checked = true;
      } else {
        suggestState.textContent = "Evaluation preset";
        verifyToggle.checked = true;
      }
    }

    function applyCandidate(candidate, runAfterApply) {
      currentExample = null;
      dslInput.value = candidate.dsl;
      currentTab = "sql";
      document.querySelectorAll(".tab").forEach(item => item.classList.toggle("active", item.dataset.tab === "sql"));
      if (runAfterApply) run();
    }

    function renderCandidates(candidates) {
      candidateList.replaceChildren();
      candidates.forEach((candidate, idx) => {
        const button = document.createElement("button");
        button.className = "candidate" + (candidate.validated ? " validated" : "");
        button.type = "button";
        const title = document.createElement("strong");
        title.textContent = (idx + 1) + ". " + candidate.rule + " - " + Math.round(candidate.confidence * 100) + "% - " + (candidate.validated ? "validated" : "needs review");
        const dsl = document.createElement("span");
        dsl.textContent = candidate.dsl;
        button.appendChild(title);
        button.appendChild(dsl);
        button.addEventListener("click", () => applyCandidate(candidate, true));
        candidateList.appendChild(button);
      });
    }

    async function suggest() {
      suggestButton.disabled = true;
      suggestState.textContent = "Suggesting";
      try {
        const res = await fetch("/api/suggest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: nlInput.value,
            dataset: "default",
            enable_prefix_sum: prefixToggle.checked,
            verify: verifyToggle.checked
          })
        });
        const data = await res.json();
        if (!data.ok) {
          throw new Error(formatError(data.error));
        }
        renderCandidates(data.candidates);
        if (!data.candidates.length) {
          suggestState.textContent = data.warnings.length ? data.warnings[0] : "No candidate";
          currentResult = null;
          outputPane.textContent = "";
          resetMetrics("No candidate");
          setState("No candidate", false);
          return;
        }
        suggestState.textContent = data.candidates[0].validated ? "Validated" : "Candidate ready";
        applyCandidate(data.candidates[0], false);
        if (data.candidates[0].analysis) {
          currentResult = data.candidates[0].analysis;
          updateMetrics(currentResult);
          setState(currentResult.verification && !currentResult.verification.passed ? "Failed" : "Passed", !(currentResult.verification && !currentResult.verification.passed));
          render();
        } else {
          await run();
        }
      } catch (err) {
        candidateList.replaceChildren();
        suggestState.textContent = "Suggest error";
        errorBox.hidden = false;
        errorBox.textContent = err.message;
        currentResult = null;
        currentError = { type: "SuggestError", message: err.message, diagnostics: [] };
        currentTab = "diagnostic";
        setActiveTab("diagnostic");
        renderDiagnostic(currentError);
        resetMetrics("ERROR");
        setState("Error", false);
      } finally {
        suggestButton.disabled = false;
      }
    }

    async function loadExamples() {
      const res = await fetch("/api/examples");
      const data = await res.json();
      sampleSelect.replaceChildren();
      data.examples.forEach((item, idx) => {
        const option = document.createElement("option");
        option.value = String(idx);
        option.dataset.example = JSON.stringify(item);
        const suffix = item.expected_code ? " [" + item.expected_code + "]" : item.scenario ? " [" + item.scenario + "]" : "";
        const dataset = item.dataset_label ? " - " + item.dataset_label : "";
        option.textContent = item.name + suffix + dataset;
        sampleSelect.appendChild(option);
      });
      selectExample(0);
    }

    async function loadEvidence() {
      const res = await fetch("/api/evidence");
      const data = await res.json();
      currentEvidence = data.evidence;
      if (currentEvidence && currentEvidence.available) {
        document.getElementById("metricEvidence").textContent = currentEvidence.headline.passed === "True" ? "PASS" : currentEvidence.headline.passed;
        document.getElementById("metricSpeedup").textContent = currentEvidence.headline.speedup || "-";
        document.getElementById("metricParity").textContent = currentEvidence.headline.row_counts_match === "True" ? "MATCH" : currentEvidence.headline.row_counts_match;
        evidenceSpeed.textContent = "Doris speedup " + (currentEvidence.headline.speedup || "-");
        evidenceRows.textContent = "Rows " + (currentEvidence.headline.row_counts_match === "True" ? "match" : currentEvidence.headline.row_counts_match);
        evidenceSpeed.className = "badge ok";
        evidenceRows.className = "badge ok";
      } else {
        document.getElementById("metricEvidence").textContent = "Missing";
        document.getElementById("metricSpeedup").textContent = "-";
        document.getElementById("metricParity").textContent = "-";
        evidenceSpeed.textContent = "Doris evidence missing";
        evidenceRows.textContent = "Rows unknown";
        evidenceSpeed.className = "badge warn";
        evidenceRows.className = "badge warn";
      }
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
            dataset: currentExample && currentExample.dataset ? currentExample.dataset : "default",
            enable_prefix_sum: prefixToggle.checked,
            verify: verifyToggle.checked
          })
        });
        const data = await res.json();
        if (!data.ok) {
          throw new Error(formatError(data.error));
        }
        currentResult = data;
        currentError = null;
        updateMetrics(data);
        setState(data.verification && !data.verification.passed ? "Failed" : "Passed", !(data.verification && !data.verification.passed));
        render();
      } catch (err) {
        currentResult = null;
        currentError = errorFromMessage(err.message);
        errorBox.hidden = false;
        errorBox.textContent = err.message;
        currentTab = "diagnostic";
        setActiveTab("diagnostic");
        renderDiagnostic(currentError);
        resetMetrics("ERROR");
        setState(currentExample && currentExample.kind === "official_negative" ? "Diagnostic" : "Error", false);
      } finally {
        runButton.disabled = false;
      }
    }

    function formatError(error) {
      const diagnostics = error.diagnostics || [];
      const suggestions = diagnostics.flatMap(item => item.suggestions || []);
      const unique = Array.from(new Set(suggestions));
      const codes = diagnostics.map(item => item.code).filter(Boolean);
      const expected = currentExample && currentExample.expected_code ? "\\nExpected diagnostic: " + currentExample.expected_code : "";
      const actual = codes.length ? "\\nActual diagnostic: " + codes.join(", ") : "";
      if (!unique.length) return error.type + ": " + error.message + expected + actual;
      return error.type + ": " + error.message + expected + actual + "\\n\\nSuggestions:\\n- " + unique.join("\\n- ");
    }

    function errorFromMessage(message) {
      const actual = (message.match(/Actual diagnostic: ([^\\n]+)/) || [])[1];
      const suggestions = message.includes("Suggestions:")
        ? message.split("Suggestions:").slice(1).join("Suggestions:").split("\\n").map(line => line.replace(/^- /, "").trim()).filter(Boolean)
        : [];
      return {
        type: "Diagnostic",
        message,
        diagnostics: actual ? [{ code: actual, message, suggestions }] : []
      };
    }

    function setActiveTab(tab) {
      document.querySelectorAll(".tab").forEach(item => item.classList.toggle("active", item.dataset.tab === tab));
    }

    document.querySelectorAll(".tab").forEach(button => {
      button.addEventListener("click", () => {
        setActiveTab(button.dataset.tab);
        currentTab = button.dataset.tab;
        render();
      });
    });
    copyButton.addEventListener("click", async () => {
      const sql = currentResult && currentResult.compile ? currentResult.compile.sql : "";
      if (!sql) return;
      await navigator.clipboard.writeText(sql);
      copyButton.textContent = "Copied";
      setTimeout(() => { copyButton.textContent = "Copy SQL"; }, 1200);
    });
    sampleSelect.addEventListener("change", () => { selectExample(Number(sampleSelect.value)); });
    suggestButton.addEventListener("click", suggest);
    runButton.addEventListener("click", run);
    nlInput.value = defaultNlRequest;
    Promise.all([loadExamples(), loadEvidence()]).then(suggest);
  </script>
</body>
</html>"""
    return html.replace('"__DEFAULT_NL_REQUEST__"', json.dumps(DEFAULT_NL_REQUEST, ensure_ascii=False))

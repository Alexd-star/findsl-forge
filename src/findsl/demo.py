from __future__ import annotations

import json
import traceback
from functools import lru_cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List

from .compiler import Compiler
from .diagnostics import diagnose_exception
from .equivalence import verify_sql_equivalence
from .evaluation import load_cases
from .nl2dsl import suggest_dsl
from .official.service import OfficialCompilerService
from .official_suite import DEFAULT_NEGATIVE_CASES, DEFAULT_POSITIVE_CASES


DEFAULT_DEMO_DSL = (
    'then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), '
    'rank(indicator("turnover_rate"), desc, top=100))'
)
DEFAULT_NL_REQUEST = "筛选A股连续3天主力净流入为正的股票，并按换手率从高到低排名前100"
DEMO_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REAL_MARKET_CASES = DEMO_REPO_ROOT / "data/real_samples/eastmoney_a_share_sample/queries.jsonl"
DEFAULT_REAL_MARKET_DATA_DIR = DEMO_REPO_ROOT / "data/real_samples/eastmoney_a_share_sample"
DEFAULT_OFFICIAL_DEMO_CASES = DEMO_REPO_ROOT / "data/samples/official_slot_demo.jsonl"
DEFAULT_EVIDENCE_METADATA = DEMO_REPO_ROOT / "submission_artifacts/evidence_metadata.json"


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


def delivery_evidence_summary(
    metadata_path: Path = DEFAULT_EVIDENCE_METADATA,
) -> Dict[str, Any]:
    metadata_path = _resolve_demo_path(metadata_path)
    if not metadata_path.exists():
        return {
            "available": False,
            "path": str(metadata_path),
            "message": "Versioned delivery metadata is not available yet.",
        }
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "available": False,
            "path": str(metadata_path),
            "message": f"Versioned delivery metadata could not be read: {exc}",
        }
    readiness = payload.get("readiness") or {}
    migration = payload.get("official_migration") or {}
    pytest = readiness.get("pytest") or {}
    git = payload.get("git") or {}
    return {
        "available": True,
        "path": str(metadata_path),
        "blocking_gates_passed": readiness.get("blocking_gates_passed"),
        "warning_count": readiness.get("warning_count"),
        "pytest_passed": pytest.get("passed"),
        "legacy_strict_success": migration.get("legacy_strict_success"),
        "legacy_to_new_migrated": migration.get("legacy_to_new_migrated"),
        "migration_coverage": migration.get("migration_coverage"),
        "new_backend_success": migration.get("new_backend_success"),
        "git_head": git.get("head_at_report_generation"),
        "metadata_warnings": payload.get("warnings") or [],
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
    payload = _official_service().compile(dsl)["result"]
    payload["pipeline"] = "official-antlr-ir-sqlglot"
    return payload


@lru_cache(maxsize=1)
def _official_service() -> OfficialCompilerService:
    return OfficialCompilerService()


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


def official_demo_examples(
    cases_path: Path = DEFAULT_OFFICIAL_DEMO_CASES,
) -> List[Dict[str, Any]]:
    return _safe_load_cases(_resolve_demo_path(cases_path))


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
            if self.path == "/favicon.ico":
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return
            if self.path == "/api/examples":
                self._send_json({"ok": True, "examples": demo_examples(cases_path)})
                return
            if self.path == "/api/official/examples":
                self._send_json({"ok": True, "examples": official_demo_examples()})
                return
            if self.path == "/api/evidence":
                self._send_json(
                    {
                        "ok": True,
                        "evidence": doris_evidence_summary(),
                        "delivery": delivery_evidence_summary(),
                    }
                )
                return
            self._send_json({"ok": False, "error": {"message": "Not found"}}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler.
            if self.path not in {
                "/api/analyze",
                "/api/suggest",
                "/api/official/analyze",
                "/api/official/preview",
            }:
                self._send_json({"ok": False, "error": {"message": "Not found"}}, HTTPStatus.NOT_FOUND)
                return
            try:
                request = self._read_json()
                if self.path in {"/api/official/analyze", "/api/official/preview"}:
                    dsl = str(request.get("dsl", "")).strip()
                    if not dsl:
                        raise ValueError("Official DSL is required")
                    if self.path == "/api/official/preview":
                        try:
                            self._send_json(analyze_official_dsl(dsl))
                        except Exception as exc:  # noqa: BLE001 - preview returns diagnostics as content.
                            self._send_json({"ok": False, "error": _error_payload(exc)})
                    else:
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
      --muted: #526469;
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
      --focus: rgba(15, 118, 110, 0.22);
    }
    * { box-sizing: border-box; min-width: 0; }
    [hidden] { display: none !important; }
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
    h1 { font-size: 20px; margin: 0; font-weight: 800; letter-spacing: 0; }
    .brand p { margin: 0; color: var(--muted); font-size: 12px; }
    .top-metrics { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
    main { padding: 18px 24px 24px; max-width: 1680px; margin: 0 auto; }
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
    }
    .brief h2 { margin: 0 0 6px; font-size: 16px; }
    .brief p { margin: 0; color: var(--muted); max-width: 84ch; overflow-wrap: anywhere; }
    .evidence-ribbon { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
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
    .pipeline-switch {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 4px;
      padding: 4px;
      margin-bottom: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #eef3f4;
    }
    .mode-button {
      height: 38px;
      background: transparent;
      color: var(--muted);
      border: 0;
      border-radius: 6px;
      box-shadow: none;
    }
    .mode-button:hover { background: #e2ebed; color: var(--ink); }
    .mode-button.active {
      background: var(--panel);
      color: var(--accent-deep);
      box-shadow: 0 1px 4px rgba(18, 36, 42, 0.14);
    }
    .mode-context {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      margin: -4px 0 14px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
    }
    .mode-context strong { color: var(--ink); white-space: nowrap; }
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
    button:disabled { cursor: wait; opacity: 0.62; transform: none; }
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
    .output {
      height: clamp(420px, 62vh, 760px);
      min-height: 0;
      overflow: auto;
      overscroll-behavior: contain;
      background: #fff;
      scrollbar-gutter: stable;
    }
    pre {
      margin: 0;
      padding: 14px;
      background: var(--code);
      color: #e5e7eb;
      font: 12px/1.55 "Cascadia Mono", Consolas, monospace;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .output > pre, .output > .structured { min-height: 100%; }
    .structured { padding: 14px; background: #fff; }
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
    .kv dd { margin: 0; font-family: "Cascadia Mono", Consolas, monospace; }
    .stage-summary {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
      gap: 8px;
      margin-bottom: 12px;
    }
    .stage-summary .metric { min-height: 54px; }
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
    details { border-top: 1px solid var(--line); padding-top: 10px; }
    summary { color: var(--accent-deep); font-weight: 700; cursor: pointer; }
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
      .output { height: clamp(360px, 58vh, 560px); }
    }
    @media (max-width: 640px) {
      .evidence-ribbon, .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
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
    @media (min-width: 961px) {
      .shell > .panel:first-child { position: sticky; top: 88px; }
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
      <span class="badge ok" id="buildState">正在读取交付状态</span>
      <span class="badge" id="evidenceSpeed">正在读取 Doris 证据</span>
      <span class="badge" id="evidenceRows">结果一致性待读取</span>
    </div>
  </div>
  <main>
    <section class="hero-strip">
      <div class="brief">
        <h2>确定性编译与审计链路</h2>
        <p>内部验证管线用于演示自然语言候选、参考执行器和前缀优化；官方赛题管线展示七槽 DSL 从 ANTLR、Typed AST、Logical IR、Physical IR 到 Doris SQL 的完整过程。两条管线均拒绝大模型直接 SQL。</p>
      </div>
      <div class="evidence-ribbon">
        <div class="metric"><strong id="metricMigration">-</strong><span>官方严格迁移</span></div>
        <div class="metric"><strong id="metricTests">-</strong><span>自动测试</span></div>
        <div class="metric"><strong id="metricSpeedup">-</strong><span>Doris 加速</span></div>
        <div class="metric"><strong id="metricParity">-</strong><span>结果集一致性</span></div>
      </div>
    </section>
    <div class="shell">
      <section class="panel">
        <div class="panel-head">
          <div class="panel-title">
            <h2 id="workbenchTitle">官方赛题编译工作台</h2>
            <p id="workbenchSubtitle">七槽 DSL 的 ANTLR、IR 与 SQLGlot 全阶段审计。</p>
          </div>
          <span class="badge" id="pipelineBadge">内部 DSL</span>
        </div>
        <div class="section">
          <div class="pipeline-switch" role="tablist" aria-label="编译管线">
            <button class="mode-button" id="internalModeButton" type="button" role="tab" aria-selected="false">内部验证管线</button>
            <button class="mode-button active" id="officialModeButton" type="button" role="tab" aria-selected="true">官方赛题管线</button>
          </div>
          <div class="mode-context" id="modeContext"><strong>当前：</strong><span>自然语言候选经过内部编译器与参考执行器双重验证。</span></div>
          <div id="nlSection">
            <div class="field">
              <label for="nlInput">中文选股需求 <span>生成受限 DSL 候选</span></label>
              <textarea id="nlInput" spellcheck="false"></textarea>
            </div>
            <div class="controls">
              <span class="badge" id="suggestState">候选生成就绪</span>
              <button class="secondary" id="suggestButton">生成 DSL 候选</button>
            </div>
            <div class="candidates" id="candidateList"></div>
          </div>
          <div class="field">
            <label for="exampleSelect">验证样例 <span id="sampleHint">正例、负例与真实行情样本</span></label>
            <select id="exampleSelect"></select>
          </div>
          <div class="field">
            <label for="dslInput"><span id="dslLabel">FinDSL</span> <span id="dslHint">编译器受控输入</span></label>
            <textarea id="dslInput" spellcheck="false"></textarea>
          </div>
          <div class="controls">
            <div class="checks" id="internalControls">
              <label><input id="prefixToggle" type="checkbox" checked> Prefix sum</label>
              <label><input id="verifyToggle" type="checkbox" checked> 独立参考验证</label>
            </div>
            <button id="runButton">执行编译分析</button>
          </div>
          <p class="small-note" id="workbenchNote">负例会展示稳定诊断码，不会绕过 DSL 编译器直接执行 SQL。</p>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div class="panel-title">
            <h2>编译结果</h2>
            <p id="resultSubtitle">SQL、AST、优化说明、结果与证据统一展示。</p>
          </div>
          <div class="panel-actions">
            <button class="ghost" id="copyButton" type="button" disabled title="执行成功后可复制 SQL">复制 SQL</button>
            <span id="resultState" class="badge" role="status" aria-live="polite">等待执行</span>
          </div>
        </div>
        <div class="section metrics">
          <div class="metric"><strong id="metricStatus">-</strong><span>验证状态</span></div>
          <div class="metric"><strong id="metricLatency">-</strong><span>编译耗时</span></div>
          <div class="metric"><strong id="metricRows">-</strong><span id="metricRowsLabel">结果行数</span></div>
          <div class="metric"><strong id="metricPrefix">-</strong><span>执行策略</span></div>
          <div class="metric"><strong id="metricDataset">-</strong><span>数据口径</span></div>
        </div>
        <div class="tabs" role="tablist" aria-label="结果阶段">
          <button class="tab active" data-tab="sql" role="tab" aria-selected="true" aria-controls="outputPane" tabindex="0">Doris SQL</button>
          <button class="tab" data-tab="ast" role="tab" aria-selected="false" aria-controls="outputPane" tabindex="-1">AST</button>
          <button class="tab official-tab" data-tab="logical" role="tab" aria-selected="false" aria-controls="outputPane" tabindex="-1" hidden>逻辑 IR</button>
          <button class="tab official-tab" data-tab="physical" role="tab" aria-selected="false" aria-controls="outputPane" tabindex="-1" hidden>物理 IR</button>
          <button class="tab" data-tab="explain" role="tab" aria-selected="false" aria-controls="outputPane" tabindex="-1">编译轨迹</button>
          <button class="tab internal-tab" data-tab="rows" role="tab" aria-selected="false" aria-controls="outputPane" tabindex="-1">结果行</button>
          <button class="tab" data-tab="evidence" role="tab" aria-selected="false" aria-controls="outputPane" tabindex="-1">交付证据</button>
          <button class="tab" data-tab="diagnostic" role="tab" aria-selected="false" aria-controls="outputPane" tabindex="-1">诊断</button>
        </div>
        <div id="errorBox" class="error" role="alert" hidden></div>
        <div id="outputPane" class="output" tabindex="0" aria-label="编译结果内容"></div>
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
    const internalModeButton = document.getElementById("internalModeButton");
    const officialModeButton = document.getElementById("officialModeButton");
    const nlSection = document.getElementById("nlSection");
    const internalControls = document.getElementById("internalControls");
    let currentResult = null;
    let currentEvidence = null;
    let currentDelivery = null;
    let currentError = null;
    let currentTab = "sql";
    let currentExample = null;
    let currentMode = "official";
    let modeGeneration = 0;
    let exampleLoadToken = 0;
    const defaultNlRequest = "__DEFAULT_NL_REQUEST__";

    function setState(text, ok) {
      resultState.textContent = text;
      resultState.className = "badge " + (ok ? "ok" : "fail");
    }
    function pretty(value) {
      return JSON.stringify(value, null, 2);
    }

    function render() {
      errorBox.hidden = true;
      const hasSql = Boolean(currentResult && currentResult.compile && currentResult.compile.sql);
      copyButton.disabled = !hasSql;
      copyButton.title = hasSql ? "复制当前 Doris SQL" : "执行成功后可复制 SQL";
      if (!currentResult || !currentResult.ok) {
        if (currentTab === "diagnostic" && currentError) {
          renderDiagnostic(currentError);
          return;
        }
        outputPane.replaceChildren(emptyState(currentMode === "official" ? "选择官方样例并执行编译，查看完整 IR 与 Doris SQL。" : "选择样例或生成 DSL 候选后执行分析。"));
        return;
      }
      const compiled = currentResult.compile;
      if (currentTab === "sql") renderCode(compiled.sql);
      if (currentTab === "ast") {
        renderCode(pretty(currentResult.official ? {
          frontend: currentResult.official.frontend,
          typed_ast: currentResult.official.typed_ast
        } : compiled.ast));
      }
      if (currentTab === "logical") renderCode(pretty({
        logical: currentResult.official && currentResult.official.logical,
        optimized: currentResult.official && currentResult.official.optimized
      }));
      if (currentTab === "physical") renderCode(pretty(currentResult.official && currentResult.official.physical));
      if (currentTab === "explain") {
        if (currentResult.official) renderOfficialStages(currentResult.official);
        else renderExplain(compiled.trace, compiled.explain);
      }
      if (currentTab === "rows") renderRows(currentResult.verification);
      if (currentTab === "evidence") renderEvidence(currentEvidence, currentDelivery);
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
        wrap.appendChild(emptyState("本次编译没有优化轨迹记录。").firstChild);
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

    function renderOfficialStages(result) {
      const wrap = document.createElement("div");
      wrap.className = "structured";
      const summary = document.createElement("div");
      summary.className = "stage-summary";
      const stages = [
        ["ANTLR 前端", result.frontend && result.frontend.ok, result.frontend && result.frontend.elapsed_ns],
        ["Typed AST", Boolean(result.typed_ast), null],
        ["Logical IR", Boolean(result.logical), result.logical && result.logical.elapsed_ns],
        ["优化器", Boolean(result.optimized), null],
        ["Physical IR", Boolean(result.physical), result.physical && result.physical.elapsed_ns],
        ["SQLGlot 后端", result.backend && result.backend.validation_passed, result.backend && result.backend.elapsed_ns]
      ];
      stages.forEach(([name, passed, elapsed]) => {
        const item = document.createElement("div");
        item.className = "metric";
        const strong = document.createElement("strong");
        strong.className = passed ? "status-ok" : "status-fail";
        strong.textContent = passed ? "PASS" : "待核验";
        const label = document.createElement("span");
        label.textContent = name + (elapsed ? " · " + (elapsed / 1000000).toFixed(3) + " ms" : "");
        item.appendChild(strong);
        item.appendChild(label);
        summary.appendChild(item);
      });
      wrap.appendChild(summary);
      const decisions = result.physical && result.physical.decisions ? result.physical.decisions : [];
      if (decisions.length) {
        decisions.forEach((decision, index) => {
          const card = document.createElement("article");
          card.className = "step-card";
          const title = document.createElement("h3");
          title.textContent = (index + 1) + ". " + (decision.reason_code || decision.strategy_id || "物理决策");
          const body = document.createElement("p");
          body.textContent = decision.reason || "";
          card.appendChild(title);
          card.appendChild(body);
          card.appendChild(kvList(decision));
          wrap.appendChild(card);
        });
      }
      outputPane.replaceChildren(wrap);
    }

    function renderRows(verification) {
      const wrap = document.createElement("div");
      wrap.className = "structured";
      if (!verification) {
        wrap.appendChild(emptyState("本次未执行独立参考验证，请启用验证后重新运行。").firstChild);
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

    function renderEvidence(evidence, delivery) {
      const wrap = document.createElement("div");
      wrap.className = "structured";
      if (delivery && delivery.available) {
        wrap.appendChild(kvList({
          "Blocking gates": delivery.blocking_gates_passed ? "PASS" : "FAIL",
          "Warning count": delivery.warning_count,
          "Pytest": delivery.pytest_passed + " passed",
          "官方严格迁移": delivery.legacy_to_new_migrated + "/" + delivery.legacy_strict_success,
          "新后端总成功": delivery.new_backend_success,
          "证据 Git HEAD": delivery.git_head,
          "Metadata warnings": (delivery.metadata_warnings || []).length
        }));
      }
      if (evidence && evidence.available) {
        wrap.appendChild(kvList({
          "Doris 证据报告": evidence.path,
          "证据状态": evidence.headline.passed,
          "集群加速": evidence.headline.speedup,
          "基线平均耗时": evidence.headline.baseline_avg_ms,
          "优化平均耗时": evidence.headline.optimized_avg_ms,
          "结果行一致": evidence.headline.row_counts_match
        }));
        const details = document.createElement("pre");
        details.textContent = pretty(evidence.metrics || {});
        details.style.marginTop = "12px";
        wrap.appendChild(details);
      }
      if ((!delivery || !delivery.available) && (!evidence || !evidence.available)) {
        wrap.appendChild(emptyState("尚未生成版本化交付证据。请先运行 submission_readiness 和证据导出脚本。").firstChild);
      }
      outputPane.replaceChildren(wrap);
    }

    function renderDiagnostic(error) {
      const wrap = document.createElement("div");
      wrap.className = "structured diagnostic-list";
      if (!error) {
        wrap.appendChild(emptyState("最近一次编译成功，没有诊断信息。").firstChild);
        outputPane.replaceChildren(wrap);
        return;
      }
      const diagnostics = (error.diagnostics || []).filter(
        item => item.code || (item.suggestions && item.suggestions.length)
      );
      if (!diagnostics.length) {
        const card = document.createElement("article");
        card.className = "diagnostic-card";
        const title = document.createElement("h3");
        const p = document.createElement("p");
        title.textContent = error.code || error.type || "编译错误";
        p.textContent = error.message || "未知编译错误";
        card.appendChild(title);
        card.appendChild(p);
        if (error.stage || error.code) {
          card.appendChild(kvList({
            "失败阶段": error.stage || "未知",
            "稳定诊断码": error.code || "未提供"
          }));
        }
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
        const actualCodes = [error.code, ...diagnostics.map(item => item.code)].filter(Boolean);
        card.appendChild(kvList({
          "预期诊断码": currentExample.expected_code,
          "实际诊断码": actualCodes.join(", ") || "<none>"
        }));
        wrap.appendChild(card);
      }
      if (error.partial) {
        const details = document.createElement("details");
        const summary = document.createElement("summary");
        const pre = document.createElement("pre");
        summary.textContent = "查看失败前已生成的编译阶段";
        pre.textContent = pretty(error.partial);
        details.appendChild(summary);
        details.appendChild(pre);
        wrap.appendChild(details);
      }
      outputPane.replaceChildren(wrap);
    }

    function updateMetrics(result) {
      if (result.official) {
        const strategy = result.official.physical && result.official.physical.selected_strategy;
        document.getElementById("metricStatus").textContent = "PASS";
        document.getElementById("metricStatus").className = "status-ok";
        document.getElementById("metricLatency").textContent = result.compile.elapsed_ms.toFixed(3) + " ms";
        document.getElementById("metricRows").textContent = "未执行";
        document.getElementById("metricRowsLabel").textContent = "浏览器执行边界";
        document.getElementById("metricPrefix").textContent = strategy || "physical";
        document.getElementById("metricPrefix").className = "status-ok";
        document.getElementById("metricDataset").textContent = "官方 Doris 表结构";
        return;
      }
      const verification = result.verification;
      const passed = verification ? verification.passed : null;
      document.getElementById("metricStatus").textContent = passed === null ? "未执行" : passed ? "PASS" : "FAIL";
      document.getElementById("metricStatus").className = passed === false ? "status-fail" : "status-ok";
      document.getElementById("metricLatency").textContent = result.compile.elapsed_ms.toFixed(3) + " ms";
      document.getElementById("metricRows").textContent = verification ? verification.sql_row_count : "-";
      document.getElementById("metricRowsLabel").textContent = "结果行数";
      const applied = result.compile.explain.some(step => step.rule === "PREFIX_SUM" && step.status === "applied");
      document.getElementById("metricPrefix").textContent = applied ? "已应用" : "未应用";
      document.getElementById("metricPrefix").className = applied ? "status-ok" : "status-warn";
      document.getElementById("metricDataset").textContent = currentExample && currentExample.dataset_label ? currentExample.dataset_label : "sample fixtures";
    }

    function resetMetrics(status) {
      document.getElementById("metricStatus").textContent = status;
      document.getElementById("metricStatus").className = status === "ERROR" ? "status-fail" : "";
      document.getElementById("metricLatency").textContent = "-";
      document.getElementById("metricRows").textContent = "-";
      document.getElementById("metricRowsLabel").textContent = currentMode === "official" ? "浏览器执行边界" : "结果行数";
      document.getElementById("metricPrefix").textContent = "-";
      document.getElementById("metricDataset").textContent = currentExample && currentExample.dataset_label ? currentExample.dataset_label : "-";
    }

    function normalizeOfficialResult(result) {
      const elapsedNs = [
        result.frontend && result.frontend.elapsed_ns,
        result.logical && result.logical.elapsed_ns,
        result.physical && result.physical.elapsed_ns,
        result.backend && result.backend.elapsed_ns
      ].filter(value => typeof value === "number").reduce((sum, value) => sum + value, 0);
      return {
        ok: true,
        official: result,
        compile: {
          elapsed_ms: elapsedNs / 1000000,
          ast: result.frontend && result.frontend.ast,
          sql: result.backend && result.backend.sql || "",
          trace: [],
          explain: []
        },
        verification: null
      };
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
      setState("就绪", true);
      render();
      if (currentMode === "official") {
        suggestState.textContent = currentExample.expected_status === "error" ? "官方诊断样例" : "官方编译样例";
        verifyToggle.checked = false;
      } else if (currentExample.kind === "official_negative") {
        suggestState.textContent = "诊断样例";
        verifyToggle.checked = false;
      } else if (currentExample.kind === "real_market") {
        suggestState.textContent = currentExample.dataset_label || "真实行情样本";
        verifyToggle.checked = true;
      } else if (currentExample.kind === "official_positive") {
        suggestState.textContent = currentExample.scenario || "验证正例";
        verifyToggle.checked = true;
      } else {
        suggestState.textContent = "评测样例";
        verifyToggle.checked = true;
      }
    }

    function setMode(mode) {
      modeGeneration += 1;
      currentMode = mode;
      const official = mode === "official";
      runButton.disabled = false;
      suggestButton.disabled = false;
      internalModeButton.classList.toggle("active", !official);
      officialModeButton.classList.toggle("active", official);
      internalModeButton.setAttribute("aria-selected", String(!official));
      officialModeButton.setAttribute("aria-selected", String(official));
      internalModeButton.tabIndex = official ? -1 : 0;
      officialModeButton.tabIndex = official ? 0 : -1;
      nlSection.hidden = official;
      internalControls.hidden = official;
      document.querySelectorAll(".official-tab").forEach(item => { item.hidden = !official; });
      document.querySelectorAll(".internal-tab").forEach(item => { item.hidden = official; });
      document.getElementById("workbenchTitle").textContent = official ? "官方赛题编译工作台" : "内部验证工作台";
      document.getElementById("workbenchSubtitle").textContent = official
        ? "七槽 DSL 的 ANTLR、IR 与 SQLGlot 全阶段审计。"
        : "中文需求、候选 FinDSL 与独立参考验证。";
      document.getElementById("pipelineBadge").textContent = official ? "ANTLR / IR" : "内部 DSL";
      document.getElementById("modeContext").querySelector("span").textContent = official
        ? "官方七槽 DSL 只编译为经过验证的 Doris SQL；缺失数据域会返回稳定诊断。"
        : "自然语言候选经过内部编译器与参考执行器双重验证。";
      document.getElementById("sampleHint").textContent = official ? "官方资源、排名、市场与数据缺失样例" : "正例、负例与真实行情样本";
      document.getElementById("dslLabel").textContent = official ? "官方七槽 DSL" : "FinDSL";
      document.getElementById("dslHint").textContent = official ? "ANTLR 前端受控输入" : "编译器受控输入";
      document.getElementById("workbenchNote").textContent = official
        ? "页面执行编译与验证，不在浏览器中直接查询生产 Doris；真实执行证据可在“交付证据”查看。"
        : "负例会展示稳定诊断码，不会绕过 DSL 编译器直接执行 SQL。";
      document.getElementById("resultSubtitle").textContent = official
        ? "Typed AST、Logical IR、Physical IR、Doris SQL 与失败阶段统一展示。"
        : "SQL、AST、优化说明、结果与证据统一展示。";
      currentTab = "sql";
      setActiveTab("sql");
      currentResult = null;
      currentError = null;
      candidateList.replaceChildren();
      resetMetrics("就绪");
      render();
      loadExamples();
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
        title.textContent = (idx + 1) + ". " + candidate.rule + " · " + Math.round(candidate.confidence * 100) + "% · " + (candidate.validated ? "已验证" : "待复核");
        const dsl = document.createElement("span");
        dsl.textContent = candidate.dsl;
        button.appendChild(title);
        button.appendChild(dsl);
        button.addEventListener("click", () => applyCandidate(candidate, true));
        candidateList.appendChild(button);
      });
    }

    async function suggest() {
      if (currentMode !== "internal") return;
      const generation = modeGeneration;
      suggestButton.disabled = true;
      suggestState.textContent = "正在生成";
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
        if (generation !== modeGeneration || currentMode !== "internal") return;
        if (!data.ok) {
          throw new Error(formatError(data.error));
        }
        renderCandidates(data.candidates);
        if (!data.candidates.length) {
          suggestState.textContent = data.warnings.length ? data.warnings[0] : "没有可用候选";
          currentResult = null;
          outputPane.textContent = "";
          resetMetrics("无候选");
          setState("无候选", false);
          return;
        }
        suggestState.textContent = data.candidates[0].validated ? "候选已验证" : "候选待复核";
        applyCandidate(data.candidates[0], false);
        if (data.candidates[0].analysis) {
          currentResult = data.candidates[0].analysis;
          updateMetrics(currentResult);
          setState(currentResult.verification && !currentResult.verification.passed ? "验证失败" : "验证通过", !(currentResult.verification && !currentResult.verification.passed));
          render();
        } else {
          await run();
        }
      } catch (err) {
        if (generation !== modeGeneration || currentMode !== "internal") return;
        candidateList.replaceChildren();
        suggestState.textContent = "候选生成失败";
        errorBox.hidden = false;
        errorBox.textContent = err.message;
        currentResult = null;
        currentError = { type: "SuggestError", message: err.message, diagnostics: [] };
        currentTab = "diagnostic";
        setActiveTab("diagnostic");
        renderDiagnostic(currentError);
        resetMetrics("ERROR");
        setState("生成失败", false);
      } finally {
        if (generation === modeGeneration) suggestButton.disabled = false;
      }
    }

    async function loadExamples() {
      const requestedMode = currentMode;
      const requestToken = ++exampleLoadToken;
      const endpoint = requestedMode === "official" ? "/api/official/examples" : "/api/examples";
      try {
        const res = await fetch(endpoint);
        if (!res.ok) throw new Error("HTTP " + res.status);
        const data = await res.json();
        if (requestToken !== exampleLoadToken || requestedMode !== currentMode) return;
        const examples = Array.isArray(data.examples) ? data.examples : [];
        sampleSelect.disabled = false;
        sampleSelect.replaceChildren();
        examples.forEach((item, idx) => {
          if (requestedMode === "official") {
            item.kind = "official_pipeline";
            item.dataset = "official_schema";
            item.dataset_label = "官方 Doris 表结构";
            if (item.expected_code) item.expected_code = String(item.expected_code);
          }
          const option = document.createElement("option");
          option.value = String(idx);
          option.dataset.example = JSON.stringify(item);
          const status = item.expected_status === "error" ? "拒绝" : item.expected_status === "success" ? "通过" : "";
          const suffix = item.expected_code ? " [" + item.expected_code + "]" : item.scenario ? " [" + item.scenario + "]" : "";
          const dataset = item.dataset_label ? " - " + item.dataset_label : "";
          option.textContent = item.name + (status ? " · " + status : "") + suffix + dataset;
          sampleSelect.appendChild(option);
        });
        if (examples.length) selectExample(0);
      } catch (err) {
        if (requestToken !== exampleLoadToken || requestedMode !== currentMode) return;
        sampleSelect.replaceChildren();
        const option = document.createElement("option");
        option.textContent = "样例加载失败：" + err.message;
        sampleSelect.appendChild(option);
        sampleSelect.disabled = true;
        setState("样例不可用", false);
      }
    }

    async function loadEvidence() {
      try {
        const res = await fetch("/api/evidence");
        if (!res.ok) throw new Error("HTTP " + res.status);
        const data = await res.json();
        currentEvidence = data.evidence;
        currentDelivery = data.delivery;
      } catch (err) {
        currentEvidence = { available: false, message: err.message };
        currentDelivery = { available: false, message: err.message };
      }
      if (currentDelivery && currentDelivery.available) {
        document.getElementById("metricMigration").textContent = currentDelivery.legacy_to_new_migrated + "/" + currentDelivery.legacy_strict_success;
        document.getElementById("metricTests").textContent = currentDelivery.pytest_passed + " passed";
        buildState.textContent = currentDelivery.blocking_gates_passed && currentDelivery.warning_count === 0 ? "交付门禁 PASS" : "交付状态待核验";
        buildState.className = "badge " + (currentDelivery.blocking_gates_passed && currentDelivery.warning_count === 0 ? "ok" : "warn");
      } else {
        document.getElementById("metricMigration").textContent = "未导出";
        document.getElementById("metricTests").textContent = "未导出";
        buildState.textContent = "交付证据缺失";
        buildState.className = "badge warn";
      }
      if (currentEvidence && currentEvidence.available) {
        document.getElementById("metricSpeedup").textContent = currentEvidence.headline.speedup || "-";
        document.getElementById("metricParity").textContent = currentEvidence.headline.row_counts_match === "True" ? "MATCH" : currentEvidence.headline.row_counts_match;
        evidenceSpeed.textContent = "Doris 加速 " + (currentEvidence.headline.speedup || "-");
        evidenceRows.textContent = "结果行 " + (currentEvidence.headline.row_counts_match === "True" ? "一致" : currentEvidence.headline.row_counts_match);
        evidenceSpeed.className = "badge ok";
        evidenceRows.className = "badge ok";
      } else {
        document.getElementById("metricSpeedup").textContent = "-";
        document.getElementById("metricParity").textContent = "-";
        evidenceSpeed.textContent = "Doris 证据缺失";
        evidenceRows.textContent = "结果一致性未知";
        evidenceSpeed.className = "badge warn";
        evidenceRows.className = "badge warn";
      }
    }

    async function run() {
      const generation = modeGeneration;
      runButton.disabled = true;
      setState("编译中", true);
      try {
        const official = currentMode === "official";
        const endpoint = official ? "/api/official/preview" : "/api/analyze";
        const requestBody = official ? { dsl: dslInput.value } : {
          dsl: dslInput.value,
          dataset: currentExample && currentExample.dataset ? currentExample.dataset : "default",
          enable_prefix_sum: prefixToggle.checked,
          verify: verifyToggle.checked
        };
        const res = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(requestBody)
        });
        const data = await res.json();
        if (generation !== modeGeneration || official !== (currentMode === "official")) return;
        if (!data.ok) {
          const apiError = new Error(formatError(data.error));
          apiError.payload = data.error;
          throw apiError;
        }
        currentResult = official ? normalizeOfficialResult(data) : data;
        currentError = null;
        updateMetrics(currentResult);
        const failed = currentResult.verification && !currentResult.verification.passed;
        setState(failed ? "验证失败" : "编译通过", !failed);
        render();
      } catch (err) {
        if (generation !== modeGeneration) return;
        currentResult = null;
        currentError = err.payload || errorFromMessage(err.message);
        errorBox.hidden = false;
        errorBox.textContent = err.message;
        currentTab = "diagnostic";
        setActiveTab("diagnostic");
        renderDiagnostic(currentError);
        resetMetrics("诊断");
        const actualCodes = [
          currentError.code,
          ...(currentError.diagnostics || []).map(item => item.code)
        ].filter(Boolean);
        const expected = currentExample && currentExample.expected_code;
        const expectedMatch = Boolean(expected && actualCodes.includes(expected));
        setState(expectedMatch ? "按预期拒绝" : "编译失败", expectedMatch);
      } finally {
        if (generation === modeGeneration) runButton.disabled = false;
      }
    }

    function formatError(error) {
      const diagnostics = (error.diagnostics || []).filter(
        item => item.code || (item.suggestions && item.suggestions.length)
      );
      const suggestions = diagnostics.flatMap(item => item.suggestions || []);
      const unique = Array.from(new Set(suggestions));
      const codes = [error.code, ...diagnostics.map(item => item.code)].filter(Boolean);
      const expected = currentExample && currentExample.expected_code ? "\\nExpected diagnostic: " + currentExample.expected_code : "";
      const actual = codes.length ? "\\nActual diagnostic: " + codes.join(", ") : "";
      const stage = error.stage ? "\\nFailed stage: " + error.stage : "";
      if (!unique.length) return (error.type || "CompilerError") + ": " + error.message + stage + expected + actual;
      return (error.type || "CompilerError") + ": " + error.message + stage + expected + actual + "\\n\\nSuggestions:\\n- " + unique.join("\\n- ");
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
      document.querySelectorAll(".tab").forEach(item => {
        const active = item.dataset.tab === tab;
        item.classList.toggle("active", active);
        item.setAttribute("aria-selected", String(active));
        item.tabIndex = active ? 0 : -1;
      });
    }

    document.querySelectorAll(".tab").forEach(button => {
      button.addEventListener("click", () => {
        setActiveTab(button.dataset.tab);
        currentTab = button.dataset.tab;
        render();
      });
      button.addEventListener("keydown", event => {
        const tabs = Array.from(document.querySelectorAll(".tab")).filter(item => !item.hidden);
        const index = tabs.indexOf(button);
        let next = null;
        if (event.key === "ArrowRight") next = tabs[(index + 1) % tabs.length];
        if (event.key === "ArrowLeft") next = tabs[(index - 1 + tabs.length) % tabs.length];
        if (event.key === "Home") next = tabs[0];
        if (event.key === "End") next = tabs[tabs.length - 1];
        if (!next) return;
        event.preventDefault();
        next.click();
        next.focus();
      });
    });
    document.querySelector(".pipeline-switch").addEventListener("keydown", event => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const target = event.key === "ArrowLeft" || event.key === "Home" ? internalModeButton : officialModeButton;
      setMode(target === officialModeButton ? "official" : "internal");
      target.focus();
    });
    copyButton.addEventListener("click", async () => {
      const sql = currentResult && currentResult.compile ? currentResult.compile.sql : "";
      if (!sql) return;
      await navigator.clipboard.writeText(sql);
      copyButton.textContent = "已复制";
      setTimeout(() => { copyButton.textContent = "复制 SQL"; }, 1200);
    });
    sampleSelect.addEventListener("change", () => { selectExample(Number(sampleSelect.value)); });
    suggestButton.addEventListener("click", suggest);
    runButton.addEventListener("click", run);
    internalModeButton.addEventListener("click", () => setMode("internal"));
    officialModeButton.addEventListener("click", () => setMode("official"));
    nlInput.value = defaultNlRequest;
    setMode("official");
    Promise.allSettled([loadEvidence()]);
  </script>
</body>
</html>"""
    return html.replace('"__DEFAULT_NL_REQUEST__"', json.dumps(DEFAULT_NL_REQUEST, ensure_ascii=False))

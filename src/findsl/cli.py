from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .compiler import Compiler
from .evaluation import evaluate_file


def _exit_official_error(exc: Exception, as_json: bool) -> None:
    code = str(getattr(exc, "code", "OFFICIAL_ERROR"))
    if as_json:
        print(
            json.dumps(
                {"ok": False, "error": {"code": code, "message": str(exc)}},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"{code}: {exc}", file=sys.stderr)
    raise SystemExit(2)


def _build_official_physical(dsl: str):
    from .official.lowering import lower_official_ast
    from .official.physical.catalog import default_physical_catalog
    from .official.physical.expressions import default_physical_expressions
    from .official.physical.planner import plan_physical
    from .official.physical.statistics import default_physical_statistics
    from .official.physical.strategies import default_physical_strategies
    from .official.registry import default_official_registry
    from .official.semantics import OfficialSemanticAnalyzer
    from .official_slot import _resolve_indicator_meta, parse_official_slot_with_diagnostics

    parsed = parse_official_slot_with_diagnostics(dsl, mode="strict", frontend="antlr")
    typed = OfficialSemanticAnalyzer(_resolve_indicator_meta).analyze(parsed.ast)
    logical = lower_official_ast(typed, strict=True, domain_registry=default_official_registry())
    catalog = default_physical_catalog()
    return plan_physical(
        logical,
        catalog,
        statistics=default_physical_statistics(catalog),
        strategies=default_physical_strategies(catalog),
        expressions=default_physical_expressions(catalog),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile financial DSL to Doris SQL")
    sub = parser.add_subparsers(dest="command", required=True)
    compile_cmd = sub.add_parser("compile", help="Compile a DSL expression")
    compile_cmd.add_argument("dsl", help="DSL expression")
    compile_cmd.add_argument("--json", action="store_true", help="Print full JSON result")
    compile_cmd.add_argument("--no-prefix-sum", action="store_true", help="Disable prefix-sum optimizer")
    canonical_compile_cmd = sub.add_parser(
        "official-compile",
        help="Compile official DSL through the canonical ANTLR/IR/Doris pipeline",
    )
    canonical_compile_cmd.add_argument("dsl")
    canonical_compile_cmd.add_argument(
        "--strategy-mode",
        choices=("auto", "force_baseline", "force_candidate"),
        default="auto",
    )
    canonical_compile_cmd.add_argument("--json", action="store_true")
    explain_cmd = sub.add_parser(
        "official-explain",
        help="Show Parser -> Semantic -> IR -> Rewrite -> Route -> Doris SQL",
    )
    explain_cmd.add_argument("dsl")
    explain_cmd.add_argument(
        "--strategy-mode",
        choices=("auto", "force_baseline", "force_candidate"),
        default="auto",
    )
    explain_cmd.add_argument("--json", action="store_true")
    explain_cmd.add_argument("--output", default=None)
    result_cmd = sub.add_parser(
        "official-result",
        help="Compile official DSL and export a complete Markdown result",
    )
    result_cmd.add_argument("dsl")
    result_cmd.add_argument("--output", required=True)
    official_parse_cmd = sub.add_parser("official-slot-parse", help="Parse official slot DSL into an AST")
    official_parse_cmd.add_argument("dsl", help="Official slot DSL expression")
    official_parse_cmd.add_argument("--mode", choices=("strict", "recovery"), default="recovery")
    official_parse_cmd.add_argument("--frontend", choices=("handwritten", "antlr"), default="handwritten")
    official_parse_cmd.add_argument("--json", action="store_true", help="Print AST as JSON")
    official_compile_cmd = sub.add_parser("official-slot-compile", help="Compile official slot DSL to Doris SQL")
    official_compile_cmd.add_argument("dsl", help="Official slot DSL expression")
    official_compile_cmd.add_argument("--mode", choices=("strict", "recovery"), default="recovery")
    official_compile_cmd.add_argument("--json", action="store_true", help="Print full JSON result")
    official_profile_cmd = sub.add_parser("official-data-profile", help="Profile official CSV data and slot DSL workbook")
    official_profile_cmd.add_argument("--root", required=True, help="Official data package root directory")
    official_profile_cmd.add_argument("--workbook", default=None, help="Optional official slot DSL workbook path")
    official_profile_cmd.add_argument("--json-output", default=None, help="Optional JSON profile output path")
    official_profile_cmd.add_argument("--report-output", default=None, help="Optional Markdown profile output path")
    official_profile_cmd.add_argument("--sample-size", type=int, default=20, help="Number of training examples to include")
    official_profile_cmd.add_argument("--json", action="store_true", help="Print profile as JSON")
    official_coverage_cmd = sub.add_parser("official-slot-coverage", help="Analyze official slot DSL parse and compile coverage")
    official_coverage_cmd.add_argument("--workbook", required=True, help="Official slot DSL workbook path")
    official_coverage_cmd.add_argument("--json-output", default=None, help="Optional JSON coverage output path")
    official_coverage_cmd.add_argument("--report-output", default=None, help="Optional Markdown coverage output path")
    official_coverage_cmd.add_argument("--sample-size", type=int, default=20, help="Number of error/success samples to include")
    official_coverage_cmd.add_argument("--mode", choices=("strict", "recovery"), default="recovery")
    official_coverage_cmd.add_argument("--json", action="store_true", help="Print coverage as JSON")
    official_frontend_cmd = sub.add_parser(
        "official-frontend-evidence", help="Compare handwritten and ANTLR frontends on the official workbook"
    )
    official_frontend_cmd.add_argument("--workbook", required=True, help="Official slot DSL workbook path")
    official_frontend_cmd.add_argument("--json-output", required=True, help="Output JSON evidence path")
    official_frontend_cmd.add_argument("--report-output", required=True, help="Output Markdown evidence path")
    official_frontend_cmd.add_argument("--sample-size", type=int, default=20)
    official_frontend_cmd.add_argument("--json", action="store_true", help="Print evidence as JSON")
    official_ir_cmd = sub.add_parser("official-slot-ir", help="Build validated logical IR for one official DSL query")
    official_ir_cmd.add_argument("dsl")
    official_ir_cmd.add_argument("--mode", choices=("strict", "recovery"), default="strict")
    official_ir_cmd.add_argument("--frontend", choices=("handwritten", "antlr"), default="antlr")
    official_ir_cmd.add_argument("--json", action="store_true")
    official_ir_evidence_cmd = sub.add_parser("official-ir-evidence", help="Audit Typed AST and Logical IR on the official workbook")
    official_ir_evidence_cmd.add_argument("--workbook", required=True)
    official_ir_evidence_cmd.add_argument("--json-output", required=True)
    official_ir_evidence_cmd.add_argument("--report-output", required=True)
    official_ir_evidence_cmd.add_argument("--sample-size", type=int, default=20)
    official_optimize_cmd = sub.add_parser("official-slot-optimize", help="Bind and optimize one official DSL query")
    official_optimize_cmd.add_argument("dsl")
    official_optimize_cmd.add_argument("--json", action="store_true")
    official_domain_cmd = sub.add_parser("official-domain-evidence", help="Audit domain binding and optimizer rules")
    official_domain_cmd.add_argument("--workbook", required=True)
    official_domain_cmd.add_argument("--json-output", required=True)
    official_domain_cmd.add_argument("--report-output", required=True)
    official_domain_cmd.add_argument("--sample-size", type=int, default=20)
    official_physical_cmd = sub.add_parser("official-slot-physical", help="Build a validated Doris physical plan")
    official_physical_cmd.add_argument("dsl")
    official_physical_cmd.add_argument("--json", action="store_true")
    official_stats_cmd = sub.add_parser("official-physical-stats", help="Collect versioned Doris physical statistics")
    official_stats_cmd.add_argument("--output", required=True)
    official_stats_cmd.add_argument("--host", default="127.0.0.1")
    official_stats_cmd.add_argument("--port", type=int, default=9030)
    official_stats_cmd.add_argument("--user", default="root")
    official_stats_cmd.add_argument("--password-env", default="DORIS_PASSWORD")
    official_stats_cmd.add_argument("--database", default="newzl")
    official_stats_cmd.add_argument("--client", default="mysql")
    official_stats_cmd.add_argument("--query-timeout", type=float, default=30.0)
    official_stats_cmd.add_argument("--json", action="store_true")
    official_prefix_cmd = sub.add_parser("official-prefix-evidence", help="Compare direct and prefix physical strategies")
    official_prefix_cmd.add_argument("--json-output", required=True)
    official_prefix_cmd.add_argument("--report-output", required=True)
    official_prefix_cmd.add_argument("--host", default="127.0.0.1")
    official_prefix_cmd.add_argument("--port", type=int, default=9030)
    official_prefix_cmd.add_argument("--user", default="root")
    official_prefix_cmd.add_argument("--password-env", default="DORIS_PASSWORD")
    official_prefix_cmd.add_argument("--database", default="newzl")
    official_prefix_cmd.add_argument("--client", default="mysql")
    official_prefix_cmd.add_argument("--query-timeout", type=float, default=180.0)
    official_backend_cmd = sub.add_parser("official-slot-backend", help="Render validated SQLGlot Doris SQL")
    official_backend_cmd.add_argument("dsl")
    official_backend_cmd.add_argument("--json", action="store_true")
    official_backend_evidence_cmd = sub.add_parser("official-backend-evidence", help="Audit the Doris backend on the official workbook")
    official_backend_evidence_cmd.add_argument("--workbook", required=True)
    official_backend_evidence_cmd.add_argument("--json-output", required=True)
    official_backend_evidence_cmd.add_argument("--report-output", required=True)
    official_backend_evidence_cmd.add_argument("--sample-size", type=int, default=20)
    official_backend_evidence_cmd.add_argument("--json", action="store_true")
    official_backend_evidence_cmd.add_argument("--execute-doris", action="store_true")
    official_backend_evidence_cmd.add_argument("--host", default="127.0.0.1")
    official_backend_evidence_cmd.add_argument("--port", type=int, default=9030)
    official_backend_evidence_cmd.add_argument("--user", default="root")
    official_backend_evidence_cmd.add_argument("--password-env", default="DORIS_PASSWORD")
    official_backend_evidence_cmd.add_argument("--database", default="newzl")
    official_backend_evidence_cmd.add_argument("--client", default="mysql")
    official_backend_evidence_cmd.add_argument("--query-timeout", type=float, default=180.0)
    official_funnel_cmd = sub.add_parser(
        "official-coverage-funnel",
        help="Measure old-to-new official compiler migration coverage",
    )
    official_funnel_cmd.add_argument("--workbook", required=True)
    official_funnel_cmd.add_argument("--json-output", required=True)
    official_funnel_cmd.add_argument("--report-output", required=True)
    official_funnel_cmd.add_argument("--json", action="store_true")
    official_repair_cmd = sub.add_parser(
        "official-repair",
        help="Propose a ledger-backed DSL repair without executing it",
    )
    official_repair_cmd.add_argument("dsl")
    official_repair_cmd.add_argument(
        "--accept-sha256",
        default=None,
        help="Explicitly accept the exact candidate SHA-256",
    )
    official_repair_cmd.add_argument("--json", action="store_true")
    official_perf_cmd = sub.add_parser(
        "official-performance-matrix",
        help="Build a per-query performance matrix from official Doris evidence",
    )
    official_perf_cmd.add_argument(
        "--evidence",
        default="reports/official_doris_evidence.json",
        help="Official Doris evidence JSON path",
    )
    official_perf_cmd.add_argument(
        "--json-output",
        default="reports/official_query_performance_matrix.json",
        help="Output JSON matrix path",
    )
    official_perf_cmd.add_argument(
        "--report-output",
        default="reports/official_query_performance_matrix.md",
        help="Output Markdown matrix path",
    )
    official_perf_cmd.add_argument("--json", action="store_true", help="Print matrix as JSON")
    diagnose_cmd = sub.add_parser("diagnose", help="Diagnose invalid DSL and print repair hints")
    diagnose_cmd.add_argument("dsl", help="DSL expression")
    diagnose_cmd.add_argument("--json", action="store_true", help="Print diagnostics as JSON")
    diagnose_cmd.add_argument("--no-prefix-sum", action="store_true", help="Disable prefix-sum optimizer")
    suggest_cmd = sub.add_parser("suggest-dsl", help="Suggest validated DSL candidates from natural language")
    suggest_cmd.add_argument("text", help="Natural-language stock-screening request")
    suggest_cmd.add_argument("--data-dir", default="data/samples", help="Directory containing sample CSV tables")
    suggest_cmd.add_argument("--json", action="store_true", help="Print suggestion payload as JSON")
    suggest_cmd.add_argument("--no-prefix-sum", action="store_true", help="Disable prefix-sum optimizer")
    suggest_cmd.add_argument("--no-verify", action="store_true", help="Skip SQL/reference verification")
    llm_cmd = sub.add_parser("validate-llm-candidates", help="Validate LLM-proposed DSL candidates through the safety loop")
    llm_cmd.add_argument("--response-file", required=True, help="File containing an LLM response or mocked payload")
    llm_cmd.add_argument("--text", default="筛选A股连续三天主力净流入为正并按换手率排名前一百", help="Original natural-language request")
    llm_cmd.add_argument("--data-dir", default="data/samples", help="Directory containing sample CSV tables")
    llm_cmd.add_argument("--max-candidates", type=int, default=5, help="Maximum candidates to extract and validate")
    llm_cmd.add_argument("--json", action="store_true", help="Print validation payload as JSON")
    llm_cmd.add_argument("--no-prefix-sum", action="store_true", help="Disable prefix-sum optimizer")
    llm_cmd.add_argument("--no-verify", action="store_true", help="Skip SQL/reference verification")
    provider_cmd = sub.add_parser(
        "llm-suggest-dsl",
        help="Ask an OpenAI-compatible provider for DSL candidates, then validate them",
    )
    provider_cmd.add_argument("text", help="Natural-language stock-screening request")
    provider_cmd.add_argument("--base-url", default=None, help="OpenAI-compatible base URL")
    provider_cmd.add_argument("--model", default=None, help="Provider model name; or set FINDSL_LLM_MODEL")
    provider_cmd.add_argument("--api-key-env", default="FINDSL_LLM_API_KEY", help="Environment variable containing the API key")
    provider_cmd.add_argument("--no-api-key", action="store_true", help="Allow local providers that do not require an API key")
    provider_cmd.add_argument("--timeout", type=float, default=30.0, help="Provider request timeout in seconds")
    provider_cmd.add_argument("--temperature", type=float, default=0.1, help="Provider sampling temperature")
    provider_cmd.add_argument("--max-tokens", type=int, default=700, help="Provider max tokens")
    provider_cmd.add_argument("--max-candidates", type=int, default=5, help="Maximum candidates to extract and validate")
    provider_cmd.add_argument("--data-dir", default="data/samples", help="Directory containing sample CSV tables")
    provider_cmd.add_argument("--raw-output", default=None, help="Optional file path for the raw provider response")
    provider_cmd.add_argument("--json-response-format", action="store_true", help="Request provider JSON-object response_format when supported")
    provider_cmd.add_argument("--json", action="store_true", help="Print validation payload as JSON")
    provider_cmd.add_argument("--no-prefix-sum", action="store_true", help="Disable prefix-sum optimizer")
    provider_cmd.add_argument("--no-verify", action="store_true", help="Skip SQL/reference verification")
    eval_cmd = sub.add_parser("evaluate", help="Evaluate compiler against a JSONL case file")
    eval_cmd.add_argument("--input", default="data/samples/queries.jsonl", help="Input JSONL case file")
    eval_cmd.add_argument("--output", default="reports/evaluation_report.md", help="Output Markdown report")
    official_cmd = sub.add_parser("official-suite", help="Run official-style coverage and diagnostics suite")
    official_cmd.add_argument("--positive-input", default="data/samples/official_positive_cases.jsonl", help="Positive official-style JSONL cases")
    official_cmd.add_argument("--negative-input", default="data/samples/official_negative_cases.jsonl", help="Negative diagnostic JSONL cases")
    official_cmd.add_argument("--data-dir", default="data/samples", help="Directory containing sample CSV tables")
    official_cmd.add_argument("--output", default="reports/official_suite_report.md", help="Output Markdown report")
    official_cmd.add_argument("--json", action="store_true", help="Print suite summary as JSON")
    defense_cmd = sub.add_parser("defense-package", help="Generate defense walkthrough and score-mapping evidence")
    defense_cmd.add_argument("--output", default="reports/defense_package.md", help="Output Markdown report")
    defense_cmd.add_argument("--data-dir", default="data/samples", help="Directory containing sample CSV tables")
    defense_cmd.add_argument("--input", default="data/samples/queries.jsonl", help="Input JSONL evaluation cases")
    defense_cmd.add_argument("--positive-input", default="data/samples/official_positive_cases.jsonl", help="Positive official-style JSONL cases")
    defense_cmd.add_argument("--negative-input", default="data/samples/official_negative_cases.jsonl", help="Negative diagnostic JSONL cases")
    defense_cmd.add_argument("--repo-root", default=".", help="Repository root for asset checks")
    defense_cmd.add_argument("--json", action="store_true", help="Print package summary as JSON")
    ref_cmd = sub.add_parser("reference", help="Evaluate DSL semantics with the Pandas reference engine")
    ref_cmd.add_argument("dsl", help="DSL expression")
    ref_cmd.add_argument("--data-dir", default="data/samples", help="Directory containing sample CSV tables")
    ref_cmd.add_argument("--json", action="store_true", help="Print result keys as JSON")
    verify_cmd = sub.add_parser("verify-sql", help="Compare compiled SQL output with Pandas reference output")
    verify_cmd.add_argument("dsl", help="DSL expression")
    verify_cmd.add_argument("--data-dir", default="data/samples", help="Directory containing sample CSV tables")
    verify_cmd.add_argument("--json", action="store_true", help="Print verification result as JSON")
    verify_cmd.add_argument("--no-prefix-sum", action="store_true", help="Disable prefix-sum optimizer")
    bench_cmd = sub.add_parser("benchmark-prefix-sum", help="Compare baseline window SQL with prefix-sum SQL")
    bench_cmd.add_argument("dsl", help="DSL expression")
    bench_cmd.add_argument("--data-dir", default="data/samples", help="Directory containing sample CSV tables")
    bench_cmd.add_argument("--iterations", type=int, default=20, help="Execution iterations per SQL variant")
    bench_cmd.add_argument("--output", default="reports/prefix_sum_benchmark.md", help="Output Markdown report")
    bench_cmd.add_argument("--json", action="store_true", help="Print benchmark result as JSON")
    synth_cmd = sub.add_parser("generate-synthetic-data", help="Generate deterministic benchmark CSV fixtures")
    synth_cmd.add_argument("--output-dir", default="data/generated/scale", help="Output directory for CSV files")
    synth_cmd.add_argument("--stocks", type=int, default=300, help="Number of synthetic stocks")
    synth_cmd.add_argument("--days", type=int, default=260, help="Number of synthetic trading days")
    synth_cmd.add_argument("--start-date", default="2025-01-01", help="First synthetic trade date")
    synth_cmd.add_argument("--seed", type=int, default=2026, help="Deterministic random seed")
    scale_cmd = sub.add_parser("scale-benchmark", help="Generate synthetic data and run a long-window benchmark")
    scale_cmd.add_argument("--data-dir", default="data/generated/scale", help="Synthetic data output directory")
    scale_cmd.add_argument("--output", default="reports/prefix_sum_scale_benchmark.md", help="Output Markdown report")
    scale_cmd.add_argument("--stocks", type=int, default=300, help="Number of synthetic stocks")
    scale_cmd.add_argument("--days", type=int, default=260, help="Number of synthetic trading days")
    scale_cmd.add_argument("--start-date", default="2025-01-01", help="First synthetic trade date")
    scale_cmd.add_argument("--seed", type=int, default=2026, help="Deterministic random seed")
    scale_cmd.add_argument("--window", type=int, default=120, help="Rolling SUM window")
    scale_cmd.add_argument("--threshold", type=int, default=None, help="Filter threshold; defaults to window * 3500")
    scale_cmd.add_argument("--iterations", type=int, default=5, help="Execution iterations per SQL variant")
    scale_cmd.add_argument("--dsl", default=None, help="Custom DSL query; overrides window and threshold")
    scale_cmd.add_argument("--json", action="store_true", help="Print benchmark summary as JSON")
    doris_cmd = sub.add_parser("emit-doris-assets", help="Generate Doris DDL and sample SQL assets")
    doris_cmd.add_argument("--data-dir", default="data/samples", help="Directory containing sample CSV tables")
    doris_cmd.add_argument("--output-dir", default="deploy/doris", help="Output directory for Doris SQL assets")
    doris_cmd.add_argument("--database", default="findsl_demo", help="Doris database name")
    doris_cmd.add_argument("--buckets", type=int, default=8, help="Doris hash bucket count")
    doris_cmd.add_argument("--replication-num", type=int, default=1, help="Doris table replication_num property")
    doris_evidence_cmd = sub.add_parser("collect-doris-evidence", help="Collect Doris EXPLAIN and latency evidence")
    doris_evidence_cmd.add_argument("--host", required=True, help="Doris FE host")
    doris_evidence_cmd.add_argument("--port", type=int, default=9030, help="Doris MySQL query port")
    doris_evidence_cmd.add_argument("--user", default="root", help="Doris user")
    doris_evidence_cmd.add_argument("--password", default="", help="Doris password; prefer environment variables in scripts")
    doris_evidence_cmd.add_argument("--database", default="findsl_demo", help="Doris database name")
    doris_evidence_cmd.add_argument("--client", default="mysql", help="MySQL-compatible client executable")
    doris_evidence_cmd.add_argument("--dsl", default=None, help="DSL to benchmark on Doris")
    doris_evidence_cmd.add_argument("--iterations", type=int, default=3, help="Execution iterations per SQL variant")
    doris_evidence_cmd.add_argument("--output", default="reports/doris_cluster_evidence.md", help="Output Markdown report")
    doris_evidence_cmd.add_argument("--password-mode", choices=["none", "inline", "prompt"], default="none", help="How to pass password to the client")
    doris_evidence_cmd.add_argument("--min-speedup", type=float, default=10.0, help="Minimum Doris speedup required for evidence to pass")
    doris_evidence_cmd.add_argument("--json", action="store_true", help="Print evidence summary as JSON")
    ready_cmd = sub.add_parser("readiness-report", help="Generate submission readiness evidence report")
    ready_cmd.add_argument("--output", default="reports/submission_readiness.md", help="Output Markdown report")
    ready_cmd.add_argument("--reports-dir", default="reports", help="Directory for generated evidence artifacts")
    ready_cmd.add_argument("--input", default="data/samples/queries.jsonl", help="Input JSONL evaluation cases")
    ready_cmd.add_argument("--data-dir", default="data/samples", help="Directory containing sample CSV tables")
    ready_cmd.add_argument("--benchmark-iterations", type=int, default=20, help="Prefix benchmark iterations")
    ready_cmd.add_argument("--skip-pytest", action="store_true", help="Skip pytest when generating the report")
    metadata_cmd = sub.add_parser("evidence-metadata", help="Build machine-readable evidence metadata from exported snapshots")
    metadata_cmd.add_argument("--snapshots-dir", default="reports", help="Directory containing generated evidence reports")
    metadata_cmd.add_argument("--manifest", default="", help="Optional evidence manifest path")
    metadata_cmd.add_argument("--output", default="reports/evidence_metadata.json", help="Output JSON metadata path")
    metadata_cmd.add_argument("--summary-output", default=None, help="Optional output Markdown summary path")
    metadata_cmd.add_argument("--contract", default=None, help="Optional evidence contract JSON path")
    metadata_cmd.add_argument("--expected-git-head", default=None, help="Expected Git HEAD for every current evidence source")
    metadata_cmd.add_argument("--require-contract-pass", action="store_true", help="Fail when the evidence contract audit does not pass")
    compliance_cmd = sub.add_parser("topic-compliance", help="Generate Topic 19 compliance and next-step planning report")
    compliance_cmd.add_argument("--output", default="reports/topic_19_compliance_plan.md", help="Output Markdown report")
    compliance_cmd.add_argument("--json", action="store_true", help="Print compliance report JSON")
    demo_cmd = sub.add_parser("serve-demo", help="Start the local web demo and JSON API")
    demo_cmd.add_argument("--host", default="127.0.0.1", help="Host interface for the demo server")
    demo_cmd.add_argument("--port", type=int, default=8765, help="Port for the demo server")
    demo_cmd.add_argument("--data-dir", default="data/samples", help="Directory containing sample CSV tables")
    demo_cmd.add_argument("--input", default="data/samples/queries.jsonl", help="Input JSONL examples")
    api_cmd = sub.add_parser("serve-api", help="Start the production-oriented official compiler API")
    api_cmd.add_argument("--host", default="127.0.0.1")
    api_cmd.add_argument("--port", type=int, default=8766)
    api_cmd.add_argument("--log-level", choices=("critical", "error", "warning", "info"), default="info")
    args = parser.parse_args()

    if args.command == "compile":
        result = Compiler(enable_prefix_sum=not args.no_prefix_sum).compile(args.dsl)
        if args.json:
            print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
        else:
            print(result.sql)
            print()
            print("Trace:")
            for item in result.trace:
                print(f"- {item}")
            print(f"Elapsed: {result.elapsed_ms:.3f} ms")
    elif args.command == "official-compile":
        from .official.pipeline import OfficialPipelineOptions
        from .official.service import OfficialCompilerService

        result = OfficialCompilerService().compile(
            args.dsl,
            options=OfficialPipelineOptions(strategy_mode=args.strategy_mode),
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(result["result"]["backend"]["sql"])
    elif args.command == "official-explain":
        from .official.explain import render_explain_markdown
        from .official.pipeline import OfficialPipelineOptions, compile_official

        try:
            compiled = compile_official(
                args.dsl,
                options=OfficialPipelineOptions(strategy_mode=args.strategy_mode),
            )
        except Exception as exc:  # noqa: BLE001 - CLI normalizes compiler diagnostics.
            _exit_official_error(exc, args.json)
        explain = compiled.explain
        content = (
            json.dumps(explain, ensure_ascii=False, indent=2) + "\n"
            if args.json
            else render_explain_markdown(explain)
        )
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(content, encoding="utf-8")
        print(content, end="")
    elif args.command == "official-result":
        from .official.pipeline import compile_official
        from .official.result_report import render_compilation_result_markdown

        try:
            compiled = compile_official(args.dsl)
        except Exception as exc:  # noqa: BLE001 - CLI normalizes compiler diagnostics.
            _exit_official_error(exc, False)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            render_compilation_result_markdown(compiled.to_dict()), encoding="utf-8"
        )
        print(str(output.resolve()))
    elif args.command == "official-slot-parse":
        from .official_slot import OfficialSlotError, parse_official_slot_with_diagnostics

        try:
            parsed = parse_official_slot_with_diagnostics(
                args.dsl, mode=args.mode, frontend=args.frontend
            )
        except OfficialSlotError as exc:
            _exit_official_error(exc, args.json)
        payload = parsed.ast.to_dict()
        payload.update(
            {
                "source": parsed.source,
                "normalized_source": parsed.normalized_source,
                "repairs": [repair.to_dict() for repair in parsed.repairs],
                "mode": args.mode,
                "frontend": args.frontend,
            }
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(parsed.ast.to_dict(), ensure_ascii=False, indent=2))
            print()
            print(f"Mode: {args.mode}")
            print(f"Frontend: {args.frontend}")
            print(f"Normalized source: {parsed.normalized_source}")
            print("Repairs:")
            if parsed.repairs:
                for repair in parsed.repairs:
                    print(f"- {repair.code} at {repair.position}: {repair.message}")
            else:
                print("- <none>")
    elif args.command == "official-slot-compile":
        from .official_slot import OfficialSlotCompiler, OfficialSlotError

        try:
            result = OfficialSlotCompiler(mode=args.mode).compile(args.dsl)
        except OfficialSlotError as exc:
            _exit_official_error(exc, args.json)
        payload = asdict(result)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(result.sql)
            print()
            print(f"Mode: {args.mode}")
            print(f"Strict success: {result.strict_success}")
            print(f"Degraded: {result.degraded}")
            print(f"Normalized source: {result.normalized_source}")
            print("Repairs:")
            if result.repairs:
                for repair in result.repairs:
                    print(f"- {repair.code} at {repair.position}: {repair.message}")
            else:
                print("- <none>")
            print(
                "Fallback predicates: "
                + (", ".join(result.fallback_predicates) if result.fallback_predicates else "<none>")
            )
            print()
            print("Requires tables:")
            for table in result.requires_tables:
                print(f"- {table}")
            if result.warnings:
                print()
                print("Warnings:")
                for warning in result.warnings:
                    print(f"- {warning}")
    elif args.command == "official-data-profile":
        from .official_slot import (
            profile_official_csvs,
            profile_to_json,
            profile_training_workbook,
            write_profile_report,
        )

        root = Path(args.root)
        workbook = (
            Path(args.workbook)
            if args.workbook
            else root / "选股 DSL 规范文档" / "选股提槽实例.xlsx"
        )
        profile = {
            "root": str(root),
            "csv": profile_official_csvs(str(root)),
            "workbook": profile_training_workbook(str(workbook), sample_size=args.sample_size),
        }
        if args.json_output:
            profile_to_json(profile, args.json_output)
        if args.report_output:
            write_profile_report(profile, args.report_output)
        if args.json:
            print(json.dumps(profile, ensure_ascii=False, indent=2))
        else:
            print(f"Official CSV tables: {len(profile['csv'])}")
            print(f"Official training rows: {profile['workbook']['row_count']}")
            print(f"Parse ok: {profile['workbook']['parse_ok']}")
    elif args.command == "official-slot-coverage":
        from .official_slot import compile_training_workbook, profile_to_json, write_coverage_report

        coverage = compile_training_workbook(
            args.workbook,
            sample_size=args.sample_size,
            mode=args.mode,
        )
        if args.json_output:
            profile_to_json(coverage, args.json_output)
        if args.report_output:
            write_coverage_report(coverage, args.report_output)
        if args.json:
            print(json.dumps(coverage, ensure_ascii=False, indent=2))
        else:
            print(f"Compile mode: {coverage['mode']}")
            print(f"Official training rows: {coverage['row_count']}")
            print(f"Selected parse ok: {coverage['selected_parse_ok']}")
            print(f"Selected compile ok: {coverage['selected_compile_ok']}")
            print(f"Strict parse ok: {coverage['strict_parse_ok']}")
            print(f"Recovery parse ok: {coverage['recovery_parse_ok']}")
            print(f"Strict compile ok: {coverage['strict_compile_ok']}")
            print(f"Recovery compile ok: {coverage['recovery_compile_ok']}")
            print(f"Degraded rows: {coverage['degraded_rows']}")
    elif args.command == "official-performance-matrix":
        from .official_performance import write_official_performance_matrix

        matrix = write_official_performance_matrix(
            evidence_path=Path(args.evidence),
            json_output=Path(args.json_output) if args.json_output else None,
            report_output=Path(args.report_output) if args.report_output else None,
        )
        if args.json:
            print(json.dumps(matrix, ensure_ascii=False, indent=2))
        else:
            summary = matrix["summary"]
            print(f"Official query count: {summary['query_count']}")
            print(f"All queries P95 <= 10s: {summary['all_queries_under_10s']}")
            print(f"Max P95: {summary['max_p95_ms']} ms")
    elif args.command == "official-frontend-evidence":
        from .official_frontend_evidence import build_frontend_evidence, write_frontend_evidence

        evidence = build_frontend_evidence(args.workbook, sample_size=args.sample_size)
        write_frontend_evidence(evidence, args.json_output, args.report_output)
        if args.json:
            print(json.dumps(evidence, ensure_ascii=False, indent=2))
        else:
            print(f"Official rows: {evidence['row_count']}")
            print(f"Recovery classifications: {evidence['recovery']['classifications']}")
    elif args.command == "official-slot-ir":
        from .official.lowering import lower_official_ast
        from .official.semantics import OfficialSemanticAnalyzer
        from .official_slot import _resolve_indicator_meta, parse_official_slot_with_diagnostics

        parsed = parse_official_slot_with_diagnostics(args.dsl, mode=args.mode, frontend=args.frontend)
        typed = OfficialSemanticAnalyzer(_resolve_indicator_meta).analyze(parsed.ast)
        result = lower_official_ast(typed, strict=args.mode == "strict")
        payload = {"typed_ast": typed.to_dict(), **result.to_dict()}
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else result.plan.canonical_json())
    elif args.command == "official-ir-evidence":
        from .official_ir_evidence import build_official_ir_evidence, write_official_ir_evidence

        evidence = build_official_ir_evidence(args.workbook, sample_size=args.sample_size)
        write_official_ir_evidence(evidence, args.json_output, args.report_output)
        print(f"IR gate: {'PASS' if evidence['gate']['passed'] else 'FAIL'}")
        print(f"Lowering: {evidence['lowering_ok']}/{evidence['row_count']}")
    elif args.command == "official-slot-optimize":
        from .official.lowering import lower_official_ast
        from .official.optimizer import DEFAULT_RULES, Optimizer
        from .official.registry import default_official_registry
        from .official.semantics import OfficialSemanticAnalyzer
        from .official_slot import _resolve_indicator_meta, parse_official_slot_with_diagnostics

        parsed = parse_official_slot_with_diagnostics(args.dsl, mode="strict", frontend="antlr")
        typed = OfficialSemanticAnalyzer(_resolve_indicator_meta).analyze(parsed.ast)
        lowered = lower_official_ast(typed, strict=True, domain_registry=default_official_registry())
        optimized = Optimizer(DEFAULT_RULES).optimize(lowered.plan)
        payload = {"lowering": lowered.to_dict(), "optimized": optimized.to_dict()}
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else optimized.plan.canonical_json())
    elif args.command == "official-domain-evidence":
        from .official_domain_evidence import build_official_domain_evidence, write_official_domain_evidence

        evidence = build_official_domain_evidence(args.workbook, sample_size=args.sample_size)
        write_official_domain_evidence(evidence, args.json_output, args.report_output)
        print(f"Domain gate: {'PASS' if evidence['gate']['passed'] else 'FAIL'}")
        print(f"Domain lowering: {evidence['domain_lowering_ok']}/{evidence['row_count']}")
    elif args.command == "official-physical-stats":
        import os

        from .official.backend.executor import DorisExecutionConfig
        from .official.physical.catalog import default_physical_catalog
        from .official.physical.statistics import collect_physical_statistics

        config = DorisExecutionConfig(
            host=args.host,
            port=args.port,
            user=args.user,
            password=os.environ.get(args.password_env, ""),
            database=args.database,
            mysql_executable=args.client,
            timeout_seconds=args.query_timeout,
        )
        snapshot = collect_physical_statistics(default_physical_catalog(), config)
        snapshot.write(Path(args.output))
        if args.json:
            print(json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"Doris version: {snapshot.doris_version}")
            print(f"Physical resources: {len(snapshot.resources)}")
    elif args.command == "official-prefix-evidence":
        import os

        from .official.backend.executor import DorisExecutionConfig
        from .official_prefix_evidence import build_official_prefix_evidence, write_official_prefix_evidence

        config = DorisExecutionConfig(
            host=args.host,
            port=args.port,
            user=args.user,
            password=os.environ.get(args.password_env, ""),
            database=args.database,
            mysql_executable=args.client,
            timeout_seconds=args.query_timeout,
        )
        evidence = build_official_prefix_evidence(config=config)
        write_official_prefix_evidence(evidence, args.json_output, args.report_output)
        print(f"Prefix gate: {evidence['status']}")
        print(f"Prefix matches: {evidence['matched']}/{evidence['case_count']}")
    elif args.command == "official-slot-physical":
        result = _build_official_physical(args.dsl)
        payload = {
            "selected_resource": result.selected_resource,
            "plan": result.plan.to_dict(),
            "plan_id": result.plan.node_id,
            "decisions": [asdict(decision) for decision in result.decisions],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else result.plan.canonical_json())
    elif args.command == "official-slot-backend":
        from .official.backend.doris import render_doris
        from .official.physical.catalog import default_physical_catalog
        from .official.physical.expressions import default_physical_expressions

        physical = _build_official_physical(args.dsl)
        catalog = default_physical_catalog()
        result = render_doris(physical.plan, catalog, default_physical_expressions(catalog))
        payload = {
            "sql": result.sql,
            "round_trip_stable": result.round_trip_stable,
            "validation_passed": result.validation.passed,
            "table_references": result.validation.table_references,
            "physical_plan_id": physical.plan.node_id,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else result.sql)
    elif args.command == "official-backend-evidence":
        import os

        from .official.backend.executor import DorisExecutionConfig
        from .official_backend_evidence import build_official_backend_evidence, write_official_backend_evidence

        config = None
        if args.execute_doris:
            config = DorisExecutionConfig(
                host=args.host,
                port=args.port,
                user=args.user,
                password=os.environ.get(args.password_env, ""),
                database=args.database,
                mysql_executable=args.client,
                timeout_seconds=args.query_timeout,
            )
        evidence = build_official_backend_evidence(
            args.workbook,
            sample_size=args.sample_size,
            doris_config=config,
        )
        write_official_backend_evidence(evidence, args.json_output, args.report_output)
        if args.json:
            print(json.dumps(evidence, ensure_ascii=False, indent=2))
        else:
            print(f"Phase 5 gate: {evidence['gates']['phase5_completion']['status']}")
            print(f"Safe Doris SQL: {evidence['safety_ok']}/{evidence['row_count']}")
    elif args.command == "official-coverage-funnel":
        from .official_coverage_funnel import (
            build_official_workbook_coverage_funnel,
            write_official_coverage_funnel,
        )

        report = build_official_workbook_coverage_funnel(args.workbook)
        write_official_coverage_funnel(report, args.json_output, args.report_output)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(
                "Migration coverage: "
                f"{report['legacy_to_new_migrated']}/{report['legacy_strict_success']} "
                f"({report['migration_coverage'] * 100:.2f}%)"
            )
    elif args.command == "official-repair":
        from .official.service import OfficialCompilerService

        result = OfficialCompilerService().repair(
            args.dsl,
            accept_candidate_sha256=args.accept_sha256,
        )
        repair = result["repair"]
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif repair["candidate"] is None:
            print("No safe ledger-backed repair candidate.")
        else:
            print(f"Repair status: {repair['status']}")
            print(f"Candidate: {repair['candidate']['candidate_dsl']}")
            print(
                "Candidate SHA-256: "
                f"{repair['candidate']['candidate_sha256']}"
            )
            print("Doris execution: disabled")
    elif args.command == "diagnose":
        from .diagnostics import diagnose_exception

        try:
            result = Compiler(enable_prefix_sum=not args.no_prefix_sum).compile(args.dsl)
            payload = {
                "ok": True,
                "dsl": args.dsl,
                "diagnostics": [],
                "compile": {"elapsed_ms": result.elapsed_ms},
            }
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print("DSL compiled successfully.")
                print(f"Elapsed: {result.elapsed_ms:.3f} ms")
        except Exception as exc:  # noqa: BLE001 - CLI diagnostics should classify compiler failures.
            diagnostics = [item.to_dict() for item in diagnose_exception(exc)]
            payload = {
                "ok": False,
                "dsl": args.dsl,
                "error": {"type": type(exc).__name__, "message": str(exc)},
                "diagnostics": diagnostics,
            }
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(f"{type(exc).__name__}: {exc}")
                print()
                print("| Code | Severity | Suggestions |")
                print("|---|---|---|")
                for item in diagnostics:
                    suggestions = "<br>".join(str(hint) for hint in item["suggestions"])
                    print(f"| {item['code']} | {item['severity']} | {suggestions} |")
            raise SystemExit(1)
    elif args.command == "suggest-dsl":
        from .demo import suggest_from_text

        result = suggest_from_text(
            text=args.text,
            data_dir=Path(args.data_dir),
            enable_prefix_sum=not args.no_prefix_sum,
            verify=not args.no_verify,
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if result["warnings"]:
                print("Warnings:")
                for warning in result["warnings"]:
                    print(f"- {warning}")
            print("| Rank | Validated | Confidence | Rule | DSL |")
            print("|---:|---:|---:|---|---|")
            for idx, candidate in enumerate(result["candidates"], 1):
                print(
                    f"| {idx} | {candidate.get('validated')} | "
                    f"{candidate.get('confidence'):.3f} | {candidate.get('rule')} | "
                    f"`{candidate.get('dsl')}` |"
                )
        if not result["candidates"] or not result["candidates"][0].get("validated"):
            raise SystemExit(1)
    elif args.command == "validate-llm-candidates":
        from .llm_adapter import validate_llm_candidates

        response_path = Path(args.response_file)
        result = validate_llm_candidates(
            text=args.text,
            payload=response_path.read_text(encoding="utf-8"),
            data_dir=Path(args.data_dir),
            enable_prefix_sum=not args.no_prefix_sum,
            verify=not args.no_verify,
            max_candidates=args.max_candidates,
        )
        payload = result.to_dict()
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            if result.warnings:
                print("Warnings:")
                for warning in result.warnings:
                    print(f"- {warning}")
            print("| Rank | Accepted | Reason | Source | DSL |")
            print("|---:|---:|---|---|---|")
            for candidate in result.candidates:
                print(
                    f"| {candidate.rank} | {candidate.accepted} | "
                    f"{candidate.reason} | {candidate.source} | `{candidate.dsl}` |"
                )
        if not result.passed:
            raise SystemExit(1)
    elif args.command == "llm-suggest-dsl":
        from .llm_provider import config_from_env, request_and_validate_llm_candidates

        try:
            config = config_from_env(
                base_url=args.base_url,
                model=args.model,
                api_key_env=args.api_key_env,
                allow_missing_api_key=args.no_api_key,
                timeout_seconds=args.timeout,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                response_format_json=args.json_response_format,
            )
            result = request_and_validate_llm_candidates(
                text=args.text,
                config=config,
                data_dir=Path(args.data_dir),
                enable_prefix_sum=not args.no_prefix_sum,
                verify=not args.no_verify,
                max_candidates=args.max_candidates,
            )
        except Exception as exc:  # noqa: BLE001 - CLI should turn provider failures into actionable output.
            if args.json:
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": {"type": type(exc).__name__, "message": str(exc)},
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                print(f"{type(exc).__name__}: {exc}")
            raise SystemExit(1)

        if args.raw_output:
            Path(args.raw_output).write_text(result.raw_response, encoding="utf-8")
        payload = result.to_dict()
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"Provider model: {payload['provider']['model']}")
            print(f"Provider base URL: {payload['provider']['base_url']}")
            if result.validation.warnings:
                print("Warnings:")
                for warning in result.validation.warnings:
                    print(f"- {warning}")
            print("| Rank | Accepted | Reason | Source | DSL |")
            print("|---:|---:|---|---|---|")
            for candidate in result.validation.candidates:
                print(
                    f"| {candidate.rank} | {candidate.accepted} | "
                    f"{candidate.reason} | {candidate.source} | `{candidate.dsl}` |"
                )
        if not result.passed:
            raise SystemExit(1)
    elif args.command == "evaluate":
        result = evaluate_file(Path(args.input), Path(args.output))
        print(result.to_markdown())
        if result.failed:
            raise SystemExit(1)
    elif args.command == "official-suite":
        from .official_suite import run_official_suite

        result = run_official_suite(
            positive_cases_path=Path(args.positive_input),
            negative_cases_path=Path(args.negative_input),
            data_dir=Path(args.data_dir),
            output_path=Path(args.output),
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "passed": result.passed,
                        "positive_passed": result.positive_passed,
                        "positive_total": result.positive_total,
                        "negative_passed": result.negative_passed,
                        "negative_total": result.negative_total,
                        "output": str(result.output_path),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(result.to_markdown())
        if not result.passed:
            raise SystemExit(1)
    elif args.command == "defense-package":
        from .defense_package import generate_defense_package

        result = generate_defense_package(
            output_path=Path(args.output),
            data_dir=Path(args.data_dir),
            cases_path=Path(args.input),
            official_positive_path=Path(args.positive_input),
            official_negative_path=Path(args.negative_input),
            repo_root=Path(args.repo_root),
        )
        if args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(result.to_markdown())
        if not result.passed:
            raise SystemExit(1)
    elif args.command == "reference":
        from .reference import PandasReferenceEvaluator

        result = PandasReferenceEvaluator(Path(args.data_dir)).evaluate(args.dsl)
        keys = result.keys()
        if args.json:
            print(json.dumps({"keys": keys, "row_count": len(keys)}, ensure_ascii=False, indent=2))
        else:
            print("| ts_code | trade_date |")
            print("|---|---|")
            for ts_code, trade_date in keys:
                print(f"| {ts_code} | {trade_date} |")
    elif args.command == "verify-sql":
        from .equivalence import verify_sql_equivalence

        result = verify_sql_equivalence(
            args.dsl,
            Path(args.data_dir),
            compiler=Compiler(enable_prefix_sum=not args.no_prefix_sum),
        )
        if args.json:
            print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
        else:
            print(result.to_markdown())
        if not result.passed:
            raise SystemExit(1)
    elif args.command == "benchmark-prefix-sum":
        from .benchmark import benchmark_prefix_sum_file

        result = benchmark_prefix_sum_file(
            args.dsl,
            Path(args.data_dir),
            Path(args.output),
            iterations=args.iterations,
        )
        if args.json:
            print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        else:
            print(result.to_markdown())
        if not result.optimized_matches_reference or not result.optimized_matches_baseline:
            raise SystemExit(1)
    elif args.command == "generate-synthetic-data":
        from .synthetic import write_synthetic_dataset

        dataset = write_synthetic_dataset(
            output_dir=Path(args.output_dir),
            stock_count=args.stocks,
            day_count=args.days,
            start_date=args.start_date,
            seed=args.seed,
        )
        print(dataset.to_markdown())
    elif args.command == "scale-benchmark":
        from .scale_benchmark import run_scale_benchmark

        result = run_scale_benchmark(
            output_path=Path(args.output),
            data_dir=Path(args.data_dir),
            stock_count=args.stocks,
            day_count=args.days,
            start_date=args.start_date,
            seed=args.seed,
            window=args.window,
            threshold=args.threshold,
            iterations=args.iterations,
            dsl=args.dsl,
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "data_dir": str(result.dataset.output_dir),
                        "stocks": result.dataset.stock_count,
                        "days": result.dataset.day_count,
                        "rows_per_table": result.dataset.row_count,
                        "iterations": result.benchmark.iterations,
                        "dsl": result.dsl,
                        "baseline_matches_reference": result.benchmark.baseline_matches_reference,
                        "optimized_matches_reference": result.benchmark.optimized_matches_reference,
                        "optimized_matches_baseline": result.benchmark.optimized_matches_baseline,
                        "local_speedup": result.benchmark.local_speedup,
                        "estimated_feature_work_reduction": result.estimated_feature_work_reduction,
                        "output": str(result.output_path),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(result.to_markdown())
        if not result.benchmark.optimized_matches_reference or not result.benchmark.optimized_matches_baseline:
            raise SystemExit(1)
    elif args.command == "emit-doris-assets":
        from .doris import write_doris_assets

        assets = write_doris_assets(
            output_dir=Path(args.output_dir),
            data_dir=Path(args.data_dir),
            database=args.database,
            buckets=args.buckets,
            replication_num=args.replication_num,
        )
        for filename in assets.files():
            print(str(Path(args.output_dir) / filename))
    elif args.command == "collect-doris-evidence":
        from .doris_evidence import DEFAULT_DORIS_EVIDENCE_DSL, DorisClientConfig, collect_doris_evidence

        result = collect_doris_evidence(
            config=DorisClientConfig(
                host=args.host,
                port=args.port,
                user=args.user,
                password=args.password,
                database=args.database,
                client=args.client,
            ),
            output_path=Path(args.output),
            dsl=args.dsl or DEFAULT_DORIS_EVIDENCE_DSL,
            iterations=args.iterations,
            password_mode=args.password_mode,
            min_speedup=args.min_speedup,
        )
        if args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(result.to_markdown())
        if not result.passed:
            raise SystemExit(1)
    elif args.command == "readiness-report":
        from .readiness import generate_readiness_report

        report = generate_readiness_report(
            output_path=Path(args.output),
            reports_dir=Path(args.reports_dir),
            cases_path=Path(args.input),
            data_dir=Path(args.data_dir),
            benchmark_iterations=args.benchmark_iterations,
            run_pytest=not args.skip_pytest,
        )
        print(report.to_markdown())
        if not report.blocking_passed:
            raise SystemExit(1)
    elif args.command == "evidence-metadata":
        from .evidence_metadata import write_evidence_metadata

        manifest_path = Path(args.manifest) if args.manifest else None
        metadata = write_evidence_metadata(
            snapshot_dir=Path(args.snapshots_dir),
            manifest_path=manifest_path,
            output_path=Path(args.output),
            summary_output_path=Path(args.summary_output) if args.summary_output else None,
            contract_path=Path(args.contract) if args.contract else None,
            expected_git_head=args.expected_git_head,
            require_contract_pass=args.require_contract_pass,
        )
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
    elif args.command == "topic-compliance":
        from .topic_compliance import topic_compliance_json, write_topic_compliance_report

        report = write_topic_compliance_report(Path(args.output))
        if args.json:
            print(topic_compliance_json(report))
        else:
            print(report.to_dict())
    elif args.command == "serve-demo":
        from .demo import run_demo_server

        run_demo_server(
            host=args.host,
            port=args.port,
            data_dir=Path(args.data_dir),
            cases_path=Path(args.input),
        )
    elif args.command == "serve-api":
        import uvicorn

        from .official.api import ApiSettings, create_app

        uvicorn.run(
            create_app(settings=ApiSettings.from_env()),
            host=args.host,
            port=args.port,
            log_level=args.log_level,
        )


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .compiler import Compiler
from .evaluation import evaluate_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile financial DSL to Doris SQL")
    sub = parser.add_subparsers(dest="command", required=True)
    compile_cmd = sub.add_parser("compile", help="Compile a DSL expression")
    compile_cmd.add_argument("dsl", help="DSL expression")
    compile_cmd.add_argument("--json", action="store_true", help="Print full JSON result")
    compile_cmd.add_argument("--no-prefix-sum", action="store_true", help="Disable prefix-sum optimizer")
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
    demo_cmd = sub.add_parser("serve-demo", help="Start the local web demo and JSON API")
    demo_cmd.add_argument("--host", default="127.0.0.1", help="Host interface for the demo server")
    demo_cmd.add_argument("--port", type=int, default=8765, help="Port for the demo server")
    demo_cmd.add_argument("--data-dir", default="data/samples", help="Directory containing sample CSV tables")
    demo_cmd.add_argument("--input", default="data/samples/queries.jsonl", help="Input JSONL examples")
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
    elif args.command == "serve-demo":
        from .demo import run_demo_server

        run_demo_server(
            host=args.host,
            port=args.port,
            data_dir=Path(args.data_dir),
            cases_path=Path(args.input),
        )


if __name__ == "__main__":
    main()

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
    eval_cmd = sub.add_parser("evaluate", help="Evaluate compiler against a JSONL case file")
    eval_cmd.add_argument("--input", default="data/samples/queries.jsonl", help="Input JSONL case file")
    eval_cmd.add_argument("--output", default="reports/evaluation_report.md", help="Output Markdown report")
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
    ready_cmd = sub.add_parser("readiness-report", help="Generate submission readiness evidence report")
    ready_cmd.add_argument("--output", default="reports/submission_readiness.md", help="Output Markdown report")
    ready_cmd.add_argument("--reports-dir", default="reports", help="Directory for generated evidence artifacts")
    ready_cmd.add_argument("--input", default="data/samples/queries.jsonl", help="Input JSONL evaluation cases")
    ready_cmd.add_argument("--data-dir", default="data/samples", help="Directory containing sample CSV tables")
    ready_cmd.add_argument("--benchmark-iterations", type=int, default=20, help="Prefix benchmark iterations")
    ready_cmd.add_argument("--skip-pytest", action="store_true", help="Skip pytest when generating the report")
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
    elif args.command == "evaluate":
        result = evaluate_file(Path(args.input), Path(args.output))
        print(result.to_markdown())
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


if __name__ == "__main__":
    main()

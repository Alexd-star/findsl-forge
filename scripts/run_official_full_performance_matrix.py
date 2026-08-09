from __future__ import annotations

import argparse
import os
from pathlib import Path

from findsl.official.backend.executor import DorisExecutionConfig
from findsl.official.correctness import load_correctness_manifest
from findsl.official.performance import (
    load_performance_manifest,
    run_performance_matrix,
    select_performance_cases,
    write_performance_manifest,
    write_performance_report,
)
from findsl.official.watermark import (
    assert_official_watermarks,
    collect_official_watermarks,
    write_official_watermark_report,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--correctness-manifest",
        type=Path,
        default=Path("data/official_correctness/manifest.jsonl"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/official_performance/matrix.jsonl"),
    )
    parser.add_argument("--build-manifest", action="store_true")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--per-family", type=int, default=3)
    parser.add_argument("--max-cases", type=int, default=48)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password-env", default="FINDSL_DORIS_PASSWORD")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--mysql", default="mysql")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--skip-watermark-check", action="store_true")
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("reports/official_full_performance_matrix.json"),
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path("reports/official_full_performance_matrix.md"),
    )
    args = parser.parse_args()

    if args.build_manifest:
        correctness = load_correctness_manifest(args.correctness_manifest)
        selected = select_performance_cases(
            correctness,
            per_family=args.per_family,
            max_cases=args.max_cases,
        )
        write_performance_manifest(selected, args.manifest)
        if args.build_only:
            print(f"manifest={args.manifest} cases={len(selected)}")
            return
    cases = load_performance_manifest(args.manifest)
    doris = DorisExecutionConfig(
        args.host,
        args.port,
        args.user,
        os.getenv(args.password_env, ""),
        args.database,
        args.mysql,
        args.timeout,
    )
    if not args.skip_watermark_check:
        watermark = collect_official_watermarks(
            statistics_path=Path("configs/official/physical_statistics.json"),
            catalog_path=Path("configs/official/physical_catalog.json"),
            doris=doris,
        )
        write_official_watermark_report(
            watermark,
            Path("reports/official_doris_watermark.json"),
            Path("reports/official_doris_watermark.md"),
        )
        assert_official_watermarks(watermark)
    report = run_performance_matrix(
        cases,
        manifest_root=args.correctness_manifest.parent,
        doris=doris,
        warmups=args.warmups,
        repeats=args.repeats,
    )
    write_performance_report(report, args.json_output, args.report_output)
    print(
        f"cases={report['case_count']} passed={report['passed']} "
        f"under_10s={report['all_queries_under_10s']}"
    )
    if not report["all_matched_reference"] or not report["all_queries_under_10s"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

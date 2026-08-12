from __future__ import annotations

import argparse
from pathlib import Path

from findsl.official.compile_latency import (
    run_compile_latency_benchmark,
    write_compile_latency_report,
)
from findsl.official.performance import load_performance_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the canonical official compiler latency gate")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/official_performance/matrix.jsonl"),
    )
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--target-p95-ms", type=float, default=50.0)
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("reports/official_compile_latency.json"),
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path("reports/official_compile_latency.md"),
    )
    args = parser.parse_args()
    report = run_compile_latency_benchmark(
        load_performance_manifest(args.manifest),
        warmups=args.warmups,
        repeats=args.repeats,
        target_p95_ms=args.target_p95_ms,
    )
    write_compile_latency_report(report, args.json_output, args.report_output)
    print(
        f"official compile latency: p95={report['p95_ms']} ms, "
        f"target=<{report['target_p95_ms']} ms, "
        f"status={'PASS' if report['target_met'] else 'FAIL'}"
    )
    return 0 if report["target_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

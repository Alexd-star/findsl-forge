from __future__ import annotations

import argparse
import os
from pathlib import Path

from findsl.official.backend.executor import DorisExecutionConfig
from findsl.official.correctness import (
    load_correctness_manifest,
    run_correctness_benchmark,
    write_correctness_report,
)
from findsl.official.watermark import (
    assert_official_watermarks,
    collect_official_watermarks,
    write_official_watermark_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the frozen official SQL correctness benchmark")
    parser.add_argument("--manifest", default="data/official_correctness/manifest.jsonl")
    parser.add_argument("--json-output", default="reports/official_correctness_benchmark.json")
    parser.add_argument("--report-output", default="reports/official_correctness_benchmark.md")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password-env", default="DORIS_PASSWORD")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--client", default="mysql")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--skip-watermark-check", action="store_true")
    parser.add_argument("--watermark-json", default="reports/official_doris_watermark.json")
    parser.add_argument("--watermark-report", default="reports/official_doris_watermark.md")
    args = parser.parse_args()
    manifest = Path(args.manifest).resolve()
    doris = DorisExecutionConfig(
        args.host,
        args.port,
        args.user,
        os.environ.get(args.password_env, ""),
        args.database,
        args.client,
        args.timeout,
    )
    if not args.skip_watermark_check:
        watermark = collect_official_watermarks(
            statistics_path=Path("configs/official/physical_statistics.json"),
            catalog_path=Path("configs/official/physical_catalog.json"),
            doris=doris,
        )
        write_official_watermark_report(
            watermark, Path(args.watermark_json), Path(args.watermark_report)
        )
        assert_official_watermarks(watermark)
    report = run_correctness_benchmark(
        load_correctness_manifest(manifest),
        manifest_root=manifest.parent,
        doris=doris,
    )
    write_correctness_report(report, Path(args.json_output), Path(args.report_output))
    return 0 if report["target_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

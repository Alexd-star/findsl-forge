from __future__ import annotations

import argparse
import os
from pathlib import Path

from findsl.official.backend.executor import DorisExecutionConfig
from findsl.official.watermark import (
    assert_official_watermarks,
    collect_official_watermarks,
    write_official_watermark_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the official Doris materialization watermarks")
    parser.add_argument("--statistics", type=Path, default=Path("configs/official/physical_statistics.json"))
    parser.add_argument("--catalog", type=Path, default=Path("configs/official/physical_catalog.json"))
    parser.add_argument("--json-output", type=Path, default=Path("reports/official_doris_watermark.json"))
    parser.add_argument("--report-output", type=Path, default=Path("reports/official_doris_watermark.md"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password-env", default="DORIS_PASSWORD")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--client", default="mysql")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    report = collect_official_watermarks(
        statistics_path=args.statistics,
        catalog_path=args.catalog,
        doris=DorisExecutionConfig(
            args.host,
            args.port,
            args.user,
            os.getenv(args.password_env, ""),
            args.database,
            args.client,
            args.timeout,
        ),
    )
    write_official_watermark_report(report, args.json_output, args.report_output)
    assert_official_watermarks(report)
    print(f"status={report['status']} resources={len(report['resources'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

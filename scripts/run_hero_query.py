from __future__ import annotations

import argparse
import os
from pathlib import Path

from findsl.official.backend.executor import DorisExecutionConfig
from findsl.official.hero import run_hero_query, write_hero_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the FinDSL Hero Query")
    parser.add_argument("--spec", type=Path, default=Path("data/hero/hero_query.json"))
    parser.add_argument("--json-output", type=Path, default=Path("reports/hero_query.json"))
    parser.add_argument("--report-output", type=Path, default=Path("reports/hero_query.md"))
    parser.add_argument("--execute-doris", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password-env", default="DORIS_PASSWORD")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--client", default="mysql")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    doris = None
    if args.execute_doris:
        doris = DorisExecutionConfig(
            args.host,
            args.port,
            args.user,
            os.environ.get(args.password_env, ""),
            args.database,
            args.client,
            args.timeout,
        )
    report = run_hero_query(args.spec.resolve(), doris=doris)
    write_hero_report(report, args.json_output, args.report_output)
    if not report["gate"]["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

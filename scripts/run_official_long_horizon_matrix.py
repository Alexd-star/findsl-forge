from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from findsl.official.long_horizon_matrix import (
    load_long_horizon_manifest,
    summarize_long_horizon_reports,
    write_long_horizon_matrix,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the stratified official long-horizon matrix")
    parser.add_argument("--manifest", type=Path, default=Path("data/official_performance/long_horizon_matrix.jsonl"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--http-port", type=int, default=8030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="")
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--expected-rows", type=int, default=13650347)
    parser.add_argument("--case-output-dir", type=Path, default=Path("reports/official_long_horizon_cases"))
    parser.add_argument("--json-output", type=Path, default=Path("reports/official_long_horizon_matrix.json"))
    parser.add_argument("--report-output", type=Path, default=Path("reports/official_long_horizon_matrix.md"))
    args = parser.parse_args()
    cases = load_long_horizon_manifest(args.manifest)
    args.case_output_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    for case in cases:
        json_path = args.case_output_dir / f"{case.case_id}.json"
        markdown_path = args.case_output_dir / f"{case.case_id}.md"
        command = [
            sys.executable,
            "scripts/collect_phase42_long_horizon_evidence.py",
            "--host", args.host,
            "--port", str(args.port),
            "--http-port", str(args.http_port),
            "--user", args.user,
            "--warmups", str(args.warmups),
            "--repeats", str(args.repeats),
            "--min-speedup", str(case.target_speedup),
            "--expected-rows", str(args.expected_rows),
            "--dsl", case.dsl,
            "--json-output", str(json_path),
            "--report-output", str(markdown_path),
        ]
        if args.password:
            command.extend(("--password", args.password))
        completed = subprocess.run(command, check=False)
        if not json_path.is_file():
            raise RuntimeError(f"long-horizon collector produced no report for {case.case_id}")
        reports.append(json.loads(json_path.read_text(encoding="utf-8")))
        if completed.returncode not in {0, 2}:
            raise RuntimeError(f"long-horizon collector failed for {case.case_id}: {completed.returncode}")
    report = summarize_long_horizon_reports(cases, reports)
    report["generated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    report["git_head"] = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()
    report["case_report_directory"] = str(args.case_output_dir)
    write_long_horizon_matrix(report, args.json_output, args.report_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["target_met"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from pathlib import Path

from findsl.final_submission import (
    build_final_submission_metadata,
    write_final_submission_metadata,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the final submission scorecard")
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("reports/final_submission_metadata.json"),
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path("reports/final_submission_summary.md"),
    )
    parser.add_argument("--expected-git-head", default=None)
    args = parser.parse_args()
    metadata = build_final_submission_metadata(
        args.reports_dir,
        expected_git_head=args.expected_git_head,
    )
    write_final_submission_metadata(metadata, args.json_output, args.report_output)
    print(f"status=PASS git_head={metadata['git_head']}")


if __name__ == "__main__":
    main()

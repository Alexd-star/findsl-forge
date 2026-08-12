from __future__ import annotations

import argparse
from pathlib import Path

from findsl.official.capabilities import build_capability_matrix, write_capability_matrix
from findsl.official.correctness import load_correctness_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the 12-family capability matrix")
    parser.add_argument(
        "--manifest", type=Path, default=Path("data/official_correctness/manifest.jsonl")
    )
    parser.add_argument(
        "--json-output", type=Path, default=Path("reports/official_capability_matrix.json")
    )
    parser.add_argument(
        "--report-output", type=Path, default=Path("reports/official_capability_matrix.md")
    )
    args = parser.parse_args()
    report = build_capability_matrix(
        load_correctness_manifest(args.manifest),
        manifest_root=args.manifest.parent,
    )
    write_capability_matrix(report, args.json_output, args.report_output)
    if not report["gate"]["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

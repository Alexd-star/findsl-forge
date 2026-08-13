from __future__ import annotations

import argparse
import json
from pathlib import Path

from findsl.official.context import CompileContext
from findsl.official.corpus_audit import (
    build_corpus_audit,
    render_corpus_audit_markdown,
)
from findsl.official.service import OfficialCompilerService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--funnel", required=True, type=Path)
    parser.add_argument("--profile", default="enriched_public")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--baseline-status-json", type=Path)
    args = parser.parse_args()
    service = OfficialCompilerService(
        context=CompileContext.load(data_profile=args.profile)
    )
    funnel = json.loads(args.funnel.read_text(encoding="utf-8"))
    baseline_status_by_row = None
    if args.baseline_status_json is not None:
        frozen = json.loads(
            args.baseline_status_json.read_text(encoding="utf-8")
        )
        if frozen.get("source_sha256") != funnel.get("source_sha256"):
            raise SystemExit("baseline status source SHA-256 does not match funnel")
        baseline_status_by_row = {
            int(item["excel_row"]): str(item["status"])
            for item in frozen["rows"]
        }
        expected_rows = {int(item["excel_row"]) for item in funnel["rows"]}
        if set(baseline_status_by_row) != expected_rows:
            raise SystemExit("baseline status rows do not exactly match funnel rows")
    report = build_corpus_audit(
        funnel,
        service,
        baseline_status_by_row=baseline_status_by_row,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.output_md.write_text(
        render_corpus_audit_markdown(report), encoding="utf-8"
    )
    print(json.dumps(report["current_status_counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()

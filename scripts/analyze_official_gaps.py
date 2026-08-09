from __future__ import annotations

import argparse
import json
from pathlib import Path

from findsl.official_gap_analysis import analyze_official_funnel, gap_analysis_markdown


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cluster official workbook failures by capability instead of row."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    report = analyze_official_funnel(payload)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered, encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(gap_analysis_markdown(report), encoding="utf-8")
    if not args.json_output and not args.markdown_output:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

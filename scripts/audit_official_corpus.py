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
    args = parser.parse_args()
    service = OfficialCompilerService(
        context=CompileContext.load(data_profile=args.profile)
    )
    report = build_corpus_audit(
        json.loads(args.funnel.read_text(encoding="utf-8")),
        service,
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

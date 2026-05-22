from __future__ import annotations

import argparse
import json
from pathlib import Path

from .compiler import Compiler
from .evaluation import evaluate_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile financial DSL to Doris SQL")
    sub = parser.add_subparsers(dest="command", required=True)
    compile_cmd = sub.add_parser("compile", help="Compile a DSL expression")
    compile_cmd.add_argument("dsl", help="DSL expression")
    compile_cmd.add_argument("--json", action="store_true", help="Print full JSON result")
    eval_cmd = sub.add_parser("evaluate", help="Evaluate compiler against a JSONL case file")
    eval_cmd.add_argument("--input", default="data/samples/queries.jsonl", help="Input JSONL case file")
    eval_cmd.add_argument("--output", default="reports/evaluation_report.md", help="Output Markdown report")
    args = parser.parse_args()

    if args.command == "compile":
        result = Compiler().compile(args.dsl)
        if args.json:
            print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
        else:
            print(result.sql)
            print()
            print("Trace:")
            for item in result.trace:
                print(f"- {item}")
            print(f"Elapsed: {result.elapsed_ms:.3f} ms")
    elif args.command == "evaluate":
        result = evaluate_file(Path(args.input), Path(args.output))
        print(result.to_markdown())


if __name__ == "__main__":
    main()

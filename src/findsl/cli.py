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
    ref_cmd = sub.add_parser("reference", help="Evaluate DSL semantics with the Pandas reference engine")
    ref_cmd.add_argument("dsl", help="DSL expression")
    ref_cmd.add_argument("--data-dir", default="data/samples", help="Directory containing sample CSV tables")
    ref_cmd.add_argument("--json", action="store_true", help="Print result keys as JSON")
    verify_cmd = sub.add_parser("verify-sql", help="Compare compiled SQL output with Pandas reference output")
    verify_cmd.add_argument("dsl", help="DSL expression")
    verify_cmd.add_argument("--data-dir", default="data/samples", help="Directory containing sample CSV tables")
    verify_cmd.add_argument("--json", action="store_true", help="Print verification result as JSON")
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
    elif args.command == "reference":
        from .reference import PandasReferenceEvaluator

        result = PandasReferenceEvaluator(Path(args.data_dir)).evaluate(args.dsl)
        keys = result.keys()
        if args.json:
            print(json.dumps({"keys": keys, "row_count": len(keys)}, ensure_ascii=False, indent=2))
        else:
            print("| ts_code | trade_date |")
            print("|---|---|")
            for ts_code, trade_date in keys:
                print(f"| {ts_code} | {trade_date} |")
    elif args.command == "verify-sql":
        from .equivalence import verify_sql_equivalence

        result = verify_sql_equivalence(args.dsl, Path(args.data_dir))
        if args.json:
            print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
        else:
            print(result.to_markdown())
        if not result.passed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
from pathlib import Path

from findsl.official.financial_rules import (
    FinancialRuleCatalog,
    validate_rule_release_transition,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a financial-rule release candidate")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    baseline = FinancialRuleCatalog.load(args.baseline)
    candidate = FinancialRuleCatalog.load(args.candidate, require_active=False)
    report = validate_rule_release_transition(baseline, candidate)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

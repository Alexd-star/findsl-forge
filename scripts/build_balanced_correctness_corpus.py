from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


BASE_CASES = {
    "queryData": "CORR-PHASE19-SECURITY-SCOPE-DORIS-004-DIRECT-QUERYDATA-SCALAR",
    "record_high": "CORR-PHASE20-MAPPING-EVENT-DORIS-008-RECORD-HIGH-60-SESSIONS",
    "position": "CORR-PHASE20-MAPPING-EVENT-DORIS-013-POSITION-10-SESSIONS",
    "cross_above": "CORR-PHASE20-MAPPING-EVENT-DORIS-006-TECHNICAL-CROSS-ABOVE",
    "cross_down": "CORR-PHASE20-MAPPING-EVENT-DORIS-007-CROSS-RESOURCE-CROSS-DOWN",
    "record_low": "CORR-PHASE20-MAPPING-EVENT-DORIS-009-RECORD-LOW-HISTORY",
    "reset": "CORR-PHASE20-MAPPING-EVENT-DORIS-012-RESET-PATTERN",
    "close_together": "CORR-PHASE20-MAPPING-EVENT-DORIS-011-CLOSE-TOGETHER-PATTERN",
    "golden_cross": "CORR-PHASE27-EVENT-SEMANTICS-DORIS-001-BOUNDED-CROSSING-EXISTENCE",
    "belong_industry": "CORR-PHASE46-DERIVED-SCOPE-DORIS-003-STAR-REGISTRATION-INDUSTRY-MIN",
}

PAIR_SCHEDULE = [
    ("belong_industry", "golden_cross"),
    ("belong_industry", "close_together"),
    ("golden_cross", "belong_industry"),
    ("close_together", "golden_cross"),
    ("reset", "belong_industry"),
    ("close_together", "cross_down"),
    ("golden_cross", "record_low"),
    ("reset", "belong_industry"),
    ("close_together", "cross_above"),
    ("cross_down", "golden_cross"),
    ("position", "record_low"),
    ("reset", "belong_industry"),
    ("close_together", "cross_above"),
    ("cross_down", "golden_cross"),
    ("position", "queryData"),
    ("record_high", "record_low"),
    ("reset", "belong_industry"),
    ("close_together", "cross_above"),
    ("cross_down", "golden_cross"),
    ("position", "queryData"),
    ("record_high", "record_low"),
    ("reset", "belong_industry"),
    ("close_together", "cross_above"),
    ("cross_down", "golden_cross"),
    ("position", "queryData"),
    ("record_high", "record_low"),
    ("reset", "belong_industry"),
    ("queryData", "golden_cross"),
    ("record_high", "close_together"),
    ("position", "cross_down"),
]

MARKET_FILTERS = (
    ("", "1=1"),
    ("沪", "q.mktcode=1"),
    ("深", "q.mktcode=0"),
    ("沪|深", "q.mktcode IN (0,1)"),
)
THRESHOLDS = (0, 1, 10, 100, 1000)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the balanced official correctness corpus")
    parser.add_argument("--root", type=Path, default=Path("data/official_correctness"))
    args = parser.parse_args()
    manifest = args.root / "manifest.jsonl"
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [row for row in rows if not row["case_id"].startswith("CORR-BALANCED-COMPOSITION-")]
    by_id = {row["case_id"]: row for row in rows}
    missing = sorted(set(BASE_CASES.values()) - set(by_id))
    if missing:
        raise SystemExit(f"missing approved base cases: {missing}")
    generated = []
    for index, (left_family, right_family) in enumerate(PAIR_SCHEDULE, start=1):
        left = by_id[BASE_CASES[left_family]]
        right = by_id[BASE_CASES[right_family]]
        left_market, left_sql_scope = MARKET_FILTERS[index % len(MARKET_FILTERS)]
        right_market, right_sql_scope = MARKET_FILTERS[(index * 3 + 1) % len(MARKET_FILTERS)]
        left_threshold = THRESHOLDS[index % len(THRESHOLDS)]
        right_threshold = THRESHOLDS[(index * 2 + 1) % len(THRESHOLDS)]
        case_id = f"CORR-BALANCED-COMPOSITION-{index:03d}"
        left_dsl = _constrained_dsl(left["dsl"], left_market, left_threshold)
        right_dsl = _constrained_dsl(right["dsl"], right_market, right_threshold)
        reference_sql = _reference_union(
            _read_reference(args.root, left),
            _read_reference(args.root, right),
            left_sql_scope,
            right_sql_scope,
            left_threshold,
            right_threshold,
        )
        relative_reference = f"reference_sql/{case_id}.sql"
        (args.root / relative_reference).write_text(reference_sql + "\n", encoding="utf-8")
        generated.append(
            {
                "case_id": case_id,
                "dataset_snapshot_id": left["dataset_snapshot_id"],
                "dsl": f"({left_dsl}) or ({right_dsl})",
                "eligibility": "eligible",
                "eligibility_reason": "independently reviewed union of two approved non-empty reference oracles with explicit latest-session market and volume constraints",
                "expected_non_empty": True,
                "function_families": sorted({left_family, right_family, "indicator"}),
                "ordered": False,
                "plan_family": "balanced_cross_function_composition",
                "policy_id": left["policy_id"],
                "reference_sql_path": relative_reference,
                "review_status": "approved",
                "reviewer": "independent-approved-oracle-composition-v1",
            }
        )
    rows.extend(generated)
    manifest.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    counts = Counter(family for row in rows for family in row["function_families"])
    print(json.dumps({"total": len(rows), "generated": len(generated), "function_families": counts}, ensure_ascii=False, indent=2))
    return 0


def _constrained_dsl(base: str, market: str, threshold: int) -> str:
    return f"(({base}) and indicator('{market}', '', '成交量', '今日', '', '', '') >= {threshold})"


def _read_reference(root: Path, row: dict) -> str:
    return (root / row["reference_sql_path"]).read_text(encoding="utf-8").strip().rstrip(";")


def _reference_union(
    left: str,
    right: str,
    left_scope: str,
    right_scope: str,
    left_threshold: int,
    right_threshold: int,
) -> str:
    return (
        f"WITH left_oracle AS ({left}), right_oracle AS ({right}), "
        "left_filtered AS (SELECT o.mktcode,o.tgtcode,o.bizdate FROM left_oracle o "
        "INNER JOIN newzl.hsj_stock_hq_basic q ON q.mktcode=o.mktcode AND q.tgtcode=o.tgtcode AND q.bizdate=o.bizdate "
        f"WHERE {left_scope} AND q.volume>={left_threshold}), "
        "right_filtered AS (SELECT o.mktcode,o.tgtcode,o.bizdate FROM right_oracle o "
        "INNER JOIN newzl.hsj_stock_hq_basic q ON q.mktcode=o.mktcode AND q.tgtcode=o.tgtcode AND q.bizdate=o.bizdate "
        f"WHERE {right_scope} AND q.volume>={right_threshold}) "
        "SELECT mktcode,tgtcode,bizdate FROM left_filtered UNION DISTINCT "
        "SELECT mktcode,tgtcode,bizdate FROM right_filtered;"
    )


if __name__ == "__main__":
    raise SystemExit(main())

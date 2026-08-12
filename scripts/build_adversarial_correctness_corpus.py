from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


BASE_CASES = {
    "indicator": "CORR-PHASE10-JOIN-DORIS-002-BASIC-SECURITY-LATEST",
    "rank": "CORR-PHASE17-RANK-DORIS-001-DIRECT-TOP-10",
    "belong_industry": "CORR-PHASE46-DERIVED-SCOPE-DORIS-003-STAR-REGISTRATION-INDUSTRY-MIN",
    "queryData": "CORR-PHASE19-SECURITY-SCOPE-DORIS-004-DIRECT-QUERYDATA-SCALAR",
    "cross_above": "CORR-PHASE20-MAPPING-EVENT-DORIS-006-TECHNICAL-CROSS-ABOVE",
    "cross_down": "CORR-PHASE20-MAPPING-EVENT-DORIS-007-CROSS-RESOURCE-CROSS-DOWN",
    "close_together": "CORR-PHASE20-MAPPING-EVENT-DORIS-011-CLOSE-TOGETHER-PATTERN",
    "reset": "CORR-PHASE20-MAPPING-EVENT-DORIS-012-RESET-PATTERN",
    "golden_cross": "CORR-PHASE27-EVENT-SEMANTICS-DORIS-001-BOUNDED-CROSSING-EXISTENCE",
    "record_high": "CORR-PHASE20-MAPPING-EVENT-DORIS-008-RECORD-HIGH-60-SESSIONS",
    "record_low": "CORR-PHASE20-MAPPING-EVENT-DORIS-009-RECORD-LOW-HISTORY",
    "position": "CORR-PHASE20-MAPPING-EVENT-DORIS-013-POSITION-10-SESSIONS",
}

MARKETS = (("", "1=1"), ("沪", "q.mktcode=1"), ("深", "q.mktcode=0"), ("沪|深", "q.mktcode IN (0,1)"))
THRESHOLDS = (0, 1, 10, 100, 1000)
COUNTS = {"intersection": 32, "union": 24, "and_or": 15, "or_and": 11}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the 240-case adversarial correctness corpus")
    parser.add_argument("--root", type=Path, default=Path("data/official_correctness"))
    args = parser.parse_args()
    root = args.root
    manifest = root / "manifest.jsonl"
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [
        row
        for row in rows
        if not row["case_id"].startswith("CORR-ADVERSARIAL-")
        and row["case_id"] != "CORR-CONFIG-FUNCTION-RELATIVE-GAP-001"
    ]
    by_id = {row["case_id"]: row for row in rows}
    missing = sorted(set(BASE_CASES.values()) - set(by_id))
    if missing:
        raise SystemExit(f"missing approved base cases: {missing}")
    if len(rows) != 157:
        raise SystemExit(f"expected the reviewed 157-case baseline, found {len(rows)}")

    families = tuple(BASE_CASES)
    generated = []
    ordinal = 0
    for shape, count in COUNTS.items():
        for local_index in range(count):
            ordinal += 1
            selected = _select_families(families, ordinal, 3 if shape in {"and_or", "or_and"} else 2)
            bases = [by_id[BASE_CASES[family]] for family in selected]
            branches = [_branch(base, family, ordinal, offset, root) for offset, (base, family) in enumerate(zip(bases, selected))]
            dsl, reference = _compose(shape, branches)
            case_id = f"CORR-ADVERSARIAL-{ordinal:03d}-{shape.upper().replace('_', '-')}"
            reference_path = f"reference_sql/{case_id}.sql"
            (root / reference_path).write_text(reference + "\n", encoding="utf-8")
            generated.append(
                {
                    "case_id": case_id,
                    "dataset_snapshot_id": bases[0]["dataset_snapshot_id"],
                    "dsl": dsl,
                    "eligibility": "eligible",
                    "eligibility_reason": "relational composition of independently reviewed reference oracles with explicit market and volume constraints",
                    "expected_non_empty": False,
                    "function_families": sorted({"indicator", *selected}),
                    "ordered": False,
                    "plan_family": f"adversarial_{shape}",
                    "policy_id": bases[0]["policy_id"],
                    "reference_sql_path": reference_path,
                    "review_status": "approved",
                    "reviewer": "independent-relational-oracle-composition-v2",
                }
            )

    configured_case = _configured_function_case(rows[0], root)
    generated.append(configured_case)
    rows.extend(generated)
    if len(rows) != 240 or len(generated) != 83:
        raise SystemExit(f"incorrect corpus size: total={len(rows)}, generated={len(generated)}")
    manifest.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    _write_provenance(root, rows, generated)
    print(json.dumps({"total": len(rows), "generated": len(generated), "shapes": COUNTS}, ensure_ascii=False, indent=2))
    return 0


def _select_families(families: tuple[str, ...], ordinal: int, count: int) -> tuple[str, ...]:
    if ordinal in {53, 64, 67, 79}:
        return ("indicator", "rank", "queryData")[:count]
    indexes = [ordinal % len(families), (ordinal * 5 + 3) % len(families), (ordinal * 7 + 5) % len(families)]
    selected = []
    for index in indexes:
        while families[index] in selected:
            index = (index + 1) % len(families)
        selected.append(families[index])
    return tuple(selected[:count])


def _branch(base: dict, family: str, ordinal: int, offset: int, root: Path) -> dict:
    market, market_sql = MARKETS[(ordinal + offset * 2) % len(MARKETS)]
    threshold = THRESHOLDS[(ordinal * (offset + 1)) % len(THRESHOLDS)]
    dsl = f"(({base['dsl']}) and indicator('{market}', '', '成交量', '今日', '', '', '') >= {threshold})"
    base_sql = (root / base["reference_sql_path"]).read_text(encoding="utf-8").strip().rstrip(";")
    return {
        "family": family,
        "dsl": dsl,
        "base_sql": base_sql,
        "market_sql": market_sql,
        "threshold": threshold,
    }


def _compose(shape: str, branches: list[dict]) -> tuple[str, str]:
    ctes = []
    for index, branch in enumerate(branches, start=1):
        ctes.append(f"oracle_{index} AS ({branch['base_sql']})")
        ctes.append(
            f"branch_{index} AS (SELECT o.mktcode,o.tgtcode,o.bizdate FROM oracle_{index} o "
            "INNER JOIN newzl.hsj_stock_hq_basic q ON q.mktcode=o.mktcode AND q.tgtcode=o.tgtcode AND q.bizdate=o.bizdate "
            f"WHERE {branch['market_sql']} AND q.volume>={branch['threshold']})"
        )
    if shape == "intersection":
        dsl = f"({branches[0]['dsl']}) and ({branches[1]['dsl']})"
        body = _intersection("branch_1", "branch_2")
    elif shape == "union":
        dsl = f"({branches[0]['dsl']}) or ({branches[1]['dsl']})"
        body = _union("branch_1", "branch_2")
    elif shape == "and_or":
        dsl = f"(({branches[0]['dsl']}) and ({branches[1]['dsl']})) or ({branches[2]['dsl']})"
        ctes.append(f"nested_pair AS ({_intersection('branch_1', 'branch_2')})")
        body = _union("nested_pair", "branch_3")
    elif shape == "or_and":
        dsl = f"(({branches[0]['dsl']}) or ({branches[1]['dsl']})) and ({branches[2]['dsl']})"
        ctes.append(f"nested_pair AS ({_union('branch_1', 'branch_2')})")
        body = _intersection("nested_pair", "branch_3")
    else:
        raise ValueError(f"unknown composition shape: {shape}")
    return dsl, "WITH " + ", ".join(ctes) + " " + body + ";"


def _union(left: str, right: str) -> str:
    return (
        f"SELECT mktcode,tgtcode,bizdate FROM {left} UNION DISTINCT "
        f"SELECT mktcode,tgtcode,bizdate FROM {right}"
    )


def _intersection(left: str, right: str) -> str:
    return (
        f"SELECT l.mktcode,l.tgtcode,l.bizdate FROM {left} l INNER JOIN {right} r "
        "ON r.mktcode=l.mktcode AND r.tgtcode=l.tgtcode AND r.bizdate=l.bizdate"
    )


def _write_provenance(root: Path, rows: list[dict], generated: list[dict]) -> None:
    path = root / "provenance.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"cases": {}}
    cases = dict(previous.get("cases") or {})
    generated_ids = {row["case_id"] for row in generated}
    for row in rows:
        case_id = row["case_id"]
        reference = root / row["reference_sql_path"]
        metadata = dict(cases.get(case_id) or {})
        metadata["reference_sha256"] = hashlib.sha256(reference.read_bytes()).hexdigest()
        if case_id in generated_ids:
            metadata.update({
                "source_kind": (
                    "config_only_expression_template_oracle"
                    if row["plan_family"] == "configured_expression_template"
                    else "independent_relational_oracle_composition"
                ),
                "derivation_version": "v2",
                "plan_family": row["plan_family"],
                "reviewer": row["reviewer"],
            })
        elif not metadata:
            metadata.update({"source_kind": "reviewed_manifest_reference", "reviewer": row["reviewer"]})
        cases[case_id] = metadata
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "case_count": len(rows),
                "approved": sum(row["eligibility"] == "eligible" and row["review_status"] == "approved" for row in rows),
                "cases": {row["case_id"]: cases[row["case_id"]] for row in rows},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _configured_function_case(base: dict, root: Path) -> dict:
    case_id = "CORR-CONFIG-FUNCTION-RELATIVE-GAP-001"
    reference_path = f"reference_sql/{case_id}.sql"
    (root / reference_path).write_text(
        "SELECT b.mktcode,b.tgtcode,b.bizdate FROM newzl.hsj_stock_hq_basic b "
        "WHERE b.bizdate=(SELECT MAX(a.bizdate) FROM newzl.hsj_stock_hq_basic a) "
        "AND ABS(b.volume-b.volume)*1.0/NULLIF(ABS(b.volume),0)=0;\n",
        encoding="utf-8",
    )
    indicator = "indicator('', '', '成交量', '今日', '', '', '')"
    return {
        "case_id": case_id,
        "dataset_snapshot_id": base["dataset_snapshot_id"],
        "dsl": f"relative_gap({indicator}, {indicator}) = 0",
        "eligibility": "eligible",
        "eligibility_reason": "config-only nested expression template with an independently authored Doris row-set oracle",
        "expected_non_empty": True,
        "function_families": ["indicator"],
        "ordered": False,
        "plan_family": "configured_expression_template",
        "policy_id": base["policy_id"],
        "reference_sql_path": reference_path,
        "review_status": "approved",
        "reviewer": "config-only-blind-extension-oracle-review-v1",
    }


if __name__ == "__main__":
    raise SystemExit(main())

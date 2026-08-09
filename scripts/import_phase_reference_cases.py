from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from findsl.official.ast import OfficialFunctionCall, walk
from findsl.official.frontend.antlr_frontend import AntlrOfficialFrontend


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import independently written phase reference SQL into the formal benchmark.",
    )
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/official_correctness"),
    )
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--policy-id", default="official-semantic-policy-v1")
    parser.add_argument(
        "--manual-manifest",
        type=Path,
        default=Path("data/official_correctness/manual_cases.jsonl"),
    )
    parser.add_argument("--reviewer", default="")
    parser.add_argument("--approve-matched", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.approve_matched and not args.reviewer.strip():
        raise ValueError("--approve-matched requires a named --reviewer")

    output_root = args.output_root.resolve()
    reference_root = output_root / "reference_sql"
    manifest_path = output_root / "manifest.jsonl"
    provenance_path = output_root / "provenance.json"
    if manifest_path.exists() and not args.force:
        raise FileExistsError(f"manifest already exists: {manifest_path}")

    imported = []
    seen = set()
    frontend = AntlrOfficialFrontend()
    for report_path in sorted(args.reports_dir.glob("phase*_doris.json")):
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        for index, item in enumerate(payload.get("cases") or (), start=1):
            source = str(item.get("source") or "").strip()
            reference_sql = str(item.get("reference_sql") or "").strip()
            if not source or not reference_sql:
                continue
            evidence_ok = _evidence_ok(item)
            identity = hashlib.sha256(
                (source + "\0" + reference_sql).encode("utf-8")
            ).hexdigest()
            if identity in seen:
                continue
            seen.add(identity)
            parsed = frontend.parse(source, original_source=source)
            functions = (
                tuple(
                    sorted(
                        {
                            node.name
                            for node in walk(parsed.ast)
                            if isinstance(node, OfficialFunctionCall)
                        }
                    )
                )
                if parsed.ok
                else ()
            )
            approved = bool(args.approve_matched and evidence_ok and functions)
            case_id = _case_id(report_path.stem, index, item.get("name"))
            reference_relative = Path("reference_sql") / f"{case_id}.sql"
            imported.append(
                {
                    "case_id": case_id,
                    "dsl": source,
                    "function_families": list(functions or ("unclassified",)),
                    "plan_family": str(
                        item.get("selected_strategy")
                        or report_path.stem.removeprefix("phase")
                    ),
                    "eligibility": "eligible" if approved else "review_pending",
                    "eligibility_reason": (
                        "historical Doris full-row oracle evidence passed and was reviewed"
                        if approved
                        else "imported independent reference SQL awaits named semantic review"
                    ),
                    "policy_id": args.policy_id,
                    "dataset_snapshot_id": args.snapshot_id,
                    "expected_non_empty": bool(
                        item.get("non_empty", int(item.get("expected_count", 0)) > 0)
                    ),
                    "reference_sql_path": reference_relative.as_posix(),
                    "review_status": "approved" if approved else "pending",
                    "reviewer": args.reviewer.strip() if approved else "",
                    "ordered": False,
                    "_reference_sql": reference_sql,
                    "_provenance": {
                        "source_report": report_path.as_posix(),
                        "source_git_head": payload.get("git_head"),
                        "source_case_name": item.get("name"),
                        "source_case_index": index,
                        "historical_matched": item.get("matched"),
                        "historical_expected_count": item.get("expected_count"),
                        "historical_actual_count": item.get("actual_count"),
                        "historical_expected_sha256": item.get("expected_sha256"),
                        "historical_actual_sha256": item.get("actual_sha256"),
                        "reference_sha256": hashlib.sha256(
                            reference_sql.encode("utf-8")
                        ).hexdigest(),
                    },
                }
            )

    reference_root.mkdir(parents=True, exist_ok=True)
    manifest_lines = []
    provenance = {}
    for item in imported:
        reference_sql = item.pop("_reference_sql")
        case_provenance = item.pop("_provenance")
        reference_path = output_root / item["reference_sql_path"]
        reference_path.write_text(reference_sql.rstrip(";") + ";\n", encoding="utf-8")
        manifest_lines.append(json.dumps(item, ensure_ascii=False, sort_keys=True))
        provenance[item["case_id"]] = case_provenance
    manual_rows = []
    if args.manual_manifest.is_file():
        for line in args.manual_manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            manual = json.loads(line)
            if manual["case_id"] in provenance:
                raise ValueError(f"duplicate manual correctness case: {manual['case_id']}")
            manual_rows.append(manual)
            manifest_lines.append(json.dumps(manual, ensure_ascii=False, sort_keys=True))
            provenance[manual["case_id"]] = {
                "source_report": args.manual_manifest.as_posix(),
                "source_git_head": "current",
                "reference_sha256": hashlib.sha256(
                    (output_root / manual["reference_sql_path"]).read_bytes()
                ).hexdigest(),
            }
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    provenance_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "case_count": len(imported) + len(manual_rows),
                "approved": sum(
                    1 for item in imported if item["review_status"] == "approved"
                ) + sum(1 for item in manual_rows if item["review_status"] == "approved"),
                "cases": provenance,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "manifest": str(manifest_path),
                "provenance": str(provenance_path),
                "imported": len(imported),
                "manual": len(manual_rows),
                "approved": sum(
                    1 for item in imported if item["review_status"] == "approved"
                ) + sum(1 for item in manual_rows if item["review_status"] == "approved"),
            },
            ensure_ascii=False,
        )
    )


def _evidence_ok(item) -> bool:
    expected_hash = str(item.get("expected_sha256") or "")
    actual_hash = str(item.get("actual_sha256") or "")
    return bool(
        item.get("matched") is True
        and expected_hash
        and expected_hash == actual_hash
        and int(item.get("expected_count", -1)) == int(item.get("actual_count", -2))
    )


def _case_id(report_stem: str, index: int, name) -> str:
    phase = re.sub(r"[^A-Za-z0-9]+", "-", report_stem).strip("-").upper()
    label = re.sub(r"[^A-Za-z0-9]+", "-", str(name or "case")).strip("-").upper()
    return f"CORR-{phase}-{index:03d}-{label[:32]}"


if __name__ == "__main__":
    main()

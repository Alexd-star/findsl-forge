from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_evidence_metadata(snapshot_dir: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    """Build a machine-readable index from exported evidence snapshots."""
    warnings: list[str] = []
    readiness_text = _read_optional_text(snapshot_dir / "submission_readiness.md", warnings)
    official_text = _read_optional_text(snapshot_dir / "official_suite_report.md", warnings)
    manifest_text = _read_optional_text(manifest_path, warnings) if manifest_path else ""
    doris_payload = _read_optional_json(snapshot_dir / "doris_cluster_evidence.json", warnings)
    official_doris_payload = _read_optional_json(
        snapshot_dir / "official_doris_evidence.json",
        warnings,
        warn_missing=False,
    )
    official_slot_payload = _read_optional_json(
        snapshot_dir / "official_slot_coverage.json",
        warnings,
        warn_missing=False,
    )
    official_performance_payload = _read_optional_json(
        snapshot_dir / "official_query_performance_matrix.json",
        warnings,
        warn_missing=False,
    )
    phase20_funnel_payload = _read_optional_json(
        snapshot_dir / "phase20_capability_funnel.json",
        warnings,
        warn_missing=False,
    )
    phase19_funnel_payload = _read_optional_json(
        snapshot_dir / "phase19_security_scope_funnel.json",
        warnings,
        warn_missing=False,
    )
    migration_funnel_payload = phase20_funnel_payload or phase19_funnel_payload or _read_optional_json(
        snapshot_dir / "phase18_dynamic_date_funnel.json",
        warnings,
        warn_missing=False,
    )
    dynamic_date_payload = _read_optional_json(
        snapshot_dir / "phase18_dynamic_date_doris.json",
        warnings,
        warn_missing=False,
    )
    security_scope_payload = _read_optional_json(
        snapshot_dir / "phase19_security_scope_doris.json",
        warnings,
        warn_missing=False,
    )
    mapping_event_payload = _read_optional_json(
        snapshot_dir / "phase20_mapping_event_doris.json",
        warnings,
        warn_missing=False,
    )

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "snapshot_dir": str(snapshot_dir),
        "git": {
            "head_at_report_generation": _extract_git_head(readiness_text),
            "head_at_export": _extract_value(manifest_text, r"- Git HEAD at export:\s*`?([^`\n]+?)`?\s*$"),
            "branch": _extract_value(readiness_text, r"- Git branch:\s*`?([^`\n]+?)`?\s*$"),
        },
        "readiness": _readiness_metadata(readiness_text),
        "official_suite": _official_suite_metadata(official_text or readiness_text),
        "official_real_data": {
            "doris": _official_doris_metadata(official_doris_payload),
            "slot_coverage": _official_slot_coverage_metadata(official_slot_payload),
            "performance_matrix": _official_performance_matrix_metadata(official_performance_payload),
        },
        "official_migration": _official_migration_metadata(
            migration_funnel_payload,
            dynamic_date_payload,
            security_scope_payload,
            mapping_event_payload,
        ),
        "doris_cluster": _doris_metadata(doris_payload),
        "warnings": warnings,
        "source_files": _source_files(snapshot_dir, manifest_path),
    }


def write_evidence_metadata(
    snapshot_dir: Path,
    output_path: Path,
    manifest_path: Path | None = None,
    summary_output_path: Path | None = None,
) -> dict[str, Any]:
    metadata = build_evidence_metadata(snapshot_dir=snapshot_dir, manifest_path=manifest_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if summary_output_path is not None:
        summary_output_path.parent.mkdir(parents=True, exist_ok=True)
        summary_output_path.write_text(render_evidence_summary_markdown(metadata), encoding="utf-8")
    return metadata


def render_evidence_summary_markdown(metadata: dict[str, Any]) -> str:
    readiness = _dict(metadata.get("readiness"))
    official = _dict(metadata.get("official_suite"))
    official_real = _dict(metadata.get("official_real_data"))
    official_doris = _dict(official_real.get("doris"))
    official_slot = _dict(official_real.get("slot_coverage"))
    official_perf = _dict(official_real.get("performance_matrix"))
    official_migration = _dict(metadata.get("official_migration"))
    dynamic_date = _dict(official_migration.get("dynamic_date_evidence"))
    security_scope = _dict(official_migration.get("security_scope_evidence"))
    mapping_event = _dict(official_migration.get("mapping_event_evidence"))
    doris = _dict(metadata.get("doris_cluster"))
    git = _dict(metadata.get("git"))
    warnings = metadata.get("warnings") if isinstance(metadata.get("warnings"), list) else []
    sources = _dict(metadata.get("source_files"))

    lines = [
        "# Evidence Summary",
        "",
        "This summary is generated from `evidence_metadata.json`. Use the snapshot files listed below as the audit source.",
        "",
        "## Headline Gates",
        "",
        "| Item | Value |",
        "|---|---|",
        f"| Blocking gates | {_pass_fail(readiness.get('blocking_gates_passed'))} |",
        f"| Warning count | {_display(readiness.get('warning_count'))} |",
        f"| Pytest regression | {_pytest_display(readiness)} |",
        f"| Official positive cases | {_ratio_display(_dict(official.get('positive')))} |",
        f"| Official negative diagnostics | {_ratio_display(_dict(official.get('negative')))} |",
        f"| Official slot coverage | {_official_slot_coverage_display(official_slot)} |",
        f"| ANTLR/IR legacy migration | {_official_migration_display(official_migration)} |",
        f"| Phase 18 dynamic date evidence | {_dynamic_date_display(dynamic_date)} |",
        f"| Phase 19 security scope evidence | {_security_scope_display(security_scope)} |",
        f"| Phase 20 mapping/event evidence | {_mapping_event_display(mapping_event)} |",
        f"| Official per-query 10s target | {_official_performance_display(official_perf)} |",
        f"| Official Doris real data | {_official_doris_display(official_doris)} |",
        f"| Official Doris feature tables | {_pass_fail(official_doris.get('feature_tables_available'))} |",
        f"| Official Doris prefix speedup | {_display(official_doris.get('baseline_vs_prefix_speedup_display'))} |",
        f"| Defense package checks | {_ratio_display(_dict(readiness.get('defense_package_checks')))} |",
        f"| Doris evidence | {_doris_evidence_display(doris)} |",
        f"| Doris cluster speedup | {_display(doris.get('speedup_display'))} |",
        f"| Doris row parity | {_pass_fail(doris.get('row_counts_match'))} |",
        f"| Git HEAD at report generation | {_display(git.get('head_at_report_generation'))} |",
        f"| Git HEAD at export | {_display(git.get('head_at_export'))} |",
        "",
        "## Source Files",
        "",
        "| Source | Path |",
        "|---|---|",
    ]
    for name, path in sources.items():
        lines.append(f"| {name} | `{_display(path)}` |")

    lines.extend(["", "## Metadata Warnings", ""])
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- <none>")
    lines.append("")
    return "\n".join(lines)


def _read_optional_text(path: Path | None, warnings: list[str]) -> str:
    if path is None:
        return ""
    if not path.exists():
        warnings.append(f"{path.name} not found; related metadata fields are unavailable.")
        return ""
    return path.read_text(encoding="utf-8")


def _read_optional_json(path: Path, warnings: list[str], *, warn_missing: bool = True) -> dict[str, Any] | None:
    if not path.exists():
        if warn_missing:
            warnings.append(f"{path.name} not found; Doris metrics are unavailable.")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(f"{path.name} is not valid JSON: {exc.msg}.")
        return None
    if not isinstance(payload, dict):
        warnings.append(f"{path.name} JSON root is not an object.")
        return None
    return payload


def _readiness_metadata(text: str) -> dict[str, Any]:
    pytest_match = re.search(r"(?m)^(\d+)\s+passed\s+in\s+([0-9.]+)s\b", text)
    return {
        "generated_at": _extract_value(text, r"- Generated at:\s*([^\n]+)"),
        "blocking_gates_passed": _extract_bool(text, r"- Blocking gates passed:\s*(True|False)"),
        "warning_count": _extract_int(text, r"- Warning count:\s*(\d+)"),
        "compile_success_rate_percent": _extract_float(text, r"- Compile success rate:\s*([0-9.]+)%"),
        "sql_fragment_accuracy_percent": _extract_float(text, r"- SQL fragment accuracy:\s*([0-9.]+)%"),
        "compile_p95_latency_ms": _extract_float(text, r"- Compile P95 latency:\s*([0-9.]+)\s*ms"),
        "evaluation_cases": _extract_ratio(text, r"- Evaluation cases passed:\s*(\d+)/(\d+)"),
        "defense_package_checks": _extract_ratio(text, r"- Defense package checks:\s*(\d+)/(\d+)"),
        "pytest": {
            "passed": int(pytest_match.group(1)) if pytest_match else None,
            "elapsed_seconds": float(pytest_match.group(2)) if pytest_match else None,
        },
    }


def _official_suite_metadata(text: str) -> dict[str, Any]:
    return {
        "suite_passed": _extract_bool(text, r"- Suite passed:\s*(True|False)"),
        "positive": _extract_ratio(
            text,
            r"- (?:Positive cases passed|Official-style positive cases):\s*(\d+)/(\d+)",
        ),
        "negative": _extract_ratio(
            text,
            r"- (?:Negative diagnostic cases passed|Official-style negative diagnostics):\s*(\d+)/(\d+)",
        ),
    }


def _doris_metadata(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {
            "available": False,
            "passed": None,
            "row_counts_match": None,
            "speedup": None,
            "speedup_display": None,
            "speedup_target_met": None,
        }
    speedup = _number_or_none(payload.get("speedup"))
    baseline = payload.get("baseline") if isinstance(payload.get("baseline"), dict) else {}
    optimized = payload.get("optimized") if isinstance(payload.get("optimized"), dict) else {}
    return {
        "available": True,
        "passed": _bool_or_none(payload.get("passed")),
        "row_counts_match": _bool_or_none(payload.get("row_counts_match")),
        "speedup": speedup,
        "speedup_display": f"{speedup:.2f}x" if speedup is not None else None,
        "speedup_target_met": _bool_or_none(payload.get("speedup_target_met")),
        "min_speedup": _number_or_none(payload.get("min_speedup")),
        "baseline_plan_contains_window": _bool_or_none(payload.get("baseline_plan_contains_window")),
        "optimized_plan_contains_prefix": _bool_or_none(payload.get("optimized_plan_contains_prefix")),
        "baseline_avg_execute_ms": _number_or_none(baseline.get("avg_execute_ms")),
        "optimized_avg_execute_ms": _number_or_none(optimized.get("avg_execute_ms")),
        "baseline_row_count": _int_or_none(baseline.get("row_count")),
        "optimized_row_count": _int_or_none(optimized.get("row_count")),
    }


def _official_doris_metadata(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {
            "available": False,
            "feature_tables_available": None,
            "baseline_prefix_row_count_match": None,
            "baseline_vs_prefix_speedup": None,
            "baseline_vs_prefix_speedup_display": None,
            "row_counts": {},
            "feature_table_row_counts": {},
        }
    speedup = _number_or_none(payload.get("baseline_vs_prefix_speedup"))
    row_counts = payload.get("row_counts") if isinstance(payload.get("row_counts"), dict) else {}
    feature_rows = (
        payload.get("feature_table_row_counts")
        if isinstance(payload.get("feature_table_row_counts"), dict)
        else {}
    )
    return {
        "available": True,
        "feature_tables_available": _bool_or_none(payload.get("feature_tables_available")),
        "baseline_prefix_row_count_match": _bool_or_none(payload.get("baseline_prefix_row_count_match")),
        "baseline_vs_prefix_speedup": speedup,
        "baseline_vs_prefix_speedup_display": f"{speedup:.2f}x" if speedup is not None else None,
        "row_counts": row_counts,
        "feature_table_row_counts": feature_rows,
    }


def _official_slot_coverage_metadata(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {
            "available": False,
            "row_count": None,
            "parse_ok": None,
            "parse_failed": None,
            "compile_ok": None,
            "compile_failed": None,
            "compile_rate_on_all_rows": None,
            "compile_rate_on_parse_ok": None,
        }
    return {
        "available": True,
        "row_count": _int_or_none(payload.get("row_count")),
        "parse_ok": _int_or_none(payload.get("parse_ok")),
        "parse_failed": _int_or_none(payload.get("parse_failed")),
        "compile_ok": _int_or_none(payload.get("compile_ok")),
        "compile_failed": _int_or_none(payload.get("compile_failed")),
        "compile_rate_on_all_rows": _number_or_none(payload.get("compile_rate_on_all_rows")),
        "compile_rate_on_parse_ok": _number_or_none(payload.get("compile_rate_on_parse_ok")),
    }


def _official_performance_matrix_metadata(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {
            "available": False,
            "query_count": None,
            "all_queries_under_10s": None,
            "max_p95_ms": None,
            "mean_avg_ms": None,
            "prefix_query_count": None,
            "window_query_count": None,
            "baseline_prefix_row_count_match": None,
            "baseline_vs_prefix_speedup": None,
            "baseline_vs_prefix_speedup_display": None,
        }
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    speedup = _number_or_none(summary.get("baseline_vs_prefix_speedup"))
    return {
        "available": True,
        "query_count": _int_or_none(summary.get("query_count")),
        "all_queries_under_10s": _bool_or_none(summary.get("all_queries_under_10s")),
        "max_p95_ms": _number_or_none(summary.get("max_p95_ms")),
        "mean_avg_ms": _number_or_none(summary.get("mean_avg_ms")),
        "prefix_query_count": _int_or_none(summary.get("prefix_query_count")),
        "window_query_count": _int_or_none(summary.get("window_query_count")),
        "baseline_prefix_row_count_match": _bool_or_none(summary.get("baseline_prefix_row_count_match")),
        "baseline_vs_prefix_speedup": speedup,
        "baseline_vs_prefix_speedup_display": f"{speedup:.2f}x" if speedup is not None else None,
    }


def _official_migration_metadata(
    funnel: dict[str, Any] | None,
    dynamic_date: dict[str, Any] | None,
    security_scope: dict[str, Any] | None,
    mapping_event: dict[str, Any] | None,
) -> dict[str, Any]:
    gaps = funnel.get("migration_gaps") if isinstance(funnel, dict) else None
    date_gap = None
    if isinstance(gaps, list):
        date_gap = 0
        for item in gaps:
            if isinstance(item, dict) and item.get("code") == "PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED":
                date_gap = _int_or_none(item.get("count"))
                break
    p95_values = []
    if isinstance(dynamic_date, dict) and isinstance(dynamic_date.get("cases"), list):
        p95_values = [
            value
            for item in dynamic_date["cases"]
            if isinstance(item, dict)
            for value in [_number_or_none(item.get("p95_ms"))]
            if value is not None
        ]
    scope_p95_values = []
    if isinstance(security_scope, dict) and isinstance(security_scope.get("cases"), list):
        scope_p95_values = [
            value
            for item in security_scope["cases"]
            if isinstance(item, dict)
            for value in [_number_or_none(item.get("p95_ms"))]
            if value is not None
        ]
    mapping_p95_values = []
    if isinstance(mapping_event, dict) and isinstance(mapping_event.get("cases"), list):
        mapping_p95_values = [
            value
            for item in mapping_event["cases"]
            if isinstance(item, dict)
            for value in [_number_or_none(item.get("p95_ms"))]
            if value is not None
        ]
    return {
        "available": funnel is not None,
        "git_head": funnel.get("git_head") if isinstance(funnel, dict) else None,
        "legacy_strict_success": _int_or_none(funnel.get("legacy_strict_success")) if isinstance(funnel, dict) else None,
        "legacy_to_new_migrated": _int_or_none(funnel.get("legacy_to_new_migrated")) if isinstance(funnel, dict) else None,
        "migration_coverage": _number_or_none(funnel.get("migration_coverage")) if isinstance(funnel, dict) else None,
        "new_backend_success": _int_or_none(funnel.get("new_backend_success")) if isinstance(funnel, dict) else None,
        "physical_date_gap": date_gap,
        "dynamic_date_evidence": {
            "available": dynamic_date is not None,
            "status": dynamic_date.get("status") if isinstance(dynamic_date, dict) else None,
            "matched": _int_or_none(dynamic_date.get("matched")) if isinstance(dynamic_date, dict) else None,
            "total": _int_or_none(dynamic_date.get("total")) if isinstance(dynamic_date, dict) else None,
            "latest_data_date": dynamic_date.get("latest_data_date") if isinstance(dynamic_date, dict) else None,
            "trading_date_count": _int_or_none(dynamic_date.get("trading_date_count")) if isinstance(dynamic_date, dict) else None,
            "max_p95_ms": max(p95_values) if p95_values else None,
        },
        "security_scope_evidence": {
            "available": security_scope is not None,
            "status": security_scope.get("status") if isinstance(security_scope, dict) else None,
            "matched": _int_or_none(security_scope.get("matched")) if isinstance(security_scope, dict) else None,
            "total": _int_or_none(security_scope.get("total")) if isinstance(security_scope, dict) else None,
            "catalog_rows": _int_or_none(security_scope.get("security_catalog_rows")) if isinstance(security_scope, dict) else None,
            "catalog_source_match": _bool_or_none(security_scope.get("security_catalog_source_match")) if isinstance(security_scope, dict) else None,
            "max_p95_ms": max(scope_p95_values) if scope_p95_values else None,
        },
        "mapping_event_evidence": {
            "available": mapping_event is not None,
            "status": mapping_event.get("status") if isinstance(mapping_event, dict) else None,
            "matched": _int_or_none(mapping_event.get("matched")) if isinstance(mapping_event, dict) else None,
            "total": _int_or_none(mapping_event.get("total")) if isinstance(mapping_event, dict) else None,
            "non_empty": _int_or_none(mapping_event.get("non_empty")) if isinstance(mapping_event, dict) else None,
            "latest_data_date": mapping_event.get("latest_data_date") if isinstance(mapping_event, dict) else None,
            "max_p95_ms": max(mapping_p95_values) if mapping_p95_values else None,
        },
    }


def _source_files(snapshot_dir: Path, manifest_path: Path | None) -> dict[str, str | None]:
    return {
        "submission_readiness": str(snapshot_dir / "submission_readiness.md"),
        "official_suite_report": str(snapshot_dir / "official_suite_report.md"),
        "official_doris_evidence_json": str(snapshot_dir / "official_doris_evidence.json"),
        "official_slot_coverage_json": str(snapshot_dir / "official_slot_coverage.json"),
        "official_query_performance_matrix_json": str(snapshot_dir / "official_query_performance_matrix.json"),
        "phase18_dynamic_date_funnel_json": str(snapshot_dir / "phase18_dynamic_date_funnel.json"),
        "phase18_dynamic_date_doris_json": str(snapshot_dir / "phase18_dynamic_date_doris.json"),
        "phase19_security_scope_funnel_json": str(snapshot_dir / "phase19_security_scope_funnel.json"),
        "phase19_security_scope_doris_json": str(snapshot_dir / "phase19_security_scope_doris.json"),
        "phase20_capability_funnel_json": str(snapshot_dir / "phase20_capability_funnel.json"),
        "phase20_mapping_event_doris_json": str(snapshot_dir / "phase20_mapping_event_doris.json"),
        "doris_cluster_evidence_json": str(snapshot_dir / "doris_cluster_evidence.json"),
        "evidence_manifest": str(manifest_path) if manifest_path else None,
    }


def _extract_git_head(text: str) -> str | None:
    value = _extract_value(text, r"- Git HEAD(?: at report generation)?:\s*`?([^`\s]+)")
    return value.strip() if value else None


def _extract_value(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def _extract_bool(text: str, pattern: str) -> bool | None:
    value = _extract_value(text, pattern)
    if value is None:
        return None
    return value == "True"


def _extract_int(text: str, pattern: str) -> int | None:
    value = _extract_value(text, pattern)
    return int(value) if value is not None else None


def _extract_float(text: str, pattern: str) -> float | None:
    value = _extract_value(text, pattern)
    return float(value) if value is not None else None


def _extract_ratio(text: str, pattern: str) -> dict[str, int | None]:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        return {"passed": None, "total": None}
    return {"passed": int(match.group(1)), "total": int(match.group(2))}


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    return None


def _bool_or_none(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _display(value: Any) -> str:
    if value is None:
        return "<unknown>"
    return str(value)


def _pass_fail(value: Any) -> str:
    if value is True:
        return "PASS"
    if value is False:
        return "FAIL"
    return "<unknown>"


def _ratio_display(value: dict[str, Any]) -> str:
    passed = value.get("passed")
    total = value.get("total")
    if passed is None or total is None:
        return "<unknown>"
    return f"{passed}/{total}"


def _pytest_display(readiness: dict[str, Any]) -> str:
    pytest = _dict(readiness.get("pytest"))
    passed = pytest.get("passed")
    elapsed = pytest.get("elapsed_seconds")
    if passed is None:
        return "<unknown>"
    if elapsed is None:
        return f"{passed} passed"
    return f"{passed} passed in {elapsed:.2f}s"


def _doris_evidence_display(doris: dict[str, Any]) -> str:
    if doris.get("available") is False:
        return "UNAVAILABLE"
    return _pass_fail(doris.get("passed"))


def _official_doris_display(doris: dict[str, Any]) -> str:
    if doris.get("available") is False:
        return "UNAVAILABLE"
    return "AVAILABLE"


def _official_slot_coverage_display(slot_coverage: dict[str, Any]) -> str:
    if slot_coverage.get("available") is False:
        return "UNAVAILABLE"
    compile_ok = slot_coverage.get("compile_ok")
    row_count = slot_coverage.get("row_count")
    if compile_ok is None or row_count is None:
        return "<unknown>"
    return f"{compile_ok}/{row_count} compiled"


def _official_migration_display(migration: dict[str, Any]) -> str:
    if migration.get("available") is False:
        return "UNAVAILABLE"
    migrated = migration.get("legacy_to_new_migrated")
    denominator = migration.get("legacy_strict_success")
    coverage = migration.get("migration_coverage")
    if migrated is None or denominator is None or coverage is None:
        return "<unknown>"
    return f"{migrated}/{denominator} ({coverage * 100:.2f}%)"


def _dynamic_date_display(evidence: dict[str, Any]) -> str:
    if evidence.get("available") is False:
        return "UNAVAILABLE"
    status = evidence.get("status") or "<unknown>"
    matched = evidence.get("matched")
    total = evidence.get("total")
    max_p95 = evidence.get("max_p95_ms")
    if matched is None or total is None:
        return str(status)
    suffix = f", max P95 {max_p95:.4f} ms" if isinstance(max_p95, (int, float)) else ""
    return f"{status}, {matched}/{total}{suffix}"


def _security_scope_display(evidence: dict[str, Any]) -> str:
    if evidence.get("available") is False:
        return "UNAVAILABLE"
    status = evidence.get("status") or "<unknown>"
    matched = evidence.get("matched")
    total = evidence.get("total")
    catalog_match = _pass_fail(evidence.get("catalog_source_match"))
    max_p95 = evidence.get("max_p95_ms")
    if matched is None or total is None:
        return str(status)
    suffix = f", max P95 {max_p95:.4f} ms" if isinstance(max_p95, (int, float)) else ""
    return f"{status}, {matched}/{total}, catalog {catalog_match}{suffix}"


def _mapping_event_display(evidence: dict[str, Any]) -> str:
    if evidence.get("available") is False:
        return "UNAVAILABLE"
    status = evidence.get("status") or "<unknown>"
    matched = evidence.get("matched")
    total = evidence.get("total")
    non_empty = evidence.get("non_empty")
    max_p95 = evidence.get("max_p95_ms")
    if matched is None or total is None:
        return str(status)
    non_empty_text = f", non-empty {non_empty}/{total}" if non_empty is not None else ""
    suffix = f", max P95 {max_p95:.4f} ms" if isinstance(max_p95, (int, float)) else ""
    return f"{status}, {matched}/{total}{non_empty_text}{suffix}"


def _official_performance_display(performance: dict[str, Any]) -> str:
    if performance.get("available") is False:
        return "UNAVAILABLE"
    status = _pass_fail(performance.get("all_queries_under_10s"))
    query_count = performance.get("query_count")
    max_p95 = performance.get("max_p95_ms")
    if query_count is None or max_p95 is None:
        return status
    return f"{status}, {query_count} queries, max P95 {max_p95} ms"

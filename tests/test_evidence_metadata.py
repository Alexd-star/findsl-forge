from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from findsl.evidence_metadata import build_evidence_metadata, render_evidence_summary_markdown


def _write_minimal_snapshots(
    snapshot_dir: Path,
    *,
    include_doris: bool = True,
    include_official_real_data: bool = True,
) -> None:
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "submission_readiness.md").write_text(
        "\n".join(
            [
                "# Submission Readiness",
                "",
                "- Generated at: 2026-06-07T09:55:48+00:00",
                "- Git HEAD at report generation: `c7a2164` fix: harden Doris SQL table validation",
                "- Git branch: `main`",
                "- Blocking gates passed: True",
                "- Warning count: 0",
                "",
                "## Competition Metrics",
                "",
                "- Compile success rate: 100.00%",
                "- SQL fragment accuracy: 100.00%",
                "- Compile P95 latency: 2.124 ms",
                "- Evaluation cases passed: 10/10",
                "- Official-style positive cases: 37/37",
                "- Official-style negative diagnostics: 37/37",
                "- Defense package checks: 13/13",
                "",
                "## Pytest Regression Suite",
                "",
                "311 passed in 28.48s",
            ]
        ),
        encoding="utf-8",
    )
    (snapshot_dir / "official_suite_report.md").write_text(
        "\n".join(
            [
                "# Official-Style Coverage Suite",
                "",
                "- Suite passed: True",
                "- Positive cases passed: 37/37",
                "- Negative diagnostic cases passed: 37/37",
            ]
        ),
        encoding="utf-8",
    )
    if include_doris:
        (snapshot_dir / "doris_cluster_evidence.json").write_text(
            json.dumps(
                {
                    "passed": True,
                    "row_counts_match": True,
                    "speedup": 36.2398279300624,
                    "speedup_target_met": True,
                    "min_speedup": 10.0,
                    "baseline_plan_contains_window": True,
                    "optimized_plan_contains_prefix": True,
                    "baseline": {"avg_execute_ms": 5182.04244, "row_count": 88586},
                    "optimized": {"avg_execute_ms": 142.99302, "row_count": 88586},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    if include_official_real_data:
        (snapshot_dir / "official_doris_evidence.json").write_text(
            json.dumps(
                {
                    "row_counts": {
                        "hsj_stock_code_info": 5686,
                        "hsj_stock_hq_basic": 13650347,
                        "hsj_stock_hq_ext": 6170822,
                    },
                    "feature_tables_available": True,
                    "feature_table_row_counts": {
                        "hsj_stock_hq_basic_prefix": 13650347,
                        "hsj_stock_hq_ext_prefix": 13650347,
                        "hsj_stock_hq_basic_technical": 13650347,
                    },
                    "baseline_prefix_row_count_match": True,
                    "baseline_vs_prefix_speedup": 1.173,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (snapshot_dir / "official_slot_coverage.json").write_text(
            json.dumps(
                {
                    "row_count": 5799,
                    "parse_ok": 5799,
                    "parse_failed": 0,
                    "compile_ok": 1882,
                    "compile_failed": 3917,
                    "compile_rate_on_all_rows": 0.324539,
                    "compile_rate_on_parse_ok": 0.324539,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (snapshot_dir / "official_query_performance_matrix.json").write_text(
            json.dumps(
                {
                    "summary": {
                        "query_count": 6,
                        "all_queries_under_10s": True,
                        "max_p95_ms": 61.269,
                        "mean_avg_ms": 45.493,
                        "prefix_query_count": 1,
                        "window_query_count": 2,
                        "baseline_prefix_row_count_match": True,
                        "baseline_vs_prefix_speedup": 1.173,
                    },
                    "queries": [
                        {"name": "simple_close_price_filter", "execution_target": "PASS"},
                        {"name": "prefix_optimized_volume_sum_20", "execution_target": "PASS"},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (snapshot_dir / "phase18_dynamic_date_funnel.json").write_text(
            json.dumps(
                {
                    "git_head": "c7a2164",
                    "legacy_strict_success": 1097,
                    "legacy_to_new_migrated": 393,
                    "migration_coverage": 0.35825,
                    "new_backend_success": 400,
                    "migration_gaps": [
                        {"code": "PHYSICAL_CONSTRAINT_UNSUPPORTED", "count": 259}
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (snapshot_dir / "phase18_dynamic_date_doris.json").write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "matched": 9,
                    "total": 9,
                    "latest_data_date": "2026-04-14",
                    "trading_date_count": 4631,
                    "cases": [{"p95_ms": 221.9858}, {"p95_ms": 180.0}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (snapshot_dir / "phase19_security_scope_funnel.json").write_text(
            json.dumps(
                {
                    "git_head": "c7a2164",
                    "legacy_strict_success": 1097,
                    "legacy_to_new_migrated": 406,
                    "migration_coverage": 0.3701,
                    "new_backend_success": 413,
                    "migration_gaps": [
                        {"code": "PHYSICAL_SCOPE_DATA_UNAVAILABLE", "count": 244}
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (snapshot_dir / "phase19_security_scope_doris.json").write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "matched": 7,
                    "total": 7,
                    "security_catalog_rows": 5686,
                    "security_catalog_source_match": True,
                    "cases": [{"p95_ms": 615.5937}, {"p95_ms": 200.0}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (snapshot_dir / "phase20_capability_funnel.json").write_text(
            json.dumps(
                {
                    "git_head": "c7a2164",
                    "legacy_strict_success": 1097,
                    "legacy_to_new_migrated": 534,
                    "migration_coverage": 0.48678,
                    "new_backend_success": 548,
                    "migration_gaps": [
                        {"code": "PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED", "count": 2}
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (snapshot_dir / "phase20_mapping_event_doris.json").write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "matched": 13,
                    "total": 13,
                    "non_empty": 13,
                    "latest_data_date": "2026-04-14",
                    "cases": [{"p95_ms": 1612.9413}, {"p95_ms": 500.0}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


def test_build_evidence_metadata_extracts_readiness_official_and_doris_metrics(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshots"
    _write_minimal_snapshots(snapshot_dir)
    manifest = tmp_path / "evidence_manifest.md"
    manifest.write_text("- Git HEAD at export: c7a2164\n", encoding="utf-8")

    metadata = build_evidence_metadata(snapshot_dir=snapshot_dir, manifest_path=manifest)

    assert metadata["readiness"]["blocking_gates_passed"] is True
    assert metadata["readiness"]["warning_count"] == 0
    assert metadata["readiness"]["pytest"]["passed"] == 311
    assert metadata["readiness"]["pytest"]["elapsed_seconds"] == 28.48
    assert metadata["official_suite"]["positive"] == {"passed": 37, "total": 37}
    assert metadata["official_suite"]["negative"] == {"passed": 37, "total": 37}
    assert metadata["doris_cluster"]["speedup"] == 36.2398279300624
    assert metadata["doris_cluster"]["speedup_display"] == "36.24x"
    assert metadata["doris_cluster"]["row_counts_match"] is True
    assert metadata["doris_cluster"]["baseline_avg_execute_ms"] == 5182.04244
    assert metadata["doris_cluster"]["optimized_avg_execute_ms"] == 142.99302
    assert metadata["official_real_data"]["doris"]["available"] is True
    assert metadata["official_real_data"]["doris"]["feature_tables_available"] is True
    assert metadata["official_real_data"]["doris"]["baseline_prefix_row_count_match"] is True
    assert metadata["official_real_data"]["doris"]["baseline_vs_prefix_speedup_display"] == "1.17x"
    assert metadata["official_real_data"]["slot_coverage"]["row_count"] == 5799
    assert metadata["official_real_data"]["slot_coverage"]["parse_ok"] == 5799
    assert metadata["official_real_data"]["slot_coverage"]["compile_ok"] == 1882
    assert metadata["official_real_data"]["performance_matrix"]["available"] is True
    assert metadata["official_real_data"]["performance_matrix"]["query_count"] == 6
    assert metadata["official_real_data"]["performance_matrix"]["all_queries_under_10s"] is True
    assert metadata["official_real_data"]["performance_matrix"]["max_p95_ms"] == 61.269
    assert metadata["official_real_data"]["performance_matrix"]["baseline_vs_prefix_speedup_display"] == "1.17x"
    assert metadata["official_migration"]["legacy_to_new_migrated"] == 534
    assert metadata["official_migration"]["legacy_strict_success"] == 1097
    assert metadata["official_migration"]["physical_date_gap"] == 2
    assert metadata["official_migration"]["dynamic_date_evidence"]["matched"] == 9
    assert metadata["official_migration"]["dynamic_date_evidence"]["max_p95_ms"] == 221.9858
    assert metadata["official_migration"]["security_scope_evidence"]["matched"] == 7
    assert metadata["official_migration"]["security_scope_evidence"]["catalog_rows"] == 5686
    assert metadata["official_migration"]["security_scope_evidence"]["catalog_source_match"] is True
    assert metadata["official_migration"]["security_scope_evidence"]["max_p95_ms"] == 615.5937
    assert metadata["official_migration"]["mapping_event_evidence"]["matched"] == 13
    assert metadata["official_migration"]["mapping_event_evidence"]["non_empty"] == 13
    assert metadata["official_migration"]["mapping_event_evidence"]["max_p95_ms"] == 1612.9413
    assert metadata["git"]["head_at_report_generation"] == "c7a2164"
    assert metadata["git"]["head_at_export"] == "c7a2164"
    assert metadata["warnings"] == []


def test_build_evidence_metadata_prefers_phase22_and_indexes_stage_rank_evidence(
    tmp_path: Path,
) -> None:
    snapshot_dir = tmp_path / "snapshots"
    _write_minimal_snapshots(snapshot_dir)
    (snapshot_dir / "phase22_capability_funnel.json").write_text(
        json.dumps(
            {
                "git_head": "phase22-head",
                "legacy_strict_success": 1097,
                "legacy_to_new_migrated": 647,
                "migration_coverage": 0.58979,
                "new_backend_success": 663,
                "migration_gaps": [
                    {"code": "PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED", "count": 4}
                ],
            }
        ),
        encoding="utf-8",
    )
    (snapshot_dir / "phase22_stage_rank_doris.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "matched": 6,
                "total": 6,
                "non_empty": 6,
                "latest_data_date": "2026-04-14",
                "cases": [{"p95_ms": 535.2768}, {"p95_ms": 426.0784}],
            }
        ),
        encoding="utf-8",
    )
    (snapshot_dir / "phase22_new_success_audit.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "new_successes": 16,
                "passed": 16,
                "failed": 0,
            }
        ),
        encoding="utf-8",
    )

    metadata = build_evidence_metadata(snapshot_dir=snapshot_dir)

    assert metadata["official_migration"]["git_head"] == "phase22-head"
    assert metadata["official_migration"]["legacy_to_new_migrated"] == 647
    assert metadata["official_migration"]["new_backend_success"] == 663
    assert metadata["official_migration"]["stage_rank_evidence"] == {
        "available": True,
        "status": "PASS",
        "matched": 6,
        "total": 6,
        "non_empty": 6,
        "latest_data_date": "2026-04-14",
        "max_p95_ms": 535.2768,
    }
    assert metadata["official_migration"]["new_success_audit"]["passed"] == 16
    assert metadata["source_files"]["phase22_stage_rank_doris_json"].endswith(
        "phase22_stage_rank_doris.json"
    )


def test_build_evidence_metadata_prefers_phase23_relational_evidence(
    tmp_path: Path,
) -> None:
    snapshot_dir = tmp_path / "snapshots"
    _write_minimal_snapshots(snapshot_dir)
    (snapshot_dir / "phase23_capability_funnel.json").write_text(
        json.dumps(
            {
                "git_head": "phase23-head",
                "legacy_strict_success": 1097,
                "legacy_to_new_migrated": 660,
                "migration_coverage": 0.601641,
                "new_backend_success": 677,
                "migration_gaps": [],
            }
        ),
        encoding="utf-8",
    )
    (snapshot_dir / "phase23_relational_doris.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "matched": 6,
                "total": 6,
                "non_empty": 6,
                "latest_data_date": "2026-04-14",
                "cases": [{"p95_ms": 1285.81}, {"p95_ms": 588.64}],
            }
        ),
        encoding="utf-8",
    )
    (snapshot_dir / "phase23_new_success_audit.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "new_successes": 14,
                "passed": 14,
                "failed": 0,
            }
        ),
        encoding="utf-8",
    )

    metadata = build_evidence_metadata(snapshot_dir=snapshot_dir)

    assert metadata["official_migration"]["git_head"] == "phase23-head"
    assert metadata["official_migration"]["legacy_to_new_migrated"] == 660
    assert metadata["official_migration"]["new_backend_success"] == 677
    assert metadata["official_migration"]["relational_evidence"] == {
        "available": True,
        "status": "PASS",
        "matched": 6,
        "total": 6,
        "non_empty": 6,
        "latest_data_date": "2026-04-14",
        "max_p95_ms": 1285.81,
    }
    assert metadata["official_migration"]["new_success_audit"]["passed"] == 14
    assert metadata["source_files"]["phase23_relational_doris_json"].endswith(
        "phase23_relational_doris.json"
    )


def test_build_evidence_metadata_prefers_phase24_period_scalar_evidence(
    tmp_path: Path,
) -> None:
    snapshot_dir = tmp_path / "snapshots"
    _write_minimal_snapshots(snapshot_dir)
    (snapshot_dir / "phase24_capability_funnel.json").write_text(
        json.dumps(
            {
                "git_head": "phase24-head",
                "legacy_strict_success": 1097,
                "legacy_to_new_migrated": 667,
                "migration_coverage": 0.608022,
                "new_backend_success": 687,
                "migration_gaps": [],
            }
        ),
        encoding="utf-8",
    )
    (snapshot_dir / "phase24_period_scalar_doris.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "matched": 4,
                "total": 4,
                "non_empty": 4,
                "latest_data_date": "2026-04-14",
                "cases": [{"p95_ms": 446.22}, {"p95_ms": 390.61}],
            }
        ),
        encoding="utf-8",
    )
    (snapshot_dir / "phase24_new_success_audit.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "new_successes": 10,
                "passed": 10,
                "failed": 0,
            }
        ),
        encoding="utf-8",
    )

    metadata = build_evidence_metadata(snapshot_dir=snapshot_dir)

    assert metadata["official_migration"]["git_head"] == "phase24-head"
    assert metadata["official_migration"]["legacy_to_new_migrated"] == 667
    assert metadata["official_migration"]["new_backend_success"] == 687
    assert metadata["official_migration"]["period_scalar_evidence"] == {
        "available": True,
        "status": "PASS",
        "matched": 4,
        "total": 4,
        "non_empty": 4,
        "latest_data_date": "2026-04-14",
        "max_p95_ms": 446.22,
    }
    assert metadata["official_migration"]["new_success_audit"]["passed"] == 10
    assert metadata["source_files"]["phase24_period_scalar_doris_json"].endswith(
        "phase24_period_scalar_doris.json"
    )


def test_build_evidence_metadata_prefers_phase25_event_candidate_evidence(
    tmp_path: Path,
) -> None:
    snapshot_dir = tmp_path / "snapshots"
    _write_minimal_snapshots(snapshot_dir)
    (snapshot_dir / "phase25_capability_funnel.json").write_text(
        json.dumps(
            {
                "git_head": "phase25-head",
                "legacy_strict_success": 1097,
                "legacy_to_new_migrated": 675,
                "migration_coverage": 0.615314,
                "new_backend_success": 695,
                "migration_gaps": [],
            }
        ),
        encoding="utf-8",
    )
    (snapshot_dir / "phase25_event_candidate_doris.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "matched": 5,
                "total": 5,
                "non_empty": 5,
                "latest_data_date": "2026-04-14",
                "cases": [{"p95_ms": 4555.13}, {"p95_ms": 1891.63}],
            }
        ),
        encoding="utf-8",
    )
    (snapshot_dir / "phase25_new_success_audit.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "new_successes": 8,
                "passed": 8,
                "failed": 0,
            }
        ),
        encoding="utf-8",
    )

    metadata = build_evidence_metadata(snapshot_dir=snapshot_dir)

    assert metadata["official_migration"]["git_head"] == "phase25-head"
    assert metadata["official_migration"]["legacy_to_new_migrated"] == 675
    assert metadata["official_migration"]["new_backend_success"] == 695
    assert metadata["official_migration"]["event_candidate_evidence"] == {
        "available": True,
        "status": "PASS",
        "matched": 5,
        "total": 5,
        "non_empty": 5,
        "latest_data_date": "2026-04-14",
        "max_p95_ms": 4555.13,
    }
    assert metadata["official_migration"]["new_success_audit"]["passed"] == 8
    assert metadata["source_files"]["phase25_event_candidate_doris_json"].endswith(
        "phase25_event_candidate_doris.json"
    )


def test_build_evidence_metadata_prefers_phase26_date_limit_evidence(
    tmp_path: Path,
) -> None:
    snapshot_dir = tmp_path / "snapshots"
    _write_minimal_snapshots(snapshot_dir)
    (snapshot_dir / "phase26_capability_funnel.json").write_text(
        json.dumps(
            {
                "git_head": "phase26-head",
                "legacy_strict_success": 1097,
                "legacy_to_new_migrated": 686,
                "migration_coverage": 0.625342,
                "new_backend_success": 709,
                "migration_gaps": [],
            }
        ),
        encoding="utf-8",
    )
    (snapshot_dir / "phase26_date_limit_doris.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "matched": 6,
                "total": 6,
                "non_empty": 6,
                "latest_data_date": "2026-04-14",
                "cases": [{"p95_ms": 821.25}, {"p95_ms": 304.1}],
            }
        ),
        encoding="utf-8",
    )
    (snapshot_dir / "phase26_new_success_audit.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "new_successes": 14,
                "passed": 14,
                "failed": 0,
            }
        ),
        encoding="utf-8",
    )

    metadata = build_evidence_metadata(snapshot_dir=snapshot_dir)

    assert metadata["official_migration"]["git_head"] == "phase26-head"
    assert metadata["official_migration"]["legacy_to_new_migrated"] == 686
    assert metadata["official_migration"]["new_backend_success"] == 709
    assert metadata["official_migration"]["date_limit_evidence"] == {
        "available": True,
        "status": "PASS",
        "matched": 6,
        "total": 6,
        "non_empty": 6,
        "latest_data_date": "2026-04-14",
        "max_p95_ms": 821.25,
    }
    assert metadata["official_migration"]["new_success_audit"]["passed"] == 14
    assert metadata["source_files"]["phase26_date_limit_doris_json"].endswith(
        "phase26_date_limit_doris.json"
    )


def test_build_evidence_metadata_warns_when_optional_doris_json_is_missing(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshots"
    _write_minimal_snapshots(snapshot_dir, include_doris=False)

    metadata = build_evidence_metadata(snapshot_dir=snapshot_dir, manifest_path=None)

    assert metadata["doris_cluster"]["available"] is False
    assert metadata["doris_cluster"]["passed"] is None
    assert "doris_cluster_evidence.json not found; Doris metrics are unavailable." in metadata["warnings"]


def test_evidence_metadata_cli_writes_json(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshots"
    output = tmp_path / "evidence_metadata.json"
    _write_minimal_snapshots(snapshot_dir)
    env = os.environ.copy()
    env["PYTHONPATH"] = "src" + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONIOENCODING"] = "utf-8"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "findsl.cli",
            "evidence-metadata",
            "--snapshots-dir",
            str(snapshot_dir),
            "--output",
            str(output),
        ],
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=env,
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["readiness"]["blocking_gates_passed"] is True
    assert payload["doris_cluster"]["speedup_display"] == "36.24x"


def test_render_evidence_summary_markdown_highlights_auditable_metrics(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshots"
    _write_minimal_snapshots(snapshot_dir)
    metadata = build_evidence_metadata(snapshot_dir=snapshot_dir)

    markdown = render_evidence_summary_markdown(metadata)

    assert markdown.startswith("# Evidence Summary")
    assert "| Blocking gates | PASS |" in markdown
    assert "| Warning count | 0 |" in markdown
    assert "| Pytest regression | 311 passed" in markdown
    assert "| Official positive cases | 37/37 |" in markdown
    assert "| Official slot coverage | 1882/5799 compiled |" in markdown
    assert "| ANTLR/IR legacy migration | 534/1097 (48.68%) |" in markdown
    assert "| Phase 18 dynamic date evidence | PASS, 9/9, max P95 221.9858 ms |" in markdown
    assert "| Phase 19 security scope evidence | PASS, 7/7, catalog PASS, max P95 615.5937 ms |" in markdown
    assert "| Phase 20 mapping/event evidence | PASS, 13/13, non-empty 13/13, max P95 1612.9413 ms |" in markdown
    assert "| Official per-query 10s target | PASS, 6 queries, max P95 61.269 ms |" in markdown
    assert "| Official Doris real data | AVAILABLE |" in markdown
    assert "| Official Doris feature tables | PASS |" in markdown
    assert "| Doris cluster speedup | 36.24x |" in markdown
    assert "| Git HEAD at report generation | c7a2164 |" in markdown
    assert "submission_readiness.md" in markdown
    assert "doris_cluster_evidence.json" in markdown


def test_render_evidence_summary_markdown_marks_missing_doris_metrics(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshots"
    _write_minimal_snapshots(snapshot_dir, include_doris=False)
    metadata = build_evidence_metadata(snapshot_dir=snapshot_dir)

    markdown = render_evidence_summary_markdown(metadata)

    assert "| Doris evidence | UNAVAILABLE |" in markdown
    assert "doris_cluster_evidence.json not found; Doris metrics are unavailable." in markdown

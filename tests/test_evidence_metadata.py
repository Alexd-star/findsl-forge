from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from findsl.evidence_metadata import build_evidence_metadata, render_evidence_summary_markdown


def _write_minimal_snapshots(snapshot_dir: Path, *, include_doris: bool = True) -> None:
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
                "192 passed in 11.61s",
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


def test_build_evidence_metadata_extracts_readiness_official_and_doris_metrics(tmp_path: Path) -> None:
    snapshot_dir = tmp_path / "snapshots"
    _write_minimal_snapshots(snapshot_dir)
    manifest = tmp_path / "evidence_manifest.md"
    manifest.write_text("- Git HEAD at export: c7a2164\n", encoding="utf-8")

    metadata = build_evidence_metadata(snapshot_dir=snapshot_dir, manifest_path=manifest)

    assert metadata["readiness"]["blocking_gates_passed"] is True
    assert metadata["readiness"]["warning_count"] == 0
    assert metadata["readiness"]["pytest"]["passed"] == 192
    assert metadata["readiness"]["pytest"]["elapsed_seconds"] == 11.61
    assert metadata["official_suite"]["positive"] == {"passed": 37, "total": 37}
    assert metadata["official_suite"]["negative"] == {"passed": 37, "total": 37}
    assert metadata["doris_cluster"]["speedup"] == 36.2398279300624
    assert metadata["doris_cluster"]["speedup_display"] == "36.24x"
    assert metadata["doris_cluster"]["row_counts_match"] is True
    assert metadata["doris_cluster"]["baseline_avg_execute_ms"] == 5182.04244
    assert metadata["doris_cluster"]["optimized_avg_execute_ms"] == 142.99302
    assert metadata["git"]["head_at_report_generation"] == "c7a2164"
    assert metadata["git"]["head_at_export"] == "c7a2164"
    assert metadata["warnings"] == []


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
    assert "| Pytest regression | 192 passed" in markdown
    assert "| Official positive cases | 37/37 |" in markdown
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

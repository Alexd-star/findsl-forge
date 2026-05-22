from pathlib import Path

from findsl.readiness import generate_readiness_report


def test_generate_readiness_report_collects_submission_evidence(tmp_path):
    reports_dir = tmp_path / "reports"
    output = reports_dir / "submission_readiness.md"

    report = generate_readiness_report(
        output_path=output,
        reports_dir=reports_dir,
        benchmark_iterations=1,
        run_pytest=False,
    )

    assert report.blocking_passed
    assert output.exists()
    assert (reports_dir / "evaluation_report.md").exists()
    assert (reports_dir / "sql_equivalence_report.md").exists()
    assert (reports_dir / "prefix_sum_benchmark.md").exists()
    assert report.evaluation.failed == 0
    assert report.equivalence.passed
    assert report.benchmark.optimized_matches_reference
    assert all(asset.passed for asset in report.doris_assets)

    content = output.read_text(encoding="utf-8")
    assert "FinDSL Forge Submission Readiness Report" in content
    assert "Compiler accuracy and latency" in content
    assert "Doris Asset Integrity" in content
    assert "Award-Readiness Differentiators" in content


def test_readiness_report_keeps_doris_scale_proof_as_warning(tmp_path):
    report = generate_readiness_report(
        output_path=tmp_path / "submission_readiness.md",
        reports_dir=tmp_path / "reports",
        benchmark_iterations=1,
        run_pytest=False,
    )

    warnings = {gate.name: gate for gate in report.gates if gate.level == "warning"}
    assert "Doris-scale performance proof" in warnings
    assert not warnings["Doris-scale performance proof"].passed
    assert report.blocking_passed

from pathlib import Path

from findsl.readiness import generate_readiness_report


def test_generate_readiness_report_collects_submission_evidence(tmp_path):
    reports_dir = tmp_path / "reports"
    output = reports_dir / "submission_readiness.md"
    (reports_dir).mkdir(parents=True)
    (reports_dir / "prefix_sum_scale_benchmark.md").write_text(
        "\n".join(
            [
                "# Prefix-Sum Scale Benchmark",
                "- Optimized matches Pandas reference: True",
                "- Optimized matches baseline: True",
                "- Long-window feature-access reduction estimate: 60.0x",
            ]
        ),
        encoding="utf-8",
    )
    (reports_dir / "doris_cluster_evidence.md").write_text(
        "\n".join(
            [
                "# Doris Cluster Evidence",
                "- Evidence source: Apache Doris MySQL-compatible query port",
                "- Evidence passed: True",
                "- Baseline success: True",
                "- Optimized success: True",
                "- Row counts match: True",
                "- Minimum Doris speedup target: 10.00x",
                "- Doris speedup target met: True",
                "- Optimized plan contains prefix table: True",
                "- Baseline plan contains window: True",
            ]
        ),
        encoding="utf-8",
    )

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
    assert (reports_dir / "official_suite_report.md").exists()
    assert (reports_dir / "defense_package.md").exists()
    assert (reports_dir / "prefix_sum_benchmark.md").exists()
    assert report.evaluation.failed == 0
    assert report.equivalence.passed
    assert report.benchmark.optimized_matches_reference
    assert all(asset.passed for asset in report.doris_assets)
    assert report.scale_report.passed
    assert report.doris_cluster_report.passed
    assert report.demo_smoke.passed
    assert report.nl2dsl_smoke.passed
    assert report.llm_safety_smoke.passed
    assert report.llm_safety_smoke.accepted_count == 1
    assert "UNSAFE_DIRECT_SQL" in report.llm_safety_smoke.rejected_codes
    assert "UNKNOWN_INDICATOR" in report.llm_safety_smoke.rejected_codes
    assert report.diagnostics_smoke.passed
    assert report.doris_sql_smoke.passed
    assert report.doris_sql_smoke.escaped_literal
    assert report.real_market_sample.passed
    assert report.real_market_sample.passed_cases == report.real_market_sample.total_cases
    assert report.real_market_sample.raw_payload_count >= 2
    assert report.official_suite.passed
    assert report.official_suite.positive_passed == 37
    assert report.official_suite.negative_passed == 37
    assert report.defense_package.passed
    assert report.defense_package.passed_count == report.defense_package.total
    required_gates = {gate.name: gate for gate in report.gates if gate.level == "required"}
    warning_gates = {gate.name: gate for gate in report.gates if gate.level == "warning"}
    assert required_gates["NL2DSL validated candidate"].passed
    assert required_gates["LLM candidate safety loop"].passed
    assert required_gates["Structured diagnostics repair hints"].passed
    assert required_gates["Doris SQL validation boundary"].passed
    assert required_gates["Real-market quote sample"].passed
    assert required_gates["Official-style coverage suite"].passed
    assert required_gates["Defense package walkthrough"].passed
    assert warning_gates["Doris-scale performance proof"].passed

    content = output.read_text(encoding="utf-8")
    assert "FinDSL Forge Submission Readiness Report" in content
    assert "Compiler accuracy and latency" in content
    assert "Long-Window Scale Evidence" in content
    assert "Doris Cluster Evidence" in content
    assert "Demo Smoke Test" in content
    assert "NL2DSL Smoke Test" in content
    assert "NL2DSL validated candidate" in content
    assert "LLM Candidate Safety Smoke Test" in content
    assert "LLM candidate safety loop" in content
    assert "UNSAFE_DIRECT_SQL" in content
    assert "Diagnostics Smoke Test" in content
    assert "Structured diagnostics repair hints" in content
    assert "Doris SQL Validation Smoke Test" in content
    assert "Doris SQL validation boundary" in content
    assert "Real-Market Quote Sample" in content
    assert "Real-market quote sample" in content
    assert "Eastmoney public historical K-line endpoint" in content
    assert "Official-Style Coverage Suite" in content
    assert "Official-style coverage suite" in content
    assert "Defense Package" in content
    assert "Defense package walkthrough" in content
    assert "Doris Asset Integrity" in content
    assert "Award-Readiness Differentiators" in content
    assert "Local SQLite prefix benchmark speedup smoke" in content
    assert "not used as the Doris-scale performance claim" in content


def test_readiness_report_keeps_doris_scale_proof_as_warning(tmp_path):
    report = generate_readiness_report(
        output_path=tmp_path / "submission_readiness.md",
        reports_dir=tmp_path / "reports",
        benchmark_iterations=1,
        run_pytest=False,
    )

    warnings = {gate.name: gate for gate in report.gates if gate.level == "warning"}
    assert "Long-window scale benchmark evidence" in warnings
    assert not warnings["Long-window scale benchmark evidence"].passed
    assert "Doris-scale performance proof" in warnings
    assert not warnings["Doris-scale performance proof"].passed
    assert not report.doris_cluster_report.passed
    assert report.blocking_passed


def test_readiness_report_requires_real_doris_evidence_markers(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "doris_cluster_evidence.md").write_text(
        "\n".join(
            [
                "# Doris Cluster Evidence",
                "- Evidence source: Apache Doris MySQL-compatible query port",
                "- Evidence passed: True",
                "- Baseline success: True",
                "- Optimized success: True",
            ]
        ),
        encoding="utf-8",
    )

    report = generate_readiness_report(
        output_path=tmp_path / "submission_readiness.md",
        reports_dir=reports_dir,
        benchmark_iterations=1,
        run_pytest=False,
    )

    warnings = {gate.name: gate for gate in report.gates if gate.level == "warning"}
    assert not report.doris_cluster_report.passed
    assert "Row counts match: True" in report.doris_cluster_report.missing_markers
    assert "Doris speedup target met: True" in report.doris_cluster_report.missing_markers
    assert "Optimized plan contains prefix table: True" in report.doris_cluster_report.missing_markers
    assert not warnings["Doris-scale performance proof"].passed

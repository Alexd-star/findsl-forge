from pathlib import Path

from findsl.official.performance_evidence import validate_performance_evidence_registry


def test_performance_evidence_metrics_are_separated_by_workload():
    report = validate_performance_evidence_registry(
        Path("configs/official/performance_evidence_registry.json")
    )

    assert report["passed"] is True
    assert len(report["metrics"]) == 5
    gates = [item for item in report["metrics"] if item["score_gate"]]
    assert [item["metric_id"] for item in gates] == ["official_long_horizon_gate"]
    assert gates[0]["speedup"] >= 10.0

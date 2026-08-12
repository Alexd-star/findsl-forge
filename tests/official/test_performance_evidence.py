import json
from pathlib import Path

from findsl.official.performance_evidence import validate_performance_evidence_registry


def test_performance_evidence_metrics_are_separated_by_workload(tmp_path):
    registry = _isolated_registry(tmp_path, long_horizon_speedup=10.5)

    report = validate_performance_evidence_registry(registry, root=tmp_path)

    assert report["passed"] is True
    assert len(report["metrics"]) == 5
    gates = [item for item in report["metrics"] if item["score_gate"]]
    assert [item["metric_id"] for item in gates] == ["official_long_horizon_gate"]
    assert gates[0]["speedup"] >= 10.0


def test_performance_evidence_registry_fails_only_the_long_horizon_gate(tmp_path):
    registry = _isolated_registry(tmp_path, long_horizon_speedup=9.99)

    report = validate_performance_evidence_registry(registry, root=tmp_path)

    assert report["passed"] is False
    metrics = {item["metric_id"]: item for item in report["metrics"]}
    assert metrics["official_long_horizon_gate"]["source_value_matched"] is False
    assert all(
        item["source_value_matched"]
        for metric_id, item in metrics.items()
        if metric_id != "official_long_horizon_gate"
    )


def _isolated_registry(tmp_path: Path, *, long_horizon_speedup: float) -> Path:
    registry = json.loads(
        Path("configs/official/performance_evidence_registry.json").read_text(
            encoding="utf-8"
        )
    )
    values = {
        "official_routine_prefix": 1.2,
        "official_long_horizon_gate": long_horizon_speedup,
        "synthetic_5m_scalability": 2.3,
        "phase6c_projection_prefix": 1.1,
        "legacy_six_query_matrix_prefix": 1.05,
    }
    for metric in registry["metrics"]:
        source = Path("evidence") / f"{metric['metric_id']}.json"
        metric["source"] = source.as_posix()
        payload = {}
        target = payload
        parts = metric["value_path"].split(".")
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = values[metric["metric_id"]]
        output = tmp_path / source
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "performance_evidence_registry.json"
    output.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
    return output

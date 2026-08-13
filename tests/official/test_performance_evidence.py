import json
from pathlib import Path

from findsl.official.performance_evidence import validate_performance_evidence_registry
from findsl.versioning import resolve_release_head


def test_performance_evidence_metrics_are_separated_by_workload(tmp_path):
    registry = _isolated_registry(tmp_path, long_horizon_speedup=10.5)

    report = validate_performance_evidence_registry(registry, root=tmp_path)

    assert report["passed"] is True
    assert len(report["metrics"]) == 6
    assert report["all_source_heads_match_packaging"] is True
    gates = {item["metric_id"] for item in report["metrics"] if item["score_gate"]}
    assert gates == {
        "official_long_horizon_min_speedup",
        "official_full_matrix_max_p95",
        "official_compile_p95",
    }


def test_performance_evidence_registry_fails_long_horizon_threshold(tmp_path):
    registry = _isolated_registry(tmp_path, long_horizon_speedup=9.99)

    report = validate_performance_evidence_registry(registry, root=tmp_path)

    assert report["passed"] is False
    metrics = {item["metric_id"]: item for item in report["metrics"]}
    assert metrics["official_long_horizon_min_speedup"]["threshold_met"] is False
    assert all(
        item["source_value_matched"]
        for metric_id, item in metrics.items()
        if metric_id != "official_long_horizon_min_speedup"
    )


def test_performance_evidence_registry_rejects_stale_source_head(tmp_path):
    registry = _isolated_registry(tmp_path, long_horizon_speedup=10.5)
    payload = json.loads(registry.read_text(encoding="utf-8"))
    source = tmp_path / payload["metrics"][0]["source"]
    evidence = json.loads(source.read_text(encoding="utf-8"))
    evidence["git_head"] = "stale-head"
    source.write_text(json.dumps(evidence), encoding="utf-8")

    report = validate_performance_evidence_registry(registry, root=tmp_path)

    assert report["passed"] is False
    assert report["all_source_heads_match_packaging"] is False
    assert report["metrics"][0]["threshold_met"] is True
    assert report["metrics"][0]["source_head_matches_packaging"] is False


def _isolated_registry(tmp_path: Path, *, long_horizon_speedup: float) -> Path:
    registry = json.loads(
        Path("configs/official/performance_evidence_registry.json").read_text(
            encoding="utf-8"
        )
    )
    values = {
        "official_routine_prefix_speedup": 1.2,
        "official_long_horizon_min_speedup": long_horizon_speedup,
        "synthetic_5m_scalability_speedup": 2.3,
        "official_full_matrix_max_p95": 9000.0,
        "official_compile_p95": 49.9,
        "hero_query_execution": 1200.0,
    }
    current_head = resolve_release_head()
    for metric in registry["metrics"]:
        source = Path("evidence") / f"{metric['metric_id']}.json"
        metric["source"] = source.as_posix()
        payload = {"git_head": current_head}
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

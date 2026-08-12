from pathlib import Path

from findsl.official.long_horizon_matrix import (
    load_long_horizon_manifest,
    summarize_long_horizon_reports,
)


def test_long_horizon_manifest_covers_five_distinct_prefix_workloads() -> None:
    cases = load_long_horizon_manifest(Path("data/official_performance/long_horizon_matrix.jsonl"))

    assert len(cases) == 5
    assert {(case.indicator, case.aggregation) for case in cases} == {
        ("成交量", "SUM"),
        ("成交量", "AVG"),
        ("成交额", "SUM"),
        ("收盘价", "SUM"),
        ("收盘价", "AVG"),
    }


def test_long_horizon_summary_requires_hash_latency_and_speedup() -> None:
    cases = load_long_horizon_manifest(Path("data/official_performance/long_horizon_matrix.jsonl"))
    reports = [
        {
            "speedup": 12.0,
            "complete_result_hash_match": True,
            "row_count_match": True,
            "result_row_count": 10,
            "baseline": {"median_ms": 1200},
            "optimized": {"median_ms": 100, "p95_ms": 150},
            "baseline_strategy": "grouped_aggregate",
            "optimized_strategy": "prefix_aggregate",
            "optimized_resource_id": "official_basic_rollup",
        }
        for _ in cases
    ]

    report = summarize_long_horizon_reports(cases, reports)

    assert report["status"] == "PASS"
    assert report["minimum_speedup"] == 12.0
    assert report["all_complete_result_hashes_match"] is True
    reports[-1]["optimized"]["p95_ms"] = 10_001
    assert summarize_long_horizon_reports(cases, reports)["status"] == "FAIL"

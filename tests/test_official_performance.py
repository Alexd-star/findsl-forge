from __future__ import annotations

import json

from findsl.official_performance import build_official_performance_matrix, write_official_performance_matrix


def _sample_evidence():
    return {
        "generated_at": "2026-07-06T08:00:00Z",
        "row_counts": {
            "hsj_stock_hq_basic": 13650347,
            "hsj_stock_hq_ext": 6170822,
            "hsj_stock_code_info": 5686,
        },
        "baseline_prefix_row_count_match": True,
        "baseline_vs_prefix_speedup": 12.345,
        "queries": [
            {
                "name": "baseline_window_volume_sum_20",
                "row_count": 5487,
                "avg_ms": 44.321,
                "p95_ms": 55.058,
                "plan_contains_prefix": False,
                "plan_contains_window": True,
                "sql": "SELECT ... ROWS BETWEEN 19 PRECEDING AND CURRENT ROW",
            },
            {
                "name": "prefix_optimized_volume_sum_20",
                "row_count": 5487,
                "avg_ms": 37.8,
                "p95_ms": 38.786,
                "plan_contains_prefix": True,
                "plan_contains_window": False,
                "sql": "SELECT ... FROM newzl.hsj_stock_hq_basic_prefix",
            },
        ],
    }


def test_build_official_performance_matrix_marks_query_level_targets():
    matrix = build_official_performance_matrix(_sample_evidence())

    assert matrix["summary"]["query_count"] == 2
    assert matrix["summary"]["all_queries_under_10s"] is True
    assert matrix["summary"]["baseline_prefix_row_count_match"] is True
    assert matrix["summary"]["baseline_vs_prefix_speedup"] == 12.345
    assert matrix["summary"]["max_p95_ms"] == 55.058
    assert matrix["queries"][0]["execution_target"] == "PASS"
    assert matrix["queries"][0]["plan_kind"] == "window"
    assert matrix["queries"][1]["plan_kind"] == "prefix"


def test_empty_official_performance_matrix_does_not_pass_10s_target():
    matrix = build_official_performance_matrix({"queries": []})

    assert matrix["summary"]["query_count"] == 0
    assert matrix["summary"]["all_queries_under_10s"] is False
    assert matrix["summary"]["max_p95_ms"] is None


def test_write_official_performance_matrix_outputs_markdown_and_json(tmp_path):
    evidence_path = tmp_path / "official_doris_evidence.json"
    json_output = tmp_path / "official_query_performance_matrix.json"
    report_output = tmp_path / "official_query_performance_matrix.md"
    evidence_path.write_text(json.dumps(_sample_evidence(), ensure_ascii=False), encoding="utf-8")

    matrix = write_official_performance_matrix(
        evidence_path=evidence_path,
        json_output=json_output,
        report_output=report_output,
    )

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    report = report_output.read_text(encoding="utf-8")
    assert payload == matrix
    assert "# 官方真实数据逐问句性能矩阵" in report
    assert "| baseline_window_volume_sum_20 | 5487 | 44.321 | 55.058 | window | PASS |" in report
    assert "官方三表行数" in report

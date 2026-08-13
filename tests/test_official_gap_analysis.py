import json
from pathlib import Path

from findsl.official_gap_analysis import analyze_official_funnel, gap_analysis_markdown


def test_gap_analysis_separates_pass_data_invalid_and_capability_rows():
    payload = {
        "row_count": 4,
        "rows": [
            {"excel_row": 2, "terminal_code": "PASS", "functions": ["indicator"]},
            {
                "excel_row": 3,
                "terminal_code": "DOMAIN_DATA_UNAVAILABLE",
                "functions": ["indicator"],
            },
            {
                "excel_row": 4,
                "terminal_code": "OFFICIAL_TYPE_ERROR",
                "functions": ["indicator"],
            },
            {
                "excel_row": 5,
                "terminal_code": "PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED",
                "functions": ["indicator", "rank"],
            },
        ],
        "migration_gaps": [
            {"code": "PHYSICAL_SCOPE_DATA_UNAVAILABLE", "count": 1}
        ],
    }

    report = analyze_official_funnel(payload)

    assert report["category_counts"] == {
        "capability_gap": 1,
        "data_unavailable": 1,
        "invalid_input": 1,
        "passed": 1,
    }
    assert report["migration_gap_count"] == 1
    assert report["development_policy"]["row_level_patches_allowed"] is False
    assert "按能力族统计" in gap_analysis_markdown(report)


def test_current_canonical_funnel_has_expected_category_totals():
    path = Path("submission_artifacts/evidence_snapshots/official_compiler_funnel.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    report = analyze_official_funnel(payload)

    assert report["row_count"] == 5799
    assert report["category_counts"] == {
        "capability_gap": 371,
        "data_unavailable": 1689,
        "invalid_input": 2466,
        "passed": 1273,
    }
    assert report["migration_gap_count"] == 53
    assert report["migration_gap_codes"] == ["PHYSICAL_SCOPE_DATA_UNAVAILABLE"]


def test_gap_analysis_subclusters_assets_intraday_and_weekday_algebra():
    payload = {
        "row_count": 3,
        "rows": [
            {"excel_row": 2, "terminal_code": "PHYSICAL_CONSTRAINT_UNSUPPORTED", "functions": ["indicator"], "source": "indicator('', '', '', '', 'ETF', '', '') = 'all'"},
            {"excel_row": 3, "terminal_code": "PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED", "functions": ["indicator"], "source": "indicator('', '', '涨幅', '开盘30分钟', '', '', '') > 0"},
            {"excel_row": 4, "terminal_code": "PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED", "functions": ["rank"], "source": "rank('', '', '最新价', 'asc', '上周二至周四', '', '', '') > 0"},
        ],
        "migration_gaps": [],
    }

    report = analyze_official_funnel(payload)
    counts = {item["key"]: item["row_count"] for item in report["semantic_subclusters"]}
    assert counts == {
        "unsupported_asset_domain": 1,
        "intraday_data_domain": 1,
        "deterministic_weekday_range": 1,
    }

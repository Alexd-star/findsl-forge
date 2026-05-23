from findsl.official_suite import run_official_suite


def test_official_suite_passes_positive_and_negative_cases(tmp_path):
    output = tmp_path / "official_suite_report.md"

    result = run_official_suite(output_path=output)

    assert result.passed
    assert result.positive_passed == 18
    assert result.positive_total == 18
    assert result.negative_passed == 22
    assert result.negative_total == 22
    assert output.exists()
    assert all(case.equivalence_passed for case in result.positive_cases)
    assert all(not case.missing_sql_fragments for case in result.positive_cases)
    assert all(not case.missing_trace_fragments for case in result.positive_cases)
    assert all(not case.missing_explain_rules for case in result.positive_cases)
    assert all(case.suggestion_count > 0 for case in result.negative_cases)
    assert all(not case.missing_suggestion_fragments for case in result.negative_cases)

    content = output.read_text(encoding="utf-8")
    assert "Official-Style Coverage Suite" in content
    assert "Suite passed: True" in content
    assert "Positive cases passed: 18/18" in content
    assert "Negative diagnostic cases passed: 22/22" in content
    assert "money_flow_prefix_sum" in content
    assert "UNKNOWN_INDICATOR" in content

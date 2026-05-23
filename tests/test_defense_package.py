from findsl.defense_package import generate_defense_package


def test_generate_defense_package_maps_demo_to_scoring_evidence(tmp_path):
    output = tmp_path / "defense_package.md"

    result = generate_defense_package(output_path=output)

    assert result.passed
    assert result.passed_count == result.total
    assert result.total >= 7
    assert output.exists()

    check_names = {check.name for check in result.checks}
    assert "NL2DSL validated candidate" in check_names
    assert "NL2DSL official template coverage" in check_names
    assert "LLM candidate safety loop" in check_names
    assert "Official prefix-sum positive preset" in check_names
    assert "Official diagnostic negative preset" in check_names
    assert "Doris SQL validation boundary" in check_names
    assert "Config-only indicator extension" in check_names
    assert "Official-style coverage suite" in check_names
    assert "Compiler accuracy and latency" in check_names
    assert "Doris deployment asset integrity" in check_names

    payload = result.to_dict()
    assert payload["passed"] is True
    assert payload["passed_count"] == payload["total"]
    assert payload["output"] == str(output)

    content = output.read_text(encoding="utf-8")
    assert "FinDSL Forge Defense Package" in content
    assert "Package passed: True" in content
    assert "real Doris 10x proof still requires a running Doris cluster" in content
    assert "money_flow_prefix_sum" in content
    assert "UNKNOWN_INDICATOR" in content
    assert "UNSAFE_DIRECT_SQL" in content
    assert "LLM candidate safety loop" in content
    assert "NL2DSL official template coverage" in content
    assert "A股每日换手率前50%" in content
    assert "date_window_pruning" in content
    assert "signed_outflow_threshold" in content
    assert "Doris SQL validation boundary" in content
    assert "Config-only indicator extension" in content
    assert "dwd_stock_money_flow_prefix" in content

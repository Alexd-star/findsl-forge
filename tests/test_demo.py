from pathlib import Path

from findsl.demo import DEFAULT_NL_REQUEST, analyze_dsl, demo_examples, render_demo_html, suggest_from_text


DATA_DIR = Path("data/samples")


def test_analyze_dsl_returns_compile_and_verification_payload():
    result = analyze_dsl('filter(SUM(indicator("volume"), 3) > 300)', DATA_DIR)

    assert result["ok"]
    assert result["compile"]["ast"]["type"] == "FunctionCall"
    assert "dwd_stock_daily_quote_prefix" in result["compile"]["sql"]
    assert result["verification"]["passed"]
    assert result["verification"]["sql_row_count"] == result["verification"]["reference_row_count"]


def test_demo_examples_loads_sample_queries():
    examples = demo_examples(Path("data/samples/queries.jsonl"))

    assert len(examples) >= 22
    assert examples[0]["name"]
    assert examples[0]["dsl"].startswith("then(")
    kinds = {example["kind"] for example in examples}
    assert {"baseline", "official_positive", "official_negative"} <= kinds
    assert any(example["scenario"] == "money_flow_prefix_sum" for example in examples)
    assert any(example.get("expected_code") == "UNKNOWN_INDICATOR" for example in examples)


def test_render_demo_html_contains_workbench_and_api_hooks():
    html = render_demo_html()

    assert "FinDSL Forge" in html
    assert "DSL Workbench" in html
    assert "Natural language" in html
    assert "/api/analyze" in html
    assert "/api/suggest" in html
    assert "Suggest DSL" in html
    assert DEFAULT_NL_REQUEST in html
    assert "__DEFAULT_NL_REQUEST__" not in html
    assert "metricStatus" in html
    assert "data-tab=\"sql\"" in html
    assert "document.createElement(\"strong\")" in html
    assert "formatError(data.error)" in html
    assert "resetMetrics(\"ERROR\")" in html
    assert "selectExample(index)" in html
    assert "Diagnostic preset" in html
    assert "Expected diagnostic:" in html
    assert "Actual diagnostic:" in html


def test_suggest_from_text_returns_validated_candidate_payload():
    result = suggest_from_text("筛选A股连续三天主力净流入为正并按换手率排名前一百", DATA_DIR)

    assert result["ok"]
    assert result["warnings"] == []
    assert result["candidates"]
    candidate = result["candidates"][0]
    assert candidate["validated"]
    assert candidate["dsl"].startswith("then(")
    assert candidate["analysis"]["verification"]["passed"]

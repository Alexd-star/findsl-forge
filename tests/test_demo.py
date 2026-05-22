from pathlib import Path

from findsl.demo import analyze_dsl, demo_examples, render_demo_html


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

    assert len(examples) >= 5
    assert examples[0]["name"]
    assert examples[0]["dsl"].startswith("then(")


def test_render_demo_html_contains_workbench_and_api_hooks():
    html = render_demo_html()

    assert "FinDSL Forge" in html
    assert "DSL Workbench" in html
    assert "/api/analyze" in html
    assert "metricStatus" in html
    assert "data-tab=\"sql\"" in html

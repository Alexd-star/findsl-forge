import json
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from findsl.demo import (
    DEFAULT_NL_REQUEST,
    analyze_dsl,
    analyze_official_dsl,
    demo_examples,
    doris_evidence_summary,
    make_demo_handler,
    render_demo_html,
    suggest_from_text,
)


DATA_DIR = Path("data/samples")


def test_analyze_dsl_returns_compile_and_verification_payload():
    result = analyze_dsl('filter(SUM(indicator("volume"), 3) > 300)', DATA_DIR)

    assert result["ok"]
    assert result["compile"]["ast"]["type"] == "FunctionCall"
    assert "dwd_stock_daily_quote_prefix" in result["compile"]["sql"]
    assert result["verification"]["passed"]
    assert result["verification"]["sql_row_count"] == result["verification"]["reference_row_count"]


def test_analyze_official_dsl_uses_the_new_auditable_pipeline():
    result = analyze_official_dsl("indicator('', '', '成交量', '', '', '', '') > 100")

    assert result["ok"] is True
    assert result["pipeline"] == "official-antlr-ir-sqlglot"
    assert result["frontend"]["frontend"] == "antlr"
    assert result["physical"]["selected_resource"] == "official_basic"
    assert result["backend"]["validation_passed"] is True


def test_official_demo_api_returns_success_and_structured_pipeline_failure():
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_demo_handler(DATA_DIR))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/api/official/analyze"
    try:
        success = _post_json(endpoint, {"dsl": "indicator('', '', '成交量', '', '', '', '') > 100"})
        assert success["pipeline"] == "official-antlr-ir-sqlglot"
        assert success["backend"]["validation_passed"] is True

        with pytest.raises(HTTPError) as excinfo:
            _post_json(endpoint, {"dsl": "indicator('', '', '涨幅', '', '', '', '') > 1"})
        error = json.loads(excinfo.value.read().decode("utf-8"))["error"]
        assert error["stage"] == "physical"
        assert error["code"] == "PHYSICAL_PLAN_UNAVAILABLE"
        assert error["partial"]["optimized"]["diagnostics"] == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _post_json(url, payload):
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def test_demo_examples_loads_sample_queries():
    examples = demo_examples(Path("data/samples/queries.jsonl"))

    assert len(examples) >= 25
    assert examples[0]["name"]
    assert examples[0]["dsl"].startswith("then(")
    kinds = {example["kind"] for example in examples}
    assert {"baseline", "official_positive", "official_negative", "real_market"} <= kinds
    assert any(example["scenario"] == "money_flow_prefix_sum" for example in examples)
    assert any(example.get("expected_code") == "UNKNOWN_INDICATOR" for example in examples)
    assert any(example.get("dataset") == "real_market" for example in examples)


def test_analyze_dsl_supports_real_market_sample_data():
    examples = [
        item for item in demo_examples(Path("data/samples/queries.jsonl"))
        if item.get("dataset") == "real_market"
    ]

    assert len(examples) == 3
    assert {item["dataset_label"] for item in examples} == {"Eastmoney A-share sample"}
    for example in examples:
        result = analyze_dsl(example["dsl"], Path("data/real_samples/eastmoney_a_share_sample"))
        assert result["ok"]
        assert result["verification"]["passed"]
        assert result["verification"]["sql_row_count"] == result["verification"]["reference_row_count"]


def test_render_demo_html_contains_workbench_and_api_hooks():
    html = render_demo_html()

    assert "FinDSL Forge" in html
    assert "DSL Workbench" in html
    assert "Natural language" in html
    assert "/api/analyze" in html
    assert "/api/suggest" in html
    assert "/api/evidence" in html
    assert "Suggest DSL" in html
    assert "Copy SQL" in html
    assert "data-tab=\"evidence\"" in html
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
    assert "dataset:" in html
    assert "real_market" in html


def test_doris_evidence_summary_reads_cluster_report(tmp_path):
    report = tmp_path / "doris_cluster_evidence.md"
    report.write_text(
        "\n".join(
            [
                "# Doris Cluster Evidence",
                "- Evidence passed: True",
                "- Row counts match: True",
                "- Doris cluster speedup: 36.24x",
                "- Baseline avg execute ms: 5182.042",
                "- Optimized avg execute ms: 142.993",
            ]
        ),
        encoding="utf-8",
    )

    summary = doris_evidence_summary(report)

    assert summary["available"]
    assert summary["headline"]["passed"] == "True"
    assert summary["headline"]["speedup"] == "36.24x"
    assert summary["headline"]["row_counts_match"] == "True"


def test_suggest_from_text_returns_validated_candidate_payload():
    result = suggest_from_text("筛选A股连续三天主力净流入为正并按换手率排名前一百", DATA_DIR)

    assert result["ok"]
    assert result["warnings"] == []
    assert result["candidates"]
    candidate = result["candidates"][0]
    assert candidate["validated"]
    assert candidate["dsl"].startswith("then(")
    assert candidate["analysis"]["verification"]["passed"]

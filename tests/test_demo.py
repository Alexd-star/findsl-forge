import json
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen

import pytest

from findsl.demo import (
    DEFAULT_NL_REQUEST,
    analyze_dsl,
    analyze_official_dsl,
    demo_examples,
    delivery_evidence_summary,
    doris_evidence_summary,
    make_demo_handler,
    official_demo_examples,
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


def test_official_demo_api_returns_grounded_t0_analysis_and_preview():
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_demo_handler(DATA_DIR))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/api/official/analyze"
    try:
        success = _post_json(endpoint, {"dsl": "indicator('', '', '成交量', '', '', '', '') > 100"})
        assert success["pipeline"] == "official-antlr-ir-sqlglot"
        assert success["backend"]["validation_passed"] is True

        t0 = _post_json(
            endpoint,
            {"dsl": "indicator('', '', '是否T+0', '', '', '', '') = True"},
        )
        assert t0["ok"] is True
        assert "findsl_ext" in t0["backend"]["sql"]
        assert "instrument_rule" in t0["backend"]["sql"]

        preview = _post_json(
            f"http://127.0.0.1:{server.server_port}/api/official/preview",
            {"dsl": "indicator('', '', '是否T+0', '', '', '', '') = True"},
        )
        assert preview["ok"] is True
        assert "instrument_rule" in preview["backend"]["sql"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_versioned_official_demo_cases_match_declared_pipeline_outcomes():
    examples = official_demo_examples()

    assert {item["scenario"] for item in examples} >= {
        "basic_filter",
        "security_join",
        "ext_join",
        "rank",
        "market_date_constraint",
        "technical_feature",
        "missing_data_domain",
    }
    for item in examples:
        if item["expected_status"] == "success":
            result = analyze_official_dsl(item["dsl"])
            assert result["ok"] is True
            assert result["physical"]["selected_resource"] == item["expected_resource"]
            if "expected_strategy" in item:
                assert (
                    result["physical"]["selected_strategy"]
                    == item["expected_strategy"]
                )
        else:
            with pytest.raises(Exception) as excinfo:
                analyze_official_dsl(item["dsl"])
            assert getattr(excinfo.value, "code", "") == item["expected_code"]


def test_official_examples_endpoint_returns_expectation_metadata():
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_demo_handler(DATA_DIR))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(
            f"http://127.0.0.1:{server.server_port}/api/official/examples",
            timeout=10,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["ok"] is True
        assert payload["examples"]
        assert all("expected_status" in item for item in payload["examples"])
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
    assert "官方赛题编译工作台" in html
    assert "中文选股需求" in html
    assert "/api/analyze" in html
    assert "/api/suggest" in html
    assert "/api/evidence" in html
    assert "/api/official/examples" in html
    assert "/api/official/preview" in html
    assert "生成 DSL 候选" in html
    assert "复制 SQL" in html
    assert "data-tab=\"evidence\"" in html
    assert DEFAULT_NL_REQUEST in html
    assert "__DEFAULT_NL_REQUEST__" not in html
    assert "metricStatus" in html
    assert "data-tab=\"sql\"" in html
    assert "document.createElement(\"strong\")" in html
    assert "formatError(data.error)" in html
    assert "resetMetrics(\"ERROR\")" in html
    assert "selectExample(index)" in html
    assert "诊断样例" in html
    assert "预期诊断码" in html
    assert "实际诊断码" in html
    assert "dataset:" in html
    assert "real_market" in html
    assert "官方赛题管线" in html
    assert "data-tab=\"logical\"" in html
    assert "data-tab=\"physical\"" in html
    assert "normalizeOfficialResult" in html
    assert "height: clamp(420px, 62vh, 760px)" in html
    assert 'id="copyButton" type="button" disabled' in html
    assert 'aria-controls="outputPane"' in html
    assert 'event.key === "ArrowRight"' in html
    assert "modeGeneration" in html
    assert "exampleLoadToken" in html
    assert "Promise.allSettled" in html
    assert 'let currentMode = "official"' in html
    assert 'setMode("official")' in html
    assert 'id="officialModeButton" type="button" role="tab" aria-selected="true"' in html


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


def test_delivery_evidence_summary_reads_versioned_metadata(tmp_path):
    metadata = tmp_path / "evidence_metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "readiness": {
                    "blocking_gates_passed": True,
                    "warning_count": 0,
                    "pytest": {"passed": 908},
                },
                "official_migration": {
                    "legacy_strict_success": 1097,
                    "legacy_to_new_migrated": 742,
                    "migration_coverage": 0.67639,
                    "new_backend_success": 766,
                },
                "git": {"head_at_report_generation": "6ef4412"},
                "warnings": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = delivery_evidence_summary(metadata)

    assert summary["available"] is True
    assert summary["blocking_gates_passed"] is True
    assert summary["warning_count"] == 0
    assert summary["pytest_passed"] == 908
    assert summary["legacy_to_new_migrated"] == 742
    assert summary["legacy_strict_success"] == 1097
    assert summary["git_head"] == "6ef4412"


def test_delivery_evidence_summary_rejects_malformed_metadata(tmp_path):
    metadata = tmp_path / "evidence_metadata.json"
    metadata.write_text("{not-json", encoding="utf-8")

    summary = delivery_evidence_summary(metadata)

    assert summary["available"] is False
    assert "could not be read" in summary["message"]


def test_suggest_from_text_returns_validated_candidate_payload():
    result = suggest_from_text("筛选A股连续三天主力净流入为正并按换手率排名前一百", DATA_DIR)

    assert result["ok"]
    assert result["warnings"] == []
    assert result["candidates"]
    candidate = result["candidates"][0]
    assert candidate["validated"]
    assert candidate["dsl"].startswith("then(")
    assert candidate["analysis"]["verification"]["passed"]

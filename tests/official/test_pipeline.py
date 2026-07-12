import pytest

from findsl.official.pipeline import OfficialPipelineError, compile_official


def test_official_pipeline_exposes_every_compiler_stage_and_safe_doris_sql():
    result = compile_official("indicator('沪|深', '', '成交量', '今日', '', '', '') > 100 limit 0,20")

    payload = result.to_dict()
    assert payload["ok"] is True
    assert payload["frontend"]["frontend"] == "antlr"
    assert payload["frontend"]["ast"]["type"] == "Limit"
    assert payload["typed_ast"]["type"]["kind"] == "boolean"
    assert payload["logical"]["validation_passed"] is True
    assert payload["optimized"]["diagnostics"] == []
    assert payload["physical"]["selected_resource"] == "official_basic"
    assert payload["physical"]["selected_strategy"] == "direct_column"
    assert payload["physical"]["decisions"][0]["selected"] is True
    assert payload["backend"]["round_trip_stable"] is True
    assert payload["backend"]["validation_passed"] is True
    assert "`newzl`.`hsj_stock_hq_basic`" in payload["backend"]["sql"]
    assert payload["elapsed_ms"] >= 0


@pytest.mark.parametrize(
    "source,stage,code",
    [
        ("indicator(", "frontend", "OFFICIAL_ANTLR_PARSE_ERROR"),
        ("indicator('', '', '营业收入', '', '', '', '') > 1", "logical", "DOMAIN_DATA_UNAVAILABLE"),
        ("indicator('', '', '涨幅', '', '', '', '') > 1", "physical", "PHYSICAL_PLAN_UNAVAILABLE"),
    ],
)
def test_official_pipeline_preserves_terminal_stage_code_and_partial_evidence(source, stage, code):
    with pytest.raises(OfficialPipelineError) as excinfo:
        compile_official(source)

    error = excinfo.value
    assert error.stage == stage
    assert error.code == code
    assert error.partial["source"] == source
    assert error.to_dict()["ok"] is False
    if stage != "frontend":
        assert error.partial["frontend"]["ast"] is not None


def test_physical_failure_keeps_candidate_decision_evidence():
    with pytest.raises(OfficialPipelineError) as excinfo:
        compile_official("indicator('', '', '涨幅', '', '', '', '') > 1")

    diagnostics = excinfo.value.diagnostics
    assert diagnostics[0]["reason_code"] == "PHYSICAL_MAPPING_MISSING"
    assert diagnostics[0]["feasible"] is False

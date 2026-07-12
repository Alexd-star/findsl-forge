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
        ("indicator('', '', '3分钟涨速', '', '', '', '') > 1", "physical", "PHYSICAL_PLAN_UNAVAILABLE"),
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
        compile_official("indicator('', '', '3分钟涨速', '', '', '', '') > 1")

    diagnostics = excinfo.value.diagnostics
    assert diagnostics[0]["reason_code"] == "PHYSICAL_MAPPING_MISSING"
    assert diagnostics[0]["feasible"] is False


@pytest.mark.parametrize(
    "source,sql_fragment",
    [
        ("indicator('', '', '最新价', '', '', '', '') > 1", "`q`.`lastPx` / 10000.0"),
        ("indicator('', '', '涨幅', '', '', '', '') > 1", "NULLIF(`q`.`preClosePx`, 0)"),
        ("indicator('', '', '涨停', '', '', '', '') = True", "`q`.`limitFlag` = 1"),
        ("indicator('', '', '总市值', '', '', '', '') > 1", "`q`.`totalShare`"),
        ("indicator('', '', '主力净流出', '', '', '', '') > 1", "-`q`.`ZJLXMainNetTur`"),
    ],
)
def test_pipeline_compiles_controlled_derived_indicators_without_legacy_sql(
    source, sql_fragment
):
    result = compile_official(source).to_dict()

    assert result["backend"]["validation_passed"] is True
    assert sql_fragment in result["backend"]["sql"]
    assert result["physical"]["selected_strategy"] == "controlled_expression"

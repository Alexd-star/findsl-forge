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
        ("indicator('', '', '是否T+0', '', '', '', '') = True", "physical", "PHYSICAL_PLAN_UNAVAILABLE"),
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
        compile_official("indicator('', '', '是否T+0', '', '', '', '') = True")

    diagnostics = excinfo.value.diagnostics
    assert diagnostics[0]["reason_code"] == "PHYSICAL_MAPPING_MISSING"
    assert diagnostics[0]["feasible"] is False


def test_pipeline_classifies_missing_industry_membership_as_data_unavailable():
    with pytest.raises(OfficialPipelineError) as excinfo:
        compile_official(
            "indicator('', '', '涨幅', '', '', '', '') > "
            "belong_industry('', '', '涨幅', '', 'AVG')"
        )

    assert excinfo.value.stage == "physical"
    assert excinfo.value.code == "PHYSICAL_INDUSTRY_DATA_UNAVAILABLE"


def test_pipeline_renders_configured_hybrid_numeric_approximation():
    result = compile_official(
        "indicator('', '', '最新价', '今日', '', '', '') ~= 10"
    ).to_dict()
    sql = result["backend"]["sql"]

    assert "ABS((`q`.`lastPx` / 10000.0) - 10)" in sql
    assert "GREATEST(0.01, 0.01 * GREATEST(ABS(`q`.`lastPx` / 10000.0), ABS(10)))" in sql
    assert result["backend"]["validation_passed"] is True


def test_pipeline_preserves_named_scalar_references_inside_approximation():
    result = compile_official(
        "indicator('沪|深|京', '', '成交量', '目前', '', '', '') ~= "
        "queryData('', '华夏银行', '30日均量线', '目前', '')"
    ).to_dict()

    assert result["physical"]["selected_strategy"] == "composite_grouped_aggregate"
    assert "ABS(`q`.`volume` - `scalar_0`.`scalar_value_0`)" in result["backend"]["sql"]
    assert result["backend"]["validation_passed"] is True


@pytest.mark.parametrize(
    "source,sql_fragment",
    [
        ("indicator('', '', '最新价', '', '', '', '') > 1", "`q`.`lastPx` / 10000.0"),
        ("indicator('', '', '涨幅', '', '', '', '') > 1", "NULLIF(`q`.`preClosePx`, 0)"),
        ("indicator('', '', '涨停', '', '', '', '') = True", "`q`.`limitFlag` = 1"),
        ("indicator('', '', '总市值', '', '', '', '') > 1", "`q`.`totalShare`"),
        ("indicator('', '', '主力净流出', '', '', '', '') > 1", "-`q`.`ZJLXMainNetTur`"),
        ("indicator('', '', '流通市值', '', '', '', '') > 1", "`q`.`listedShare`"),
        ("indicator('', '', '委比', '', '', '', '') > 1", "`q`.`commissionBuy`"),
        ("indicator('', '', '成交均价', '', '', '', '') > 1", "NULLIF(`q`.`volume`, 0)"),
        ("indicator('', '', '3分钟涨速', '', '', '', '') > 1", "`q`.`riseSpd3m` / 10000.0"),
        ("indicator('', '', '主力买入占比', '', '', '', '') > 1", "`q`.`ZJLXMainBuyCntPer` / 10000.0"),
        ("indicator('', '', '放量', '', '', '', '') = True", "`q`.`volume_breakout` = TRUE"),
        ("indicator('', '', '均线多头排列', '', '', '', '') = True", "`q`.`ma_bullish` = TRUE"),
        ("indicator('', '', '涨停炸板', '今日', '', '', '') = True", "(COALESCE(`q`.`lmtUpNum`, 0) > 0 OR COALESCE(`q`.`boardBreaks`, 0) > 0) = TRUE"),
    ],
)
def test_pipeline_compiles_controlled_derived_indicators_without_legacy_sql(
    source, sql_fragment
):
    result = compile_official(source).to_dict()

    assert result["backend"]["validation_passed"] is True
    assert sql_fragment in result["backend"]["sql"]
    assert result["physical"]["selected_strategy"] == "controlled_expression"


@pytest.mark.parametrize(
    "source,current_fragment,previous_fragment",
    [
        (
            "cross_above('', '', '5日均线', '20日均线', '今日', '', '') = True",
            "`q`.`ma5` > `q`.`ma20`",
            "LAG(`q`.`ma5`, 1, NULL) OVER",
        ),
        (
            "cross_down('', '', '最新价', '30日均线', '', '', '') = True",
            "`official_basic`.`lastPx` / 10000.0 < `official_technical`.`ma30`",
            "LAG(`official_basic`.`lastPx` / 10000.0, 1, NULL) OVER",
        ),
        (
            "golden_cross('', '', '10日均线', '20日均线', '', '', '') = True",
            "`q`.`ma10` > `q`.`ma20`",
            "LAG(`q`.`ma10`, 1, NULL) OVER",
        ),
    ],
)
def test_pipeline_lowers_crossing_functions_to_set_based_window_relation(
    source, current_fragment, previous_fragment
):
    result = compile_official(source).to_dict()
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "crossing_window"
    assert current_fragment in sql
    assert previous_fragment in sql
    assert "`event_rows`.`event_0` = TRUE" in sql
    assert "WHERE LAG(" not in sql
    assert result["backend"]["validation_passed"] is True


def test_pipeline_combines_crossing_events_without_scalar_fallback():
    result = compile_official(
        "cross_above('', '', '5日均线', '10日均线', '', '', '') = True "
        "or cross_down('', '', '5日均线', '10日均线', '', '', '') = True"
    ).to_dict()

    assert result["physical"]["selected_strategy"] == "crossing_window"
    assert "`event_rows`.`event_0` = TRUE OR `event_rows`.`event_1` = TRUE" in result["backend"]["sql"]


@pytest.mark.parametrize(
    "source,window_fragment,comparison_fragment",
    [
        (
            "record_high('', '', '最高价', '60日', '今日', '', '', '') = True",
            "ROWS BETWEEN 59 PRECEDING AND CURRENT ROW",
            ">= MAX(`q`.`highPx` / 10000.0) OVER",
        ),
        (
            "record_low('', '', '最低价', '历史', '', '', '', '') = True",
            "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW",
            "<= MIN(`q`.`lowPx` / 10000.0) OVER",
        ),
        (
            "record_high('', '', '最高价', '四个月', '今日', '', '', '') = True",
            "ROWS BETWEEN 79 PRECEDING AND CURRENT ROW",
            ">= MAX(`q`.`highPx` / 10000.0) OVER",
        ),
    ],
)
def test_pipeline_lowers_record_extrema_to_typed_window_frames(
    source, window_fragment, comparison_fragment
):
    result = compile_official(source).to_dict()
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "crossing_window"
    assert window_fragment in sql
    assert comparison_fragment in sql
    assert "`event_rows`.`event_0` = TRUE" in sql


@pytest.mark.parametrize(
    "source,frame",
    [
        ("position('', '', '最新价', '10日', '今日', '', '', '') = '最高'", "ROWS BETWEEN 9 PRECEDING AND CURRENT ROW"),
        ("position('', '', '市净率', '历史', '今日', '', '', '') = '低'", "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW"),
        ("position('', '', '最新价', '七年内', '今日', '', '', '') = '低'", "ROWS BETWEEN 1749 PRECEDING AND CURRENT ROW"),
    ],
)
def test_pipeline_lowers_position_to_windowed_five_bucket_case(source, frame):
    result = compile_official(source).to_dict()
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "crossing_window"
    assert frame in sql
    assert "CASE WHEN" in sql
    assert "THEN '最低'" in sql
    assert "THEN '最高'" in sql
    assert "THEN '低'" in sql
    assert "THEN '高'" in sql
    assert "ELSE '中' END AS `event_0`" in sql
    assert "`event_rows`.`event_0`" in sql


def test_pipeline_projects_scalar_indicators_next_to_window_events():
    result = compile_official(
        "cross_above('', '', '5日均线', '20日均线', '', '', '') = True "
        "and indicator('', '', '成交量', '', '', '', '') > 0"
    ).to_dict()
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "crossing_window"
    assert "`official_basic`.`volume` AS `projected_0`" in sql
    assert "`event_rows`.`event_0` = TRUE AND `event_rows`.`projected_0` > 0" in sql


def test_pipeline_composes_conflicting_event_and_scalar_dates_by_security_key():
    result = compile_official(
        "cross_above('', '', '5日均线', '20日均线', '今日', '', '') = True "
        "and indicator('', '', '成交量', '昨日', '', '', '') > 0"
    ).to_dict()
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "event_candidate_intersect"
    assert "INTERSECT" in sql
    assert "SELECT DISTINCT `candidate_left_rows`.`mktcode`" in sql
    assert "SELECT DISTINCT `candidate_right_rows`.`mktcode`" in sql
    assert "MAX(`candidate_latest`.`bizdate`)" in sql


@pytest.mark.parametrize(
    "source",
    [
        (
            "record_high('深', '', '成交量', '20日', '近1日', '', '', '') = True "
            "and indicator('深', '', '成交量', '近1日', '', 'SUM', '') > 0"
        ),
        (
            "reset('', '', '5日均线', '10日均线', '30日内', '', '') = True "
            "and indicator('', '', '5日均线', '30日内', '', 'GROWTH_RISE', '') > 0"
        ),
        (
            "position('', '', '量比', '', '', '', '', '') = '高' and "
            "indicator('', '', '最新价', '', '', '', '') ~= "
            "queryData('', '思源电气', '最新价', '', '')"
        ),
        (
            "(cross_above('', '', '20日均线', '60日均线', '近五天', '', '') = True "
            "or cross_down('', '', '20日均线', '60日均线', '近五天', '', '') = True) "
            "and indicator('', '', '20日均线', '近五天', '', 'GROWTH_RISE', '') > 0"
        ),
    ],
)
def test_pipeline_composes_event_and_relational_candidates(source):
    result = compile_official(source).to_dict()

    assert result["physical"]["selected_strategy"] == "event_candidate_intersect"
    assert result["physical"]["plan"]["kind"] == "PhysicalCandidateSetOperation"
    assert "INTERSECT" in result["backend"]["sql"]
    assert result["backend"]["validation_passed"] is True


def test_pipeline_unions_event_and_aggregate_candidate_branches():
    result = compile_official(
        "cross_above('', '', '5日均线', '20日均线', '今日', '', '') = True or "
        "indicator('', '', '成交量', '近5日', '', 'AVG', '') > 100"
    ).to_dict()

    assert result["physical"]["selected_strategy"] == "event_candidate_union"
    assert result["physical"]["plan"]["operation"] == "union"
    assert " UNION " in result["backend"]["sql"]


def test_pipeline_event_false_means_no_true_event_in_eligible_period():
    result = compile_official(
        "cross_down('', '', '最新价', '10日均线', '近三天', '', '') = False"
    ).to_dict()
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "crossing_window_absence"
    assert result["physical"]["plan"]["operation"] == "except"
    assert " EXCEPT " in sql
    assert "`event_rows`.`event_0` = TRUE" in sql
    eligible_sql, occurred_sql = sql.split(" EXCEPT ", 1)
    assert "`event_rows`.`event_0` = FALSE" in eligible_sql
    assert "`event_rows`.`event_0` = FALSE" not in occurred_sql
    assert "LIMIT 3" in sql


def test_pipeline_undated_event_is_evaluated_at_latest_session():
    result = compile_official(
        "cross_down('', '', '成交量', '10日均量线', '', '', '') = True"
    ).to_dict()

    assert "MAX(`q_latest`.`bizdate`)" in result["backend"]["sql"]


def test_pipeline_position_ratio_preserves_fraction_parentheses():
    result = compile_official(
        "position('', '', '量比', '', '', '', '', '') = '高'"
    ).to_dict()

    assert "WHEN (`q`.`quantRatio` / 10000.0 - MIN(" in result["backend"]["sql"]


def test_pipeline_never_ignores_non_empty_window_event_slots():
    with pytest.raises(OfficialPipelineError) as excinfo:
        compile_official(
            "record_high('', '', '最高价', '20日', '今日', '', 'MAX', '') = True"
        )

    assert excinfo.value.code == "PHYSICAL_EVENT_COMPOSITION_UNSUPPORTED"


@pytest.mark.parametrize(
    "source,sql_fragments",
    [
        (
            "close_together('', '', '5日均线', '20日均线', '今日', '', '') = True",
            ("ABS(`q`.`ma5` - `q`.`ma20`)", "GREATEST(ABS(`q`.`ma5`), ABS(`q`.`ma20`))", "<= 0.03"),
        ),
        (
            "reset('', '', '最新价', '20日均线', '今日', '', '') = True",
            ("ABS((`official_basic`.`lastPx` / 10000.0) - `official_technical`.`ma20`)", "<= 0.02", "* 0.995"),
        ),
    ],
)
def test_pipeline_lowers_configured_technical_patterns_without_raw_sql(source, sql_fragments):
    result = compile_official(source).to_dict()
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "crossing_window"
    for fragment in sql_fragments:
        assert fragment in sql
    assert "NULLIF" in sql

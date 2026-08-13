import pytest

from findsl.official.external.runtime import (
    default_benchmark_policy_catalog,
    default_external_index_quote_catalog,
)
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
    assert payload["backend"]["round_trip_checked"] is False
    assert payload["backend"]["round_trip_stable"] is None
    assert payload["backend"]["validation_passed"] is True
    assert "`newzl`.`hsj_stock_hq_basic`" in payload["backend"]["sql"]
    assert payload["elapsed_ms"] >= 0
    assert payload["timings_ns"]["total"] == result.elapsed_ns
    assert {
        "context_preflight",
        "frontend",
        "typed",
        "logical",
        "optimizer",
        "physical",
        "backend",
        "context_postflight",
        "total",
    } <= set(payload["timings_ns"])


def test_pipeline_compiles_previous_close_from_official_basic_table():
    result = compile_official(
        "indicator('', '', '昨收价', '', '', '', '') > 10"
    ).to_dict()

    assert "(`q`.`preClosePx` / 10000.0) > 10" in result["backend"]["sql"]
    assert result["physical"]["selected_resource"] == "official_basic"


def test_empty_rank_uses_only_stable_keys_without_positional_ordering():
    sql = compile_official(
        "rank('', '', '', 'desc', '', '', '', '') <= 3"
    ).backend["sql"]

    assert "ORDER BY 0" not in sql
    assert "ORDER BY `q`.`mktcode` ASC, `q`.`tgtcode` ASC" in sql


@pytest.mark.parametrize(
    "scope,index_code,date",
    [
        ("上证指数", "000001", "今年"),
        ("沪深300", "000300", "今年以来"),
        ("深成指数", "399001", "去年"),
    ],
)
def test_querydata_index_scalar_uses_versioned_quote_and_official_time_anchor(
    scope, index_code, date
):
    sql = compile_official(
        f"indicator('', '', '涨跌幅', '{date}', '', '', '') > "
        f"queryData('', '{scope}', '涨跌幅', '{date}', '')"
    ).backend["sql"]

    assert "`findsl_ext`.`index_quote`" in sql
    assert f"`external_index_quote`.`index_code` = '{index_code}'" in sql
    assert default_external_index_quote_catalog().resolve(index_code).snapshot_id in sql
    assert "FROM `newzl`.`hsj_stock_hq_basic` AS calendar_anchor" in sql


@pytest.mark.parametrize("indicator,date", [("涨幅", "今天"), ("涨跌幅", "近一月")])
def test_querydata_broad_market_uses_versioned_business_policy(indicator, date):
    policy = default_benchmark_policy_catalog().resolve("大盘")
    sql = compile_official(
        f"indicator('', '', '{indicator}', '{date}', '', '', '') > "
        f"queryData('', '大盘', '{indicator}', '{date}', '')"
    ).backend["sql"]

    assert policy.policy_id == "a-share-broad-market-v1"
    assert "`findsl_ext`.`index_quote`" in sql
    assert f"`external_index_quote`.`index_code` = '{policy.index_code}'" in sql
    assert (
        default_external_index_quote_catalog().resolve(policy.index_code).snapshot_id
        in sql
    )
    assert "FROM `newzl`.`hsj_stock_hq_basic` AS q_latest" in sql


def test_undated_external_index_scalar_uses_official_quote_calendar_anchor():
    sql = compile_official(
        "indicator('', '', '涨跌幅', '', '', '', '') > "
        "queryData('', '沪深300', '涨跌幅', '', '')"
    ).backend["sql"]

    assert (
        "`external_index_quote`.`bizdate` = (SELECT MAX(`q_latest`.`bizdate`) "
        "FROM `newzl`.`hsj_stock_hq_basic` AS q_latest)"
    ) in sql


def test_multiple_singleton_dates_become_independent_security_relations():
    sql = compile_official(
        "indicator('', 'aigc', '成交量', '昨日', '', '', '') = "
        "indicator('', 'aigc', '成交量', '本季度', '', 'MIN', '') and "
        "indicator('', 'aigc', '成交量', '前天', '', '', '') = "
        "indicator('', 'aigc', '成交量', '本季度', '', 'MIN', '')"
    ).backend["sql"]

    assert "AS scalar_0" in sql and "AS scalar_1" in sql
    assert "DESC LIMIT 1 OFFSET 1" in sql
    assert "DESC LIMIT 1 OFFSET 2" in sql
    assert "SELECT `q`.`mktcode`, `q`.`tgtcode`, `q`.`volume`" in sql
    assert "`scalar_0`.`scalar_value_0`" in sql
    assert "`scalar_1`.`scalar_value_1`" in sql


def test_cross_scope_temporal_querydata_uses_independent_aggregate_scalar():
    result = compile_official(
        "indicator('', 'AIGC概念', '收盘价', '近两年', '', '', 'EXIST=9季度') <= "
        "queryData('', '白酒|ai|华为', '收盘价', '近两年', 'AVG')"
    ).to_dict()
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "temporal_cross_scope_scalar"
    assert "CROSS JOIN (SELECT AVG(" in sql
    assert "AS temporal_scalar_0" in sql
    assert "DATE_TRUNC(`source_rows`.`bizdate`, 'QUARTER')" in sql
    assert "`temporal_metrics`.`metric_value` = 9" in sql


def test_open_ended_limit_uses_doris_safe_maximum_with_offset():
    result = compile_official(
        "indicator('', '', '涨幅', '今日', '', '', '') > 0 limit 7,-1"
    ).to_dict()

    assert result["logical"]["plan"]["count"] is None
    assert result["physical"]["plan"]["count"] is None
    assert "ORDER BY `mktcode`, `tgtcode`, `bizdate`" in result["backend"]["sql"]
    assert "LIMIT 9223372036854775800 OFFSET 7" in result["backend"]["sql"]


@pytest.mark.parametrize(
    "source,fragments",
    [
        (
            "indicator('', '', '成交量', '2012年的后4年', '', 'AVG', '') > 0",
            ("`q`.`bizdate` >= '2013-01-01'", "`q`.`bizdate` <= '2016-12-31'"),
        ),
        (
            "indicator('', '', '成交量', '9号的前1日', '', '', '') > 0",
            ("`boundary_sessions`.`bizdate` < DATE_ADD", "DESC LIMIT 1"),
        ),
        (
            "indicator('', '', '成交量', '3月9号的后3日', '', '', 'CONS=每日') > 0",
            ("`boundary_sessions`.`bizdate` > DATE_ADD", "ASC LIMIT 3"),
        ),
        (
            "indicator('', '', '成交量', '近半年', '', 'AVG', '') > 0",
            ("INTERVAL '6' MONTH", "SELECT MAX(`calendar_anchor`.`bizdate`)"),
        ),
        (
            "indicator('', '', '成交量', '近两年', '', 'SUM', 'CONS=0.5年') > 0",
            ("DATE_TRUNC(`aggregate_source`.`bizdate`, 'MONTH')", "* 12 + MONTH("),
        ),
    ],
)
def test_extended_date_algebra_reaches_structured_doris_ast(source, fragments):
    result = compile_official(source).to_dict()

    for fragment in fragments:
        assert fragment in result["backend"]["sql"]
    assert result["backend"]["validation_passed"] is True


@pytest.mark.parametrize(
    "source,stage,code",
    [
        ("indicator(", "frontend", "OFFICIAL_ANTLR_PARSE_ERROR"),
        ("indicator('', '', '营业收入', '', '', '', '') > 1", "logical", "DOMAIN_DATA_UNAVAILABLE"),
        (
            "indicator('', '', 'KDJ底背离', '', '', '', '') = True",
            "logical",
            "DOMAIN_DATA_UNAVAILABLE",
        ),
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


def test_t0_indicator_uses_versioned_exchange_rule_membership():
    result = compile_official(
        "indicator('', '', '是否T+0', '', '', '', '') = True"
    ).to_dict()

    assert result["physical"]["selected_resource"] == "official_basic"
    assert "`findsl_ext`.`instrument_rule`" in result["backend"]["sql"]
    assert "`external_lookup`.`t0_eligible` = TRUE" in result["backend"]["sql"]
    assert ") = TRUE" not in result["backend"]["sql"]
    assert "exchange-stock-rules-2026-07-13-bd7ff74aef53" in result["backend"]["sql"]
    assert result["backend"]["validation_passed"] is True


def test_pipeline_materializes_versioned_industry_relative_aggregate():
    result = compile_official(
        "indicator('', '', '涨幅', '', '', '', '') > "
        "belong_industry('', '', '涨幅', '', 'AVG')"
    ).to_dict()

    assert result["physical"]["selected_strategy"] == "composite_grouped_aggregate"
    assert "`findsl_ext`.`industry_membership`" in result["backend"]["sql"]
    assert "baostock-industry-2026-07-13-4d38e6963e35" in result["backend"]["sql"]
    assert "GROUP BY" in result["backend"]["sql"]
    assert result["backend"]["validation_passed"] is True


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


@pytest.mark.parametrize(
    "source,sql_fragments",
    [
        (
            "cross_above('', '', '', '20日均线', '', '', '') = True",
            ("`official_basic`.`lastPx` / 10000.0 > `official_technical`.`ma20`",),
        ),
        (
            "reset('', '', '', '20日均线', '', '', '') = True",
            (
                "ABS((`official_basic`.`lastPx` / 10000.0) - `official_technical`.`ma20`)",
                "(`official_basic`.`lastPx` / 10000.0) >= (`official_technical`.`ma20` * 0.995)",
            ),
        ),
        (
            "record_low('', '', '', '20日', '', '', '', '') = True",
            (
                "`q`.`lastPx` / 10000.0 <= MIN(`q`.`lastPx` / 10000.0) OVER",
                "ROWS BETWEEN 19 PRECEDING AND CURRENT ROW",
            ),
        ),
        (
            "position('', '', '', '历史', '', '', '', '') = '低'",
            (
                "MIN(`q`.`lastPx` / 10000.0) OVER",
                "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW",
            ),
        ),
    ],
)
def test_pipeline_materializes_documented_default_price_for_event_functions(
    source, sql_fragments
):
    result = compile_official(source).to_dict()
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "crossing_window"
    for fragment in sql_fragments:
        assert fragment in sql
    assert result["backend"]["validation_passed"] is True


def test_pipeline_combines_crossing_events_without_scalar_fallback():
    result = compile_official(
        "cross_above('', '', '5日均线', '10日均线', '', '', '') = True "
        "or cross_down('', '', '5日均线', '10日均线', '', '', '') = True"
    ).to_dict()

    assert result["physical"]["selected_strategy"] == "crossing_window"
    assert "`event_rows`.`event_0` = TRUE OR `event_rows`.`event_1` = TRUE" in result["backend"]["sql"]


@pytest.mark.parametrize(
    "scope,fragments",
    [
        ("科创板注册制", ("688000", "688999")),
        ("沪深主板注册制", ("600000", "000000", "605999", "003999")),
    ],
)
def test_pipeline_lowers_registration_scope_as_controlled_board_ranges(scope, fragments):
    result = compile_official(
        f"indicator('', '{scope}', '', '', '', '', '') = 'all'"
    ).to_dict()

    sql = result["backend"]["sql"]
    assert result["backend"]["validation_passed"] is True
    for fragment in fragments:
        assert fragment in sql
    assert "registration" not in sql.casefold()


def test_pipeline_lowers_t0_scope_from_the_instrument_rule_resource():
    result = compile_official(
        "indicator('', '当天买当天卖', '是否T+0', '', '', '', '') = True"
    ).to_dict()

    assert result["backend"]["validation_passed"] is True
    sql = result["backend"]["sql"]
    assert "findsl_ext" in sql
    assert "t0_eligible" in sql
    assert sql.count("`findsl_ext`.`instrument_rule`") == 1


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
        (
            "record_high('', '', '最高价', '1日内', '今日', '', '', '') = True",
            "ROWS BETWEEN CURRENT ROW AND CURRENT ROW",
            ">= MAX(`q`.`highPx` / 10000.0) OVER",
        ),
        (
            "record_low('京', '辽宁指数', '', '季度', '', '', '', '') = True",
            "ROWS BETWEEN 59 PRECEDING AND CURRENT ROW",
            "<= MIN(`q`.`lastPx` / 10000.0) OVER",
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
    assert result["physical"]["plan"]["quantifier"] == "none"
    assert result["physical"]["plan"]["eligibility_predicate"] is not None
    assert " EXCEPT " not in sql
    assert "`event_rows`.`event_0` = TRUE" in sql
    assert "`event_rows`.`event_0` = FALSE" in sql
    assert "GROUP BY `event_rows`.`mktcode`, `event_rows`.`tgtcode`" in sql
    assert "HAVING MAX(CASE WHEN" in sql
    assert "= 1 AND MAX(CASE WHEN" in sql
    assert "= 0" in sql
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


def test_pipeline_splits_events_with_different_date_contracts_by_security():
    result = compile_official(
        "record_low('^创业板', '', '最低价', '历史', '今日', '', '', '') = True "
        "and record_high('^创业板', '', '最高价', '历史', '昨日', '', '', '') = True "
        "and indicator('^创业板', '', 'ST股票标识', '昨日', '', '', '') = False"
    ).to_dict()

    assert result["physical"]["selected_strategy"] == "event_candidate_intersect"
    assert result["backend"]["sql"].count(" INTERSECT ") >= 1
    assert "MAX(`q_latest`.`bizdate`)" in result["backend"]["sql"]
    assert "OFFSET 1" in result["backend"]["sql"]


def test_pipeline_normalizes_shorthand_extreme_period_and_latest_scalar_scope():
    result = compile_official(
        "record_high('', '', '收盘价', '80内', '三日内', '', '', '') = True "
        "and indicator('', '', '收盘价', '', '', '', '') < 10"
    ).to_dict()
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "event_candidate_intersect"
    assert "ROWS BETWEEN 79 PRECEDING AND CURRENT ROW" in sql
    assert "LIMIT 3" in sql
    assert "MAX(`q_latest`.`bizdate`)" in sql


@pytest.mark.parametrize(
    "source",
    [
        "indicator('', '', '成交量', '', '', '', '') > 0",
        (
            "indicator('', '', '最新价', '', '', '', '') >= "
            "indicator('', '', '5日均线', '', '', '', '')"
        ),
    ],
)
def test_pipeline_undated_direct_filters_use_latest_data_snapshot(source):
    result = compile_official(source).to_dict()

    assert "SELECT MAX(" in result["backend"]["sql"]
    assert "`bizdate`" in result["backend"]["sql"]


@pytest.mark.parametrize(
    "source,fragments",
    [
        (
            "golden_cross('科创板', '', '3日均线', '30日均线', '17年', '', 'CONS=每月') = True",
            ("DATE_TRUNC(`source_rows`.`bizdate`, 'MONTH')", "SUM(`bucket_rows`.`matched`)"),
        ),
        (
            "golden_cross('京|深', '', '20日均线', '200日均线', '', '', 'CONS=5日') = True",
            ("AS `all_seq`", "AS `matched_seq`", "MAX(`runs`.`run_length`)"),
        ),
    ],
)
def test_pipeline_projects_crossing_events_before_temporal_quantification(
    source,
    fragments,
):
    result = compile_official(source).to_dict()
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "temporal_event_projection"
    assert result["physical"]["plan"]["input"]["kind"] == "PhysicalEventProjection"
    assert "LAG(" in sql
    assert "CASE WHEN `event_rows`.`event_0` = TRUE THEN 1 ELSE 0 END" in sql
    for fragment in fragments:
        assert fragment in sql


@pytest.mark.parametrize(
    "source,event_kind,sql_fragments",
    [
        (
            "position('', '', '', '历史', '', '', '', 'CONS>1') = '低'",
            "PhysicalPosition",
            (
                "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW",
                "CASE WHEN `event_rows`.`event_0` = '低' THEN 1 ELSE 0 END",
                "MAX(`runs`.`run_length`)",
            ),
        ),
        (
            "record_low('', '', '', '20日', '近5日', '', '', 'EXIST>=2日') = True",
            "PhysicalExtreme",
            (
                "ROWS BETWEEN 19 PRECEDING AND CURRENT ROW",
                "CASE WHEN `event_rows`.`event_0` = TRUE THEN 1 ELSE 0 END",
                "`temporal_metrics`.`metric_value` >= 2",
            ),
        ),
        (
            "close_together('', '', '', '5日均线', '', '', 'CONS=5日') = True",
            "PhysicalPattern",
            (
                "GREATEST(",
                "CASE WHEN `event_rows`.`event_0` = TRUE THEN 1 ELSE 0 END",
                "MAX(`runs`.`run_length`)",
            ),
        ),
    ],
)
def test_pipeline_projects_all_event_kinds_before_temporal_quantification(
    source, event_kind, sql_fragments
):
    result = compile_official(source).to_dict()
    projection = result["physical"]["plan"]["input"]
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "temporal_event_projection"
    assert projection["kind"] == "PhysicalEventProjection"
    assert projection["events"][0]["kind"] == event_kind
    for fragment in sql_fragments:
        assert fragment in sql


def test_pipeline_never_ignores_non_empty_window_event_slots():
    with pytest.raises(OfficialPipelineError) as excinfo:
        compile_official(
            "record_high('', '', '最高价', '20日', '今日', '', 'MAX', '') = True"
        )

    assert excinfo.value.code == "PHYSICAL_EVENT_COMPOSITION_UNSUPPORTED"


@pytest.mark.parametrize(
    "source,frame",
    [
        ("record_low('', '', '', '半个月', '上月', '', '', '') = True", 9),
        ("record_high('', '', '', '上个月', '', '', '', '') = True", 19),
    ],
)
def test_pipeline_normalizes_grounded_natural_event_periods(source, frame):
    result = compile_official(source).to_dict()

    assert f"ROWS BETWEEN {frame} PRECEDING AND CURRENT ROW" in result["backend"]["sql"]
    assert result["physical"]["selected_strategy"] == "crossing_window"


def test_pipeline_projects_exact_security_scope_before_temporal_event():
    result = compile_official(
        "cross_above('', '上海电力', '', '60日均线', '', '', 'EXIST>1') = True"
    ).to_dict()
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "temporal_event_projection"
    assert "`hsj_stock_code_info` AS official_security" in sql
    assert "`official_security`.`name` = '上海电力'" in sql
    assert "LAG(" in sql
    assert "`temporal_metrics`.`metric_value` > 1" in sql


def test_pipeline_combines_prefix_average_crossing_with_temporal_quantifier():
    result = compile_official(
        "cross_above('', '', '', '7日均线', '八月一号开始4日', '', "
        "'CONS=每日') = True"
    ).to_dict()
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "temporal_event_projection"
    assert "prefix_anchor_rows" in sql
    assert "LAG(" in sql
    assert "temporal_metrics" in sql


def test_pipeline_materializes_pressure_events_without_placeholder_sql():
    result = compile_official(
        "reset('', '', '', '支撑位', '今天', '', '') = True and "
        "(cross_above('', '', '', '压力位', '', '', 'EXIST>0') = True or "
        "cross_down('', '', '', '压力位', '', '', 'EXIST>0') = True)"
    ).to_dict()
    sql = result["backend"]["sql"]

    assert "`q`.`support` / 10000.0" in sql
    assert "`q`.`pressure` / 10000.0" in sql
    assert "LAG(`q`.`pressure` / 10000.0" in sql
    assert "1 = 0" not in sql and "1 = 1" not in sql


def test_pipeline_materializes_unsealed_limit_event_from_grounded_quote_fields():
    result = compile_official(
        "indicator('', '', '涨停未封板', '2月25号', '', '', '') = True"
    ).to_dict()
    sql = result["backend"]["sql"]

    assert "`q`.`upSealPx` > 0" in sql
    assert "`q`.`highPx` >= `q`.`upSealPx`" in sql
    assert "`q`.`limitFlag` <> 1" in sql
    assert "MONTH(" in sql


def test_pipeline_accepts_half_year_event_date_as_six_calendar_months():
    result = compile_official(
        "position('', '', '', '历史', '半年内', '', '', '') = '最低'"
    ).to_dict()

    assert "INTERVAL '6' MONTH" in result["backend"]["sql"]


def test_pipeline_filters_fixed_since_period_before_event_window():
    result = compile_official(
        "record_high('', '', '', '2025年10月9日以来', '', '', '', '') = True "
        "and indicator('', '', '涨幅', '最新', '', '', '') > 6% "
        "and indicator('', '', '换手率', '最新', '', '', '') > 10%"
    ).to_dict()
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "crossing_window"
    assert "WHERE `q`.`bizdate` >= '2025-10-09'" in sql
    assert "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW" in sql
    assert "`event_rows`.`bizdate` = (SELECT MAX(" in sql


@pytest.mark.parametrize(
    "period,end_month_offset",
    [("今年1月到10月", 10), ("上半年", 6)],
)
def test_pipeline_filters_calendar_period_before_event_window(
    period, end_month_offset
):
    result = compile_official(
        f"record_high('', '房地产服务', '', '{period}', '近3天', '', '', '') = True"
    ).to_dict()
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "crossing_window"
    assert "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW" in sql
    assert "LIMIT 3" in sql
    assert "DATE_TRUNC" in sql
    assert f"INTERVAL '{end_month_offset}' MONTH" in sql


def test_pipeline_ranks_the_materialized_event_candidate_stage():
    result = compile_official(
        "indicator('科创板', '', 'MA角度', '', '', '', '') = 45 and "
        "position('科创板', '', '', '历史', '目前', '', '', '') = '低' "
        "then rank('科创板', '', '主力净流入', 'asc', '', '', '', '') <= 5"
    ).to_dict()
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "stage_rank"
    assert "CASE WHEN `official_basic`.`lastPx` / 10000.0" in sql
    assert "`stage_1_candidates_raw`" in sql
    assert "ROW_NUMBER() OVER (ORDER BY" in sql
    assert "`stage_1_ranked`.`stage_rank` <= 5" in sql


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

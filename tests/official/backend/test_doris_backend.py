import sqlglot
import pytest
from sqlglot import exp

from findsl.official.backend.doris import render_doris
from findsl.official.lowering import lower_official_ast
from findsl.official.physical.catalog import default_physical_catalog
from findsl.official.physical import (
    PhysicalBinary,
    PhysicalCoalesce,
    PhysicalColumn,
    PhysicalComparison,
    PhysicalFilter,
    PhysicalLiteral,
    PhysicalNullIf,
    PhysicalScan,
    PhysicalUnary,
)
from findsl.official.physical.planner import plan_physical
from findsl.official.physical.expressions import default_physical_expressions
from findsl.official.registry import default_official_registry
from findsl.official.semantics import OfficialSemanticAnalyzer
from findsl.official_slot import _resolve_indicator_meta, parse_official_slot
from findsl.official.types import BOOLEAN, NUMERIC, STRING


def _physical(source):
    typed = OfficialSemanticAnalyzer(_resolve_indicator_meta).analyze(parse_official_slot(source, mode="strict"))
    logical = lower_official_ast(typed, domain_registry=default_official_registry())
    return plan_physical(logical, default_physical_catalog()).plan


def test_direct_filter_and_limit_render_as_stable_doris_select_ast():
    result = render_doris(
        _physical("indicator('', '', '成交量', '', '', '', '') > 100 limit 0,20"),
        default_physical_catalog(),
    )

    parsed = sqlglot.parse_one(result.sql, read="doris")
    assert isinstance(result.ast, exp.Select)
    assert isinstance(parsed, exp.Select)
    assert [item.alias_or_name for item in parsed.expressions] == ["mktcode", "tgtcode", "bizdate"]
    assert parsed.args["limit"].expression.this == "20"
    assert result.round_trip_stable is True
    assert result.validation.passed is True
    assert result.validation.table_references == ["hsj_stock_hq_basic"]


def test_backend_uses_sqlglot_literal_escaping():
    column = PhysicalColumn("official_security", "name", STRING)
    plan = PhysicalFilter(
        PhysicalScan("official_security", (column,), None, "official_basic"),
        PhysicalComparison("=", column, PhysicalLiteral("O'Reilly", STRING)),
    )
    result = render_doris(
        plan,
        default_physical_catalog(),
    )

    assert "O''Reilly" in result.sql
    assert result.validation.passed is True
    assert "`anchor`.`bizdate`" in result.sql


def test_between_is_lowered_to_auditable_bounded_comparisons():
    result = render_doris(
        _physical("indicator('', '', '成交量', '', '', '', '') between [1, 5]"),
        default_physical_catalog(),
    )

    where = sqlglot.parse_one(result.sql, read="doris").args["where"].this
    assert isinstance(where, exp.And)
    assert isinstance(where.this, exp.GTE)
    assert isinstance(where.expression, exp.LTE)


def test_numeric_percent_literal_is_rendered_as_number_not_sql_string():
    result = render_doris(
        _physical("indicator('', '', '成交量', '', '', '', '') > 2%"),
        default_physical_catalog(),
    )

    assert "`q`.`volume` > 2" in result.sql
    assert "'2%'" not in result.sql


def test_latest_date_and_market_constraints_render_as_sqlglot_ast():
    result = render_doris(
        _physical("indicator('沪|深', '', '成交量', '今日', '', '', '') > 100"),
        default_physical_catalog(),
    )

    parsed = sqlglot.parse_one(result.sql, read="doris")
    assert len(list(parsed.find_all(exp.Max))) == 1
    assert "`q`.`mktcode` IN (0, 1)" in result.sql
    assert result.validation.passed is True


def test_market_set_algebra_renders_typed_code_ranges_and_not():
    result = render_doris(
        _physical(
            "indicator('沪|深&^创业板', '', '成交量', '今日', '', '', '') > 100"
        ),
        default_physical_catalog(),
    )

    assert "`q`.`mktcode` IN (1)" in result.sql
    assert "`q`.`mktcode` IN (0)" in result.sql
    assert "NOT" in result.sql
    assert "`q`.`tgtcode` >= '300000'" in result.sql
    assert "`q`.`tgtcode` <= '300999'" in result.sql
    assert "`q`.`tgtcode` >= '301000'" in result.sql
    assert "`q`.`tgtcode` <= '301999'" in result.sql
    assert "kcbFlag" not in result.sql
    assert "gemFlag" not in result.sql
    assert result.validation.passed is True


def test_universe_selector_materializes_market_and_date_without_placeholder_sql():
    result = render_doris(
        _physical("indicator('沪主板', '', '', '今日', '', '', '') = 'all'"),
        default_physical_catalog(),
    )

    assert "'all' = 'all'" in result.sql
    assert "`q`.`mktcode` IN (1)" in result.sql
    assert "`q`.`tgtcode` >= '600000'" in result.sql
    assert "SELECT MAX(`q_latest`.`bizdate`)" in result.sql
    assert "1 = 0" not in result.sql
    assert "1 = 1" not in result.sql
    assert result.validation.passed is True


def test_security_name_scope_renders_catalog_join_and_exact_name_predicate():
    result = render_doris(
        _physical("indicator('', '华泰证券', '', '', '', '', '') = 'all'"),
        default_physical_catalog(),
    )

    assert "LEFT JOIN `newzl`.`hsj_stock_code_info` AS q" in result.sql
    assert "`q`.`name` = '华泰证券'" in result.sql
    assert "hyBlkRefName" not in result.sql
    assert result.validation.passed is True


def test_querydata_aggregate_uses_global_scalar_group_with_security_join():
    result = render_doris(
        _physical(
            "indicator('', '', '成交量', '', '', 'AVG', '') > "
            "queryData('', '贵州茅台', '成交量', '', 'AVG')"
        ),
        default_physical_catalog(),
    )

    assert "CROSS JOIN" in result.sql
    assert "LEFT JOIN `newzl`.`hsj_stock_code_info` AS official_security" in result.sql
    assert "`official_security`.`name` = '贵州茅台'" in result.sql
    assert "SELECT AVG(`official_basic`.`volume`) AS `metric_1`" in result.sql
    assert "GROUP BY `official_security`" not in result.sql
    assert "`q`.`name`" not in result.sql
    assert result.validation.passed is True


def test_querydata_direct_value_uses_singleton_named_relation_not_global_filter():
    result = render_doris(
        _physical(
            "indicator('', '', '成交量', '', '', '', '') > "
            "queryData('', '贵州茅台', '成交量', '', '')"
        ),
        default_physical_catalog(),
    )

    assert "CROSS JOIN" in result.sql
    assert "AS scalar_0" in result.sql
    assert "`official_security`.`name` = '贵州茅台'" in result.sql
    assert "`official_basic`.`bizdate` = (SELECT MAX(" in result.sql
    outer_where = result.sql.rsplit(" WHERE ", 1)[-1]
    assert "贵州茅台" not in outer_where
    assert "`q`.`volume` > `scalar_0`.`scalar_value_0`" in result.sql
    assert result.validation.passed is True


def test_typed_year_range_renders_bounded_partition_predicate():
    result = render_doris(
        _physical("indicator('', '', '成交量', '一八年', '', '', '') > 100"),
        default_physical_catalog(),
    )

    assert "`q`.`bizdate` >= '2018-01-01'" in result.sql
    assert "`q`.`bizdate` <= '2018-12-31'" in result.sql
    assert result.validation.passed is True


def test_yesterday_uses_distinct_trading_calendar_offset_not_date_sub():
    result = render_doris(
        _physical("indicator('', '', '成交量', '昨天', '', '', '') > 100"),
        default_physical_catalog(),
    )

    assert "GROUP BY `q_session`.`bizdate`" in result.sql
    assert "ORDER BY `q_session`.`bizdate` DESC" in result.sql
    assert "LIMIT 1 OFFSET 1" in result.sql
    assert "DATE_SUB" not in result.sql
    assert result.validation.passed is True


def test_recent_sessions_use_distinct_exchange_calendar_membership():
    result = render_doris(
        _physical("indicator('', '', '成交量', '近5日', '', '', '') > 100"),
        default_physical_catalog(),
    )

    assert "`q`.`bizdate` IN (SELECT `calendar_sessions`.`bizdate`" in result.sql
    assert "GROUP BY `calendar_sessions`.`bizdate`" in result.sql
    assert "ORDER BY `calendar_sessions`.`bizdate` DESC" in result.sql
    assert "LIMIT 5" in result.sql
    assert "ROW_NUMBER" not in result.sql
    assert result.validation.passed is True


@pytest.mark.parametrize(
    "date,required",
    [
        ("本月", ("DATE_TRUNC", "MONTH")),
        ("本季度", ("DATE_TRUNC", "QUARTER")),
        ("上周", ("DATE_TRUNC", "WEEK", "DATE_SUB")),
        ("前年", ("DATE_TRUNC", "YEAR", "INTERVAL '2' YEAR")),
        ("近五周", ("DATE_SUB", "INTERVAL '34' DAY")),
        ("近两个月", ("DATE_SUB", "INTERVAL '2' MONTH", "DATE_ADD")),
        ("3月2号", ("DATE_TRUNC", "INTERVAL '2' MONTH", "INTERVAL '1' DAY")),
    ],
)
def test_dynamic_calendar_ranges_render_from_latest_data_anchor(date, required):
    result = render_doris(
        _physical(f"indicator('', '', '成交量', '{date}', '', '', '') > 100"),
        default_physical_catalog(),
    )

    assert "MAX(`calendar_anchor`.`bizdate`)" in result.sql
    for fragment in required:
        assert fragment in result.sql
    assert result.validation.passed is True


def test_preceding_session_slice_uses_distinct_calendar_limit_and_offset():
    result = render_doris(
        _physical(
            "indicator('', '', '成交额', '最近三天的前3日', '', '', '') > 100"
        ),
        default_physical_catalog(),
    )

    assert "GROUP BY `calendar_sessions`.`bizdate`" in result.sql
    assert "ORDER BY `calendar_sessions`.`bizdate` DESC" in result.sql
    assert "LIMIT 3 OFFSET 3" in result.sql
    assert result.validation.passed is True


@pytest.mark.parametrize(
    "date,comparison,order,limit",
    [
        ("本周的前3天", "< DATE_TRUNC", "DESC", 3),
        ("2024年3月10号的后5日", "> '2024-03-10'", "", 5),
    ],
)
def test_boundary_session_ranges_select_real_exchange_dates(date, comparison, order, limit):
    result = render_doris(
        _physical(f"indicator('', '', '成交量', '{date}', '', '', 'EXIST>0') > 10"),
        default_physical_catalog(),
    )

    assert comparison in result.sql
    ordered = next(
        item
        for item in result.ast.find_all(exp.Ordered)
        if isinstance(item.this, exp.Column) and item.this.table == "boundary_sessions"
    )
    assert bool(ordered.args.get("desc")) is (order == "DESC")
    assert f"LIMIT {limit}" in result.sql
    assert result.validation.passed is True


def test_grouped_sum_uses_set_plan_and_latest_snapshot_join():
    result = render_doris(
        _physical(
            "indicator('沪', '', '成交量', '近5日', '', 'SUM', '') > 100000000"
        ),
        default_physical_catalog(),
    )

    assert "SUM(`q`.`volume`) AS `metric_value`" in result.sql
    assert "GROUP BY `q`.`mktcode`, `q`.`tgtcode`" in result.sql
    assert "`aggregate_rows`.`metric_value` > 100000000" in result.sql
    assert "INNER JOIN" in result.sql
    assert "`anchor_out`.`bizdate` = (SELECT MAX(" in result.sql
    assert result.sql.count("SELECT SUM(") == 0
    assert result.validation.passed is True


def test_grouped_aggregate_preserves_ext_anchor_join_keys():
    result = render_doris(
        _physical(
            "indicator('', '', '主力净流入', '近5日', '', 'AVG', '') > 0"
        ),
        default_physical_catalog(),
    )

    assert "LEFT JOIN `newzl`.`hsj_stock_hq_ext` AS q" in result.sql
    assert "AVG(`q`.`ZJLXMainNetTur`) AS `metric_value`" in result.sql
    assert "GROUP BY `anchor`.`mktcode`, `anchor`.`tgtcode`" in result.sql
    assert result.validation.passed is True


@pytest.mark.parametrize(
    ("function", "delta"),
    [
        ("GROWTH_RISE", "MAX_BY(`q`.`volume`, `q`.`bizdate`) - MIN_BY(`q`.`volume`, `q`.`bizdate`)"),
        ("GROWTH_FALL", "MIN_BY(`q`.`volume`, `q`.`bizdate`) - MAX_BY(`q`.`volume`, `q`.`bizdate`)"),
    ],
)
def test_growth_aggregate_uses_ordered_first_last_values_and_zero_guard(function, delta):
    result = render_doris(
        _physical(
            f"indicator('', '', '成交量', '近5日', '', '{function}', '') > 10"
        ),
        default_physical_catalog(),
    )

    assert delta in result.sql
    assert "NULLIF(ABS(MIN_BY(`q`.`volume`, `q`.`bizdate`)), 0)" in result.sql
    assert "AS `metric_value`" in result.sql
    assert result.validation.passed is True


def test_composite_aggregate_ratio_renders_named_set_relations_and_safe_division():
    result = render_doris(
        _physical(
            "indicator('', '', '主力净流入', '近5日', '', 'AVG', '') / "
            "indicator('', '', '成交额', '近5日', '', 'AVG', '') < 20%"
        ),
        default_physical_catalog(),
    )

    parsed = sqlglot.parse_one(result.sql, read="doris")
    assert result.sql.count("AVG(") == 2
    assert "AS aggregate_0" in result.sql
    assert "AS aggregate_1" in result.sql
    assert "(`aggregate_0`.`metric_0` / NULLIF(`aggregate_1`.`metric_1`, 0)) < 20" in result.sql
    assert len(list(parsed.find_all(exp.Join))) == 3
    assert "WHERE (SELECT AVG(" not in result.sql
    assert result.validation.passed is True


def test_composite_scalar_to_min_renders_latest_anchor_and_grouped_window():
    result = render_doris(
        _physical(
            "indicator('', '', '成交量', '今日', '', '', '') = "
            "indicator('', '', '成交量', '近100个交易日', '', 'MIN', '')"
        ),
        default_physical_catalog(),
    )

    assert "MIN(`q`.`volume`) AS `metric_0`" in result.sql
    assert "LIMIT 100" in result.sql
    assert "`q`.`volume` = `aggregate_0`.`metric_0`" in result.sql
    assert result.sql.count("SELECT MIN(") == 0
    assert result.validation.passed is True


def test_rank_renders_window_in_subquery_and_filters_outer_query():
    result = render_doris(
        _physical("rank('', '', '成交量', 'desc', '今日', '', '', '') <= 10"),
        default_physical_catalog(),
    )

    parsed = sqlglot.parse_one(result.sql, read="doris")
    assert len(list(parsed.find_all(exp.RowNumber))) == 1
    assert len(list(parsed.find_all(exp.Window))) == 1
    assert "`ranked`.`__rank_value` <= 10" in result.sql
    assert "`q`.`volume` DESC, `q`.`mktcode` ASC, `q`.`tgtcode` ASC" in result.sql
    outer_order = parsed.args.get("order")
    assert outer_order is None
    assert result.validation.passed is True


def test_percentage_rank_uses_partition_cardinality_and_ceiling():
    result = render_doris(
        _physical("rank('', '', '成交量', 'desc', '今日', '', '', '') <= 10%"),
        default_physical_catalog(),
    )

    parsed = sqlglot.parse_one(result.sql, read="doris")
    assert len(list(parsed.find_all(exp.RowNumber))) == 1
    assert len(list(parsed.find_all(exp.Count))) == 1
    assert "CEIL(`ranked`.`__partition_count` * 10 / 100.0)" in result.sql
    assert result.validation.passed is True


def test_aggregate_rank_renders_group_then_window_without_correlated_aggregate():
    result = render_doris(
        _physical("rank('', '', '成交量', 'desc', '近5日', '', 'AVG', '') <= 10"),
        default_physical_catalog(),
    )

    parsed = sqlglot.parse_one(result.sql, read="doris")
    assert "AVG(`q`.`volume`) AS `metric_value`" in result.sql
    assert "GROUP BY `q`.`mktcode`, `q`.`tgtcode`" in result.sql
    assert "ROW_NUMBER() OVER (ORDER BY `aggregate_rows`.`metric_value` DESC" in result.sql
    assert "`aggregate_ranked`.`__rank_value` <= 10" in result.sql
    assert result.sql.count("SELECT AVG(") == 0
    assert len(list(parsed.find_all(exp.RowNumber))) == 1
    assert result.validation.passed is True


def test_growth_rank_reuses_ordered_growth_measure_before_ranking():
    result = render_doris(
        _physical(
            "rank('', '', '成交量', 'desc', '近10日', '', 'GROWTH_RISE', '') <= 10"
        ),
        default_physical_catalog(),
    )

    assert "MAX_BY(`q`.`volume`, `q`.`bizdate`)" in result.sql
    assert "MIN_BY(`q`.`volume`, `q`.`bizdate`)" in result.sql
    assert "ROW_NUMBER() OVER (ORDER BY `aggregate_rows`.`metric_value` DESC" in result.sql
    assert result.validation.passed is True


def test_temporal_growth_uses_one_lag_stage_and_parenthesized_rate():
    result = render_doris(
        _physical(
            "indicator('', '', '成交量', '近10个交易日内', '', "
            "'GROWTH_RISE', 'EXIST>0') > 50%"
        ),
        default_physical_catalog(),
    )

    assert result.sql.count("LAG(") == 1
    assert "(`aggregate_lag`.`daily_value` - `aggregate_lag`.`previous_value`) * 100" in result.sql
    assert "NULLIF(ABS(`aggregate_lag`.`previous_value`), 0)" in result.sql
    assert "SUM(`aggregate_matched`.`matched`) AS `metric_value`" in result.sql
    assert result.validation.passed is True


def test_temporal_calendar_aggregate_groups_before_consecutive_evaluation():
    result = render_doris(
        _physical(
            "indicator('', '', '成交额', '近3月', '', 'AVG', 'CONS>=2月') > 30000"
        ),
        default_physical_catalog(),
    )

    assert "DATE_TRUNC(`aggregate_source`.`bizdate`, 'MONTH')" in result.sql
    assert "AVG(`aggregate_source`.`measure_value`) AS `metric_value`" in result.sql
    assert "AS `run_group`" in result.sql
    assert "MAX(`aggregate_runs`.`run_length`) AS `metric_value`" in result.sql
    assert result.validation.passed is True


def test_temporal_growth_rank_orders_metric_before_percentage_count():
    result = render_doris(
        _physical(
            "rank('', '', '成交量', 'desc', '', '', 'GROWTH_RISE', 'CONS=10日') <= 20%"
        ),
        default_physical_catalog(),
    )

    assert "AS `previous_value`" in result.sql
    assert "ROW_NUMBER() OVER (PARTITION BY `aggregate_metric`.`bizdate`" in result.sql
    assert "`aggregate_metric`.`metric_value` DESC" in result.sql
    assert "COUNT(*) OVER (PARTITION BY `aggregate_metric`.`bizdate`) AS `rank_population`" in result.sql
    assert "CEIL(`aggregate_ranked`.`rank_population` * 20 / 100.0)" in result.sql
    assert result.validation.passed is True


def test_temporal_direct_rank_collapses_daily_matches_into_calendar_buckets():
    result = render_doris(
        _physical(
            "rank('', '', '涨停时间', 'asc', '最近一周', '', '', 'CONS=每周') = 1"
        ),
        default_physical_catalog(),
    )

    assert "ROW_NUMBER() OVER (PARTITION BY `aggregate_metric`.`bizdate`" in result.sql
    assert "DATE_TRUNC(`aggregate_matched`.`bizdate`, 'WEEK')" in result.sql
    assert "MAX(`aggregate_matched`.`matched`) AS `matched`" in result.sql
    assert result.validation.passed is True


def test_rank_and_scalar_filter_render_as_set_intersection():
    result = render_doris(
        _physical(
            "rank('', '', '成交量', 'desc', '今日', '', '', '') <= 10 and "
            "indicator('', '', '成交量', '今日', '', '', '') > 100"
        ),
        default_physical_catalog(),
    )

    assert len(list(sqlglot.parse_one(result.sql, read="doris").find_all(exp.Intersect))) == 1
    assert result.validation.passed is True


def test_filter_then_rank_stage_scans_one_resource_once():
    result = render_doris(
        _physical(
            "indicator('', '', '成交量', '', '', '', '') > 0 "
            "then rank('', '', '成交量', 'desc', '', '', '', '') <= 10"
        ),
        default_physical_catalog(),
    )

    parsed = sqlglot.parse_one(result.sql, read="doris")
    tables = [table.name for table in parsed.find_all(exp.Table)]
    assert tables == ["hsj_stock_hq_basic"]
    assert "`q`.`volume` > 0" in result.sql


def test_ext_scan_preserves_official_basic_universe_with_left_join():
    result = render_doris(
        _physical("indicator('', '', '主力净流入', '', '', '', '') > 0"),
        default_physical_catalog(),
    )

    parsed = sqlglot.parse_one(result.sql, read="doris")
    assert [table.name for table in parsed.find_all(exp.Table)] == [
        "hsj_stock_hq_basic",
        "hsj_stock_hq_ext",
    ]
    assert "LEFT JOIN" in result.sql
    assert "`q`.`bizdate` = `anchor`.`bizdate`" in result.sql
    assert [item.table for item in parsed.expressions] == ["anchor", "anchor", "anchor"]


def test_multi_resource_join_renders_one_star_join_with_all_stable_keys():
    catalog = default_physical_catalog()
    typed = OfficialSemanticAnalyzer(_resolve_indicator_meta).analyze(
        parse_official_slot(
            "indicator('', '', '成交量', '', '', '', '') > 100 and "
            "indicator('', '', '主力净流入', '', '', '', '') > 0",
            mode="strict",
        )
    )
    logical = lower_official_ast(typed, domain_registry=default_official_registry())
    physical = plan_physical(logical, catalog)

    result = render_doris(physical.plan, catalog)

    assert result.sql.count("`hsj_stock_hq_basic`") == 1
    assert result.sql.count("`hsj_stock_hq_ext`") == 1
    assert "LEFT JOIN" in result.sql
    assert "`official_basic`.`mktcode` = `official_ext`.`mktcode`" in result.sql
    assert "`official_basic`.`tgtcode` = `official_ext`.`tgtcode`" in result.sql
    assert "`official_basic`.`bizdate` = `official_ext`.`bizdate`" in result.sql
    assert "`official_basic`.`volume` > 100" in result.sql
    assert "`official_ext`.`ZJLXMainNetTur` > 0" in result.sql
    assert result.validation.passed is True


def test_three_resource_join_uses_static_dimension_keys_without_bizdate():
    catalog = default_physical_catalog()
    typed = OfficialSemanticAnalyzer(_resolve_indicator_meta).analyze(
        parse_official_slot(
            "indicator('', '', '成交量', '', '', '', '') > 100 and "
            "indicator('', '', '主力净流入', '', '', '', '') > 0 and "
            "indicator('', '', 'ST股票标识', '', '', '', '') = False",
            mode="strict",
        )
    )
    logical = lower_official_ast(typed, domain_registry=default_official_registry())
    physical = plan_physical(logical, catalog)

    result = render_doris(physical.plan, catalog)

    assert result.sql.count("LEFT JOIN") == 2
    security_on = result.sql.split("LEFT JOIN `newzl`.`hsj_stock_code_info`")[1].split(" WHERE ")[0]
    assert "`official_security`.`mktcode`" in security_on
    assert "`official_security`.`tgtcode`" in security_on
    assert "`official_security`.`bizdate`" not in security_on
    assert "`official_security`.`stFlag` = FALSE" in result.sql
    assert result.validation.passed is True


def test_multi_resource_join_deduplicates_identical_latest_date_constraints():
    catalog = default_physical_catalog()
    typed = OfficialSemanticAnalyzer(_resolve_indicator_meta).analyze(
        parse_official_slot(
            "indicator('', '', '成交量', '今日', '', '', '') > 100 and "
            "indicator('', '', '主力净流入', '今日', '', '', '') > 0 and "
            "indicator('', '', 'ST股票标识', '今日', '', '', '') = False",
            mode="strict",
        )
    )
    logical = lower_official_ast(typed, domain_registry=default_official_registry())
    physical = plan_physical(logical, catalog)

    result = render_doris(physical.plan, catalog)

    assert len(list(sqlglot.parse_one(result.sql, read="doris").find_all(exp.Max))) == 1


def test_ext_market_constraint_renders_against_anchor_universe():
    result = render_doris(
        _physical("rank('沪|深', '', '连涨天数', 'desc', '', '', '', '') <= 10"),
        default_physical_catalog(),
    )

    assert "`anchor`.`mktcode` IN (0, 1)" in result.sql


def test_prefix_average_candidate_renders_as_controlled_correlated_subquery():
    catalog = default_physical_catalog()
    typed = OfficialSemanticAnalyzer(_resolve_indicator_meta).analyze(
        parse_official_slot("indicator('', '', '5日均线', '', '', '', '') > 10", mode="strict")
    )
    logical = lower_official_ast(typed, domain_registry=default_official_registry())
    from findsl.official.physical.statistics import default_physical_statistics
    from findsl.official.physical.strategies import default_physical_strategies

    physical = plan_physical(
        logical,
        catalog,
        statistics=default_physical_statistics(catalog),
        strategies=default_physical_strategies(catalog),
        allow_shadow_strategies=True,
    )
    result = render_doris(physical.plan, catalog)

    assert physical.selected_strategy == "ma5_prefix_average"
    assert result.sql.count("`hsj_stock_hq_basic_prefix`") == 2
    assert "`p_prev`.`row_no` = `p`.`row_no` - 5" in result.sql
    assert "`p`.`close_prefix`" in result.sql
    assert "`p`.`close_count_prefix`" in result.sql
    assert "(`p`.`close_prefix` - COALESCE(`p_prev`.`close_prefix`, 0)) * 1.0" in result.sql
    assert result.validation.passed is True


def test_controlled_safe_divide_renders_explicit_nullif_ast():
    catalog = default_physical_catalog()
    last = PhysicalColumn("official_basic", "lastPx", NUMERIC)
    previous = PhysicalColumn("official_basic", "preClosePx", NUMERIC)
    numerator = PhysicalBinary(
        "*",
        PhysicalBinary("-", last, previous, NUMERIC),
        PhysicalLiteral(100.0, NUMERIC),
        NUMERIC,
    )
    change = PhysicalBinary(
        "/",
        numerator,
        PhysicalNullIf(previous, PhysicalLiteral(0, NUMERIC), NUMERIC),
        NUMERIC,
    )
    plan = PhysicalFilter(
        PhysicalScan("official_basic", (last, previous), None),
        PhysicalComparison(">", change, PhysicalLiteral(1, NUMERIC)),
    )

    result = render_doris(plan, catalog, default_physical_expressions(catalog))

    parsed = sqlglot.parse_one(result.sql, read="doris")
    assert len(list(parsed.find_all(exp.Nullif))) == 1
    assert "(`q`.`lastPx` - `q`.`preClosePx`) * 100.0" in result.sql
    assert "NULLIF(`q`.`preClosePx`, 0)" in result.sql
    assert result.round_trip_stable is True


def test_controlled_unary_and_coalesce_render_without_raw_sql():
    catalog = default_physical_catalog()
    net = PhysicalColumn("official_ext", "ZJLXMainNetTur", NUMERIC)
    limit_flag = PhysicalColumn("official_basic", "limitFlag", NUMERIC)
    serial = PhysicalColumn("official_basic", "upSerialLb", NUMERIC)
    coalesced = PhysicalCoalesce(
        (serial, PhysicalLiteral(0, NUMERIC)),
        NUMERIC,
    )
    condition = PhysicalBinary(
        "and",
        PhysicalComparison("=", limit_flag, PhysicalLiteral(1, NUMERIC)),
        PhysicalComparison("=", coalesced, PhysicalLiteral(1, NUMERIC)),
        BOOLEAN,
    )
    basic_plan = PhysicalFilter(
        PhysicalScan("official_basic", (limit_flag, serial), None),
        condition,
    )
    ext_plan = PhysicalFilter(
        PhysicalScan("official_ext", (net,), None, "official_basic"),
        PhysicalComparison(">", PhysicalUnary("negate", net, NUMERIC), PhysicalLiteral(0, NUMERIC)),
    )
    expressions = default_physical_expressions(catalog)

    basic_sql = render_doris(basic_plan, catalog, expressions).sql
    ext_sql = render_doris(ext_plan, catalog, expressions).sql

    assert "COALESCE(`q`.`upSerialLb`, 0) = 1" in basic_sql
    assert "-`q`.`ZJLXMainNetTur` > 0" in ext_sql
    assert "Raw" not in repr(sqlglot.parse_one(basic_sql, read="doris"))


def test_exist_temporal_plan_renders_set_based_ctes_and_latest_snapshot_join():
    result = render_doris(
        _physical("indicator('', '', '成交量', '', '', '', 'EXIST>=5') > 100"),
        default_physical_catalog(),
    )

    parsed = sqlglot.parse_one(result.sql, read="doris")
    aliases = {cte.alias_or_name for cte in parsed.find_all(exp.CTE)}
    assert {"source_rows", "temporal_metrics", "qualified"}.issubset(aliases)
    assert "SUM" in result.sql
    assert "`metric_value` >= 5" in result.sql
    assert "JOIN `qualified`" in result.sql
    assert result.validation.passed is True


def test_consecutive_temporal_plan_uses_trading_row_islands_not_calendar_day_difference():
    result = render_doris(
        _physical("indicator('', '', '成交量', '最近10日', '', '', 'CONS=3日') > 100"),
        default_physical_catalog(),
    )

    parsed = sqlglot.parse_one(result.sql, read="doris")
    aliases = {cte.alias_or_name for cte in parsed.find_all(exp.CTE)}
    assert {"source_rows", "eligible_rows", "matched_rows", "runs", "temporal_metrics", "qualified"}.issubset(aliases)
    assert result.sql.count("ROW_NUMBER() OVER") >= 2
    assert "DATEDIFF" not in result.sql.upper()
    assert "`run_length`" in result.sql
    assert "`metric_value` >= 3" in result.sql
    assert result.validation.passed is True


def test_same_scope_temporal_arithmetic_renders_inside_source_row_predicate():
    result = render_doris(
        _physical(
            "indicator('', '', '成交量', '最近10日', '', '', 'CONS=3日') / "
            "indicator('', '', '成交额', '最近10日', '', '', '') > 0"
        ),
        default_physical_catalog(),
    )

    assert "(`q`.`volume` / `q`.`turnover`) > 0" in result.sql
    assert result.sql.count("`hsj_stock_hq_basic`") == 3
    assert result.validation.passed is True


def test_recent_calendar_temporal_window_uses_latest_data_anchor_and_date_sub():
    result = render_doris(
        _physical("indicator('', '', '成交量', '两年内', '', '', 'EXIST>0') > 100"),
        default_physical_catalog(),
    )

    assert "DATE_SUB" in result.sql
    assert "INTERVAL '1' YEAR" in result.sql
    assert "DATE_TRUNC" in result.sql
    assert result.sql.count("MAX(`calendar_anchor`.`bizdate`)") == 2
    assert result.validation.passed is True


def test_temporal_and_branches_render_as_set_intersection_with_isolated_ctes():
    result = render_doris(
        _physical(
            "indicator('', '', '成交量', '最近5日', '', '', 'EXIST>0') > 100 and "
            "indicator('', '', '成交额', '最近10日', '', '', 'CONS=3日') > 0"
        ),
        default_physical_catalog(),
    )

    parsed = sqlglot.parse_one(result.sql, read="doris")
    assert len(list(parsed.find_all(exp.Intersect))) == 1
    assert "left_source_rows" in result.sql
    assert "right_source_rows" in result.sql
    assert result.validation.passed is True


def test_temporal_or_branches_render_as_distinct_union_across_resources():
    result = render_doris(
        _physical(
            "indicator('', '', '成交量', '最近5日', '', '', 'EXIST>0') > 100 or "
            "indicator('', '', '主力净流入', '最近5日', '', '', 'EXIST>0') > 0"
        ),
        default_physical_catalog(),
    )

    parsed = sqlglot.parse_one(result.sql, read="doris")
    assert len(list(parsed.find_all(exp.Union))) == 1
    assert {table.name for table in parsed.find_all(exp.Table)} >= {
        "hsj_stock_hq_basic",
        "hsj_stock_hq_ext",
    }
    assert result.validation.passed is True


def test_nested_temporal_or_chain_has_unique_cte_names_and_two_unions():
    result = render_doris(
        _physical(
            "indicator('', '', '成交量', '最近10日', '', '', 'EXIST=1') > 100 or "
            "indicator('', '', '成交量', '最近10日', '', '', 'EXIST=2') > 100 or "
            "indicator('', '', '成交量', '最近10日', '', '', 'EXIST=3') > 100"
        ),
        default_physical_catalog(),
        default_physical_expressions(default_physical_catalog()),
    )

    parsed = sqlglot.parse_one(result.sql, read="doris")
    cte_names = [cte.alias_or_name for cte in parsed.find_all(exp.CTE)]
    assert len(list(parsed.find_all(exp.Union))) == 2
    assert len(cte_names) == len(set(cte_names))
    assert result.validation.passed is True


@pytest.mark.parametrize(
    "count_exp,granularity,ordinal_signal",
    [
        ("CONS=每年", "YEAR", "YEAR("),
        ("EXIST>=2月", "MONTH", "MONTH("),
        ("CONS=3季度", "QUARTER", "QUARTER("),
        ("CONS=每周", "WEEK", "UNIX_TIMESTAMP("),
    ],
)
def test_calendar_bucket_temporal_sql_uses_date_trunc_and_gap_aware_ordinal(
    count_exp, granularity, ordinal_signal
):
    result = render_doris(
        _physical(
            f"indicator('', '', '成交量', '两年内', '', '', '{count_exp}') > 100"
        ),
        default_physical_catalog(),
    )

    assert f"DATE_TRUNC(`source_rows`.`bizdate`, '{granularity}')" in result.sql
    assert "bucket_rows" in result.sql
    assert ordinal_signal in result.sql
    assert "DATEDIFF" not in result.sql.upper()
    assert result.validation.passed is True


def test_every_calendar_bucket_requires_non_empty_gap_free_bucket_span():
    result = render_doris(
        _physical("indicator('', '', '成交量', '两年内', '', '', 'CONS=每年') > 100"),
        default_physical_catalog(),
    )

    assert "MAX(`bucket_rows`.`bucket_ordinal`)" in result.sql
    assert "MIN(`bucket_rows`.`bucket_ordinal`)" in result.sql
    assert "`temporal_metrics`.`total_buckets` > 0" in result.sql
    assert "`temporal_metrics`.`metric_value` = `temporal_metrics`.`total_buckets`" in result.sql

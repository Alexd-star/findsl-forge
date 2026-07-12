import sqlglot
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


def test_latest_date_and_market_constraints_render_as_sqlglot_ast():
    result = render_doris(
        _physical("indicator('沪|深', '', '成交量', '今日', '', '', '') > 100"),
        default_physical_catalog(),
    )

    parsed = sqlglot.parse_one(result.sql, read="doris")
    assert len(list(parsed.find_all(exp.Max))) == 1
    assert "`q`.`mktcode` IN (0, 1)" in result.sql
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
    assert "`q`.`volume` DESC, `q`.`tgtcode` ASC" in result.sql
    outer_order = parsed.args.get("order")
    assert outer_order is None
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

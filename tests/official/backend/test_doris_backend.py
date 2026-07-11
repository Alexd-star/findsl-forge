import sqlglot
from sqlglot import exp

from findsl.official.backend.doris import render_doris
from findsl.official.lowering import lower_official_ast
from findsl.official.physical.catalog import default_physical_catalog
from findsl.official.physical import PhysicalColumn, PhysicalComparison, PhysicalFilter, PhysicalLiteral, PhysicalScan
from findsl.official.physical.planner import plan_physical
from findsl.official.registry import default_official_registry
from findsl.official.semantics import OfficialSemanticAnalyzer
from findsl.official_slot import _resolve_indicator_meta, parse_official_slot
from findsl.official.types import STRING


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

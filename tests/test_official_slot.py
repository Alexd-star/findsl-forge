from __future__ import annotations

import subprocess
import sys
import os

import pytest

from findsl.official_slot import (
    OfficialSlotCompiler,
    OfficialSlotError,
    OfficialSlotParser,
    classify_official_indicator_domain,
    compile_training_workbook,
    parse_official_slot,
    parse_official_slot_with_diagnostics,
    profile_training_workbook,
    write_coverage_report,
)

OFFICIAL_WORKBOOK = (
    r"D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统"
    r"\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统"
    r"\选股 DSL 规范文档\选股提槽实例.xlsx"
)


def test_parse_official_slot_supports_single_quotes_percent_and_word_logic():
    ast = parse_official_slot(
        "indicator('深', '', '最新价', '2026-04-14', '', '', '') > 5% "
        "and indicator('深', '', '涨停', '2026-04-14', '', '', '') = True"
    )

    payload = ast.to_dict()

    assert payload["type"] == "BinaryOp"
    assert payload["op"] == "and"
    assert payload["left"]["op"] == ">"
    assert payload["left"]["right"]["value"] == "5%"
    assert payload["right"]["right"]["value"] is True


def test_strict_parse_rejects_leading_boolean_operator():
    with pytest.raises(OfficialSlotError) as excinfo:
        parse_official_slot(
            "and indicator('', '', '涨停', '', '', '', '') = True",
            mode="strict",
        )

    assert excinfo.value.code == "OFFICIAL_PARSE_ERROR"


def test_recovery_parse_reports_leading_operator_repair():
    parsed = parse_official_slot_with_diagnostics(
        "and indicator('', '', '涨停', '', '', '', '') = True",
        mode="recovery",
    )

    assert parsed.repairs[0].code == "LEADING_BOOLEAN_OPERATOR"
    assert parsed.normalized_source.startswith("indicator(")


def test_strict_parse_preserves_source_verbatim():
    source = "  indicator('', '', '涨停', '', '', '', '') = True  "

    parsed = parse_official_slot_with_diagnostics(source, mode="strict")

    assert parsed.source == source
    assert parsed.normalized_source == source
    assert parsed.repairs == ()


def test_direct_parser_keeps_legacy_recovery_normalization():
    ast = OfficialSlotParser(
        "and indicator('', '', '涨停', '', '', '', '') = True"
    ).parse()

    assert ast.to_dict()["op"] == "="


def test_recovery_repairs_use_original_source_positions():
    source = "and indicator('', '', '涨停', '', '', '', '') = True)"

    parsed = parse_official_slot_with_diagnostics(source, mode="recovery")

    positions = {repair.code: repair.position for repair in parsed.repairs}
    assert positions == {
        "LEADING_BOOLEAN_OPERATOR": source.index("and"),
        "UNMATCHED_CLOSING_PAREN": source.rindex(")"),
    }


def test_recovery_reports_each_orphan_literal_repair():
    source = (
        "reset('', '', '', 20日均线'', '', '', '') = True and "
        "reset('', '', '', 30日均线'', '', '', '') = True"
    )

    parsed = parse_official_slot_with_diagnostics(source, mode="recovery")

    orphan_repairs = [
        repair for repair in parsed.repairs if repair.code == "ORPHAN_LITERAL_QUOTED"
    ]
    assert [repair.position for repair in orphan_repairs] == [
        source.index("20日均线"),
        source.index("30日均线"),
    ]


def test_recovery_reports_each_dangling_edge_quote():
    source = '"indicator(\'\', \'\', \'涨停\', \'\', \'\', \'\', \'\') = True\''

    parsed = parse_official_slot_with_diagnostics(source, mode="recovery")

    quote_repairs = [
        repair for repair in parsed.repairs if repair.code == "DANGLING_EDGE_QUOTE"
    ]
    assert [repair.position for repair in quote_repairs] == [len(source) - 1, 0]


@pytest.mark.parametrize("source", ["'涨停", "'123"])
def test_recovery_does_not_hide_unterminated_string_literals(source):
    with pytest.raises(OfficialSlotError) as excinfo:
        parse_official_slot_with_diagnostics(source, mode="recovery")

    assert excinfo.value.code == "OFFICIAL_LEX_ERROR"


def test_recovery_normalized_source_keeps_legacy_outer_whitespace_cleanup():
    source = "  indicator('', '', '涨停', '', '', '', '') = True  "

    parsed = parse_official_slot_with_diagnostics(source, mode="recovery")

    assert parsed.normalized_source == source.strip()


@pytest.mark.parametrize(
    "dirty_dsl",
    [
        "rank('', '', '现金储备率', 'desc', '', '', '', '') <= 20 and record_high('', '', '', '200天', '今日', '', '', '') = True and indicator('', '', '回调', '昨天', '', '', '') = True and indicator('', '', '十字星', 昨天'', '', '', 'EXIST>0') = True",
        "indicator('', '', '成分股', '', '', '', '') = '光伏ETF基金515790' and indicator('', '', '有息负债', '', '', '', '') between [500000000,700000000]'",
        "indicator('沪|深', '', '外盘', '昨天', '', '', '') != indicator('沪|深', '', '外盘', '昨天的前1日', '', '', '')\"",
        "indicator('', '人工智能', '成交量', '今天', '', 'GROWTH_RISE', '') = 400% and reset('', '人工智能', '', '20日均线', '今天', '', '') = True and indicator('', '人工智能', '十字星', '今天', '', '', '') = True then rank('', '人工智能', '营业收入同比增长率', 'desc', '今天', '', '', '') <= 10)",
        "rank('其他&法', '', '市盈率', 'desc', '', '', '', '') > 0\"",
        "and indicator('', '', '涨停未封板', '前天', '', '', '') = True",
        "\"indicator('', '', '涨幅', '', '', '', '') between '[3%,9%]' and indicator('', '', '成交量', '', '', '', '') >= indicator('', '', '成交量', '近5日', '', 'AVG', '') * 1.5 and indicator('', '', '大单净流入', '', '', '', '') >= 0.5% and indicator('', '', 'RSI(6)', '', '', '', '') < 20",
    ],
)
def test_parse_official_slot_tolerates_documented_workbook_punctuation_noise(dirty_dsl):
    ast = parse_official_slot(dirty_dsl)

    assert ast.to_dict()["type"] in {"BinaryOp", "Comparison"}


def test_compile_indicator_to_official_doris_sql_with_market_and_date_filters():
    result = OfficialSlotCompiler().compile(
        "indicator('深', '', '最新价', '2026-04-14', '', '', '') > 10.5"
    )

    assert "newzl.hsj_stock_hq_basic" in result.sql
    assert "(base.lastPx / 10000.0) > 10.5" in result.sql
    assert "base.mktcode IN (0)" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql
    assert result.requires_tables == ["hsj_stock_hq_basic"]


def test_compile_official_relative_date_to_anchor_filter_without_warning():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('沪', '', '成交量', '今天', '', '', '') > 1000"
    )

    assert "base.bizdate = '2026-04-14'" in result.sql
    assert result.warnings == []


def test_compile_official_recent_date_with_trading_calendar_window():
    compiler = OfficialSlotCompiler(
        anchor_date="2026-04-14",
        trading_dates=["2026-04-08", "2026-04-09", "2026-04-10", "2026-04-13", "2026-04-14"],
    )

    result = compiler.compile("indicator('', '', '成交量', '近3日', '', '', '') > 1000")

    assert "base.bizdate BETWEEN '2026-04-10' AND '2026-04-14'" in result.sql
    assert result.warnings == []


def test_compile_official_composite_date_slots_from_real_workbook():
    compiler = OfficialSlotCompiler(
        anchor_date="2026-04-14",
        trading_dates=["2026-04-09", "2026-04-10", "2026-04-13", "2026-04-14"],
    )

    recent_ordinal = compiler.compile("indicator('', '', '跌幅', '最近的第二天', '', '', '') >= 0")
    clipped_following = compiler.compile("indicator('', '', '跌幅', '最近的第二天的后3日', '', '', '') > 8")
    previous_week = compiler.compile("indicator('', '', '成交量', '本月的前一周', '', '', '') > 0")
    ordinal_year = compiler.compile("indicator('', '', '成交量', '2018年的第五年', '', '', '') > 0")
    impossible_future = compiler.compile("indicator('', '', '成交量', '本周的后3日', '', '', '') > 0")

    assert "base.bizdate = '2026-04-13'" in recent_ordinal.sql
    assert recent_ordinal.warnings == []
    assert "base.bizdate = '2026-04-14'" in clipped_following.sql
    assert clipped_following.warnings == [
        "date slot '最近的第二天的后3日' extends beyond official anchor date 2026-04-14; clipped to available official data"
    ]
    assert "base.bizdate BETWEEN '2026-03-25' AND '2026-03-31'" in previous_week.sql
    assert previous_week.warnings == []
    assert "base.bizdate BETWEEN '2022-01-01' AND '2022-12-31'" in ordinal_year.sql
    assert ordinal_year.warnings == []
    assert "1=0" in impossible_future.sql
    assert impossible_future.warnings == [
        "date slot '本周的后3日' starts after official anchor date 2026-04-14; no official rows can satisfy it"
    ]
    assert all("1=1" not in result.sql for result in [recent_ordinal, clipped_following, previous_week, ordinal_year])


def test_compile_official_year_range_date_slot_from_real_workbook():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '成交量', '2006年-12年', '', '', '') > 0"
    )

    assert "base.bizdate BETWEEN '2006-01-01' AND '2012-12-31'" in result.sql
    assert "1=1" not in result.sql
    assert result.warnings == []


def test_compile_official_numeric_scales_to_human_units():
    result = OfficialSlotCompiler().compile(
        "indicator('', '', '市净率', '今日', '', '', '') < 2 "
        "and indicator('', '', '涨幅', '今日', '', '', '') > 5%"
    )

    assert "(base.pBR / 10000.0) < 2" in result.sql
    assert "((base.lastPx - base.preClosePx) * 100.0 / NULLIF(base.preClosePx, 0)) > 5" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql


def test_compile_official_limit_count_aliases_from_real_workbook():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '涨停天数', '近10个交易日', '', '', '') <= 3 "
        "and indicator('', '', '连续涨停天数', '近10个交易日', '', '', '') >= 2 "
        "and rank('', '', '跌停天数', 'desc', '本周', '', '', '') <= 10"
    )

    assert "base.upCount <= 3" in result.sql
    assert "base.upSerialLb >= 2" in result.sql
    assert "ORDER BY rb.downCount DESC" in result.sql
    assert "UNSUPPORTED_OFFICIAL_INDICATOR" not in result.sql


def test_compile_official_lot_size_as_a_share_rule_constant():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '成交量', '今天', '', '', '') "
        "/ indicator('', '', '每手股数', '今天', '', '', '') > 1000"
    )

    assert "(base.volume / 100) > 1000" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql
    assert result.warnings == []


def test_compile_official_t0_flag_as_a_share_rule_constant_false():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '是否T+0', '今天', '', '', '') = True"
    )

    assert "WHERE FALSE AND base.bizdate = '2026-04-14'" in result.sql
    assert result.warnings == []


def test_compile_official_hk_connect_aliases_from_real_workbook():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '沪港通标识', '今天', '', '', '') = True "
        "and indicator('', '', '深港通标识', '今天', '', '', '') = False"
    )

    assert "code.shConnFlag = TRUE" in result.sql
    assert "NOT (code.szConnFlag = TRUE)" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql


def test_compile_official_order_book_and_ma_aliases_from_real_workbook():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '委比', '今天', '', '', '') > 10 "
        "and rank('', '', '委比', 'desc', '今天', '', '', '') <= 5 "
        "and indicator('', '', '买方未匹配量', '今天', '', '', '') > 100 "
        "and indicator('', '', '卖方未匹配量', '今天', '', '', '') < 50 "
        "and indicator('', '', '一周均线', '今天', '', '', '') > 10 "
        "and indicator('', '', '一个月均线', '今天', '', '', '') > 10 "
        "and indicator('', '', '一个季度均线', '今天', '', '', '') > 10"
    )

    assert "((base.commissionBuy - base.commissionSale) * 100.0 / NULLIF(base.commissionBuy + base.commissionSale, 0)) > 10" in result.sql
    assert "ORDER BY ((rb.commissionBuy - rb.commissionSale) * 100.0 / NULLIF(rb.commissionBuy + rb.commissionSale, 0)) DESC" in result.sql
    assert "ext.callAucBid2Vol > 100" in result.sql
    assert "ext.callAucAsk2Vol < 50" in result.sql
    assert "tech.ma5 > 10" in result.sql
    assert "tech.ma20 > 10" in result.sql
    assert "tech.ma60 > 10" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql


def test_compile_official_extended_ma_and_volume_average_aliases_from_real_workbook():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '3日均线', '今天', '', '', '') > 10 "
        "and indicator('', '', '30日均线', '今天', '', '', '') > 10 "
        "and indicator('', '', '120日均线', '今天', '', '', '') > 10 "
        "and indicator('', '', '200日均线', '今天', '', '', '') > 10 "
        "and indicator('', '', '250日均线', '今天', '', '', '') > 10 "
        "and indicator('', '', '半年均线', '今天', '', '', '') > 10 "
        "and indicator('', '', '一年均线', '今天', '', '', '') > 10 "
        "and indicator('', '', '5日均量线', '今天', '', '', '') > 1000 "
        "and indicator('', '', '10日均量线', '今天', '', '', '') > 1000 "
        "and indicator('', '', '30日均量线', '今天', '', '', '') > 1000 "
        "and indicator('', '', '一个季度均量线', '今天', '', '', '') > 1000"
    )

    assert "tech.ma3 > 10" in result.sql
    assert "tech.ma30 > 10" in result.sql
    assert "tech.ma120 > 10" in result.sql
    assert "tech.ma200 > 10" in result.sql
    assert "tech.ma250 > 10" in result.sql
    assert result.sql.count("tech.ma120 > 10") == 2
    assert result.sql.count("tech.ma250 > 10") == 2
    assert "tech.volume_avg_5 > 1000" in result.sql
    assert "tech.volume_avg_10 > 1000" in result.sql
    assert "tech.volume_avg_30 > 1000" in result.sql
    assert "tech.volume_avg_60 > 1000" in result.sql
    assert "hsj_stock_hq_basic_technical" in result.requires_tables


def test_compile_dynamic_daily_ma_uses_official_prefix_table():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '7日均线', '今天', '', '', '') > 10"
    )

    assert "newzl.hsj_stock_hq_basic_prefix AS p" in result.sql
    assert "p_prev.row_no = p.row_no - 7" in result.sql
    assert "p.close_prefix" in result.sql
    assert "p.close_count_prefix" in result.sql
    assert "/ 10000.0" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql
    assert "hsj_stock_hq_basic_prefix" in result.requires_tables


def test_compile_dynamic_daily_volume_average_uses_official_prefix_table():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '8日均量线', '今天', '', '', '') > 1000"
    )

    assert "newzl.hsj_stock_hq_basic_prefix AS p" in result.sql
    assert "p_prev.row_no = p.row_no - 8" in result.sql
    assert "p.volume_prefix" in result.sql
    assert "p.volume_count_prefix" in result.sql
    assert "hsj_stock_hq_basic_prefix" in result.requires_tables


def test_dynamic_prefix_indicators_work_inside_pattern_and_cross_functions():
    reset_result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "reset('', '', '最新价', '25日均线', '今天', '', '') = True"
    )
    cross_result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "cross_above('', '', '13日均线', '55日均线', '今天', '', '') = True"
    )

    assert "p_prev.row_no = p.row_no - 25" in reset_result.sql
    assert "p_prev.row_no = p.row_no - 13" in cross_result.sql
    assert "p_prev.row_no = p.row_no - 55" in cross_result.sql
    assert "hsj_stock_hq_basic_prefix" in reset_result.requires_tables
    assert "hsj_stock_hq_basic_prefix" in cross_result.requires_tables


def test_weekly_and_monthly_moving_averages_remain_explicitly_unsupported():
    with pytest.raises(OfficialSlotError) as excinfo:
        OfficialSlotCompiler().compile("indicator('', '', '5周均线', '', '', '', '') > 0")

    assert excinfo.value.code == "UNSUPPORTED_OFFICIAL_INDICATOR"


def test_rank_function_can_be_used_inside_arithmetic_expression():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "rank('', '', '涨停天数', 'desc', '本周', '', '', '') "
        "+ rank('', '', '跌停天数', 'desc', '本周', '', '', '') > 0"
    )

    assert "SELECT ranked.rank_no" in result.sql
    assert "ROW_NUMBER() OVER" in result.sql
    assert "ORDER BY rb.upCount DESC" in result.sql
    assert "ORDER BY rb.downCount DESC" in result.sql
    assert "ranked.mktcode = base.mktcode" in result.sql


def test_rank_expression_supports_division_with_ext_indicators():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "rank('', '', '主力净流入', 'desc', '今天', '', '', '') "
        "/ rank('', '', '主力净流出', 'desc', '今天', '', '', '') <= 3"
    )

    assert "ORDER BY rext.ZJLXMainNetTur DESC" in result.sql
    assert "ORDER BY (-rext.ZJLXMainNetTur) DESC" in result.sql
    assert "newzl.hsj_stock_hq_ext AS rext" in result.sql


def test_rank_approximate_operator_falls_back_to_scalar_rank_expression():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "rank('', '', '跌幅', 'desc', '四月二十号', '', 'AVG', '') ~= 10"
    )

    assert "SELECT ranked.rank_no" in result.sql
    assert "= 10" in result.sql


def test_compile_official_board_break_order_diff_and_drawdown_aliases_from_real_workbook():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '委差', '今天', '', '', '') > 0 "
        "and rank('', '', '委差', 'desc', '今天', '', '', '') <= 20 "
        "and indicator('', '', '涨停炸板', '今天', '', '', '') = True "
        "and indicator('', '', '涨停未封板', '今天', '', '', '') = True "
        "and indicator('', '', '历史最大跌幅', '今天', '', '', '') > 5 "
        "and indicator('', '', '大单卖出金额', '今天', '', '', '') > 1000000 "
        "and indicator('', '', '大单买入金额', '今天', '', '', '') > 1000000"
    )

    assert "(base.commissionBuy - base.commissionSale) > 0" in result.sql
    assert "ORDER BY (rb.commissionBuy - rb.commissionSale) DESC" in result.sql
    assert "COALESCE(ext.lmtUpNum, 0) > 0" in result.sql
    assert "COALESCE(ext.boardBreaks, 0) > 0" in result.sql
    assert "base.limitFlag != 1" in result.sql
    assert "(ext.maxRetreat / 10000.0) > 5" in result.sql
    assert "ext.bigSellTur > 1000000" in result.sql
    assert "ext.bigBuyTur > 1000000" in result.sql
    assert "hsj_stock_hq_ext" in result.requires_tables


def test_compile_official_string_percent_wildcard_uses_like_without_breaking_numeric_percent():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '股票名称', '', '', '', '') = '%科技%' "
        "and indicator('', '', '涨幅', '今天', '', '', '') > 5%"
    )

    assert "code.name LIKE '%科技%'" in result.sql
    assert "code.name = %科技" not in result.sql
    assert "((base.lastPx - base.preClosePx) * 100.0 / NULLIF(base.preClosePx, 0)) > 5" in result.sql


def test_compile_official_price_like_auxiliary_fields_to_human_units():
    result = OfficialSlotCompiler().compile(
        "indicator('', '', '每股净资产', '今日', '', '', '') > 5 "
        "and indicator('', '', '集合竞价匹配价', '今日', '', '', '') > 10 "
        "and indicator('', '', '涨停封单价', '今日', '', '', '') > 10"
    )

    assert "(base.bVPS / 10000.0) > 5" in result.sql
    assert "(ext.callAucMatchPx / 10000.0) > 10" in result.sql
    assert "(base.upSealPx / 10000.0) > 10" in result.sql


def test_compile_or_keeps_branch_specific_date_constraints_inside_each_branch():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('创业板', '', '开盘价', '20年', '', '', '') > 50 "
        "or indicator('创业板', '', '开盘价', '近三年', '', '', '') ~= 92"
    )

    first_branch = (
        "((base.openPx / 10000.0) > 50 AND code.gemFlag = TRUE "
        "AND base.bizdate BETWEEN '2020-01-01' AND '2020-12-31')"
    )
    second_branch = (
        "((base.openPx / 10000.0) = 92 AND code.gemFlag = TRUE "
        "AND base.bizdate BETWEEN '2024-01-01' AND '2026-04-14')"
    )

    assert f"({first_branch} OR {second_branch})" in result.sql
    assert "AND base.bizdate BETWEEN '2020-01-01' AND '2020-12-31' AND base.bizdate BETWEEN '2024-01-01' AND '2026-04-14'" not in result.sql


def test_compile_and_with_different_date_slots_uses_correlated_exists_per_branch():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '流通股本', '零三年', '', '', '') > 3005200 "
        "and indicator('', '', '跌停', '零四年', '', '', '') = True"
    )

    assert result.sql.count("EXISTS (") == 2
    assert "lb.bizdate BETWEEN '2003-01-01' AND '2003-12-31'" in result.sql
    assert "lb.bizdate BETWEEN '2004-01-01' AND '2004-12-31'" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql
    assert "base.bizdate BETWEEN '2003-01-01' AND '2003-12-31' AND base.bizdate BETWEEN '2004-01-01' AND '2004-12-31'" not in result.sql


def test_compile_official_generated_market_value_indicators_from_real_columns():
    result = OfficialSlotCompiler().compile(
        "indicator('', '', '总市值', '', '', '', '') > 10000000000 "
        "and indicator('', '', '流通市值', '', '', '', '') > 5000000000"
    )

    assert "((base.lastPx / 10000.0) * base.totalShare) > 10000000000" in result.sql
    assert "((base.lastPx / 10000.0) * base.listedShare) > 5000000000" in result.sql


def test_compile_belong_industry_uses_code_table_industry_aggregate():
    result = OfficialSlotCompiler().compile(
        "indicator('', '', '市盈率', '', '', '', '') < belong_industry('', '', '市盈率', '', 'AVG')"
    )

    assert "SELECT AVG((wb.pETTM / 10000.0))" in result.sql
    assert "wc.hyBlkRefName = code.hyBlkRefName" in result.sql
    assert "wc.hyBlkRefName IS NOT NULL" in result.sql
    assert "LEFT JOIN newzl.hsj_stock_code_info AS wc" in result.sql


def test_compile_official_technical_indicators_from_feature_table():
    result = OfficialSlotCompiler().compile(
        "indicator('', '', '5日均线', '今天', '', '', '') > 10 "
        "and indicator('', '', '放量', '今天', '', '', '') = True "
        "and indicator('', '', '均线多头排列', '今天', '', '', '') = True "
        "and indicator('', '', '十字星', '今天', '', '', '') = False"
    )

    assert "newzl.hsj_stock_hq_basic_technical AS tech" in result.sql
    assert "tech.ma5 > 10" in result.sql
    assert "tech.volume_breakout = TRUE" in result.sql
    assert "tech.ma_bullish = TRUE" in result.sql
    assert "NOT (tech.doji = TRUE)" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql
    assert "hsj_stock_hq_basic_technical" in result.requires_tables


def test_compile_close_together_default_price_to_ma_uses_configured_relative_threshold():
    result = OfficialSlotCompiler().compile(
        "close_together('', '', '', '20日均线', '今天', '', '') = True"
    )

    assert "ABS((base.lastPx / 10000.0) - tech.ma20)" in result.sql
    assert "0.03" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql
    assert "hsj_stock_hq_basic_technical" in result.requires_tables


def test_compile_reset_default_price_to_support_line_uses_near_line_threshold():
    result = OfficialSlotCompiler().compile(
        "reset('', '', '', '支撑位', '今天', '', '') = True"
    )

    assert "ABS((base.lastPx / 10000.0) - (base.support / 10000.0))" in result.sql
    assert "0.02" in result.sql
    assert "0.005" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql


def test_compile_reset_false_negates_grounded_pattern_expression():
    result = OfficialSlotCompiler().compile(
        "reset('', '', '最新价', '10日均线', '今天', '', '') = False"
    )

    assert "NOT (" in result.sql
    assert "tech.ma10" in result.sql


def test_compile_close_together_count_exp_uses_window_count():
    result = OfficialSlotCompiler(
        trading_dates=["2026-04-08", "2026-04-09", "2026-04-10", "2026-04-13", "2026-04-14"]
    ).compile("close_together('', '', '', '5日均线', '近5日', '', 'CONS=5日') = True")

    assert "SELECT COUNT(*)" in result.sql
    assert "SUM(CASE WHEN" in result.sql
    assert "ABS((wb.lastPx / 10000.0) - wt.ma5)" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql


def test_close_together_missing_indicator_stays_diagnostic_not_fake_sql():
    with pytest.raises(OfficialSlotError) as exc:
        OfficialSlotCompiler().compile(
            "close_together('', '', 'K值', 'D值', '近五天', '', '') = True"
        )

    assert exc.value.code == "UNSUPPORTED_OFFICIAL_INDICATOR"


def test_compile_record_high_low_uses_official_ext_days_without_window_predicate():
    result = OfficialSlotCompiler().compile(
        "record_high('', '', '', '120日', '今天', '', '', '') = True "
        "and record_low('', '', '', '60日', '今天', '', '', '') = False"
    )

    assert "ext.pxMkTopDays >= 120" in result.sql
    assert "NOT (ext.pxMkBotDays >= 60)" in result.sql
    assert "OVER (" not in result.sql
    assert "newzl.hsj_stock_hq_ext AS ext" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql


def test_compile_position_generates_grounded_case_expression_for_price_window():
    result = OfficialSlotCompiler().compile(
        "position('', '', '最新价', '10日', '今天', '', '', '') = '低'"
    )

    assert "CASE" in result.sql
    assert "MIN((wb.lastPx / 10000.0))" in result.sql
    assert "MAX((wb.lastPx / 10000.0))" in result.sql
    assert "DATE_SUB(base.bizdate, INTERVAL 9 DAY)" in result.sql
    assert "= '低'" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql


def test_compile_position_count_exp_window_predicate():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "position('', '', '最新价', '10日', '近5日', '', '', 'CONS=3日') = '低'"
    )

    assert "CASE" in result.sql
    assert "MAX(run_length) >= 3" in result.sql
    assert "= '低'" in result.sql
    assert "wb.bizdate BETWEEN '2026-04-10' AND '2026-04-14'" in result.sql


def test_compile_record_high_count_exp_window_predicate():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "record_high('', '', '最高价', '120日', '近5日', '', '', 'EXIST>=2日') = True"
    )

    assert "we.pxMkTopDays >= 120" in result.sql
    assert ") >= 2" in result.sql
    assert "wb.bizdate BETWEEN '2026-04-10' AND '2026-04-14'" in result.sql


def test_compile_official_time_and_order_flow_indicators_from_real_columns():
    result = OfficialSlotCompiler().compile(
        "indicator('', '', '涨停时间', '', '', '', '') < '10:00:00' "
        "and indicator('', '', '外盘', '', '', '', '') > 1000 "
        "and indicator('', '', '主力成交量占比', '', '', '', '') > 5"
    )

    assert "base.firstLimitUpTime < '10:00:00'" in result.sql
    assert "base.outerVol > 1000" in result.sql
    assert "(ext.ZJLXMainTradeVolPer / 10000.0) > 5" in result.sql


def test_compile_official_avg_volume_window_uses_correlated_aggregate():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '成交量', '近5日', '', 'AVG', '') > 1000"
    )

    assert "SELECT AVG(wb.volume)" in result.sql
    assert "FROM newzl.hsj_stock_hq_basic AS wb" in result.sql
    assert "wb.mktcode = base.mktcode" in result.sql
    assert "wb.tgtcode = base.tgtcode" in result.sql
    assert "wb.bizdate BETWEEN '2026-04-10' AND '2026-04-14'" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql


def test_compile_official_sum_main_net_inflow_window_joins_ext_table():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '主力净流入', '近5日', '', 'SUM', '') > 50000000"
    )

    assert "SELECT SUM(we.ZJLXMainNetTur)" in result.sql
    assert "FROM newzl.hsj_stock_hq_basic AS wb" in result.sql
    assert "LEFT JOIN newzl.hsj_stock_hq_ext AS we" in result.sql
    assert "we.bizdate = wb.bizdate" in result.sql
    assert "wb.bizdate BETWEEN '2026-04-10' AND '2026-04-14'" in result.sql


def test_compile_official_min_max_price_windows_scale_to_human_units():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '最高价', '近5日', '', 'MAX', '') > 20 "
        "and indicator('', '', '最低价', '近5日', '', 'MIN', '') < 10"
    )

    assert "SELECT MAX((wb.highPx / 10000.0))" in result.sql
    assert "SELECT MIN((wb.lowPx / 10000.0))" in result.sql
    assert result.sql.count("wb.bizdate BETWEEN '2026-04-10' AND '2026-04-14'") == 2


def test_compile_official_growth_rate_window_uses_min_by_and_max_by():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '成交量', '近5日', '', 'GROWTH_RISE', '') > 60% "
        "and indicator('', '', '成交量', '近5日', '', 'GROWTH_FALL', '') > 20%"
    )

    assert "MAX_BY(wb.volume, wb.bizdate)" in result.sql
    assert "MIN_BY(wb.volume, wb.bizdate)" in result.sql
    assert "(MAX_BY(wb.volume, wb.bizdate) - MIN_BY(wb.volume, wb.bizdate))" in result.sql
    assert "(MIN_BY(wb.volume, wb.bizdate) - MAX_BY(wb.volume, wb.bizdate))" in result.sql
    assert result.sql.count("wb.bizdate BETWEEN '2026-04-10' AND '2026-04-14'") == 2


def test_compile_official_exist_rise_pct_count_window():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '涨幅', '近5日', '', '', 'EXIST>=3日') > 5%"
    )

    assert "SELECT COUNT(*)" in result.sql
    assert "FROM newzl.hsj_stock_hq_basic AS wb" in result.sql
    assert "((wb.lastPx - wb.preClosePx) * 100.0 / NULLIF(wb.preClosePx, 0)) > 5" in result.sql
    assert "wb.bizdate BETWEEN '2026-04-10' AND '2026-04-14'" in result.sql
    assert ") >= 3" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql


def test_compile_official_cons_everyday_volume_count_window():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '成交量', '近5日', '', '', 'CONS=每日') > 1000"
    )

    assert "SELECT COUNT(*)" in result.sql
    assert "SUM(CASE WHEN wb.volume > 1000 THEN 1 ELSE 0 END) = COUNT(*)" in result.sql
    assert "wb.bizdate BETWEEN '2026-04-10' AND '2026-04-14'" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql


def test_compile_official_count_exp_between_window():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '换手率', '近5日', '', '', 'EXIST>=3日') between '[9%,18%]'"
    )

    assert "SELECT COUNT(*)" in result.sql
    assert "(wb.turnRatio / 10000.0) >= 9" in result.sql
    assert "(wb.turnRatio / 10000.0) <= 18" in result.sql
    assert "wb.bizdate BETWEEN '2026-04-10' AND '2026-04-14'" in result.sql
    assert ") >= 3" in result.sql


def test_compile_count_exp_inside_arithmetic_expression_uses_window_predicate():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('沪', '', '内盘', '近5周', '', '', 'EXIST>6日') "
        "/ indicator('沪', '', '每手股数', '近5周', '', '', 'EXIST>6日') > 2000"
    )

    assert "FROM newzl.hsj_stock_hq_basic AS wb" in result.sql
    assert "(wb.innerVol / 100) > 2000" in result.sql
    assert ") > 6" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql


def test_compile_count_exp_expression_supports_indicator_to_indicator_comparison():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '收盘价', '近三十天', '', '', 'CONS=4日') "
        ">= indicator('', '', '5日均线', '近三十天', '', '', 'CONS=4日')"
    )

    assert "(wb.closePx / 10000.0) >= wt.ma5" in result.sql
    assert "MAX(run_length) >= 4" in result.sql
    assert "wb.bizdate BETWEEN '2026-03-16' AND '2026-04-14'" in result.sql


def test_compile_official_aggregate_count_exp_uses_bucketed_aggregate():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '成交量', '近5日', '', 'AVG', 'EXIST>=3日') > 1000"
    )

    assert "DATE_TRUNC(wb.bizdate, 'day') AS bucket_key" in result.sql
    assert "AVG(wb.volume) AS agg_value" in result.sql
    assert "GROUP BY DATE_TRUNC(wb.bizdate, 'day')" in result.sql
    assert "bucketed.agg_value > 1000" in result.sql
    assert ") >= 3" in result.sql


def test_compile_aggregate_count_exp_inside_arithmetic_expression_uses_bucket_rows():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '外盘', '近3日', '', 'AVG', 'CONS=每日') "
        "/ indicator('', '', '每手股数', '近3日', '', '', '') < 80000"
    )

    assert "DATE_TRUNC(wb.bizdate, 'day') AS bucket_key" in result.sql
    assert "AVG(wb.outerVol) AS agg_0" in result.sql
    assert "MAX(100) AS value_0" in result.sql
    assert "(bucketed.agg_0 / bucketed.value_0) < 80000" in result.sql
    assert "SUM(CASE WHEN (bucketed.agg_0 / bucketed.value_0) < 80000 THEN 1 ELSE 0 END) = COUNT(*)" in result.sql
    assert "wb.bizdate BETWEEN '2026-04-12' AND '2026-04-14'" in result.sql


def test_compile_count_exp_range_exist_uses_bounded_match_count():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '涨停', '过去20天', '', '', 'EXIST=2-5') = True"
    )

    assert "COUNT(*)" in result.sql
    assert "BETWEEN 2 AND 5" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql
    assert result.warnings == []


def test_compile_daily_cons_count_exp_range_uses_bounded_run_length():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '阳线', '近10日', '', '', 'CONS=3-4日') = True"
    )

    assert "MAX(run_length) BETWEEN 3 AND 4" in result.sql
    assert "DATEDIFF(matched.bizdate, '1970-01-01')" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql
    assert result.warnings == []


def test_compile_half_year_aggregate_count_exp_normalizes_to_month_buckets():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('沪主板', '', '涨跌幅', '', '', 'SUM', 'CONS=0.5年') > 3.5%"
    )

    assert "DATE_TRUNC(wb.bizdate, 'month')" in result.sql
    assert "SUM(((wb.lastPx - wb.preClosePx) * 100.0 / NULLIF(wb.preClosePx, 0))) AS agg_value" in result.sql
    assert ">= 6" in result.sql
    assert "base.mktcode IN (1)" in result.sql


def test_compile_official_daily_growth_count_exp_uses_lag_pairs():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '成交量', '近5日', '', 'GROWTH_FALL', 'CONS=每日') > 0"
    )

    assert "LAG(wb.volume) OVER" in result.sql
    assert "((LAG(wb.volume) OVER" in result.sql
    assert "- wb.volume) * 100.0" in result.sql
    assert "bucketed.agg_value IS NOT NULL" in result.sql
    assert "SUM(CASE WHEN bucketed.agg_value > 0 THEN 1 ELSE 0 END) = COUNT(*)" in result.sql


def test_compile_cons_count_exp_uses_longest_run_not_plain_count():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '涨幅', '近5日', '', '', 'CONS=3日') > 5%"
    )

    assert "ROW_NUMBER() OVER (ORDER BY matched.bizdate)" in result.sql
    assert "DATEDIFF(matched.bizdate" in result.sql
    assert "MAX(run_length) >= 3" in result.sql


def test_compile_rank_then_pipeline_for_official_slot_dsl():
    result = OfficialSlotCompiler().compile(
        "indicator('沪', '', '涨停', '2026-04-14', '', '', '') = True "
        "then rank('沪', '', '成交量', 'desc', '2026-04-14', '', '', '') <= 10"
    )

    assert "ROW_NUMBER() OVER" in result.sql
    assert "ORDER BY base.volume DESC" in result.sql
    assert "rank_no <= 10" in result.sql
    assert "base.limitFlag = 1" in result.sql


def test_compile_chained_then_rank_pipeline_uses_cte_stages():
    result = OfficialSlotCompiler().compile(
        "indicator('', '', '涨停', '今天', '', '', '') = True "
        "then rank('', '', '成交量', 'desc', '今天', '', '', '') <= 50 "
        "then rank('', '', '主力净流入', 'desc', '今天', '', '', '') <= 10"
    )

    assert "WITH stage_0 AS" in result.sql
    assert "stage_1 AS" in result.sql
    assert "stage_2 AS" in result.sql
    assert "base.limitFlag = 1" in result.sql
    assert "ORDER BY base.volume DESC" in result.sql
    assert "ORDER BY ext.ZJLXMainNetTur DESC" in result.sql
    assert "ranked_1.rank_no <= 50" in result.sql
    assert "ranked_2.rank_no <= 10" in result.sql
    assert result.requires_tables == ["hsj_stock_hq_basic", "hsj_stock_code_info", "hsj_stock_hq_ext"]


def test_compile_then_rank_between_uses_scoped_rank_stage():
    result = OfficialSlotCompiler().compile(
        "indicator('', '', '最新价', '', '', '', '') < 100 "
        "then rank('', '', '最新价', 'desc', '', '', '', '') between '[5,10]'"
    )

    assert "WITH stage_0 AS" in result.sql
    assert "stage_1 AS" in result.sql
    assert "FROM stage_0 AS prev" in result.sql
    assert "ROW_NUMBER() OVER" in result.sql
    assert "ranked.rank_no >= 5" in result.sql
    assert "ranked.rank_no <= 10" in result.sql


def test_compile_then_rank_and_plain_filter_stays_inside_prefiltered_stage():
    result = OfficialSlotCompiler().compile(
        "indicator('沪', '', '涨停', '8号', '', '', '') = True "
        "then rank('沪', '', '总市值', 'desc', '8号', '', '', '') = 3 "
        "and indicator('沪', '', 'ST股票标识', '8号', '', '', '') = False"
    )

    assert "WITH stage_0 AS" in result.sql
    assert "stage_1 AS" in result.sql
    assert "FROM stage_0 AS prev" in result.sql
    assert "ranked.rank_no = 3" in result.sql
    assert "NOT (code.stFlag = TRUE)" in result.sql
    assert "base.mktcode IN (1)" in result.sql


def test_compile_then_grouped_rank_or_conditions_share_prefiltered_stage():
    result = OfficialSlotCompiler().compile(
        "indicator('沪主板|深主板', '', '开盘价', '', '', '', '') < 2 "
        "then (rank('沪主板|深主板', '', '开盘价', 'asc', '', '', '', '') <= 20 "
        "or rank('沪主板|深主板', '', '开盘价', 'desc', '', '', '', '') <= 20)"
    )

    assert "WITH stage_0 AS" in result.sql
    assert "stage_1 AS" in result.sql
    assert "FROM stage_0 AS prev" in result.sql
    assert result.sql.count("ROW_NUMBER() OVER") == 2
    assert "ORDER BY (rb.openPx / 10000.0) ASC" in result.sql
    assert "ORDER BY (rb.openPx / 10000.0) DESC" in result.sql
    assert " OR " in result.sql


def test_compile_or_of_independent_then_rank_branches_uses_union():
    result = OfficialSlotCompiler().compile(
        "(indicator('', '', '港股通标识', '', '', '', '') = True "
        "then rank('', '', '主力净流入', 'desc', '', '', '', '') = 1) "
        "or (indicator('', '', '陆股通标识', '', '', '', '') = True "
        "then rank('', '', '主力净流入', 'desc', '', '', '', '') = 1)"
    )

    assert "\nUNION\n" in result.sql
    assert result.sql.count("ROW_NUMBER() OVER") == 2
    assert "code.hkConnFlag = TRUE" in result.sql
    assert "ORDER BY ext.ZJLXMainNetTur DESC" in result.sql
    assert result.requires_tables == ["hsj_stock_hq_basic", "hsj_stock_code_info", "hsj_stock_hq_ext"]


def test_compile_then_branch_inside_and_as_membership_condition():
    result = OfficialSlotCompiler().compile(
        "(indicator('', '', '港股通标识', '', '', '', '') = True "
        "then rank('', '', '主力净流入', 'desc', '', '', '', '') = 1) "
        "and indicator('', '', 'ST股票标识', '', '', '', '') = False"
    )

    assert "EXISTS (" in result.sql
    assert "then_result.mktcode = base.mktcode" in result.sql
    assert "then_result.tgtcode = base.tgtcode" in result.sql
    assert "ROW_NUMBER() OVER" in result.sql
    assert "code.hkConnFlag = TRUE" in result.sql
    assert "NOT (code.stFlag = TRUE)" in result.sql


def test_compile_rank_comparison_inside_boolean_pipeline():
    result = OfficialSlotCompiler().compile(
        "rank('', '', '市净率', 'desc', '', '', '', '') <= 10 "
        "and indicator('', '', '涨停', '', '', '', '') = True"
    )

    assert "EXISTS (" in result.sql
    assert "ROW_NUMBER() OVER" in result.sql
    assert "ranked.rank_no <= 10" in result.sql
    assert "base.limitFlag = 1" in result.sql


def test_compile_rank_between_top_level_condition():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "rank('', '', '收盘价', 'desc', '今天', '', '', '') between '[5,10]'"
    )

    assert "ROW_NUMBER() OVER" in result.sql
    assert "ranked.rank_no >= 5" in result.sql
    assert "ranked.rank_no <= 10" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql


def test_compile_rank_greater_than_zero_as_official_rank_only_intent():
    result = OfficialSlotCompiler().compile(
        "rank('', '', '涨幅', 'desc', '今日', '板块', '', '') > 0 limit 30,-1"
    )

    assert "rank_no > 0" in result.sql
    assert "ORDER BY ((base.lastPx - base.preClosePx) * 100.0 / NULLIF(base.preClosePx, 0)) DESC" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql


def test_compile_rank_count_exp_exist_over_date_buckets():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "rank('', '', '收盘价', 'desc', '近5日', '', '', 'EXIST>=3日') <= 3"
    )

    assert "ROW_NUMBER() OVER" in result.sql
    assert "DATE_TRUNC(rb.bizdate, 'day')" in result.sql
    assert "ranked.rank_no <= 3" in result.sql
    assert ") >= 3" in result.sql
    assert "rb.bizdate BETWEEN '2026-04-10' AND '2026-04-14'" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql


def test_compile_rank_count_exp_every_bucket_requires_all_ranked_buckets():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "rank('', '', '成交量', 'desc', '近5日', '', '', 'CONS=每日') <= 10"
    )

    assert "SUM(CASE WHEN ranked.rank_no <= 10 THEN 1 ELSE 0 END) = COUNT(*)" in result.sql
    assert "COUNT(*) > 0" in result.sql
    assert "DATE_TRUNC(rb.bizdate, 'day')" in result.sql


def test_compile_rank_count_exp_between_percent_uses_partition_count():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "rank('', '', '市盈率', 'desc', '近15天', '', '', 'CONS=3日') between '[5%,10%]'"
    )

    assert "COUNT(*) OVER (PARTITION BY DATE_TRUNC(rb.bizdate, 'day')) AS partition_count" in result.sql
    assert "CEIL((ranked.partition_count * 5) / 100.0)" in result.sql
    assert "CEIL((ranked.partition_count * 10) / 100.0)" in result.sql
    assert "ranked.rank_no >=" in result.sql
    assert "ranked.rank_no <=" in result.sql


def test_compile_rank_aggregate_count_exp_growth_percent_bucket_rank():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "rank('', '', '成交量', 'desc', '近10日', '', 'GROWTH_RISE', 'CONS=10日') <= 20%"
    )

    assert "DATE_TRUNC(rb.bizdate, 'day') AS bucket_key" in result.sql
    assert "MAX_BY(rb.volume, rb.bizdate)" in result.sql
    assert "MIN_BY(rb.volume, rb.bizdate)" in result.sql
    assert "ROW_NUMBER() OVER (PARTITION BY bucketed.bucket_key ORDER BY bucketed.agg_value DESC" in result.sql
    assert "COUNT(*) OVER (PARTITION BY bucketed.bucket_key) AS partition_count" in result.sql
    assert "CEIL((ranked.partition_count * 20) / 100.0)" in result.sql


def test_compile_rank_aggregate_count_exp_yearly_average_bucket_rank():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "rank('', '', '集合竞价金额', 'asc', '2023年', '', 'AVG', 'CONS=每年') <= 10"
    )

    assert "DATE_TRUNC(rb.bizdate, 'year') AS bucket_key" in result.sql
    assert "AVG(rext.callAucAmt) AS agg_value" in result.sql
    assert "GROUP BY rb.mktcode, rb.tgtcode, DATE_TRUNC(rb.bizdate, 'year')" in result.sql
    assert "ORDER BY bucketed.agg_value ASC" in result.sql
    assert "SUM(CASE WHEN ranked.rank_no <= 10 THEN 1 ELSE 0 END) = COUNT(*)" in result.sql


def test_compile_cross_above_count_exp_everyday_event_window():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "cross_above('', '', '最新价', '60日均线', '近5日', '', 'CONS=每日') = True"
    )

    assert "LAG((wb.lastPx / 10000.0)) OVER" in result.sql
    assert "wt.ma60" in result.sql
    assert "AS event_value" in result.sql
    assert "SUM(CASE WHEN event_rows.event_value THEN 1 ELSE 0 END) = COUNT(*)" in result.sql
    assert "event_rows.bizdate BETWEEN '2026-04-10' AND '2026-04-14'" in result.sql


def test_compile_cross_count_exp_lag_source_keeps_pre_window_rows():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "cross_above('', '', '最新价', '60日均线', '近5日', '', 'EXIST=1日') = True"
    )

    assert "wb.bizdate <= '2026-04-14'" in result.sql
    assert "event_rows.bizdate BETWEEN '2026-04-10' AND '2026-04-14'" in result.sql


def test_compile_golden_cross_count_exp_exist_event_window():
    result = OfficialSlotCompiler(
        anchor_date="2026-04-14",
        trading_dates=[
            "2026-04-01",
            "2026-04-02",
            "2026-04-03",
            "2026-04-06",
            "2026-04-07",
            "2026-04-08",
            "2026-04-09",
            "2026-04-10",
            "2026-04-13",
            "2026-04-14",
        ],
    ).compile(
        "golden_cross('', '', '5日均量线', '10日均量线', '近10个交易日', '', 'EXIST=2日') = True"
    )

    assert "wt.volume_avg_5" in result.sql
    assert "wt.volume_avg_10" in result.sql
    assert "AS event_value" in result.sql
    assert ") = 2" in result.sql
    assert "event_rows.bizdate BETWEEN '2026-04-01' AND '2026-04-14'" in result.sql


def test_compile_count_exp_comparison_accepts_equivalent_recent_date_spellings():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '涨停价', '30个交易日内', '', '', 'EXIST=2') >= "
        "indicator('', '', '60日均线', '30个交易日', '', '', 'EXIST=2')"
    )

    assert "(wb.upSealPx / 10000.0)" in result.sql
    assert "wt.ma60" in result.sql
    assert "wb.bizdate BETWEEN '2026-03-16' AND '2026-04-14'" in result.sql
    assert ") = 2" in result.sql


def test_parse_official_slot_supports_signed_percent_and_negative_limit_bound():
    ast = parse_official_slot(
        "indicator('', '', '跌幅', '', '', '', '') > -5% limit 20,-1"
    )

    payload = ast.to_dict()

    assert payload["type"] == "Limit"
    assert payload["lower"] == 20
    assert payload["upper"] == -1
    assert payload["expr"]["right"]["value"] == "-5%"


def test_compile_between_range_literal_from_official_workbook_style():
    result = OfficialSlotCompiler().compile(
        "indicator('沪|深', '', '市净率', '', '', '', '') between [10,50]"
    )

    assert "((base.pBR / 10000.0) >= 10 AND (base.pBR / 10000.0) <= 50)" in result.sql
    assert "base.mktcode IN (0, 1)" in result.sql


def test_compile_official_slot_keeps_sql_comment_free_and_reports_warnings():
    result = OfficialSlotCompiler().compile(
        "indicator('港', '', '最新价', '今天', '期货', '', '') > 10"
    )

    assert "/*" not in result.sql
    assert "*/" not in result.sql
    assert "1=0" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql
    assert "date slot requires runtime normalization: 今天" not in result.warnings
    assert "select_type '期货' is not present in official A-share CSV tables" in result.warnings
    assert "market '港' is not present in official A-share CSV tables" in result.warnings


def test_compile_unsupported_indicator_fails_with_stable_code():
    with pytest.raises(OfficialSlotError) as excinfo:
        OfficialSlotCompiler().compile(
            "indicator('', '', '相似K线', '', '', '', '') = '沪上阿姨'"
        )

    assert excinfo.value.code == "UNSUPPORTED_OFFICIAL_INDICATOR"
    assert "相似K线" in str(excinfo.value)


def test_profile_training_workbook_reads_official_examples():
    profile = profile_training_workbook(OFFICIAL_WORKBOOK, sample_size=20)

    assert profile["row_count"] == 5799
    assert profile["sample_size"] == 20
    assert profile["function_counts"]["indicator"] > 0
    assert profile["operator_counts"]["then"] >= 0
    assert "CONS=每日" not in profile["indicator_counts"]
    assert profile["count_exp_counts"]["CONS=每日"] > 100
    assert profile["indicator_counts"]["涨跌幅"] > 0


def test_compile_training_workbook_reports_real_parse_and_compile_coverage(tmp_path):
    coverage = compile_training_workbook(OFFICIAL_WORKBOOK, sample_size=5)
    output = tmp_path / "coverage.md"

    write_coverage_report(coverage, str(output))

    assert coverage["row_count"] == 5799
    assert coverage["parse_ok"] >= 5790
    assert coverage["compile_ok"] > 900
    assert coverage["compile_failed"] > 0
    assert coverage["compile_errors"]["UNSUPPORTED_OFFICIAL_INDICATOR"] > 0
    assert coverage["compile_error_samples"]
    assert coverage["compile_error_domains"]["财务报表数据缺失"] > 0
    assert coverage["compile_error_domains"]["指数成分与权重数据缺失"] > 0
    assert "官方槽位 DSL 编译覆盖率报告" in output.read_text(encoding="utf-8")
    assert "缺失数据域分层" in output.read_text(encoding="utf-8")


def test_classify_official_indicator_domains_for_audit_report():
    assert classify_official_indicator_domain("成分股") == "指数成分与权重数据缺失"
    assert classify_official_indicator_domain("归母净利润") == "财务报表数据缺失"
    assert classify_official_indicator_domain("基金十大重仓股") == "基金产品与持仓数据缺失"
    assert classify_official_indicator_domain("我的持仓股") == "用户账户与自选股数据缺失"
    assert classify_official_indicator_domain("龙虎榜净流入") == "龙虎榜与交易异动数据缺失"
    assert classify_official_indicator_domain("相似K线") == "高级形态/相似度模型数据缺失"


def test_official_slot_compile_cli_prints_json_payload():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "findsl.cli",
            "official-slot-compile",
            "indicator('沪', '', '成交量', '2026-04-14', '', '', '') > 1000",
            "--json",
        ],
        check=True,
        capture_output=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONPATH": "src", "PYTHONIOENCODING": "utf-8"},
    )

    assert '"requires_tables"' in proc.stdout
    assert "newzl.hsj_stock_hq_basic" in proc.stdout
    assert "base.volume > 1000" in proc.stdout


def test_official_slot_coverage_cli_writes_json_and_markdown(tmp_path):
    json_output = tmp_path / "official_slot_coverage.json"
    report_output = tmp_path / "official_slot_coverage.md"

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "findsl.cli",
            "official-slot-coverage",
            "--workbook",
            OFFICIAL_WORKBOOK,
            "--json-output",
            str(json_output),
            "--report-output",
            str(report_output),
            "--sample-size",
            "3",
            "--json",
        ],
        check=True,
        capture_output=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONPATH": "src", "PYTHONIOENCODING": "utf-8"},
    )

    assert '"compile_ok"' in proc.stdout
    assert json_output.exists()
    assert report_output.exists()
    assert "官方槽位 DSL 编译覆盖率报告" in report_output.read_text(encoding="utf-8")

from __future__ import annotations

import subprocess
import sys
import os

import pytest

from findsl.official_slot import (
    OfficialSlotCompiler,
    OfficialSlotError,
    compile_training_workbook,
    parse_official_slot,
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


def test_compile_official_numeric_scales_to_human_units():
    result = OfficialSlotCompiler().compile(
        "indicator('', '', '市净率', '今日', '', '', '') < 2 "
        "and indicator('', '', '涨幅', '今日', '', '', '') > 5%"
    )

    assert "(base.pBR / 10000.0) < 2" in result.sql
    assert "((base.lastPx - base.preClosePx) * 100.0 / NULLIF(base.preClosePx, 0)) > 5" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql


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


def test_compile_official_generated_market_value_indicators_from_real_columns():
    result = OfficialSlotCompiler().compile(
        "indicator('', '', '总市值', '', '', '', '') > 10000000000 "
        "and indicator('', '', '流通市值', '', '', '', '') > 5000000000"
    )

    assert "((base.lastPx / 10000.0) * base.totalShare) > 10000000000" in result.sql
    assert "((base.lastPx / 10000.0) * base.listedShare) > 5000000000" in result.sql


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


def test_compile_official_aggregate_count_exp_uses_bucketed_aggregate():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '成交量', '近5日', '', 'AVG', 'EXIST>=3日') > 1000"
    )

    assert "DATE_TRUNC(wb.bizdate, 'day') AS bucket_key" in result.sql
    assert "AVG(wb.volume) AS agg_value" in result.sql
    assert "GROUP BY DATE_TRUNC(wb.bizdate, 'day')" in result.sql
    assert "bucketed.agg_value > 1000" in result.sql
    assert ") >= 3" in result.sql


def test_compile_official_daily_growth_count_exp_uses_lag_pairs():
    result = OfficialSlotCompiler(anchor_date="2026-04-14").compile(
        "indicator('', '', '成交量', '近5日', '', 'GROWTH_FALL', 'CONS=每日') > 0"
    )

    assert "LAG(wb.volume) OVER" in result.sql
    assert "((LAG(wb.volume) OVER" in result.sql
    assert "- wb.volume) * 100.0" in result.sql
    assert "bucketed.agg_value IS NOT NULL" in result.sql
    assert "SUM(CASE WHEN bucketed.agg_value > 0 THEN 1 ELSE 0 END) = COUNT(*)" in result.sql


def test_compile_rank_then_pipeline_for_official_slot_dsl():
    result = OfficialSlotCompiler().compile(
        "indicator('沪', '', '涨停', '2026-04-14', '', '', '') = True "
        "then rank('沪', '', '成交量', 'desc', '2026-04-14', '', '', '') <= 10"
    )

    assert "ROW_NUMBER() OVER" in result.sql
    assert "ORDER BY base.volume DESC" in result.sql
    assert "rank_no <= 10" in result.sql
    assert "base.limitFlag = 1" in result.sql


def test_compile_rank_comparison_inside_boolean_pipeline():
    result = OfficialSlotCompiler().compile(
        "rank('', '', '市净率', 'desc', '', '', '', '') <= 10 "
        "and indicator('', '', '涨停', '', '', '', '') = True"
    )

    assert "EXISTS (" in result.sql
    assert "ROW_NUMBER() OVER" in result.sql
    assert "ranked.rank_no <= 10" in result.sql
    assert "base.limitFlag = 1" in result.sql


def test_compile_rank_greater_than_zero_as_official_rank_only_intent():
    result = OfficialSlotCompiler().compile(
        "rank('', '', '涨幅', 'desc', '今日', '板块', '', '') > 0 limit 30,-1"
    )

    assert "rank_no > 0" in result.sql
    assert "ORDER BY ((base.lastPx - base.preClosePx) * 100.0 / NULLIF(base.preClosePx, 0)) DESC" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql


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
    assert "官方槽位 DSL 编译覆盖率报告" in output.read_text(encoding="utf-8")


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
        encoding="gb18030",
        env={**os.environ, "PYTHONPATH": "src"},
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
        encoding="gb18030",
        env={**os.environ, "PYTHONPATH": "src"},
    )

    assert '"compile_ok"' in proc.stdout
    assert json_output.exists()
    assert report_output.exists()
    assert "官方槽位 DSL 编译覆盖率报告" in report_output.read_text(encoding="utf-8")

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
        "indicator('深', '', '最新价', '2026-04-14', '', '', '') > 100000"
    )

    assert "newzl.hsj_stock_hq_basic" in result.sql
    assert "base.lastPx > 100000" in result.sql
    assert "base.mktcode IN (0)" in result.sql
    assert "base.bizdate = '2026-04-14'" in result.sql
    assert result.requires_tables == ["hsj_stock_hq_basic"]


def test_compile_official_generated_market_value_indicators_from_real_columns():
    result = OfficialSlotCompiler().compile(
        "indicator('', '', '总市值', '', '', '', '') > 10000000000 "
        "and indicator('', '', '流通市值', '', '', '', '') > 5000000000"
    )

    assert "(base.lastPx * base.totalShare) > 10000000000" in result.sql
    assert "(base.lastPx * base.listedShare) > 5000000000" in result.sql


def test_compile_official_time_and_order_flow_indicators_from_real_columns():
    result = OfficialSlotCompiler().compile(
        "indicator('', '', '涨停时间', '', '', '', '') < '10:00:00' "
        "and indicator('', '', '外盘', '', '', '', '') > 1000 "
        "and indicator('', '', '主力成交量占比', '', '', '', '') > 5"
    )

    assert "base.firstLimitUpTime < '10:00:00'" in result.sql
    assert "base.outerVol > 1000" in result.sql
    assert "ext.ZJLXMainTradeVolPer > 5" in result.sql


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
    assert "ORDER BY ((base.lastPx - base.preClosePx) / NULLIF(base.preClosePx, 0)) DESC" in result.sql


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

    assert "(base.pBR >= 10 AND base.pBR <= 50)" in result.sql
    assert "base.mktcode IN (0, 1)" in result.sql


def test_compile_official_slot_keeps_sql_comment_free_and_reports_warnings():
    result = OfficialSlotCompiler().compile(
        "indicator('港', '', '最新价', '今天', '期货', '', '') > 10"
    )

    assert "/*" not in result.sql
    assert "*/" not in result.sql
    assert "1=0" in result.sql
    assert "date slot requires runtime normalization: 今天" in result.warnings
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

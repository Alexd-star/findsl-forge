from pathlib import Path

from findsl.reference import PandasReferenceEvaluator


DATA_DIR = Path("data/samples")


def test_reference_max_window_breakout():
    evaluator = PandasReferenceEvaluator(DATA_DIR)
    result = evaluator.evaluate('filter(indicator("close") >= MAX(indicator("close"), 3))')
    assert result.keys() == [
        ("AAA", "2026-01-01"),
        ("BBB", "2026-01-01"),
        ("CCC", "2026-01-01"),
        ("AAA", "2026-01-02"),
        ("CCC", "2026-01-02"),
        ("AAA", "2026-01-03"),
        ("BBB", "2026-01-03"),
        ("AAA", "2026-01-04"),
        ("BBB", "2026-01-04"),
        ("CCC", "2026-01-04"),
        ("BBB", "2026-01-05"),
        ("CCC", "2026-01-05"),
    ]


def test_reference_cons_main_net_inflow():
    evaluator = PandasReferenceEvaluator(DATA_DIR)
    result = evaluator.evaluate('filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3))')
    assert result.keys() == [
        ("AAA", "2026-01-04"),
        ("BBB", "2026-01-05"),
    ]


def test_reference_exist_volume_above_ma():
    evaluator = PandasReferenceEvaluator(DATA_DIR)
    result = evaluator.evaluate('filter(EXIST(indicator("volume") > MA(indicator("volume"), 3), 2))')
    assert ("AAA", "2026-01-03") in result.keys()
    assert ("BBB", "2026-01-04") in result.keys()
    assert ("CCC", "2026-01-05") in result.keys()


def test_reference_then_filter_rank_top_one_by_turnover():
    evaluator = PandasReferenceEvaluator(DATA_DIR)
    result = evaluator.evaluate('then(filter(market("A")), rank(indicator("turnover_rate"), desc, top=1))')
    assert result.keys() == [
        ("AAA", "2026-01-01"),
        ("AAA", "2026-01-02"),
        ("BBB", "2026-01-03"),
        ("BBB", "2026-01-04"),
        ("BBB", "2026-01-05"),
    ]


def test_reference_then_filter_rank_percent_by_turnover():
    evaluator = PandasReferenceEvaluator(DATA_DIR)
    result = evaluator.evaluate('then(filter(market("A")), rank(indicator("turnover_rate"), desc, percent=50))')
    assert result.keys() == [
        ("AAA", "2026-01-01"),
        ("AAA", "2026-01-02"),
        ("BBB", "2026-01-03"),
        ("BBB", "2026-01-04"),
        ("BBB", "2026-01-05"),
    ]


def test_reference_date_between_filters_trade_date_range():
    evaluator = PandasReferenceEvaluator(DATA_DIR)
    result = evaluator.evaluate('filter(date_between("2026-01-02", "2026-01-04") & indicator("close") > 10)')
    assert result.keys() == [
        ("AAA", "2026-01-02"),
        ("BBB", "2026-01-02"),
        ("AAA", "2026-01-03"),
        ("BBB", "2026-01-03"),
        ("AAA", "2026-01-04"),
        ("BBB", "2026-01-04"),
    ]

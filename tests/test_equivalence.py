from pathlib import Path

from findsl.compiler import Compiler
from findsl.equivalence import verify_sql_equivalence
from findsl.executor import SQLiteSampleExecutor


DATA_DIR = Path("data/samples")


def _write_tie_fixture(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "daily_quote.csv").write_text(
        "\n".join(
            [
                "ts_code,trade_date,close,turnover_rate,volume",
                "BBB,2026-01-01,10,1.0,100",
                "AAA,2026-01-01,10,1.0,100",
                "CCC,2026-01-01,8,0.5,80",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (data_dir / "money_flow.csv").write_text(
        "\n".join(
            [
                "ts_code,trade_date,main_net_inflow",
                "BBB,2026-01-01,1",
                "AAA,2026-01-01,1",
                "CCC,2026-01-01,1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (data_dir / "stock_universe.csv").write_text(
        "\n".join(
            [
                "ts_code,trade_date,market",
                "BBB,2026-01-01,A",
                "AAA,2026-01-01,A",
                "CCC,2026-01-01,A",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_sqlite_executor_runs_generated_cons_sql():
    compiled = Compiler().compile('filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3))')
    result = SQLiteSampleExecutor(DATA_DIR).execute(compiled.sql)
    assert result.keys() == [
        ("AAA", "2026-01-04"),
        ("BBB", "2026-01-05"),
    ]


def test_sqlite_executor_can_reuse_loaded_fixture_database():
    compiled = Compiler().compile('filter(SUM(indicator("volume"), 3) > 300)')
    with SQLiteSampleExecutor(DATA_DIR) as executor:
        first = executor.execute(compiled.sql)
        second = executor.execute(compiled.sql)
    assert first.keys() == second.keys()
    assert len(first.keys()) == 7


def test_sql_matches_reference_for_cons_main_net_inflow():
    result = verify_sql_equivalence(
        'filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3))',
        DATA_DIR,
    )
    assert result.passed
    assert result.sql_row_count == 2
    assert result.missing_keys == []
    assert result.extra_keys == []


def test_sql_matches_reference_for_max_window():
    result = verify_sql_equivalence(
        'filter(indicator("close") >= MAX(indicator("close"), 3))',
        DATA_DIR,
    )
    assert result.passed


def test_sql_matches_reference_for_exist_and_ma():
    result = verify_sql_equivalence(
        'filter(EXIST(indicator("volume") > MA(indicator("volume"), 3), 2))',
        DATA_DIR,
    )
    assert result.passed


def test_sql_matches_reference_for_then_filter_rank():
    result = verify_sql_equivalence(
        'then(filter(market("A")), rank(indicator("turnover_rate"), desc, top=1))',
        DATA_DIR,
    )
    assert result.passed


def test_sql_matches_reference_for_rank_ties_with_stable_ts_code_order(tmp_path):
    _write_tie_fixture(tmp_path)

    result = verify_sql_equivalence(
        'rank(indicator("close"), desc, top=1)',
        tmp_path,
    )

    assert result.passed
    assert result.sql_keys == [("AAA", "2026-01-01")]
    assert result.reference_keys == [("AAA", "2026-01-01")]


def test_sql_matches_reference_for_then_filter_filter():
    result = verify_sql_equivalence(
        'then(filter(market("A")), filter(indicator("close") > 10))',
        DATA_DIR,
    )
    assert result.passed
    assert result.sql_row_count == 9


def test_sql_matches_reference_for_then_filter_window_filter():
    result = verify_sql_equivalence(
        'then(filter(market("A")), filter(MA(indicator("close"), 2) > 10))',
        DATA_DIR,
    )
    assert result.passed


def test_sql_matches_reference_for_rank_by_window_feature():
    result = verify_sql_equivalence(
        'rank(MA(indicator("close"), 2), desc, top=1)',
        DATA_DIR,
    )
    assert result.passed
    assert result.sql_row_count == 5


def test_sql_matches_reference_for_then_rank_by_window_feature():
    result = verify_sql_equivalence(
        'then(filter(market("A")), rank(MA(indicator("close"), 2), desc, top=1))',
        DATA_DIR,
    )
    assert result.passed
    assert result.sql_row_count == 5


def test_sql_matches_reference_for_then_filter_rank_percent():
    result = verify_sql_equivalence(
        'then(filter(market("A")), rank(indicator("turnover_rate"), desc, percent=50))',
        DATA_DIR,
    )
    assert result.passed
    assert result.sql_row_count == 5


def test_sql_matches_reference_for_date_between_pushdown():
    result = verify_sql_equivalence(
        'filter(date_between("2026-01-02", "2026-01-04") & indicator("close") > 10)',
        DATA_DIR,
    )
    assert result.passed
    assert result.sql_row_count == 6


def test_sql_matches_reference_for_prefix_sum_rewrite():
    result = verify_sql_equivalence(
        'filter(SUM(indicator("volume"), 3) > 300)',
        DATA_DIR,
    )
    assert result.passed
    assert result.sql_row_count == 7
    assert result.missing_keys == []
    assert result.extra_keys == []


def test_sql_matches_reference_for_signed_numeric_threshold():
    result = verify_sql_equivalence(
        'filter(indicator("main_net_inflow") < -1.5)',
        DATA_DIR,
    )

    assert result.passed
    assert result.sql_row_count > 0


def test_sql_matches_reference_for_single_equal_comparison():
    result = verify_sql_equivalence(
        'filter(indicator("close") = 10)',
        DATA_DIR,
    )

    assert result.passed
    assert result.sql_row_count == 1

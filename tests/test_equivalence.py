from pathlib import Path

from findsl.compiler import Compiler
from findsl.equivalence import verify_sql_equivalence
from findsl.executor import SQLiteSampleExecutor


DATA_DIR = Path("data/samples")


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


def test_sql_matches_reference_for_prefix_sum_rewrite():
    result = verify_sql_equivalence(
        'filter(SUM(indicator("volume"), 3) > 300)',
        DATA_DIR,
    )
    assert result.passed
    assert result.sql_row_count == 7
    assert result.missing_keys == []
    assert result.extra_keys == []

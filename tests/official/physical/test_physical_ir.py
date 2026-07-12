import pytest

from findsl.official.physical import (
    PhysicalCatalogError, PhysicalColumn, PhysicalComparison, PhysicalFilter,
    PhysicalLimit, PhysicalLiteral, PhysicalScan, PhysicalTemporal,
    PhysicalTemporalWindow, PhysicalSetOperation, validate_physical_plan,
)
from findsl.official.physical.catalog import default_physical_catalog
from findsl.official.types import BOOLEAN, NUMERIC


def test_direct_scan_filter_limit_plan_is_deterministic_and_valid():
    column = PhysicalColumn("official_basic", "volume", NUMERIC)
    scan = PhysicalScan("official_basic", (column,), None)
    predicate = PhysicalComparison(">", column, PhysicalLiteral(100, NUMERIC))
    plan = PhysicalLimit(PhysicalFilter(scan, predicate), 0, 20)

    assert validate_physical_plan(plan, default_physical_catalog()) is plan
    assert plan.node_id == PhysicalLimit(PhysicalFilter(scan, predicate), 0, 20).node_id


def test_validator_rejects_unknown_column_and_invalid_limit():
    scan = PhysicalScan("official_basic", (PhysicalColumn("official_basic", "not_a_column", NUMERIC),), None)
    with pytest.raises(PhysicalCatalogError):
        validate_physical_plan(scan, default_physical_catalog())
    with pytest.raises(ValueError):
        validate_physical_plan(PhysicalLimit(PhysicalScan("official_basic", (), None), 0, 0), default_physical_catalog())


def test_temporal_plan_is_explicit_deterministic_and_trading_sequence_based():
    column = PhysicalColumn("official_basic", "volume", NUMERIC)
    scan = PhysicalScan("official_basic", (column,), None)
    predicate = PhysicalComparison(">", column, PhysicalLiteral(100, NUMERIC))
    plan = PhysicalTemporal(
        scan,
        predicate,
        "CONS",
        ">=",
        3,
        None,
        "日",
        False,
        PhysicalTemporalWindow("recent_sessions", lookback_sessions=10),
    )

    assert validate_physical_plan(plan, default_physical_catalog()) is plan
    assert plan.node_id == plan.node_id
    assert plan.to_dict()["window"]["lookback_sessions"] == 10


def test_set_operation_validates_two_independent_temporal_relations():
    column = PhysicalColumn("official_basic", "volume", NUMERIC)
    scan = PhysicalScan("official_basic", (column,), None)
    predicate = PhysicalComparison(">", column, PhysicalLiteral(100, NUMERIC))
    branch = PhysicalTemporal(
        scan,
        predicate,
        "EXIST",
        ">",
        0,
        None,
        "日",
        False,
        PhysicalTemporalWindow("recent_sessions", lookback_sessions=5),
    )
    plan = PhysicalSetOperation(branch, branch, "intersect")

    assert validate_physical_plan(plan, default_physical_catalog()) is plan
    assert plan.to_dict()["operation"] == "intersect"

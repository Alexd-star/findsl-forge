import pytest

from findsl.official.physical import (
    PhysicalCatalogError, PhysicalColumn, PhysicalComparison, PhysicalFilter,
    PhysicalLimit, PhysicalLiteral, PhysicalScan, validate_physical_plan,
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

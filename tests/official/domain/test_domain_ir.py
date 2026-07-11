import pytest

from findsl.official.domain import DataRequirement, DateConstraint, IndicatorRef, MarketScope, RankSpec
from findsl.official.ir import Field, LiteralExpr, LogicalDomainScan, LogicalEmpty, Schema
from findsl.official.ir.validate import OfficialIrError, validate_plan
from findsl.official.types import NUMERIC, STRING


SCHEMA = Schema((Field("stock_code", STRING, False),))


def test_domain_nodes_are_deterministic_and_sql_free():
    indicator = IndicatorRef("涨幅", NUMERIC, "ratio_percent", "quote", "official_provided")
    requirement = DataRequirement(frozenset({"quote"}), frozenset({"ordered"}))
    rank = RankSpec(indicator, "desc", LiteralExpr(10, NUMERIC), ())

    assert indicator.node_id == IndicatorRef("涨幅", NUMERIC, "ratio_percent", "quote", "official_provided").node_id
    assert requirement.to_dict()["domains"] == ["quote"]
    assert rank.to_dict()["direction"] == "desc"
    assert "SELECT" not in rank.canonical_json().upper()


def test_domain_scan_and_proven_empty_relation_validate():
    requirement = DataRequirement(frozenset({"quote"}), frozenset())
    scan = LogicalDomainScan("market_observation", requirement, SCHEMA)
    empty = LogicalEmpty(SCHEMA, "PROVEN_CONSTRAINT_CONFLICT")

    assert validate_plan(scan) is scan
    assert validate_plan(empty) is empty


def test_empty_relation_requires_proven_reason():
    with pytest.raises(OfficialIrError) as excinfo:
        validate_plan(LogicalEmpty(SCHEMA, "missing data"))
    assert excinfo.value.code == "IR_EMPTY_REASON"

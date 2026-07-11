import pytest

from findsl.official.ir import (
    BinaryExpr,
    ComparisonExpr,
    Field,
    FieldRef,
    LiteralExpr,
    LogicalFilter,
    LogicalLimit,
    LogicalScan,
    Schema,
)
from findsl.official.types import BOOLEAN, NUMERIC, STRING


def test_logical_nodes_are_deterministic_and_sql_free():
    schema = Schema((Field("stock_code", STRING, False), Field("value", NUMERIC, True)))
    scan = LogicalScan("market_observation", schema)
    predicate = ComparisonExpr(">", FieldRef("value", NUMERIC), LiteralExpr(5, NUMERIC))
    plan = LogicalLimit(LogicalFilter(scan, predicate, schema), 0, 20, schema)

    assert plan.node_id == LogicalLimit(LogicalFilter(scan, predicate, schema), 0, 20, schema).node_id
    assert plan.to_dict()["kind"] == "LogicalLimit"
    assert "SELECT" not in plan.canonical_json().upper()


def test_expression_types_are_explicit():
    expression = BinaryExpr("and", LiteralExpr(True, BOOLEAN), LiteralExpr(False, BOOLEAN), BOOLEAN)
    assert expression.type is BOOLEAN
    assert expression.to_dict()["left"]["value"] is True


def test_schema_rejects_duplicate_names():
    with pytest.raises(ValueError, match="duplicate"):
        Schema((Field("value", NUMERIC), Field("value", STRING)))

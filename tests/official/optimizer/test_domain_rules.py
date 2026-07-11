from findsl.official.domain import DataRequirement, DateConstraint, MarketScope
from findsl.official.ir import (
    BinaryExpr, ComparisonExpr, Field, FieldRef, LiteralExpr, LogicalConstraint,
    LogicalDomainScan, LogicalEmpty, LogicalFilter, LogicalStage, Schema,
)
from findsl.official.optimizer import BoolFlattenRule, ConstraintMergeRule, FilterPushDownRule, Optimizer, StageNormalizeRule
from findsl.official.types import BOOLEAN, NUMERIC, STRING


SCHEMA = Schema((Field("stock_code", STRING, False), Field("value", NUMERIC)))
SCAN = LogicalDomainScan("market_observation", DataRequirement(frozenset({"quote"}), frozenset()), SCHEMA)


def test_boolean_flatten_produces_canonical_left_associative_tree():
    a = ComparisonExpr(">", FieldRef("value", NUMERIC), LiteralExpr(1, NUMERIC))
    b = ComparisonExpr("<", FieldRef("value", NUMERIC), LiteralExpr(9, NUMERIC))
    c = ComparisonExpr("!=", FieldRef("value", NUMERIC), LiteralExpr(4, NUMERIC))
    right_nested = BinaryExpr("and", a, BinaryExpr("and", b, c, BOOLEAN), BOOLEAN)
    result = Optimizer((BoolFlattenRule(),)).optimize(LogicalFilter(SCAN, right_nested, SCHEMA))
    assert isinstance(result.plan.predicate.left, BinaryExpr)


def test_compatible_constraints_merge_and_conflicts_become_proven_empty():
    inner = LogicalConstraint(SCAN, MarketScope(("SH", "SZ")), DateConstraint("exact", "2026-01-01", "2026-01-01"), SCHEMA)
    compatible = LogicalConstraint(inner, MarketScope(("SH",)), DateConstraint("unspecified"), SCHEMA)
    merged = Optimizer((ConstraintMergeRule(),)).optimize(compatible).plan
    assert merged.market_scope.markets == ("SH",)

    conflict = LogicalConstraint(inner, MarketScope(("BJ",)), DateConstraint("unspecified"), SCHEMA)
    assert isinstance(Optimizer((ConstraintMergeRule(),)).optimize(conflict).plan, LogicalEmpty)


def test_row_local_filter_pushes_below_constraint_and_stage_indexes_normalize():
    constraint = LogicalConstraint(SCAN, MarketScope(("SH",)), DateConstraint("unspecified"), SCHEMA)
    predicate = ComparisonExpr(">", FieldRef("value", NUMERIC), LiteralExpr(1, NUMERIC))
    pushed = Optimizer((FilterPushDownRule(),)).optimize(LogicalFilter(constraint, predicate, SCHEMA)).plan
    assert isinstance(pushed.input, LogicalFilter)

    operation = LogicalFilter(SCAN, predicate, SCHEMA)
    stage = LogicalStage(SCAN, 9, operation, SCHEMA)
    assert Optimizer((StageNormalizeRule(),)).optimize(stage).plan.stage_index == 1

from findsl.official.ir import BinaryExpr, ComparisonExpr, Field, LiteralExpr, LogicalFilter, LogicalLimit, LogicalScan, Schema
from findsl.official.optimizer import ConstFoldRule, FilterMergeRule, LimitNormalizeRule, Optimizer, PredicateDedupRule
from findsl.official.types import BOOLEAN, NUMERIC, STRING


SCHEMA = Schema((Field("stock_code", STRING, False),))
SCAN = LogicalScan("market_observation", SCHEMA)


def test_constant_fold_records_auditable_trace():
    predicate = ComparisonExpr(">", LiteralExpr(3, NUMERIC), LiteralExpr(2, NUMERIC))
    result = Optimizer((ConstFoldRule(),)).optimize(LogicalFilter(SCAN, predicate, SCHEMA))

    assert result.plan.predicate == LiteralExpr(True, BOOLEAN)
    assert result.trace[0].rule_id == "CONST_FOLD"
    assert result.trace[0].before_hash != result.trace[0].after_hash
    assert result.trace[0].proof_obligation


def test_duplicate_predicate_and_nested_filters_are_normalized():
    predicate = ComparisonExpr("=", LiteralExpr(1, NUMERIC), LiteralExpr(1, NUMERIC))
    duplicate = BinaryExpr("and", predicate, predicate, BOOLEAN)
    nested = LogicalFilter(LogicalFilter(SCAN, duplicate, SCHEMA), predicate, SCHEMA)
    result = Optimizer((PredicateDedupRule(), FilterMergeRule())).optimize(nested)

    assert not isinstance(result.plan.input, LogicalFilter)


def test_nested_limits_follow_relational_slice_semantics():
    inner = LogicalLimit(SCAN, 10, 100, SCHEMA)
    outer = LogicalLimit(inner, 5, 20, SCHEMA)
    result = Optimizer((LimitNormalizeRule(),)).optimize(outer)

    assert (result.plan.offset, result.plan.count) == (15, 20)


def test_open_ended_nested_limit_is_not_unsafely_collapsed():
    plan = LogicalLimit(LogicalLimit(SCAN, 10, None, SCHEMA), 5, 20, SCHEMA)
    result = Optimizer((LimitNormalizeRule(),)).optimize(plan)

    assert isinstance(result.plan.input, LogicalLimit)
    assert result.plan.input.count is None

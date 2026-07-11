from findsl.official.ir import BinaryExpr, ComparisonExpr, Field, FieldRef, LiteralExpr, LogicalFilter, LogicalLimit, LogicalScan, Schema
from findsl.official.optimizer import DEFAULT_RULES, Optimizer
from findsl.official.optimizer.interpreter import interpret
from findsl.official.types import BOOLEAN, NUMERIC, STRING


SCHEMA = Schema((Field("stock_code", STRING, False), Field("value", NUMERIC, False)))
ROWS = ({"stock_code": "A", "value": 1}, {"stock_code": "B", "value": 3}, {"stock_code": "C", "value": 5})


def test_optimizer_preserves_row_keys_for_supported_rules():
    scan = LogicalScan("market_observation", SCHEMA)
    predicate = ComparisonExpr(">", FieldRef("value", NUMERIC), LiteralExpr(1, NUMERIC))
    duplicate = BinaryExpr("and", predicate, predicate, BOOLEAN)
    plan = LogicalLimit(LogicalLimit(LogicalFilter(scan, duplicate, SCHEMA), 0, 3, SCHEMA), 1, 1, SCHEMA)
    optimized = Optimizer(DEFAULT_RULES).optimize(plan)

    before = interpret(plan, ROWS)
    after = interpret(optimized.plan, ROWS)
    assert [row["stock_code"] for row in before] == [row["stock_code"] for row in after]

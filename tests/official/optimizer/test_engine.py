from findsl.official.ir import Field, LiteralExpr, LogicalFilter, LogicalScan, Schema
from findsl.official.optimizer import Optimizer, PredicateDedupRule
from findsl.official.types import BOOLEAN, STRING


SCHEMA = Schema((Field("stock_code", STRING, False),))


def test_optimizer_records_hashes_and_can_disable_rules():
    scan = LogicalScan("market_observation", SCHEMA)
    predicate = LiteralExpr(True, BOOLEAN)
    plan = LogicalFilter(scan, predicate, SCHEMA)

    disabled = Optimizer(()).optimize(plan)
    assert disabled.plan.node_id == plan.node_id
    assert disabled.trace == ()


def test_optimizer_is_deterministic_and_idempotent():
    scan = LogicalScan("market_observation", SCHEMA)
    plan = LogicalFilter(scan, LiteralExpr(True, BOOLEAN), SCHEMA)
    optimizer = Optimizer((PredicateDedupRule(),))

    first = optimizer.optimize(plan)
    second = optimizer.optimize(first.plan)
    assert first.plan.node_id == second.plan.node_id
    assert second.trace == ()

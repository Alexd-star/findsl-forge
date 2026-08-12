from __future__ import annotations

import random

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
from findsl.official.optimizer import DEFAULT_RULES, Optimizer
from findsl.official.optimizer.interpreter import interpret
from findsl.official.types import BOOLEAN, NUMERIC, STRING


SCHEMA = Schema(
    (Field("stock_code", STRING, False), Field("value", NUMERIC, False))
)


def test_optimizer_preserves_results_for_deterministic_generated_plans() -> None:
    randomizer = random.Random(20260812)
    comparisons = (">", ">=", "<", "<=", "=", "!=")
    boolean_ops = ("and", "or")

    for case_index in range(120):
        rows = tuple(
            {"stock_code": f"S{row_index:02d}", "value": randomizer.randint(-20, 20)}
            for row_index in range(randomizer.randint(1, 30))
        )
        left = ComparisonExpr(
            randomizer.choice(comparisons),
            FieldRef("value", NUMERIC),
            LiteralExpr(randomizer.randint(-10, 10), NUMERIC),
        )
        right = ComparisonExpr(
            randomizer.choice(comparisons),
            FieldRef("value", NUMERIC),
            LiteralExpr(randomizer.randint(-10, 10), NUMERIC),
        )
        predicate = BinaryExpr(randomizer.choice(boolean_ops), left, right, BOOLEAN)
        if case_index % 3 == 0:
            predicate = BinaryExpr("and", predicate, predicate, BOOLEAN)
        scan = LogicalScan("market_observation", SCHEMA)
        plan = LogicalFilter(scan, predicate, SCHEMA)
        if case_index % 2 == 0:
            plan = LogicalFilter(plan, LiteralExpr(True, BOOLEAN), SCHEMA)
        inner_offset = randomizer.randint(0, 4)
        inner_count = randomizer.randint(1, 12)
        outer_offset = randomizer.randint(0, 3)
        outer_count = randomizer.randint(1, 8)
        plan = LogicalLimit(
            LogicalLimit(plan, inner_offset, inner_count, SCHEMA),
            outer_offset,
            outer_count,
            SCHEMA,
        )

        optimized = Optimizer(DEFAULT_RULES).optimize(plan)

        assert optimized.diagnostics == (), f"generated case {case_index} failed"
        assert interpret(optimized.plan, rows) == interpret(plan, rows)


def test_mutation_sentinel_detects_an_invalid_and_rewrite() -> None:
    rows = tuple(
        {"stock_code": str(value), "value": value} for value in range(7)
    )
    scan = LogicalScan("market_observation", SCHEMA)
    greater = ComparisonExpr(
        ">", FieldRef("value", NUMERIC), LiteralExpr(1, NUMERIC)
    )
    less = ComparisonExpr(
        "<", FieldRef("value", NUMERIC), LiteralExpr(5, NUMERIC)
    )
    original = LogicalFilter(
        scan, BinaryExpr("and", greater, less, BOOLEAN), SCHEMA
    )
    mutant = LogicalFilter(scan, greater, SCHEMA)

    assert interpret(original, rows) != interpret(mutant, rows)
    assert [item["stock_code"] for item in interpret(original, rows)] == ["2", "3", "4"]
    assert [item["stock_code"] for item in interpret(mutant, rows)] == [
        "2",
        "3",
        "4",
        "5",
        "6",
    ]

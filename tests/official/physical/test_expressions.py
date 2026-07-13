import pytest

from findsl.official.physical.catalog import default_physical_catalog
from findsl.official.physical.expressions import (
    PhysicalExpressionError,
    PhysicalExpressionRegistry,
    default_physical_expressions,
)


def test_default_registry_loads_typed_scaled_ratio_and_boolean_strategies():
    registry = default_physical_expressions(default_physical_catalog())

    latest = registry.resolve("最新价")
    assert latest.resource_id == "official_basic"
    assert latest.expression.op == "divide"
    assert latest.expression.type == "numeric"
    assert latest.required_columns == (("lastPx", "numeric"),)

    change = registry.resolve("涨幅")
    assert change.expression.op == "safe_divide"
    assert change.required_columns == (
        ("lastPx", "numeric"),
        ("preClosePx", "numeric"),
    )

    first_limit = registry.resolve("首板涨停")
    assert first_limit.expression.op == "and"
    assert first_limit.expression.type == "boolean"
    assert first_limit.required_columns == (
        ("limitFlag", "numeric"),
        ("upSerialLb", "numeric"),
    )
    assert len(registry.definitions) >= 49
    assert len(registry.fingerprint) == 64


@pytest.mark.parametrize(
    "indicator,resource,columns,root_op",
    [
        ("流通市值", "official_basic", (("lastPx", "numeric"), ("listedShare", "numeric")), "multiply"),
        ("委比", "official_basic", (("commissionBuy", "numeric"), ("commissionSale", "numeric")), "safe_divide"),
        ("成交均价", "official_basic", (("turnover", "numeric"), ("volume", "numeric")), "divide"),
        ("3分钟涨速", "official_ext", (("riseSpd3m", "numeric"),), "divide"),
        ("涨停炸板", "official_ext", (("boardBreaks", "numeric"), ("lmtUpNum", "numeric")), "or"),
        ("压力位", "official_basic", (("pressure", "numeric"),), "divide"),
        (
            "涨停未封板",
            "official_basic",
            (("highPx", "numeric"), ("limitFlag", "numeric"), ("upSealPx", "numeric")),
            "and",
        ),
        ("放量", "official_technical", (("volume_breakout", "boolean"),), "equal"),
        ("均线多头排列", "official_technical", (("ma_bullish", "boolean"),), "equal"),
    ],
)
def test_phase20_grounded_expression_registry_contracts(indicator, resource, columns, root_op):
    definition = default_physical_expressions(default_physical_catalog()).resolve(indicator)

    assert definition.resource_id == resource
    assert definition.required_columns == columns
    assert definition.expression.op == root_op


def test_registry_rejects_arithmetic_over_boolean_values():
    raw = {
        "schema_version": 1,
        "definitions": [
            {
                "indicator_id": "bad",
                "resource_id": "official_basic",
                "value_type": "numeric",
                "nullable": True,
                "expression": {
                    "op": "add",
                    "left": {"op": "literal", "value": True, "type": "boolean"},
                    "right": {"op": "literal", "value": 1, "type": "numeric"},
                },
            }
        ],
    }

    with pytest.raises(PhysicalExpressionError, match="numeric operands"):
        PhysicalExpressionRegistry.from_dict(raw, default_physical_catalog())


@pytest.mark.parametrize(
    "expression,message",
    [
        ({"op": "column", "column": "lastPx; DROP TABLE x", "type": "numeric"}, "invalid physical column"),
        ({"op": "sql", "value": "base.lastPx / 10000"}, "unsupported expression operator"),
    ],
)
def test_registry_rejects_invalid_identifiers_and_sql_escape_hatches(expression, message):
    raw = {
        "schema_version": 1,
        "definitions": [
            {
                "indicator_id": "bad",
                "resource_id": "official_basic",
                "value_type": "numeric",
                "nullable": True,
                "expression": expression,
            }
        ],
    }

    with pytest.raises(PhysicalExpressionError, match=message):
        PhysicalExpressionRegistry.from_dict(raw, default_physical_catalog())


def test_registry_rejects_duplicate_indicator_and_unknown_resource():
    definition = {
        "indicator_id": "重复",
        "resource_id": "official_basic",
        "value_type": "numeric",
        "nullable": False,
        "expression": {"op": "literal", "value": 1, "type": "numeric"},
    }
    with pytest.raises(PhysicalExpressionError, match="duplicate physical expression"):
        PhysicalExpressionRegistry.from_dict(
            {"schema_version": 1, "definitions": [definition, definition]},
            default_physical_catalog(),
        )

    invalid = dict(definition, indicator_id="未知资源", resource_id="not_a_resource")
    with pytest.raises(PhysicalExpressionError, match="unknown physical resource"):
        PhysicalExpressionRegistry.from_dict(
            {"schema_version": 1, "definitions": [invalid]},
            default_physical_catalog(),
        )

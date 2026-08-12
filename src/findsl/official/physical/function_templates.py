from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..template_language import FunctionTemplateError, literal_kind
from ..types import BOOLEAN, NUMERIC, STRING, OfficialType
from .ir import (
    PhysicalAbs,
    PhysicalBinary,
    PhysicalCoalesce,
    PhysicalComparison,
    PhysicalGreatest,
    PhysicalLiteral,
    PhysicalNot,
    PhysicalNullIf,
    PhysicalUnary,
)


def instantiate_expression_template(
    template: Mapping[str, Any],
    arguments: Sequence[Any],
    result_type: OfficialType,
):
    if set(template) == {"arg"}:
        return arguments[int(template["arg"])]
    if set(template) == {"literal"}:
        value = template["literal"]
        return PhysicalLiteral(value, _literal_type(value))
    operation = str(template["op"])
    children = tuple(
        instantiate_expression_template(item, arguments, result_type)
        for item in template["args"]
    )
    if operation == "abs":
        return PhysicalAbs(children[0], NUMERIC)
    if operation == "negate":
        return PhysicalUnary("negate", children[0], NUMERIC)
    if operation == "not":
        return PhysicalNot(children[0])
    binary = {"add": "+", "subtract": "-", "multiply": "*"}
    if operation in binary:
        return PhysicalBinary(binary[operation], children[0], children[1], NUMERIC)
    if operation == "safe_divide":
        return PhysicalBinary(
            "/",
            children[0],
            PhysicalNullIf(children[1], PhysicalLiteral(0, NUMERIC), NUMERIC),
            NUMERIC,
        )
    if operation == "greatest":
        return PhysicalGreatest(children, NUMERIC)
    comparison = {
        "greater_than": ">",
        "greater_equal": ">=",
        "less_than": "<",
        "less_equal": "<=",
        "equal": "=",
        "not_equal": "!=",
    }
    if operation in comparison:
        return PhysicalComparison(comparison[operation], children[0], children[1])
    if operation in {"and", "or"}:
        return PhysicalBinary(operation, children[0], children[1], BOOLEAN)
    if operation == "coalesce":
        return PhysicalCoalesce(children, result_type)
    raise FunctionTemplateError(f"unsupported function template operation: {operation}")


def _literal_type(value: Any) -> OfficialType:
    return {"boolean": BOOLEAN, "numeric": NUMERIC, "string": STRING}[literal_kind(value)]

from __future__ import annotations

import json
from typing import Any, Sequence


class FunctionTemplateError(ValueError):
    pass


_UNARY = {"abs": "numeric", "negate": "numeric", "not": "boolean"}
_NUMERIC_BINARY = {"add", "subtract", "multiply", "safe_divide", "greatest"}
_COMPARISON = {
    "greater_than",
    "greater_equal",
    "less_than",
    "less_equal",
    "equal",
    "not_equal",
}
_BOOLEAN_BINARY = {"and", "or"}


def validate_expression_template(
    template: Any,
    *,
    arg_types: Sequence[str],
    result_kind: str,
) -> dict[str, Any]:
    normalized = json.loads(json.dumps(template, ensure_ascii=False))
    nodes = [0]
    inferred = _infer_kind(
        normalized,
        arg_types=tuple(arg_types),
        depth=0,
        nodes=nodes,
    )
    if inferred != result_kind:
        raise FunctionTemplateError(
            f"function template returns {inferred}, expected {result_kind}"
        )
    return normalized


def _infer_kind(
    node: Any,
    *,
    arg_types: tuple[str, ...],
    depth: int,
    nodes: list[int],
) -> str:
    nodes[0] += 1
    if depth > 16 or nodes[0] > 64:
        raise FunctionTemplateError("function template exceeds depth or node limit")
    if not isinstance(node, dict):
        raise FunctionTemplateError("function template node must be an object")
    if set(node) == {"arg"}:
        index = node["arg"]
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(arg_types):
            raise FunctionTemplateError(f"invalid function template argument: {index}")
        return arg_types[index]
    if set(node) == {"literal"}:
        return literal_kind(node["literal"])
    if set(node) != {"op", "args"} or not isinstance(node["args"], list):
        raise FunctionTemplateError("function template node has unsupported fields")
    operation = str(node["op"])
    children = tuple(
        _infer_kind(item, arg_types=arg_types, depth=depth + 1, nodes=nodes)
        for item in node["args"]
    )
    if operation in _UNARY:
        _require_arity(operation, children, 1)
        _require_kind(operation, children, _UNARY[operation])
        return _UNARY[operation]
    if operation in _NUMERIC_BINARY:
        _require_arity(operation, children, 2)
        _require_kind(operation, children, "numeric")
        return "numeric"
    if operation in _COMPARISON:
        _require_arity(operation, children, 2)
        if operation not in {"equal", "not_equal"}:
            _require_kind(operation, children, "numeric")
        elif children[0] != children[1]:
            raise FunctionTemplateError(f"{operation} requires matching argument kinds")
        return "boolean"
    if operation in _BOOLEAN_BINARY:
        _require_arity(operation, children, 2)
        _require_kind(operation, children, "boolean")
        return "boolean"
    if operation == "coalesce":
        if len(children) < 2 or len(set(children)) != 1:
            raise FunctionTemplateError("coalesce requires at least two matching arguments")
        return children[0]
    raise FunctionTemplateError(f"unsupported function template operation: {operation}")


def _require_arity(operation: str, children: tuple[str, ...], expected: int) -> None:
    if len(children) != expected:
        raise FunctionTemplateError(f"{operation} requires {expected} arguments")


def _require_kind(operation: str, children: tuple[str, ...], expected: str) -> None:
    if any(item != expected for item in children):
        raise FunctionTemplateError(f"{operation} requires {expected} arguments")


def literal_kind(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "numeric"
    if isinstance(value, str):
        return "string"
    raise FunctionTemplateError("function template literal must be boolean, numeric, or string")

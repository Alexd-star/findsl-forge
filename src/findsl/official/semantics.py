from __future__ import annotations

import re
from typing import Any, Callable, Optional

from .signatures import OFFICIAL_FUNCTION_SIGNATURES, FunctionSignature
from .ast import OfficialFunctionCall, OfficialLiteral, iter_child_nodes
from .typed_ast import FunctionBinding, TypedNode
from .types import BOOLEAN, NUMERIC, STRING, TIME, UNKNOWN, OfficialType, RangeType


IndicatorResolver = Callable[[str], Optional[Any]]

_TIME_LITERAL = re.compile(
    r"(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?(?:\.\d+)?"
)


class OfficialSemanticAnalyzer:
    def __init__(self, indicator_resolver: IndicatorResolver):
        self._indicator_resolver = indicator_resolver

    def validate(self, node: Any) -> str:
        return self.analyze(node).type.legacy_name

    def analyze(self, node: Any) -> TypedNode:
        return self._build_typed(node)

    def _build_typed(self, node: Any) -> TypedNode:
        inferred = self._infer(node)
        children = tuple(self._build_typed(child) for child in iter_child_nodes(node))
        binding = None
        if isinstance(node, OfficialFunctionCall):
            signature = OFFICIAL_FUNCTION_SIGNATURES[node.name]
            binding = FunctionBinding.create(
                signature,
                {
                    slot: arg.value
                    for slot, arg in zip(signature.slots, node.args)
                    if isinstance(arg, OfficialLiteral)
                },
            )
        return TypedNode(node, self._type_from_legacy(inferred), children, binding)

    @staticmethod
    def _type_from_legacy(value: str) -> OfficialType:
        basic = {
            "boolean": BOOLEAN,
            "numeric": NUMERIC,
            "string": STRING,
            "time": TIME,
            "unknown": UNKNOWN,
        }
        if value in basic:
            return basic[value]
        if value.startswith("range["):
            parts = value[6:-1].split(",")
            element = basic.get(parts[0], UNKNOWN)
            if any(basic.get(part, UNKNOWN) is not element for part in parts):
                element = UNKNOWN
            return RangeType(element)
        return UNKNOWN

    def _infer(self, node: Any) -> str:
        from ..official_slot import (
            OfficialBinaryOp,
            OfficialComparison,
            OfficialFunctionCall,
            OfficialIdentifier,
            OfficialLimit,
            OfficialLiteral,
            OfficialRangeLiteral,
            OfficialSlotError,
        )

        if isinstance(node, OfficialLiteral):
            return self._literal_kind(node.value)
        if isinstance(node, OfficialIdentifier):
            raise OfficialSlotError(
                "OFFICIAL_TYPE_ERROR",
                f"Bare identifier is not a valid official DSL expression: {node.name}",
            )
        if isinstance(node, OfficialFunctionCall):
            return self._infer_function(node)
        if isinstance(node, OfficialBinaryOp):
            left_kind = self._infer(node.left)
            right_kind = self._infer(node.right)
            if node.op in {"+", "-", "*", "/"}:
                self._require_numeric(node.op, left_kind, right_kind)
                return "unknown" if "unknown" in {left_kind, right_kind} else "numeric"
            if node.op in {"and", "or", "then"}:
                self._require_boolean(node.op, left_kind, right_kind)
                return "boolean"
            raise OfficialSlotError(
                "OFFICIAL_TYPE_ERROR",
                f"Unsupported official binary operator for semantic analysis: {node.op}",
            )
        if isinstance(node, OfficialComparison):
            return self._infer_comparison(node)
        if isinstance(node, OfficialLimit):
            return self._infer(node.expr)
        if isinstance(node, OfficialRangeLiteral):
            lower_kind = self._infer(node.lower)
            upper_kind = self._infer(node.upper)
            self._require_ordered_compatible("between", lower_kind, upper_kind)
            return f"range[{lower_kind},{upper_kind}]"
        raise OfficialSlotError(
            "OFFICIAL_TYPE_ERROR",
            f"Unsupported official AST node for semantic analysis: {type(node).__name__}",
        )

    def _infer_function(self, node: Any) -> str:
        from ..official_slot import OfficialLiteral, OfficialSlotError

        signature = OFFICIAL_FUNCTION_SIGNATURES.get(node.name)
        if signature is None:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_FUNCTION",
                f"Unsupported official function: {node.name}",
            )
        if len(node.args) != signature.arity:
            raise OfficialSlotError(
                "OFFICIAL_SLOT_ARITY_ERROR",
                f"{node.name}() expects exactly {signature.arity} args, got {len(node.args)}",
            )
        for index, (slot, arg) in enumerate(zip(signature.slots, node.args), start=1):
            if not isinstance(arg, OfficialLiteral) or not isinstance(arg.value, str):
                raise OfficialSlotError(
                    "OFFICIAL_SLOT_ARG_ERROR",
                    f"{node.name}() slot {index} ({slot}) must be a string literal",
                )
        return self._function_result_kind(node, signature)

    def _function_result_kind(self, node: Any, signature: FunctionSignature) -> str:
        if signature.result_kind != "dynamic":
            return signature.result_kind
        indicator_index = signature.slots.index("indicator_name")
        indicator_name = node.args[indicator_index].value
        if node.name in {"indicator", "queryData"} and not indicator_name:
            return "string"
        meta = self._indicator_resolver(indicator_name)
        if meta is None:
            return "unknown"
        return str(getattr(meta, "kind", "unknown"))

    def _infer_comparison(self, node: Any) -> str:
        from ..official_slot import OfficialRangeLiteral

        left_kind = self._infer(node.left)
        if node.op == "between":
            if not isinstance(node.right, OfficialRangeLiteral):
                from ..official_slot import OfficialSlotError

                raise OfficialSlotError(
                    "OFFICIAL_TYPE_ERROR",
                    "between requires an explicit range literal such as [lower, upper]",
                )
            lower_kind = self._infer(node.right.lower)
            upper_kind = self._infer(node.right.upper)
            self._require_ordered_compatible(node.op, left_kind, lower_kind)
            self._require_ordered_compatible(node.op, left_kind, upper_kind)
            return "boolean"

        right_kind = self._infer(node.right)
        if node.op in {">", "<", ">=", "<="}:
            self._require_ordered_compatible(node.op, left_kind, right_kind)
        elif node.op == "~=":
            self._require_approximate_compatible(left_kind, right_kind)
        else:
            self._require_equality_compatible(node.op, left_kind, right_kind)
        return "boolean"

    def _literal_kind(self, value: Any) -> str:
        from ..official_slot import _is_numeric_percent_literal

        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float)):
            return "numeric"
        if isinstance(value, str):
            if _is_numeric_percent_literal(value):
                return "numeric"
            if _TIME_LITERAL.fullmatch(value):
                return "time"
            return "string"
        return "unknown"

    def _require_numeric(self, op: str, left_kind: str, right_kind: str) -> None:
        from ..official_slot import OfficialSlotError

        invalid = [kind for kind in (left_kind, right_kind) if kind not in {"numeric", "unknown"}]
        if invalid:
            raise OfficialSlotError(
                "OFFICIAL_TYPE_ERROR",
                f"Arithmetic operator {op} requires numeric operands, got {left_kind} and {right_kind}",
            )

    def _require_boolean(self, op: str, left_kind: str, right_kind: str) -> None:
        from ..official_slot import OfficialSlotError

        invalid = [kind for kind in (left_kind, right_kind) if kind not in {"boolean", "unknown"}]
        if invalid:
            raise OfficialSlotError(
                "OFFICIAL_TYPE_ERROR",
                f"Logical operator {op} requires boolean operands, got {left_kind} and {right_kind}",
            )

    def _require_ordered_compatible(self, op: str, left_kind: str, right_kind: str) -> None:
        from ..official_slot import OfficialSlotError

        if "unknown" in {left_kind, right_kind}:
            return
        if left_kind == right_kind and left_kind in {"numeric", "time"}:
            return
        raise OfficialSlotError(
            "OFFICIAL_TYPE_ERROR",
            f"Ordered comparison {op} requires matching numeric or time operands, got {left_kind} and {right_kind}",
        )

    def _require_equality_compatible(self, op: str, left_kind: str, right_kind: str) -> None:
        from ..official_slot import OfficialSlotError

        if "unknown" in {left_kind, right_kind} or left_kind == right_kind:
            return
        raise OfficialSlotError(
            "OFFICIAL_TYPE_ERROR",
            f"Comparison {op} requires compatible operands, got {left_kind} and {right_kind}",
        )

    def _require_approximate_compatible(self, left_kind: str, right_kind: str) -> None:
        from ..official_slot import OfficialSlotError

        if "unknown" in {left_kind, right_kind}:
            return
        if left_kind == right_kind and left_kind in {"numeric", "string"}:
            return
        raise OfficialSlotError(
            "OFFICIAL_TYPE_ERROR",
            f"Approximate comparison ~= requires numeric or string operands, got {left_kind} and {right_kind}",
        )

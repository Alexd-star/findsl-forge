from __future__ import annotations

from datetime import date

from .ast_nodes import BinaryOp, Comparison, FunctionCall, Identifier, Literal, Node
from .errors import SemanticError
from .registry import Registry


class SemanticAnalyzer:
    def __init__(self, registry: Registry):
        self.registry = registry

    def validate(self, node: Node) -> str:
        return self._validate_node(node)

    def _validate_node(self, node: Node) -> str:
        if isinstance(node, Literal):
            if isinstance(node.value, (int, float)):
                return "numeric"
            return "string"
        if isinstance(node, Identifier):
            if node.name.lower() in {"asc", "desc"}:
                return "order"
            return "identifier"
        if isinstance(node, Comparison):
            left_type = self._validate_node(node.left)
            right_type = self._validate_node(node.right)
            if left_type == "identifier":
                raise SemanticError(_bare_identifier_message(node.left, "Left"))
            if right_type == "identifier":
                raise SemanticError(_bare_identifier_message(node.right, "Right"))
            if left_type != "numeric":
                raise SemanticError(f"Left side of comparison must be numeric, got {left_type}")
            if right_type != "numeric":
                raise SemanticError(f"Right side of comparison must be numeric, got {right_type}")
            return "boolean"
        if isinstance(node, BinaryOp):
            left_type = self._validate_node(node.left)
            right_type = self._validate_node(node.right)
            if node.op in {"&", "|"}:
                if left_type != "boolean" or right_type != "boolean":
                    raise SemanticError(f"Operator {node.op} requires boolean operands")
                return "boolean"
            if left_type != "numeric" or right_type != "numeric":
                raise SemanticError(f"Operator {node.op} requires numeric operands")
            return "numeric"
        if isinstance(node, FunctionCall):
            return self._validate_call(node)
        raise SemanticError(f"Unsupported AST node: {node!r}")

    def _validate_call(self, node: FunctionCall) -> str:
        meta = self.registry.function(node.name)
        min_args = int(meta.get("min_args", 0))
        max_args = int(meta.get("max_args", 999))
        if not (min_args <= len(node.args) <= max_args):
            raise SemanticError(f"{node.name} expects {min_args}-{max_args} args, got {len(node.args)}")
        allowed_named = set(meta.get("named_args", []))
        for named in node.named_args or []:
            if named.name not in allowed_named:
                raise SemanticError(f"{node.name} does not allow named arg {named.name}")
            self._validate_node(named.value)
        name = node.name.upper()
        if name == "FILTER":
            self._validate_filter(node)
        elif name == "THEN":
            self._validate_then(node)
        elif name == "RANK":
            self._validate_rank(node)
        elif name == "INDICATOR":
            indicator_name = _symbol_arg(node.args[0], "indicator")
            self.registry.indicator(indicator_name)
        elif name == "MARKET":
            _symbol_arg(node.args[0], "market")
        elif name == "DATE_BETWEEN":
            self._validate_date_between(node)
        elif name in {"CONS", "EXIST"}:
            cond_type = self._validate_node(node.args[0])
            if cond_type != "boolean":
                raise SemanticError(f"{node.name} first argument must be boolean")
            self._validate_window_arg(node.args[1], node.name)
        elif name in {"MA", "SUM", "MAX", "MIN"}:
            value_type = self._validate_node(node.args[0])
            if value_type != "numeric":
                raise SemanticError(f"{node.name} first argument must be numeric")
            self._validate_window_arg(node.args[1], node.name)
        else:
            for arg in node.args:
                self._validate_node(arg)
        return str(meta.get("return_type", "unknown"))

    def _validate_filter(self, node: FunctionCall) -> None:
        condition_type = self._validate_node(node.args[0])
        if condition_type != "boolean":
            raise SemanticError(
                f"filter() condition must be boolean, got {condition_type}; "
                "wrap numeric expressions in comparisons"
            )

    def _validate_then(self, node: FunctionCall) -> None:
        for index, stage in enumerate(node.args, 1):
            if not isinstance(stage, FunctionCall) or stage.name.lower() not in {"filter", "rank"}:
                raise SemanticError("then() stages must be relation-producing filter() or rank() calls")
            stage_type = self._validate_node(stage)
            if stage_type != "relation":
                raise SemanticError(f"then() stage {index} must produce a relation, got {stage_type}")

    def _validate_window_arg(self, node: Node, function_name: str) -> None:
        if not isinstance(node, Literal) or not isinstance(node.value, int):
            raise SemanticError(f"{function_name} window must be an integer literal")
        if node.value <= 0:
            raise SemanticError(f"{function_name} window must be positive")

    def _validate_rank(self, node: FunctionCall) -> None:
        value_type = self._validate_node(node.args[0])
        order_type = self._validate_node(node.args[1])
        if value_type != "numeric":
            raise SemanticError("rank() first argument must be numeric")
        if order_type != "order":
            raise SemanticError("rank() second argument must be asc or desc")
        order = node.args[1].name.lower() if isinstance(node.args[1], Identifier) else ""
        limit_names = [named.name for named in node.named_args or [] if named.name in {"top", "bottom", "percent"}]
        if len(limit_names) > 1:
            raise SemanticError("rank() accepts only one of top, bottom, or percent")
        for named in node.named_args or []:
            if named.name == "top" and order != "desc":
                raise SemanticError("rank() top must use desc order; use bottom with asc order for low-value picks")
            if named.name == "bottom" and order != "asc":
                raise SemanticError("rank() bottom must use asc order; use top with desc order for high-value picks")
            if named.name in {"top", "bottom"}:
                if not isinstance(named.value, Literal) or not isinstance(named.value.value, int):
                    raise SemanticError(f"rank() {named.name} must be an integer literal")
                if named.value.value <= 0:
                    raise SemanticError(f"rank() {named.name} must be positive")
            if named.name == "percent":
                if not isinstance(named.value, Literal) or not isinstance(named.value.value, (int, float)):
                    raise SemanticError("rank() percent must be a numeric literal")
                if not (0 < float(named.value.value) <= 100):
                    raise SemanticError("rank() percent must satisfy 0 < percent <= 100")

    def _validate_date_between(self, node: FunctionCall) -> None:
        start = _date_arg(node.args[0], "date_between")
        end = _date_arg(node.args[1], "date_between")
        if start > end:
            raise SemanticError("date_between() start date must be <= end date")


def _symbol_arg(node: Node, function_name: str) -> str:
    if isinstance(node, Literal) and isinstance(node.value, str):
        return node.value
    if isinstance(node, Identifier):
        return node.name
    raise SemanticError(f"{function_name}() requires a string or identifier argument")


def _bare_identifier_message(node: Node, side: str) -> str:
    name = node.name if isinstance(node, Identifier) else "<unknown>"
    return (
        f"{side} side of comparison uses bare identifier {name}; "
        f'wrap configured fields with indicator("{name}")'
    )


def _date_arg(node: Node, function_name: str) -> date:
    if not isinstance(node, Literal) or not isinstance(node.value, str):
        raise SemanticError(f"{function_name}() requires ISO date string arguments")
    try:
        return date.fromisoformat(node.value)
    except ValueError as exc:
        raise SemanticError(f"{function_name}() requires ISO date strings like 2026-01-01") from exc

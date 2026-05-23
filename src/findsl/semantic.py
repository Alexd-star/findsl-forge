from __future__ import annotations

from .ast_nodes import BinaryOp, Comparison, FunctionCall, Identifier, Literal, Node
from .errors import SemanticError
from .registry import Registry


class SemanticAnalyzer:
    def __init__(self, registry: Registry):
        self.registry = registry

    def validate(self, node: Node) -> None:
        self._validate_node(node)

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
            if left_type not in {"numeric", "identifier"}:
                raise SemanticError(f"Left side of comparison must be numeric, got {left_type}")
            if right_type not in {"numeric", "identifier"}:
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
        if name == "RANK":
            self._validate_rank(node)
        if name == "INDICATOR":
            indicator_name = _symbol_arg(node.args[0], "indicator")
            self.registry.indicator(indicator_name)
        if name in {"CONS", "EXIST"}:
            cond_type = self._validate_node(node.args[0])
            window_type = self._validate_node(node.args[1])
            if cond_type != "boolean":
                raise SemanticError(f"{node.name} first argument must be boolean")
            if window_type != "numeric":
                raise SemanticError(f"{node.name} window must be numeric")
            if isinstance(node.args[1], Literal) and int(node.args[1].value) <= 0:
                raise SemanticError(f"{node.name} window must be positive")
        elif name in {"MA", "SUM", "MAX", "MIN"}:
            value_type = self._validate_node(node.args[0])
            window_type = self._validate_node(node.args[1])
            if value_type != "numeric":
                raise SemanticError(f"{node.name} first argument must be numeric")
            if window_type != "numeric":
                raise SemanticError(f"{node.name} window must be numeric")
        else:
            for arg in node.args:
                self._validate_node(arg)
        return str(meta.get("return_type", "unknown"))

    def _validate_rank(self, node: FunctionCall) -> None:
        value_type = self._validate_node(node.args[0])
        order_type = self._validate_node(node.args[1])
        if value_type != "numeric":
            raise SemanticError("rank() first argument must be numeric")
        if order_type != "order":
            raise SemanticError("rank() second argument must be asc or desc")
        limit_names = [named.name for named in node.named_args or [] if named.name in {"top", "bottom", "percent"}]
        if len(limit_names) > 1:
            raise SemanticError("rank() accepts only one of top, bottom, or percent")
        for named in node.named_args or []:
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


def _symbol_arg(node: Node, function_name: str) -> str:
    if isinstance(node, Literal) and isinstance(node.value, str):
        return node.value
    if isinstance(node, Identifier):
        return node.name
    raise SemanticError(f"{function_name}() requires a string or identifier argument")

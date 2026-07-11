from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


class OfficialNode:
    def to_dict(self) -> Dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class OfficialLiteral(OfficialNode):
    value: Any

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "Literal", "value": self.value}


@dataclass(frozen=True)
class OfficialIdentifier(OfficialNode):
    name: str

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "Identifier", "name": self.name}


@dataclass(frozen=True)
class OfficialFunctionCall(OfficialNode):
    name: str
    args: List[OfficialNode]

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "FunctionCall", "name": self.name, "args": [arg.to_dict() for arg in self.args]}


@dataclass(frozen=True)
class OfficialBinaryOp(OfficialNode):
    op: str
    left: OfficialNode
    right: OfficialNode

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "BinaryOp", "op": self.op, "left": self.left.to_dict(), "right": self.right.to_dict()}


@dataclass(frozen=True)
class OfficialComparison(OfficialNode):
    op: str
    left: OfficialNode
    right: OfficialNode

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "Comparison", "op": self.op, "left": self.left.to_dict(), "right": self.right.to_dict()}


@dataclass(frozen=True)
class OfficialLimit(OfficialNode):
    expr: OfficialNode
    lower: int
    upper: int

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "Limit", "lower": self.lower, "upper": self.upper, "expr": self.expr.to_dict()}


@dataclass(frozen=True)
class OfficialRangeLiteral(OfficialNode):
    lower: OfficialNode
    upper: OfficialNode
    lower_inclusive: bool
    upper_inclusive: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "RangeLiteral",
            "lower": self.lower.to_dict(),
            "upper": self.upper.to_dict(),
            "lower_inclusive": self.lower_inclusive,
            "upper_inclusive": self.upper_inclusive,
        }


def iter_child_nodes(node: OfficialNode) -> Iterable[OfficialNode]:
    if isinstance(node, OfficialFunctionCall):
        yield from node.args
    elif isinstance(node, (OfficialBinaryOp, OfficialComparison)):
        yield node.left
        yield node.right
    elif isinstance(node, OfficialLimit):
        yield node.expr
    elif isinstance(node, OfficialRangeLiteral):
        yield node.lower
        yield node.upper


def walk(node: OfficialNode) -> Iterable[OfficialNode]:
    yield node
    for child in iter_child_nodes(node):
        yield from walk(child)

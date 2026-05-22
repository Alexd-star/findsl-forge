from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class Node:
    def to_dict(self) -> Dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class Literal(Node):
    value: Any

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "Literal", "value": self.value}


@dataclass(frozen=True)
class Identifier(Node):
    name: str

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "Identifier", "name": self.name}


@dataclass(frozen=True)
class NamedArg:
    name: str
    value: Node

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "value": self.value.to_dict()}


@dataclass(frozen=True)
class FunctionCall(Node):
    name: str
    args: List[Node]
    named_args: Optional[List[NamedArg]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "FunctionCall",
            "name": self.name,
            "args": [arg.to_dict() for arg in self.args],
            "named_args": [arg.to_dict() for arg in self.named_args or []],
        }


@dataclass(frozen=True)
class BinaryOp(Node):
    op: str
    left: Node
    right: Node

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "BinaryOp",
            "op": self.op,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
        }


@dataclass(frozen=True)
class Comparison(Node):
    op: str
    left: Node
    right: Node

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "Comparison",
            "op": self.op,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
        }


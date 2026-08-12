from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from ..typed_ast import FunctionBinding
from ..types import BOOLEAN, OfficialType, RangeType
from .base import CanonicalIr


class LogicalExpr(CanonicalIr):
    type: OfficialType


@dataclass(frozen=True)
class LiteralExpr(LogicalExpr):
    value: Any
    type: OfficialType

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "LiteralExpr", "value": self.value, "type": self.type.to_dict()}


@dataclass(frozen=True)
class FieldRef(LogicalExpr):
    name: str
    type: OfficialType
    qualifier: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "FieldRef", "name": self.name, "qualifier": self.qualifier, "type": self.type.to_dict()}


@dataclass(frozen=True)
class CallExpr(LogicalExpr):
    name: str
    args: Tuple[LogicalExpr, ...]
    type: OfficialType
    binding: Optional[FunctionBinding] = None
    date_constraint: Optional[Any] = None
    market_expression: Optional[Any] = None
    scope_expression: Optional[Any] = None
    entity_target: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "CallExpr",
            "name": self.name,
            "args": [arg.to_dict() for arg in self.args],
            "type": self.type.to_dict(),
            "binding": self.binding.to_dict() if self.binding else None,
            "date_constraint": self.date_constraint.to_dict() if self.date_constraint else None,
            "market_expression": self.market_expression.to_dict() if self.market_expression else None,
            "scope_expression": self.scope_expression.to_dict() if self.scope_expression else None,
            "entity_target": self.entity_target.to_dict() if self.entity_target else None,
        }


@dataclass(frozen=True)
class BinaryExpr(LogicalExpr):
    op: str
    left: LogicalExpr
    right: LogicalExpr
    type: OfficialType

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "BinaryExpr", "op": self.op, "left": self.left.to_dict(), "right": self.right.to_dict(), "type": self.type.to_dict()}


@dataclass(frozen=True)
class ComparisonExpr(LogicalExpr):
    op: str
    left: LogicalExpr
    right: LogicalExpr
    type: OfficialType = BOOLEAN

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "ComparisonExpr", "op": self.op, "left": self.left.to_dict(), "right": self.right.to_dict(), "type": self.type.to_dict()}


@dataclass(frozen=True)
class RangeExpr(LogicalExpr):
    lower: LogicalExpr
    upper: LogicalExpr
    lower_inclusive: bool
    upper_inclusive: bool
    element_type: OfficialType

    @property
    def type(self) -> RangeType:
        return RangeType(self.element_type)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "RangeExpr",
            "lower": self.lower.to_dict(),
            "upper": self.upper.to_dict(),
            "lower_inclusive": self.lower_inclusive,
            "upper_inclusive": self.upper_inclusive,
            "type": self.type.to_dict(),
        }

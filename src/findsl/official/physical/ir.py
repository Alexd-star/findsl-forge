from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple

from ..ir.base import CanonicalIr
from ..types import BOOLEAN, OfficialType


class PhysicalExpr(CanonicalIr):
    type: OfficialType


@dataclass(frozen=True)
class PhysicalColumn(PhysicalExpr):
    resource_id: str
    column: str
    type: OfficialType

    def to_dict(self):
        return {"kind": "PhysicalColumn", "resource_id": self.resource_id, "column": self.column, "type": self.type.to_dict()}


@dataclass(frozen=True)
class PhysicalLiteral(PhysicalExpr):
    value: Any
    type: OfficialType

    def to_dict(self):
        return {"kind": "PhysicalLiteral", "value": self.value, "type": self.type.to_dict()}


@dataclass(frozen=True)
class PhysicalBinary(PhysicalExpr):
    op: str
    left: PhysicalExpr
    right: PhysicalExpr
    type: OfficialType

    def to_dict(self):
        return {"kind": "PhysicalBinary", "op": self.op, "left": self.left.to_dict(), "right": self.right.to_dict(), "type": self.type.to_dict()}


@dataclass(frozen=True)
class PhysicalComparison(PhysicalExpr):
    op: str
    left: PhysicalExpr
    right: PhysicalExpr
    type: OfficialType = BOOLEAN

    def to_dict(self):
        return {"kind": "PhysicalComparison", "op": self.op, "left": self.left.to_dict(), "right": self.right.to_dict(), "type": self.type.to_dict()}


@dataclass(frozen=True)
class PhysicalIn(PhysicalExpr):
    expression: PhysicalExpr
    values: Tuple[PhysicalLiteral, ...]
    type: OfficialType = BOOLEAN

    def to_dict(self):
        return {"kind": "PhysicalIn", "expression": self.expression.to_dict(), "values": [value.to_dict() for value in self.values], "type": self.type.to_dict()}


@dataclass(frozen=True)
class PhysicalLatestValue(PhysicalExpr):
    resource_id: str
    column: str
    type: OfficialType

    def to_dict(self):
        return {"kind": "PhysicalLatestValue", "resource_id": self.resource_id, "column": self.column, "type": self.type.to_dict()}


class PhysicalPlan(CanonicalIr):
    pass


@dataclass(frozen=True)
class PhysicalScan(PhysicalPlan):
    resource_id: str
    columns: Tuple[PhysicalColumn, ...]
    partition_predicate: Optional[PhysicalExpr]
    anchor_resource_id: Optional[str] = None

    def to_dict(self):
        return {"kind": "PhysicalScan", "resource_id": self.resource_id, "columns": [item.to_dict() for item in self.columns], "partition_predicate": self.partition_predicate.to_dict() if self.partition_predicate else None, "anchor_resource_id": self.anchor_resource_id}


@dataclass(frozen=True)
class PhysicalFilter(PhysicalPlan):
    input: PhysicalPlan
    predicate: PhysicalExpr

    def to_dict(self):
        return {"kind": "PhysicalFilter", "input": self.input.to_dict(), "predicate": self.predicate.to_dict()}


@dataclass(frozen=True)
class PhysicalJoin(PhysicalPlan):
    left: PhysicalPlan
    right: PhysicalPlan
    join_type: str
    keys: Tuple[Tuple[PhysicalColumn, PhysicalColumn], ...]

    def to_dict(self):
        return {"kind": "PhysicalJoin", "left": self.left.to_dict(), "right": self.right.to_dict(), "join_type": self.join_type, "keys": [[a.to_dict(), b.to_dict()] for a, b in self.keys]}


@dataclass(frozen=True)
class PhysicalAggregate(PhysicalPlan):
    input: PhysicalPlan
    group_keys: Tuple[PhysicalExpr, ...]
    measures: Tuple[Tuple[str, PhysicalExpr], ...]

    def to_dict(self):
        return {"kind": "PhysicalAggregate", "input": self.input.to_dict(), "group_keys": [item.to_dict() for item in self.group_keys], "measures": [{"name": name, "expr": expr.to_dict()} for name, expr in self.measures]}


@dataclass(frozen=True)
class PhysicalWindow(PhysicalPlan):
    input: PhysicalPlan
    expressions: Tuple[Tuple[str, PhysicalExpr], ...]
    partition_by: Tuple[PhysicalExpr, ...]
    order_by: Tuple[PhysicalExpr, ...]

    def to_dict(self):
        return {"kind": "PhysicalWindow", "input": self.input.to_dict(), "expressions": [{"name": n, "expr": e.to_dict()} for n, e in self.expressions], "partition_by": [e.to_dict() for e in self.partition_by], "order_by": [e.to_dict() for e in self.order_by]}


@dataclass(frozen=True)
class PhysicalRank(PhysicalPlan):
    input: PhysicalPlan
    expression: PhysicalExpr
    direction: str
    bound: PhysicalLiteral
    comparator: str = "<="

    def to_dict(self):
        return {"kind": "PhysicalRank", "input": self.input.to_dict(), "expression": self.expression.to_dict(), "direction": self.direction, "bound": self.bound.to_dict(), "comparator": self.comparator}


@dataclass(frozen=True)
class PhysicalLimit(PhysicalPlan):
    input: PhysicalPlan
    offset: int
    count: int

    def to_dict(self):
        return {"kind": "PhysicalLimit", "input": self.input.to_dict(), "offset": self.offset, "count": self.count}


@dataclass(frozen=True)
class PhysicalPrefixLookup(PhysicalPlan):
    input: PhysicalPlan
    resource_id: str
    value_column: str
    window: int

    def to_dict(self):
        return {"kind": "PhysicalPrefixLookup", "input": self.input.to_dict(), "resource_id": self.resource_id, "value_column": self.value_column, "window": self.window}


@dataclass(frozen=True)
class PhysicalEmpty(PhysicalPlan):
    proven_reason: str

    def to_dict(self):
        return {"kind": "PhysicalEmpty", "proven_reason": self.proven_reason}

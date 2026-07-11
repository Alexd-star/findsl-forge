from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from ..types import OfficialType
from .base import CanonicalIr
from .expressions import LogicalExpr


@dataclass(frozen=True)
class Field:
    name: str
    type: OfficialType
    nullable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "type": self.type.to_dict(), "nullable": self.nullable}


@dataclass(frozen=True)
class Schema:
    fields: Tuple[Field, ...]

    def __post_init__(self) -> None:
        names = [field.name for field in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("duplicate field name in logical schema")

    def to_dict(self) -> Dict[str, Any]:
        return {"fields": [field.to_dict() for field in self.fields]}


class LogicalPlan(CanonicalIr):
    schema: Schema


def _plan(kind: str, schema: Schema, **values: Any) -> Dict[str, Any]:
    result = {"kind": kind, **values, "schema": schema.to_dict()}
    return result


@dataclass(frozen=True)
class LogicalScan(LogicalPlan):
    entity: str
    schema: Schema

    def to_dict(self):
        return _plan("LogicalScan", self.schema, entity=self.entity)


@dataclass(frozen=True)
class LogicalDomainScan(LogicalPlan):
    entity: str
    requirements: Any
    schema: Schema

    def to_dict(self):
        return _plan("LogicalDomainScan", self.schema, entity=self.entity, requirements=self.requirements.to_dict())


@dataclass(frozen=True)
class LogicalEmpty(LogicalPlan):
    schema: Schema
    reason: str

    def to_dict(self):
        return _plan("LogicalEmpty", self.schema, reason=self.reason)


@dataclass(frozen=True)
class LogicalEvent(LogicalPlan):
    input: LogicalPlan
    event: Any
    schema: Schema

    def to_dict(self):
        return _plan("LogicalEvent", self.schema, input=self.input.to_dict(), event=self.event.to_dict())


@dataclass(frozen=True)
class LogicalConsecutive(LogicalPlan):
    input: LogicalPlan
    spec: Any
    schema: Schema

    def to_dict(self):
        return _plan("LogicalConsecutive", self.schema, input=self.input.to_dict(), spec=self.spec.to_dict())


@dataclass(frozen=True)
class LogicalExist(LogicalPlan):
    input: LogicalPlan
    spec: Any
    schema: Schema

    def to_dict(self):
        return _plan("LogicalExist", self.schema, input=self.input.to_dict(), spec=self.spec.to_dict())


@dataclass(frozen=True)
class LogicalDomainRank(LogicalPlan):
    input: LogicalPlan
    spec: Any
    schema: Schema

    def to_dict(self):
        return _plan("LogicalDomainRank", self.schema, input=self.input.to_dict(), spec=self.spec.to_dict())


@dataclass(frozen=True)
class LogicalConstraint(LogicalPlan):
    input: LogicalPlan
    market_scope: Any
    date_constraint: Any
    schema: Schema

    def to_dict(self):
        return _plan("LogicalConstraint", self.schema, input=self.input.to_dict(), market_scope=self.market_scope.to_dict(), date_constraint=self.date_constraint.to_dict())


@dataclass(frozen=True)
class LogicalFilter(LogicalPlan):
    input: LogicalPlan
    predicate: LogicalExpr
    schema: Schema

    def to_dict(self):
        return _plan("LogicalFilter", self.schema, input=self.input.to_dict(), predicate=self.predicate.to_dict())


@dataclass(frozen=True)
class LogicalProject(LogicalPlan):
    input: LogicalPlan
    expressions: Tuple[Tuple[str, LogicalExpr], ...]
    schema: Schema

    def to_dict(self):
        return _plan("LogicalProject", self.schema, input=self.input.to_dict(), expressions=[{"name": n, "expr": e.to_dict()} for n, e in self.expressions])


@dataclass(frozen=True)
class LogicalAggregate(LogicalPlan):
    input: LogicalPlan
    group_keys: Tuple[LogicalExpr, ...]
    measures: Tuple[Tuple[str, LogicalExpr], ...]
    schema: Schema

    def to_dict(self):
        return _plan("LogicalAggregate", self.schema, input=self.input.to_dict(), group_keys=[e.to_dict() for e in self.group_keys], measures=[{"name": n, "expr": e.to_dict()} for n, e in self.measures])


@dataclass(frozen=True)
class LogicalWindow(LogicalPlan):
    input: LogicalPlan
    expressions: Tuple[Tuple[str, LogicalExpr], ...]
    schema: Schema

    def to_dict(self):
        return _plan("LogicalWindow", self.schema, input=self.input.to_dict(), expressions=[{"name": n, "expr": e.to_dict()} for n, e in self.expressions])


@dataclass(frozen=True)
class LogicalRank(LogicalPlan):
    input: LogicalPlan
    order_by: LogicalExpr
    direction: str
    bound: LogicalExpr
    schema: Schema

    def to_dict(self):
        return _plan("LogicalRank", self.schema, input=self.input.to_dict(), order_by=self.order_by.to_dict(), direction=self.direction, bound=self.bound.to_dict())


@dataclass(frozen=True)
class LogicalStage(LogicalPlan):
    input: LogicalPlan
    stage_index: int
    operation: LogicalPlan
    schema: Schema

    def to_dict(self):
        return _plan("LogicalStage", self.schema, input=self.input.to_dict(), stage_index=self.stage_index, operation=self.operation.to_dict())


@dataclass(frozen=True)
class LogicalLimit(LogicalPlan):
    input: LogicalPlan
    offset: int
    count: int
    schema: Schema

    def to_dict(self):
        return _plan("LogicalLimit", self.schema, input=self.input.to_dict(), offset=self.offset, count=self.count)

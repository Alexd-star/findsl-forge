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
class PhysicalUnary(PhysicalExpr):
    op: str
    operand: PhysicalExpr
    type: OfficialType

    def to_dict(self):
        return {"kind": "PhysicalUnary", "op": self.op, "operand": self.operand.to_dict(), "type": self.type.to_dict()}


@dataclass(frozen=True)
class PhysicalNot(PhysicalExpr):
    operand: PhysicalExpr
    type: OfficialType = BOOLEAN

    def to_dict(self):
        return {
            "kind": "PhysicalNot",
            "operand": self.operand.to_dict(),
            "type": self.type.to_dict(),
        }


@dataclass(frozen=True)
class PhysicalNullIf(PhysicalExpr):
    expression: PhysicalExpr
    null_value: PhysicalExpr
    type: OfficialType

    def to_dict(self):
        return {"kind": "PhysicalNullIf", "expression": self.expression.to_dict(), "null_value": self.null_value.to_dict(), "type": self.type.to_dict()}


@dataclass(frozen=True)
class PhysicalCoalesce(PhysicalExpr):
    expressions: Tuple[PhysicalExpr, ...]
    type: OfficialType

    def to_dict(self):
        return {"kind": "PhysicalCoalesce", "expressions": [item.to_dict() for item in self.expressions], "type": self.type.to_dict()}


@dataclass(frozen=True)
class PhysicalAbs(PhysicalExpr):
    expression: PhysicalExpr
    type: OfficialType

    def to_dict(self):
        return {"kind": "PhysicalAbs", "expression": self.expression.to_dict(), "type": self.type.to_dict()}


@dataclass(frozen=True)
class PhysicalGreatest(PhysicalExpr):
    expressions: Tuple[PhysicalExpr, ...]
    type: OfficialType

    def to_dict(self):
        return {"kind": "PhysicalGreatest", "expressions": [item.to_dict() for item in self.expressions], "type": self.type.to_dict()}


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
class PhysicalExternalExists(PhysicalExpr):
    lookup_resource_id: str
    anchor_resource_id: str
    filters: Tuple[Tuple[str, PhysicalLiteral], ...]
    type: OfficialType = BOOLEAN
    policy_id: Optional[str] = None
    policy_semantic_basis: Optional[str] = None
    policy_risk_level: Optional[str] = None
    policy_rationale_urls: Tuple[str, ...] = ()

    def to_dict(self):
        payload = {
            "kind": "PhysicalExternalExists",
            "lookup_resource_id": self.lookup_resource_id,
            "anchor_resource_id": self.anchor_resource_id,
            "filters": [
                {"column": column, "value": value.to_dict()}
                for column, value in self.filters
            ],
            "type": self.type.to_dict(),
        }
        if self.policy_id is not None:
            payload["semantic_policy"] = {
                "policy_id": self.policy_id,
                "semantic_basis": self.policy_semantic_basis,
                "risk_level": self.policy_risk_level,
                "rationale_urls": list(self.policy_rationale_urls),
            }
        return payload


@dataclass(frozen=True)
class PhysicalEventRef(PhysicalExpr):
    alias: str
    type: OfficialType = BOOLEAN

    def to_dict(self):
        return {"kind": "PhysicalEventRef", "alias": self.alias, "type": self.type.to_dict()}


@dataclass(frozen=True)
class PhysicalProjectedRef(PhysicalExpr):
    alias: str
    type: OfficialType

    def to_dict(self):
        return {"kind": "PhysicalProjectedRef", "alias": self.alias, "type": self.type.to_dict()}


@dataclass(frozen=True)
class PhysicalPrefixRef(PhysicalExpr):
    alias: str
    type: OfficialType

    def to_dict(self):
        return {
            "kind": "PhysicalPrefixRef",
            "alias": self.alias,
            "type": self.type.to_dict(),
        }


@dataclass(frozen=True)
class PhysicalLatestValue(PhysicalExpr):
    resource_id: str
    column: str
    type: OfficialType

    def to_dict(self):
        return {"kind": "PhysicalLatestValue", "resource_id": self.resource_id, "column": self.column, "type": self.type.to_dict()}


@dataclass(frozen=True)
class PhysicalNthLatestValue(PhysicalExpr):
    resource_id: str
    column: str
    offset: int
    type: OfficialType

    def to_dict(self):
        return {
            "kind": "PhysicalNthLatestValue",
            "resource_id": self.resource_id,
            "column": self.column,
            "offset": self.offset,
            "type": self.type.to_dict(),
        }


@dataclass(frozen=True)
class PhysicalRecentSessions(PhysicalExpr):
    resource_id: str
    column: str
    amount: int
    offset: int = 0
    type: OfficialType = BOOLEAN
    anchor_resource_id: Optional[str] = None

    def to_dict(self):
        return {
            "kind": "PhysicalRecentSessions",
            "resource_id": self.resource_id,
            "column": self.column,
            "amount": self.amount,
            "offset": self.offset,
            "anchor_resource_id": self.anchor_resource_id,
            "type": self.type.to_dict(),
        }


@dataclass(frozen=True)
class PhysicalDynamicDateRange(PhysicalExpr):
    resource_id: str
    column: str
    range_kind: str
    unit: str
    amount: int = 1
    offset: int = 0
    month: Optional[int] = None
    day: Optional[int] = None
    end_month: Optional[int] = None
    anchor_resource_id: Optional[str] = None
    type: OfficialType = BOOLEAN

    def to_dict(self):
        return {
            "kind": "PhysicalDynamicDateRange",
            "resource_id": self.resource_id,
            "column": self.column,
            "range_kind": self.range_kind,
            "unit": self.unit,
            "amount": self.amount,
            "offset": self.offset,
            "month": self.month,
            "day": self.day,
            "end_month": self.end_month,
            "anchor_resource_id": self.anchor_resource_id,
            "type": self.type.to_dict(),
        }


@dataclass(frozen=True)
class PhysicalSessionBoundaryRange(PhysicalExpr):
    resource_id: str
    column: str
    direction: str
    boundary_kind: str
    amount: int
    unit: Optional[str] = None
    offset: int = 0
    boundary_date: Optional[str] = None
    month: Optional[int] = None
    day: Optional[int] = None
    type: OfficialType = BOOLEAN
    anchor_resource_id: Optional[str] = None

    def to_dict(self):
        return {
            "kind": "PhysicalSessionBoundaryRange",
            "resource_id": self.resource_id,
            "column": self.column,
            "direction": self.direction,
            "boundary_kind": self.boundary_kind,
            "amount": self.amount,
            "unit": self.unit,
            "offset": self.offset,
            "boundary_date": self.boundary_date,
            "month": self.month,
            "day": self.day,
            "anchor_resource_id": self.anchor_resource_id,
            "type": self.type.to_dict(),
        }


@dataclass(frozen=True)
class PhysicalPrefixAverage(PhysicalExpr):
    resource_id: str
    sum_column: str
    count_column: str
    window: int
    scale_divisor: float
    type: OfficialType

    def to_dict(self):
        return {
            "kind": "PhysicalPrefixAverage",
            "resource_id": self.resource_id,
            "sum_column": self.sum_column,
            "count_column": self.count_column,
            "window": self.window,
            "scale_divisor": self.scale_divisor,
            "type": self.type.to_dict(),
        }


class PhysicalPlan(CanonicalIr):
    pass


@dataclass(frozen=True)
class PhysicalTemporalWindow(CanonicalIr):
    kind: str
    lookback_sessions: Optional[int] = None
    start: Optional[str] = None
    end: Optional[str] = None
    calendar_amount: Optional[int] = None
    calendar_unit: Optional[str] = None
    calendar_offset: int = 0
    session_offset: int = 0
    anchor_month: Optional[int] = None
    anchor_day: Optional[int] = None
    boundary_direction: Optional[str] = None
    boundary_kind: Optional[str] = None
    boundary_date: Optional[str] = None

    def to_dict(self):
        return {"kind": self.kind, "lookback_sessions": self.lookback_sessions, "start": self.start, "end": self.end, "calendar_amount": self.calendar_amount, "calendar_unit": self.calendar_unit, "calendar_offset": self.calendar_offset, "session_offset": self.session_offset, "anchor_month": self.anchor_month, "anchor_day": self.anchor_day, "boundary_direction": self.boundary_direction, "boundary_kind": self.boundary_kind, "boundary_date": self.boundary_date}


@dataclass(frozen=True)
class PhysicalScan(PhysicalPlan):
    resource_id: str
    columns: Tuple[PhysicalColumn, ...]
    partition_predicate: Optional[PhysicalExpr]
    anchor_resource_id: Optional[str] = None

    def to_dict(self):
        return {"kind": "PhysicalScan", "resource_id": self.resource_id, "columns": [item.to_dict() for item in self.columns], "partition_predicate": self.partition_predicate.to_dict() if self.partition_predicate else None, "anchor_resource_id": self.anchor_resource_id}


@dataclass(frozen=True)
class PhysicalTableScan(PhysicalPlan):
    resource_id: str
    columns: Tuple[PhysicalColumn, ...]
    partition_predicate: Optional[PhysicalExpr] = None

    def to_dict(self):
        return {
            "kind": "PhysicalTableScan",
            "resource_id": self.resource_id,
            "columns": [item.to_dict() for item in self.columns],
            "partition_predicate": self.partition_predicate.to_dict() if self.partition_predicate else None,
        }


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
    percentage: bool = False
    upper_bound: Optional[PhysicalLiteral] = None
    lower_inclusive: bool = True
    upper_inclusive: bool = True

    def to_dict(self):
        return {
            "kind": "PhysicalRank",
            "input": self.input.to_dict(),
            "expression": self.expression.to_dict(),
            "direction": self.direction,
            "bound": self.bound.to_dict(),
            "comparator": self.comparator,
            "percentage": self.percentage,
            "upper_bound": self.upper_bound.to_dict() if self.upper_bound else None,
            "lower_inclusive": self.lower_inclusive,
            "upper_inclusive": self.upper_inclusive,
        }


@dataclass(frozen=True)
class PhysicalGroupedAggregate(PhysicalPlan):
    input: PhysicalPlan
    measure: PhysicalExpr
    function: str
    comparator: str
    bound: PhysicalLiteral
    anchor_resource_id: str

    def to_dict(self):
        return {
            "kind": "PhysicalGroupedAggregate",
            "input": self.input.to_dict(),
            "measure": self.measure.to_dict(),
            "function": self.function,
            "comparator": self.comparator,
            "bound": self.bound.to_dict(),
            "anchor_resource_id": self.anchor_resource_id,
        }


@dataclass(frozen=True)
class PhysicalAggregateRank(PhysicalPlan):
    input: PhysicalPlan
    measure: PhysicalExpr
    function: str
    direction: str
    bound: PhysicalLiteral
    comparator: str
    percentage: bool
    anchor_resource_id: str
    upper_bound: Optional[PhysicalLiteral] = None
    lower_inclusive: bool = True
    upper_inclusive: bool = True

    def to_dict(self):
        return {
            "kind": "PhysicalAggregateRank",
            "input": self.input.to_dict(),
            "measure": self.measure.to_dict(),
            "function": self.function,
            "direction": self.direction,
            "bound": self.bound.to_dict(),
            "comparator": self.comparator,
            "percentage": self.percentage,
            "anchor_resource_id": self.anchor_resource_id,
            "upper_bound": self.upper_bound.to_dict() if self.upper_bound else None,
            "lower_inclusive": self.lower_inclusive,
            "upper_inclusive": self.upper_inclusive,
        }


@dataclass(frozen=True)
class PhysicalCrossing(CanonicalIr):
    alias: str
    left: PhysicalExpr
    right: PhysicalExpr
    direction: str

    def to_dict(self):
        return {
            "kind": "PhysicalCrossing",
            "alias": self.alias,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "direction": self.direction,
        }


@dataclass(frozen=True)
class PhysicalExtreme(CanonicalIr):
    alias: str
    expression: PhysicalExpr
    direction: str
    lookback_sessions: Optional[int] = None

    def to_dict(self):
        return {
            "kind": "PhysicalExtreme",
            "alias": self.alias,
            "expression": self.expression.to_dict(),
            "direction": self.direction,
            "lookback_sessions": self.lookback_sessions,
        }


@dataclass(frozen=True)
class PhysicalProjection(CanonicalIr):
    alias: str
    expression: PhysicalExpr

    def to_dict(self):
        return {
            "kind": "PhysicalProjection",
            "alias": self.alias,
            "expression": self.expression.to_dict(),
        }


@dataclass(frozen=True)
class PhysicalPattern(CanonicalIr):
    alias: str
    predicate: PhysicalExpr
    pattern: str

    def to_dict(self):
        return {
            "kind": "PhysicalPattern",
            "alias": self.alias,
            "predicate": self.predicate.to_dict(),
            "pattern": self.pattern,
        }


@dataclass(frozen=True)
class PhysicalPosition(CanonicalIr):
    alias: str
    expression: PhysicalExpr
    lookback_sessions: Optional[int] = None

    def to_dict(self):
        return {
            "kind": "PhysicalPosition",
            "alias": self.alias,
            "expression": self.expression.to_dict(),
            "lookback_sessions": self.lookback_sessions,
        }


@dataclass(frozen=True)
class PhysicalEventProjection(PhysicalPlan):
    input: PhysicalPlan
    events: Tuple[CanonicalIr, ...]
    projections: Tuple[PhysicalProjection, ...] = ()

    def to_dict(self):
        return {
            "kind": "PhysicalEventProjection",
            "input": self.input.to_dict(),
            "events": [event.to_dict() for event in self.events],
            "projections": [item.to_dict() for item in self.projections],
        }


@dataclass(frozen=True)
class PhysicalEventFilter(PhysicalPlan):
    input: PhysicalPlan
    events: Tuple[CanonicalIr, ...]
    projections: Tuple[PhysicalProjection, ...]
    predicate: PhysicalExpr
    result_constraints: Tuple[PhysicalExpr, ...] = ()
    quantifier: str = "rows"
    eligibility_predicate: Optional[PhysicalExpr] = None
    anchor_resource_id: Optional[str] = None

    def to_dict(self):
        return {
            "kind": "PhysicalEventFilter",
            "input": self.input.to_dict(),
            "events": [event.to_dict() for event in self.events],
            "projections": [item.to_dict() for item in self.projections],
            "predicate": self.predicate.to_dict(),
            "result_constraints": [item.to_dict() for item in self.result_constraints],
            "quantifier": self.quantifier,
            "eligibility_predicate": (
                self.eligibility_predicate.to_dict()
                if self.eligibility_predicate
                else None
            ),
            "anchor_resource_id": self.anchor_resource_id,
        }


@dataclass(frozen=True)
class PhysicalAggregateRef(PhysicalExpr):
    relation_alias: str
    measure_alias: str
    type: OfficialType

    def to_dict(self):
        return {
            "kind": "PhysicalAggregateRef",
            "relation_alias": self.relation_alias,
            "measure_alias": self.measure_alias,
            "type": self.type.to_dict(),
        }


@dataclass(frozen=True)
class PhysicalNamedAggregate(CanonicalIr):
    alias: str
    function: str
    expression: PhysicalExpr

    def to_dict(self):
        return {
            "kind": "PhysicalNamedAggregate",
            "alias": self.alias,
            "function": self.function,
            "expression": self.expression.to_dict(),
        }


@dataclass(frozen=True)
class PhysicalAggregateGroup(CanonicalIr):
    alias: str
    input: PhysicalPlan
    measures: Tuple[PhysicalNamedAggregate, ...]
    group_by_security: bool = True
    industry_membership_resource_id: Optional[str] = None
    industry_snapshot_id: Optional[str] = None
    industry_classification_system: Optional[str] = None
    industry_level: Optional[str] = None

    def to_dict(self):
        return {
            "kind": "PhysicalAggregateGroup",
            "alias": self.alias,
            "input": self.input.to_dict(),
            "measures": [measure.to_dict() for measure in self.measures],
            "group_by_security": self.group_by_security,
            "industry_membership_resource_id": self.industry_membership_resource_id,
            "industry_snapshot_id": self.industry_snapshot_id,
            "industry_classification_system": self.industry_classification_system,
            "industry_level": self.industry_level,
        }


@dataclass(frozen=True)
class PhysicalNamedScalar(CanonicalIr):
    alias: str
    input: PhysicalPlan
    expression: PhysicalExpr
    value_alias: str
    group_by_security: bool = False
    collapse_latest: bool = False
    function: Optional[str] = None

    def to_dict(self):
        return {
            "kind": "PhysicalNamedScalar",
            "alias": self.alias,
            "input": self.input.to_dict(),
            "expression": self.expression.to_dict(),
            "value_alias": self.value_alias,
            "group_by_security": self.group_by_security,
            "collapse_latest": self.collapse_latest,
            "function": self.function,
        }


@dataclass(frozen=True)
class PhysicalCompositeAggregate(PhysicalPlan):
    input: PhysicalPlan
    groups: Tuple[PhysicalAggregateGroup, ...]
    scalars: Tuple[PhysicalNamedScalar, ...]
    predicate: PhysicalExpr
    anchor_resource_id: str

    def to_dict(self):
        return {
            "kind": "PhysicalCompositeAggregate",
            "input": self.input.to_dict(),
            "groups": [group.to_dict() for group in self.groups],
            "scalars": [scalar.to_dict() for scalar in self.scalars],
            "predicate": self.predicate.to_dict(),
            "anchor_resource_id": self.anchor_resource_id,
        }


@dataclass(frozen=True)
class PhysicalTemporal(PhysicalPlan):
    input: PhysicalPlan
    predicate: PhysicalExpr
    mode: str
    comparator: str
    threshold: Optional[int]
    maximum: Optional[int]
    unit: str
    every: bool
    window: PhysicalTemporalWindow
    trading_sequence: bool = True
    scalars: Tuple[PhysicalNamedScalar, ...] = ()

    def to_dict(self):
        return {
            "kind": "PhysicalTemporal",
            "input": self.input.to_dict(),
            "predicate": self.predicate.to_dict(),
            "mode": self.mode,
            "comparator": self.comparator,
            "threshold": self.threshold,
            "maximum": self.maximum,
            "unit": self.unit,
            "every": self.every,
            "window": self.window.to_dict(),
            "semantics": "trading_sequence" if self.trading_sequence else "calendar_sequence",
            "scalars": [item.to_dict() for item in self.scalars],
        }


@dataclass(frozen=True)
class PhysicalTemporalAggregate(PhysicalPlan):
    input: PhysicalPlan
    measure: PhysicalExpr
    function: str
    value_comparator: str
    value_bound: PhysicalLiteral
    mode: str
    comparator: str
    threshold: Optional[int]
    maximum: Optional[int]
    unit: str
    every: bool
    window: PhysicalTemporalWindow
    anchor_resource_id: str
    trading_sequence: bool = True

    def to_dict(self):
        return {
            "kind": "PhysicalTemporalAggregate",
            "input": self.input.to_dict(),
            "measure": self.measure.to_dict(),
            "function": self.function,
            "value_comparator": self.value_comparator,
            "value_bound": self.value_bound.to_dict(),
            "mode": self.mode,
            "comparator": self.comparator,
            "threshold": self.threshold,
            "maximum": self.maximum,
            "unit": self.unit,
            "every": self.every,
            "window": self.window.to_dict(),
            "anchor_resource_id": self.anchor_resource_id,
            "semantics": "trading_sequence" if self.trading_sequence else "calendar_sequence",
        }


@dataclass(frozen=True)
class PhysicalTemporalRank(PhysicalPlan):
    input: PhysicalPlan
    measure: PhysicalExpr
    aggregate_function: Optional[str]
    direction: str
    rank_comparator: str
    rank_bound: PhysicalLiteral
    rank_percentage: bool
    mode: str
    comparator: str
    threshold: Optional[int]
    maximum: Optional[int]
    unit: str
    every: bool
    window: PhysicalTemporalWindow
    anchor_resource_id: str
    trading_sequence: bool = True
    rank_upper_bound: Optional[PhysicalLiteral] = None
    rank_lower_inclusive: bool = True
    rank_upper_inclusive: bool = True

    def to_dict(self):
        return {
            "kind": "PhysicalTemporalRank",
            "input": self.input.to_dict(),
            "measure": self.measure.to_dict(),
            "aggregate_function": self.aggregate_function,
            "direction": self.direction,
            "rank_comparator": self.rank_comparator,
            "rank_bound": self.rank_bound.to_dict(),
            "rank_percentage": self.rank_percentage,
            "rank_upper_bound": self.rank_upper_bound.to_dict() if self.rank_upper_bound else None,
            "rank_lower_inclusive": self.rank_lower_inclusive,
            "rank_upper_inclusive": self.rank_upper_inclusive,
            "mode": self.mode,
            "comparator": self.comparator,
            "threshold": self.threshold,
            "maximum": self.maximum,
            "unit": self.unit,
            "every": self.every,
            "window": self.window.to_dict(),
            "anchor_resource_id": self.anchor_resource_id,
            "semantics": "trading_sequence" if self.trading_sequence else "calendar_sequence",
        }


@dataclass(frozen=True)
class PhysicalNamedRank(CanonicalIr):
    alias: str
    input: PhysicalPlan
    expression: PhysicalExpr
    direction: str
    value_alias: str
    aggregate_function: Optional[str] = None
    collapse_latest: bool = False

    def to_dict(self):
        return {
            "kind": "PhysicalNamedRank",
            "alias": self.alias,
            "input": self.input.to_dict(),
            "expression": self.expression.to_dict(),
            "direction": self.direction,
            "value_alias": self.value_alias,
            "aggregate_function": self.aggregate_function,
            "collapse_latest": self.collapse_latest,
        }


@dataclass(frozen=True)
class PhysicalRankExpression(PhysicalPlan):
    input: PhysicalPlan
    ranks: Tuple[PhysicalNamedRank, ...]
    predicate: PhysicalExpr
    anchor_resource_id: str
    scalars: Tuple[PhysicalNamedScalar, ...] = ()

    def to_dict(self):
        return {
            "kind": "PhysicalRankExpression",
            "input": self.input.to_dict(),
            "ranks": [rank.to_dict() for rank in self.ranks],
            "predicate": self.predicate.to_dict(),
            "anchor_resource_id": self.anchor_resource_id,
            "scalars": [scalar.to_dict() for scalar in self.scalars],
        }


@dataclass(frozen=True)
class PhysicalStageRank(PhysicalPlan):
    input: PhysicalPlan
    measure_input: PhysicalPlan
    measure: PhysicalExpr
    aggregate_function: Optional[str]
    direction: str
    bound: PhysicalLiteral
    comparator: str
    percentage: bool
    stage_index: int = 1
    collapse_latest: bool = False
    upper_bound: Optional[PhysicalLiteral] = None
    lower_inclusive: bool = True
    upper_inclusive: bool = True

    def to_dict(self):
        return {
            "kind": "PhysicalStageRank",
            "input": self.input.to_dict(),
            "measure_input": self.measure_input.to_dict(),
            "measure": self.measure.to_dict(),
            "aggregate_function": self.aggregate_function,
            "direction": self.direction,
            "bound": self.bound.to_dict(),
            "comparator": self.comparator,
            "percentage": self.percentage,
            "stage_index": self.stage_index,
            "collapse_latest": self.collapse_latest,
            "upper_bound": self.upper_bound.to_dict() if self.upper_bound else None,
            "lower_inclusive": self.lower_inclusive,
            "upper_inclusive": self.upper_inclusive,
        }


@dataclass(frozen=True)
class PhysicalSetOperation(PhysicalPlan):
    left: PhysicalPlan
    right: PhysicalPlan
    operation: str

    def to_dict(self):
        return {
            "kind": "PhysicalSetOperation",
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "operation": self.operation,
        }


@dataclass(frozen=True)
class PhysicalCandidateSetOperation(PhysicalPlan):
    left: PhysicalPlan
    right: PhysicalPlan
    operation: str
    anchor_resource_id: str

    def to_dict(self):
        return {
            "kind": "PhysicalCandidateSetOperation",
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "operation": self.operation,
            "anchor_resource_id": self.anchor_resource_id,
            "key_semantics": "security",
            "output_date_policy": "latest_anchor",
        }


@dataclass(frozen=True)
class PhysicalPrefixJoin(PhysicalPlan):
    input: PhysicalPlan
    projections: Tuple[PhysicalProjection, ...]
    predicate: Optional[PhysicalExpr]

    def to_dict(self):
        return {
            "kind": "PhysicalPrefixJoin",
            "input": self.input.to_dict(),
            "projections": [item.to_dict() for item in self.projections],
            "predicate": self.predicate.to_dict() if self.predicate is not None else None,
            "join_semantics": "stable_observation",
        }


@dataclass(frozen=True)
class PhysicalPrefixAggregate(PhysicalPlan):
    resource_id: str
    anchor_resource_id: str
    sum_column: str
    count_column: str
    window: int
    function: str
    comparator: str
    bound: PhysicalLiteral
    scale_divisor: float
    constraints: Tuple[PhysicalExpr, ...] = ()

    def to_dict(self):
        return {
            "kind": "PhysicalPrefixAggregate",
            "resource_id": self.resource_id,
            "anchor_resource_id": self.anchor_resource_id,
            "sum_column": self.sum_column,
            "count_column": self.count_column,
            "window": self.window,
            "function": self.function,
            "comparator": self.comparator,
            "bound": self.bound.to_dict(),
            "scale_divisor": self.scale_divisor,
            "constraints": [item.to_dict() for item in self.constraints],
        }


@dataclass(frozen=True)
class PhysicalLimit(PhysicalPlan):
    input: PhysicalPlan
    offset: int
    count: Optional[int]

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

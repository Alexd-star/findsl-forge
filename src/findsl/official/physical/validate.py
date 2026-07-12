from __future__ import annotations

from .catalog import PhysicalCatalog, PhysicalCatalogError
from .ir import (
    PhysicalAggregate, PhysicalAggregateRank, PhysicalAggregateRef, PhysicalBinary, PhysicalColumn, PhysicalComparison, PhysicalCompositeAggregate, PhysicalEmpty,
    PhysicalFilter, PhysicalJoin, PhysicalLimit, PhysicalPlan, PhysicalPrefixLookup,
    PhysicalDynamicDateRange, PhysicalGroupedAggregate, PhysicalIn, PhysicalLatestValue, PhysicalNamedScalar, PhysicalNthLatestValue, PhysicalPrefixAverage, PhysicalRank, PhysicalRecentSessions, PhysicalScan, PhysicalSessionBoundaryRange, PhysicalTableScan, PhysicalWindow,
    PhysicalTemporal,
    PhysicalSetOperation,
    PhysicalCoalesce, PhysicalNot, PhysicalNullIf, PhysicalUnary,
)
from ..types import BOOLEAN, NUMERIC


def validate_physical_plan(plan: PhysicalPlan, catalog: PhysicalCatalog, expressions=None) -> PhysicalPlan:
    _validate_plan(plan, catalog, expressions)
    return plan


def _validate_plan(plan, catalog, expressions):
    if isinstance(plan, PhysicalTableScan):
        catalog.resource(plan.resource_id)
        for column in plan.columns:
            if column.resource_id != plan.resource_id:
                raise PhysicalCatalogError("table scan column belongs to another resource")
            _validate_expr(column, catalog, expressions)
        if plan.partition_predicate:
            _validate_expr(plan.partition_predicate, catalog, expressions)
        return
    if isinstance(plan, PhysicalScan):
        resource = catalog.resource(plan.resource_id)
        if plan.anchor_resource_id != resource.anchor_resource_id:
            raise PhysicalCatalogError("physical scan anchor does not match catalog")
        if plan.anchor_resource_id:
            anchor = catalog.resource(plan.anchor_resource_id)
            if anchor.logical_entity != resource.logical_entity:
                raise PhysicalCatalogError("physical scan anchor entity mismatch")
        for column in plan.columns:
            _validate_expr(column, catalog, expressions)
        if plan.partition_predicate:
            _validate_expr(plan.partition_predicate, catalog, expressions)
        return
    if isinstance(plan, PhysicalEmpty):
        if not plan.proven_reason.startswith("PROVEN_"):
            raise ValueError("physical empty requires a proven reason")
        return
    if isinstance(plan, PhysicalSetOperation):
        if plan.operation not in {"intersect", "union"}:
            raise ValueError("unsupported physical set operation")
        _validate_plan(plan.left, catalog, expressions)
        _validate_plan(plan.right, catalog, expressions)
        return
    if isinstance(plan, PhysicalJoin):
        _validate_plan(plan.left, catalog, expressions); _validate_plan(plan.right, catalog, expressions)
        if plan.join_type not in {"inner", "left"}:
            raise ValueError("unsupported physical join type")
        for left, right in plan.keys:
            _validate_expr(left, catalog, expressions); _validate_expr(right, catalog, expressions)
            left_resource = catalog.resource(left.resource_id)
            right_resource = catalog.resource(right.resource_id)
            if left_resource.logical_entity != right_resource.logical_entity:
                raise PhysicalCatalogError("physical join crosses logical entities")
            if left.column != right.column:
                raise PhysicalCatalogError("physical join keys must preserve canonical key names")
            if left.column not in left_resource.stable_keys or right.column not in right_resource.stable_keys:
                raise PhysicalCatalogError("physical join key is not catalog-declared stable")
        return
    _validate_plan(plan.input, catalog, expressions)
    if isinstance(plan, PhysicalFilter):
        _validate_expr(plan.predicate, catalog, expressions)
        if plan.predicate.type is not BOOLEAN:
            raise ValueError("physical filter predicate must be boolean")
    elif isinstance(plan, PhysicalLimit):
        if plan.offset < 0 or plan.count <= 0:
            raise ValueError("physical limit bounds are invalid")
    elif isinstance(plan, PhysicalRank):
        if plan.direction not in {"asc", "desc"}:
            raise ValueError("physical rank direction is invalid")
        if plan.comparator not in {"<", "<=", "=", "!=", ">", ">="}:
            raise ValueError("physical rank comparator is invalid")
        if (
            not isinstance(plan.bound.value, (int, float))
            or plan.bound.value < 0
            or (plan.bound.value == 0 and plan.comparator not in {">", ">="})
        ):
            raise ValueError("physical rank bound is invalid")
        if plan.percentage and plan.bound.value > 100:
            raise ValueError("physical percentage rank bound exceeds 100")
        _validate_expr(plan.expression, catalog, expressions)
    elif isinstance(plan, PhysicalAggregateRank):
        if plan.function not in {"sum", "avg", "max", "min"}:
            raise ValueError("unsupported aggregate rank function")
        if plan.direction not in {"asc", "desc"}:
            raise ValueError("aggregate rank direction is invalid")
        if plan.comparator not in {"<", "<=", "=", "!=", ">", ">="}:
            raise ValueError("aggregate rank comparator is invalid")
        if (
            not isinstance(plan.bound.value, (int, float))
            or plan.bound.value < 0
            or (plan.bound.value == 0 and plan.comparator not in {">", ">="})
            or (plan.percentage and plan.bound.value > 100)
        ):
            raise ValueError("aggregate rank bound is invalid")
        anchor = catalog.resource(plan.anchor_resource_id)
        if anchor.partition_key is None:
            raise PhysicalCatalogError("aggregate rank anchor requires a partition key")
        _validate_expr(plan.measure, catalog, expressions)
    elif isinstance(plan, PhysicalGroupedAggregate):
        if plan.function not in {"sum", "avg", "max", "min"}:
            raise ValueError("unsupported grouped aggregate function")
        if plan.comparator not in {"<", "<=", "=", "!=", ">", ">="}:
            raise ValueError("unsupported grouped aggregate comparator")
        anchor = catalog.resource(plan.anchor_resource_id)
        if anchor.partition_key is None:
            raise PhysicalCatalogError("grouped aggregate anchor requires a partition key")
        _validate_expr(plan.measure, catalog, expressions)
        _validate_expr(plan.bound, catalog, expressions)
    elif isinstance(plan, PhysicalCompositeAggregate):
        if (not plan.groups and not plan.scalars) or plan.predicate.type is not BOOLEAN:
            raise ValueError("composite named relation plan requires relations and a boolean predicate")
        anchor = catalog.resource(plan.anchor_resource_id)
        if anchor.partition_key is None:
            raise PhysicalCatalogError("composite aggregate anchor requires a partition key")
        relation_aliases = set()
        declared_refs = set()
        for group in plan.groups:
            if not group.alias.isidentifier() or group.alias in relation_aliases:
                raise ValueError("composite aggregate relation alias is invalid or duplicated")
            relation_aliases.add(group.alias)
            if not group.measures:
                raise ValueError("composite aggregate group requires at least one measure")
            _validate_plan(group.input, catalog, expressions)
            measure_aliases = set()
            for measure in group.measures:
                if (
                    not measure.alias.isidentifier()
                    or measure.alias in measure_aliases
                    or measure.function not in {"sum", "avg", "max", "min"}
                ):
                    raise ValueError("composite aggregate measure contract is invalid")
                measure_aliases.add(measure.alias)
                declared_refs.add((group.alias, measure.alias))
                _validate_expr(measure.expression, catalog, expressions)
        scalar_aliases = set()
        for scalar in plan.scalars:
            if (
                not scalar.alias.isidentifier()
                or scalar.alias in relation_aliases
                or scalar.alias in scalar_aliases
                or not scalar.value_alias.isidentifier()
            ):
                raise ValueError("composite scalar relation alias is invalid or duplicated")
            scalar_aliases.add(scalar.alias)
            declared_refs.add((scalar.alias, scalar.value_alias))
            _validate_plan(scalar.input, catalog, expressions)
            _validate_expr(scalar.expression, catalog, expressions)
        used_refs = {
            (item.relation_alias, item.measure_alias)
            for item in _walk_aggregate_refs(plan.predicate)
        }
        if not used_refs or not used_refs.issubset(declared_refs):
            raise ValueError("composite aggregate predicate references an undeclared measure")
        _validate_expr(plan.predicate, catalog, expressions)
    elif isinstance(plan, PhysicalTemporal):
        _validate_expr(plan.predicate, catalog, expressions)
        if plan.predicate.type is not BOOLEAN:
            raise ValueError("physical temporal predicate must be boolean")
        if plan.mode not in {"CONS", "EXIST"} or not plan.trading_sequence:
            raise ValueError("invalid physical temporal mode or sequence semantics")
        if plan.comparator not in {"<", "<=", "=", "!=", ">", ">=", "between"}:
            raise ValueError("invalid physical temporal comparator")
        if plan.unit not in {"", "日", "周", "月", "季度", "年"}:
            raise ValueError("physical temporal bucket unit is not implemented")
        if plan.window.kind not in {"all_history", "recent_sessions", "session_slice", "boundary_sessions", "recent_calendar", "dynamic_period", "anchor_calendar", "calendar_range", "exact_date", "latest_session"}:
            raise ValueError("invalid physical temporal window")
        if plan.window.kind in {"recent_sessions", "session_slice"} and (plan.window.lookback_sessions is None or plan.window.lookback_sessions <= 0):
            raise ValueError("recent temporal window requires positive trading sessions")
        if plan.window.session_offset < 0:
            raise ValueError("session window offset cannot be negative")
        if plan.window.kind == "boundary_sessions" and (
            plan.window.lookback_sessions is None
            or plan.window.lookback_sessions <= 0
            or plan.window.boundary_direction not in {"before", "after"}
            or plan.window.boundary_kind not in {"period", "date"}
            or (plan.window.boundary_kind == "period" and plan.window.calendar_unit not in {"week", "month", "quarter", "year"})
            or (plan.window.boundary_kind == "date" and not plan.window.boundary_date)
        ):
            raise ValueError("session boundary window is incomplete")
        if plan.window.kind == "recent_calendar" and (
            plan.window.calendar_amount is None
            or plan.window.calendar_amount <= 0
            or plan.window.calendar_unit not in {"day", "week", "month", "year"}
        ):
            raise ValueError("recent calendar window requires a positive typed interval")
        if plan.window.kind == "dynamic_period" and (
            plan.window.calendar_unit not in {"week", "month", "quarter", "year"}
            or plan.window.calendar_offset > 0
        ):
            raise ValueError("dynamic period requires a supported non-future calendar contract")
        if plan.window.kind == "anchor_calendar" and (
            plan.window.calendar_unit not in {"day", "month"}
            or (plan.window.anchor_month is not None and not 1 <= plan.window.anchor_month <= 12)
            or (plan.window.anchor_day is not None and not 1 <= plan.window.anchor_day <= 31)
        ):
            raise ValueError("anchor calendar window has invalid components")
        if plan.window.kind in {"calendar_range", "exact_date"} and (
            not plan.window.start or not plan.window.end
        ):
            raise ValueError("calendar range requires explicit bounds")
        if plan.every:
            if plan.threshold is not None or plan.comparator not in {"=", "!="}:
                raise ValueError("invalid every-session temporal contract")
        elif plan.threshold is None or plan.threshold < 0:
            raise ValueError("invalid physical temporal threshold")
    elif isinstance(plan, PhysicalPrefixLookup):
        resource = catalog.resource(plan.resource_id)
        if "prefix" not in resource.capabilities or plan.window <= 0:
            raise ValueError("invalid prefix lookup")
    elif isinstance(plan, PhysicalAggregate):
        for expression in plan.group_keys:
            _validate_expr(expression, catalog, expressions)
        for _, expression in plan.measures:
            _validate_expr(expression, catalog, expressions)
    elif isinstance(plan, PhysicalWindow):
        for _, expression in plan.expressions:
            _validate_expr(expression, catalog, expressions)


def _validate_expr(expression, catalog, expressions=None):
    if isinstance(expression, PhysicalAggregateRef):
        if not expression.relation_alias.isidentifier() or not expression.measure_alias.isidentifier():
            raise ValueError("physical aggregate reference alias is invalid")
    elif isinstance(expression, PhysicalColumn):
        catalog.resource(expression.resource_id)
        allowed = {field.column for field in catalog.fields if field.resource_id == expression.resource_id}
        if expressions is not None:
            for definition in expressions.definitions:
                if definition.resource_id == expression.resource_id:
                    allowed.update(name for name, _ in definition.required_columns)
        allowed.update({"mktcode", "tgtcode", "bizdate", "name"})
        if expression.column not in allowed:
            raise PhysicalCatalogError(f"unknown column {expression.resource_id}.{expression.column}")
    elif isinstance(expression, PhysicalLatestValue):
        resource = catalog.resource(expression.resource_id)
        if expression.column != resource.partition_key:
            raise PhysicalCatalogError("latest value is restricted to the resource partition key")
    elif isinstance(expression, PhysicalNthLatestValue):
        resource = catalog.resource(expression.resource_id)
        if expression.column != resource.partition_key:
            raise PhysicalCatalogError("nth latest value is restricted to the resource partition key")
        if expression.offset <= 0:
            raise ValueError("nth latest value requires a positive offset")
    elif isinstance(expression, PhysicalRecentSessions):
        resource = catalog.resource(expression.resource_id)
        if expression.column != resource.partition_key:
            raise PhysicalCatalogError("recent sessions are restricted to the resource partition key")
        if expression.amount <= 0:
            raise ValueError("recent sessions require a positive amount")
        if expression.offset < 0:
            raise ValueError("recent sessions offset cannot be negative")
    elif isinstance(expression, PhysicalDynamicDateRange):
        resource = catalog.resource(expression.resource_id)
        if expression.column != resource.partition_key:
            raise PhysicalCatalogError("dynamic date ranges are restricted to the resource partition key")
        if expression.range_kind not in {"period", "recent", "anchor_calendar"}:
            raise ValueError("unsupported dynamic date range kind")
        if expression.amount <= 0 or expression.offset > 0:
            raise ValueError("dynamic date range cannot be empty or future-relative")
        allowed_units = {
            "period": {"week", "month", "quarter", "year"},
            "recent": {"week", "month", "year"},
            "anchor_calendar": {"day", "month"},
        }
        if expression.unit not in allowed_units[expression.range_kind]:
            raise ValueError("dynamic date range unit does not match its kind")
        if expression.month is not None and not 1 <= expression.month <= 12:
            raise ValueError("dynamic date month is invalid")
        if expression.day is not None and not 1 <= expression.day <= 31:
            raise ValueError("dynamic date day is invalid")
    elif isinstance(expression, PhysicalSessionBoundaryRange):
        resource = catalog.resource(expression.resource_id)
        if expression.column != resource.partition_key:
            raise PhysicalCatalogError("session boundary ranges require the partition key")
        if expression.direction not in {"before", "after"} or expression.boundary_kind not in {"period", "date"}:
            raise ValueError("invalid session boundary range contract")
        if expression.amount <= 0 or expression.offset > 0:
            raise ValueError("session boundary range cannot be empty or future-relative")
        if expression.boundary_kind == "period" and expression.unit not in {"week", "month", "quarter", "year"}:
            raise ValueError("session period boundary has no supported unit")
        if expression.boundary_kind == "date" and not expression.boundary_date:
            raise ValueError("explicit session boundary requires a date")
    elif isinstance(expression, PhysicalPrefixAverage):
        resource = catalog.resource(expression.resource_id)
        if "prefix" not in resource.capabilities:
            raise PhysicalCatalogError("prefix average requires a prefix resource")
        if expression.window <= 0 or expression.scale_divisor <= 0:
            raise ValueError("prefix average window and scale must be positive")
        for column in (expression.sum_column, expression.count_column):
            if not column or not column.replace("_", "a").isalnum():
                raise PhysicalCatalogError("invalid prefix average column")
    elif isinstance(expression, PhysicalIn):
        _validate_expr(expression.expression, catalog, expressions)
        if not expression.values:
            raise ValueError("physical IN requires at least one value")
        for value in expression.values:
            _validate_expr(value, catalog, expressions)
    elif isinstance(expression, (PhysicalBinary, PhysicalComparison)):
        _validate_expr(expression.left, catalog, expressions); _validate_expr(expression.right, catalog, expressions)
    elif isinstance(expression, PhysicalUnary):
        if expression.op != "negate" or expression.type is not NUMERIC:
            raise ValueError("unsupported physical unary expression")
        _validate_expr(expression.operand, catalog, expressions)
    elif isinstance(expression, PhysicalNot):
        if expression.operand.type is not BOOLEAN:
            raise ValueError("physical NOT requires a boolean operand")
        _validate_expr(expression.operand, catalog, expressions)
    elif isinstance(expression, PhysicalNullIf):
        if expression.expression.type is not expression.null_value.type or expression.type is not expression.expression.type:
            raise ValueError("physical NULLIF operands must have identical types")
        _validate_expr(expression.expression, catalog, expressions)
        _validate_expr(expression.null_value, catalog, expressions)
    elif isinstance(expression, PhysicalCoalesce):
        if len(expression.expressions) < 2 or any(item.type is not expression.type for item in expression.expressions):
            raise ValueError("physical COALESCE requires compatible operands")
        for item in expression.expressions:
            _validate_expr(item, catalog, expressions)


def _walk_aggregate_refs(expression):
    if isinstance(expression, PhysicalAggregateRef):
        yield expression
    elif isinstance(expression, (PhysicalBinary, PhysicalComparison)):
        yield from _walk_aggregate_refs(expression.left)
        yield from _walk_aggregate_refs(expression.right)
    elif isinstance(expression, (PhysicalUnary, PhysicalNot)):
        yield from _walk_aggregate_refs(expression.operand)
    elif isinstance(expression, PhysicalNullIf):
        yield from _walk_aggregate_refs(expression.expression)
        yield from _walk_aggregate_refs(expression.null_value)
    elif isinstance(expression, PhysicalCoalesce):
        for item in expression.expressions:
            yield from _walk_aggregate_refs(item)
    elif isinstance(expression, PhysicalIn):
        yield from _walk_aggregate_refs(expression.expression)

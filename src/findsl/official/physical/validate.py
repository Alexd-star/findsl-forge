from __future__ import annotations

from .catalog import PhysicalCatalog, PhysicalCatalogError
from .ir import (
    PhysicalAggregate, PhysicalBinary, PhysicalColumn, PhysicalComparison, PhysicalEmpty,
    PhysicalFilter, PhysicalJoin, PhysicalLimit, PhysicalPlan, PhysicalPrefixLookup,
    PhysicalIn, PhysicalLatestValue, PhysicalPrefixAverage, PhysicalRank, PhysicalScan, PhysicalWindow,
    PhysicalTemporal,
    PhysicalCoalesce, PhysicalNullIf, PhysicalUnary,
)
from ..types import BOOLEAN, NUMERIC


def validate_physical_plan(plan: PhysicalPlan, catalog: PhysicalCatalog, expressions=None) -> PhysicalPlan:
    _validate_plan(plan, catalog, expressions)
    return plan


def _validate_plan(plan, catalog, expressions):
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
    if isinstance(plan, PhysicalJoin):
        _validate_plan(plan.left, catalog, expressions); _validate_plan(plan.right, catalog, expressions)
        if plan.join_type not in {"inner", "left"}:
            raise ValueError("unsupported physical join type")
        for left, right in plan.keys:
            _validate_expr(left, catalog, expressions); _validate_expr(right, catalog, expressions)
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
        if not isinstance(plan.bound.value, (int, float)) or plan.bound.value <= 0:
            raise ValueError("physical rank bound is invalid")
        _validate_expr(plan.expression, catalog, expressions)
    elif isinstance(plan, PhysicalTemporal):
        _validate_expr(plan.predicate, catalog, expressions)
        if plan.predicate.type is not BOOLEAN:
            raise ValueError("physical temporal predicate must be boolean")
        if plan.mode not in {"CONS", "EXIST"} or not plan.trading_sequence:
            raise ValueError("invalid physical temporal mode or sequence semantics")
        if plan.comparator not in {"<", "<=", "=", "!=", ">", ">=", "between"}:
            raise ValueError("invalid physical temporal comparator")
        if plan.unit not in {"", "日"}:
            raise ValueError("physical temporal bucket unit is not implemented")
        if plan.window.kind not in {"all_history", "recent_sessions", "exact_date", "latest_session"}:
            raise ValueError("invalid physical temporal window")
        if plan.window.kind == "recent_sessions" and (plan.window.lookback_sessions is None or plan.window.lookback_sessions <= 0):
            raise ValueError("recent temporal window requires positive trading sessions")
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
    if isinstance(expression, PhysicalColumn):
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

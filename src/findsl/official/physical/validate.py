from __future__ import annotations

from .catalog import PhysicalCatalog, PhysicalCatalogError
from .ir import (
    PhysicalAggregate, PhysicalBinary, PhysicalColumn, PhysicalComparison, PhysicalEmpty,
    PhysicalFilter, PhysicalJoin, PhysicalLimit, PhysicalPlan, PhysicalPrefixLookup,
    PhysicalIn, PhysicalLatestValue, PhysicalPrefixAverage, PhysicalRank, PhysicalScan, PhysicalWindow,
)
from ..types import BOOLEAN


def validate_physical_plan(plan: PhysicalPlan, catalog: PhysicalCatalog) -> PhysicalPlan:
    _validate_plan(plan, catalog)
    return plan


def _validate_plan(plan, catalog):
    if isinstance(plan, PhysicalScan):
        resource = catalog.resource(plan.resource_id)
        if plan.anchor_resource_id != resource.anchor_resource_id:
            raise PhysicalCatalogError("physical scan anchor does not match catalog")
        if plan.anchor_resource_id:
            anchor = catalog.resource(plan.anchor_resource_id)
            if anchor.logical_entity != resource.logical_entity:
                raise PhysicalCatalogError("physical scan anchor entity mismatch")
        for column in plan.columns:
            _validate_expr(column, catalog)
        if plan.partition_predicate:
            _validate_expr(plan.partition_predicate, catalog)
        return
    if isinstance(plan, PhysicalEmpty):
        if not plan.proven_reason.startswith("PROVEN_"):
            raise ValueError("physical empty requires a proven reason")
        return
    if isinstance(plan, PhysicalJoin):
        _validate_plan(plan.left, catalog); _validate_plan(plan.right, catalog)
        if plan.join_type not in {"inner", "left"}:
            raise ValueError("unsupported physical join type")
        for left, right in plan.keys:
            _validate_expr(left, catalog); _validate_expr(right, catalog)
        return
    _validate_plan(plan.input, catalog)
    if isinstance(plan, PhysicalFilter):
        _validate_expr(plan.predicate, catalog)
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
        _validate_expr(plan.expression, catalog)
    elif isinstance(plan, PhysicalPrefixLookup):
        resource = catalog.resource(plan.resource_id)
        if "prefix" not in resource.capabilities or plan.window <= 0:
            raise ValueError("invalid prefix lookup")
    elif isinstance(plan, PhysicalAggregate):
        for expression in plan.group_keys:
            _validate_expr(expression, catalog)
        for _, expression in plan.measures:
            _validate_expr(expression, catalog)
    elif isinstance(plan, PhysicalWindow):
        for _, expression in plan.expressions:
            _validate_expr(expression, catalog)


def _validate_expr(expression, catalog):
    if isinstance(expression, PhysicalColumn):
        catalog.resource(expression.resource_id)
        allowed = {field.column for field in catalog.fields if field.resource_id == expression.resource_id}
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
        _validate_expr(expression.expression, catalog)
        if not expression.values:
            raise ValueError("physical IN requires at least one value")
        for value in expression.values:
            _validate_expr(value, catalog)
    elif isinstance(expression, (PhysicalBinary, PhysicalComparison)):
        _validate_expr(expression.left, catalog); _validate_expr(expression.right, catalog)

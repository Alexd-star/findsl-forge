from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter_ns
from typing import FrozenSet, List, Optional, Tuple

from .ast import (
    OfficialBinaryOp,
    OfficialComparison,
    OfficialFunctionCall,
    OfficialIdentifier,
    OfficialLimit,
    OfficialLiteral,
    OfficialRangeLiteral,
    walk,
)
from .ir import (
    BinaryExpr,
    CallExpr,
    ComparisonExpr,
    Field,
    FieldRef,
    LiteralExpr,
    LogicalFilter,
    LogicalDomainScan,
    LogicalLimit,
    LogicalRank,
    LogicalScan,
    LogicalStage,
    RangeExpr,
    Schema,
)
from .ir.relational import LogicalPlan
from .ir.validate import OfficialIrError, validate_plan
from .typed_ast import TypedNode
from .types import BOOLEAN, STRING, UNKNOWN, RangeType
from .domain.binder import BoundFunction, DomainBindingError, bind_function
from .domain.expressions import DataRequirement
from .registry import OfficialIndicatorRegistry


class OfficialLoweringError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class LoweringResult:
    plan: LogicalPlan
    required_functions: FrozenSet[str]
    validation_passed: bool
    elapsed_ns: int
    domain_bindings: Tuple[BoundFunction, ...] = ()

    def to_dict(self):
        return {
            "plan": self.plan.to_dict(),
            "plan_id": self.plan.node_id,
            "required_functions": sorted(self.required_functions),
            "validation_passed": self.validation_passed,
            "elapsed_ns": self.elapsed_ns,
            "domain_bindings": [binding.to_dict() for binding in self.domain_bindings],
        }


DEFAULT_SCHEMA = Schema(
    (
        Field("stock_code", STRING, False),
        Field("bizdate", STRING, False),
    )
)


def lower_official_ast(
    typed: TypedNode,
    *,
    strict: bool = True,
    domain_registry: Optional[OfficialIndicatorRegistry] = None,
) -> LoweringResult:
    started = perf_counter_ns()
    functions = frozenset(
        item.name for item in walk(typed.node) if isinstance(item, OfficialFunctionCall)
    )
    bindings: Tuple[BoundFunction, ...] = ()
    try:
        if domain_registry is None:
            scan = LogicalScan("market_observation", DEFAULT_SCHEMA)
        else:
            bindings = tuple(
                bind_function(node, domain_registry)
                for node in _walk_typed(typed)
                if isinstance(node.node, OfficialFunctionCall)
            )
            requirement = DataRequirement(
                frozenset(domain for binding in bindings for domain in binding.requirement.domains),
                frozenset(capability for binding in bindings for capability in binding.requirement.capabilities),
            )
            scan = LogicalDomainScan("market_observation", requirement, DEFAULT_SCHEMA)
        plan = _lower_root(typed, scan)
        validate_plan(plan, strict=strict)
    except DomainBindingError as exc:
        raise OfficialLoweringError(exc.code, str(exc)) from exc
    except (OfficialIrError, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, OfficialLoweringError):
            raise
        detail = f"{getattr(exc, 'code', type(exc).__name__)}: {exc}"
        raise OfficialLoweringError("UNSUPPORTED_LOGICAL_LOWERING", detail) from exc
    return LoweringResult(plan, functions, True, perf_counter_ns() - started, bindings)


def _walk_typed(node: TypedNode):
    yield node
    for child in node.children:
        yield from _walk_typed(child)


def _lower_root(typed: TypedNode, scan: LogicalPlan) -> LogicalPlan:
    if isinstance(typed.node, OfficialLimit):
        inner = _lower_root(typed.children[0], scan)
        return LogicalLimit(inner, typed.node.lower, typed.node.upper, inner.schema)
    stages = _flatten_then(typed)
    current = _lower_stage(stages[0], scan)
    for index, stage in enumerate(stages[1:], start=1):
        operation = _lower_stage(stage, current)
        current = LogicalStage(current, index, operation, operation.schema)
    return current


def _flatten_then(typed: TypedNode) -> List[TypedNode]:
    if isinstance(typed.node, OfficialBinaryOp) and typed.node.op == "then":
        return _flatten_then(typed.children[0]) + _flatten_then(typed.children[1])
    return [typed]


def _lower_stage(typed: TypedNode, input_plan: LogicalPlan) -> LogicalPlan:
    node = typed.node
    if (
        isinstance(node, OfficialComparison)
        and isinstance(node.left, OfficialFunctionCall)
        and node.left.name == "rank"
    ):
        if node.op not in {"<", "<=", ">", ">="}:
            raise OfficialLoweringError("UNSUPPORTED_LOGICAL_LOWERING", f"unsupported rank comparison {node.op}")
        call = typed.children[0]
        bound = _lower_expr(typed.children[1])
        direction = call.binding.slots["direction"].lower() if call.binding else ""
        return LogicalRank(input_plan, _lower_expr(call), direction, bound, input_plan.schema)
    if typed.type is UNKNOWN:
        raise OfficialLoweringError("UNSUPPORTED_LOGICAL_LOWERING", "top-level expression has unknown type")
    predicate = _lower_expr(typed)
    if predicate.type is not BOOLEAN:
        raise OfficialLoweringError("UNSUPPORTED_LOGICAL_LOWERING", "top-level expression must be boolean")
    return LogicalFilter(input_plan, predicate, input_plan.schema)


def _lower_expr(typed: TypedNode):
    node = typed.node
    if typed.type is UNKNOWN:
        raise OfficialLoweringError("UNSUPPORTED_LOGICAL_LOWERING", "unknown expression type")
    if isinstance(node, OfficialLiteral):
        return LiteralExpr(node.value, typed.type)
    if isinstance(node, OfficialIdentifier):
        return FieldRef(node.name, typed.type)
    if isinstance(node, OfficialFunctionCall):
        return CallExpr(node.name, tuple(_lower_expr(child) for child in typed.children), typed.type, typed.binding)
    if isinstance(node, OfficialBinaryOp):
        return BinaryExpr(node.op, _lower_expr(typed.children[0]), _lower_expr(typed.children[1]), typed.type)
    if isinstance(node, OfficialComparison):
        return ComparisonExpr(node.op, _lower_expr(typed.children[0]), _lower_expr(typed.children[1]))
    if isinstance(node, OfficialRangeLiteral):
        element = typed.type.element_type if isinstance(typed.type, RangeType) else typed.children[0].type
        return RangeExpr(
            _lower_expr(typed.children[0]),
            _lower_expr(typed.children[1]),
            node.lower_inclusive,
            node.upper_inclusive,
            element,
        )
    raise OfficialLoweringError("UNSUPPORTED_LOGICAL_LOWERING", f"unsupported AST node {type(node).__name__}")

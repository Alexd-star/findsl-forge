from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter_ns
from typing import Dict, FrozenSet, List, Optional, Tuple

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
    LogicalConsecutive,
    LogicalDomainScan,
    LogicalExist,
    LogicalLimit,
    LogicalRank,
    LogicalScan,
    LogicalSetOperation,
    LogicalStage,
    RangeExpr,
    Schema,
)
from .ir.relational import LogicalPlan
from .ir.validate import OfficialIrError, validate_plan
from .typed_ast import FunctionBinding, TypedNode
from .types import BOOLEAN, STRING, UNKNOWN, RangeType
from .domain.binder import (
    BoundFunction,
    DomainBindingError,
    bind_function,
    normalize_function_slots,
)
from .domain.expressions import ConsecutiveSpec, DataRequirement, ExistSpec
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
    binding_by_node: Dict[int, BoundFunction] = {}
    try:
        if domain_registry is None:
            scan = LogicalScan("market_observation", DEFAULT_SCHEMA)
        else:
            bound_nodes = tuple(
                (node, bind_function(node, domain_registry))
                for node in _walk_typed(typed)
                if isinstance(node.node, OfficialFunctionCall)
                and node.binding is not None
                and node.binding.signature.argument_mode == "slot_literals"
            )
            bindings = tuple(binding for _, binding in bound_nodes)
            binding_by_node = {id(node.node): binding for node, binding in bound_nodes}
            requirement = DataRequirement(
                frozenset(domain for binding in bindings for domain in binding.requirement.domains),
                frozenset(capability for binding in bindings for capability in binding.requirement.capabilities),
            )
            scan = LogicalDomainScan("market_observation", requirement, DEFAULT_SCHEMA)
        plan = _lower_root(typed, scan, binding_by_node)
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


def _lower_root(typed: TypedNode, scan: LogicalPlan, bindings: Dict[int, BoundFunction]) -> LogicalPlan:
    if isinstance(typed.node, OfficialLimit):
        inner = _lower_root(typed.children[0], scan, bindings)
        count = None if typed.node.upper == -1 else typed.node.upper
        return LogicalLimit(inner, typed.node.lower, count, inner.schema)
    stages = _flatten_then(typed)
    current = _lower_stage(stages[0], scan, bindings)
    for index, stage in enumerate(stages[1:], start=1):
        operation = _lower_stage(stage, current, bindings)
        current = LogicalStage(current, index, operation, operation.schema)
    return current


def _flatten_then(typed: TypedNode) -> List[TypedNode]:
    if isinstance(typed.node, OfficialBinaryOp) and typed.node.op == "then":
        return _flatten_then(typed.children[0]) + _flatten_then(typed.children[1])
    return [typed]


def _lower_stage(
    typed: TypedNode,
    input_plan: LogicalPlan,
    bindings: Dict[int, BoundFunction],
) -> LogicalPlan:
    node = typed.node
    if isinstance(node, OfficialBinaryOp) and node.op == "then":
        stages = _flatten_then(typed)
        current = _lower_stage(stages[0], input_plan, bindings)
        for index, stage in enumerate(stages[1:], start=1):
            operation = _lower_stage(stage, current, bindings)
            current = LogicalStage(current, index, operation, operation.schema)
        return current
    if (
        isinstance(node, OfficialBinaryOp)
        and node.op in {"and", "or"}
        and _contains_temporal_binding(typed, bindings)
    ):
        left = _lower_stage(typed.children[0], input_plan, bindings)
        right = _lower_stage(typed.children[1], input_plan, bindings)
        operation = "intersect" if node.op == "and" else "union"
        return LogicalSetOperation(left, right, operation, input_plan.schema)
    if (
        isinstance(node, OfficialBinaryOp)
        and node.op in {"and", "or"}
        and _contains_rank_comparison(typed)
    ):
        left = _lower_stage(typed.children[0], input_plan, bindings)
        right = _lower_stage(typed.children[1], input_plan, bindings)
        operation = "intersect" if node.op == "and" else "union"
        return LogicalSetOperation(left, right, operation, input_plan.schema)
    temporal_binding = _temporal_binding_for_stage(typed, bindings)
    if temporal_binding is not None:
        predicate = _lower_expr(typed, strip_count_exp=True, bindings=bindings)
        temporal = temporal_binding.temporal
        if temporal is None:
            raise OfficialLoweringError("TEMPORAL_BINDING_MISSING", "temporal stage has no typed quantifier")
        if temporal.mode == "CONS":
            spec = ConsecutiveSpec(
                predicate,
                temporal.comparator,
                temporal.threshold,
                temporal.maximum,
                temporal.unit,
                temporal.every,
                temporal.source,
                temporal_binding.date_constraint,
                temporal.trading_sequence,
            )
            return LogicalConsecutive(input_plan, spec, input_plan.schema)
        spec = ExistSpec(
            predicate,
            temporal.comparator,
            temporal.threshold,
            temporal.maximum,
            temporal.unit,
            temporal.every,
            temporal.source,
            temporal_binding.date_constraint,
            temporal.trading_sequence,
        )
        return LogicalExist(input_plan, spec, input_plan.schema)
    if (
        isinstance(node, OfficialComparison)
        and isinstance(node.left, OfficialFunctionCall)
        and node.left.name == "rank"
    ):
        if node.op not in {"<", "<=", "=", "!=", ">", ">=", "between"}:
            raise OfficialLoweringError("UNSUPPORTED_LOGICAL_LOWERING", f"unsupported rank comparison {node.op}")
        call = typed.children[0]
        direction = call.binding.slots["direction"].lower() if call.binding else ""
        if isinstance(node.right, OfficialRangeLiteral) and node.op == "between":
            range_node = typed.children[1]
            return LogicalRank(
                input_plan,
                _lower_expr(call, bindings=bindings),
                direction,
                _lower_expr(range_node.children[0], bindings=bindings),
                input_plan.schema,
                comparator="between",
                upper_bound=_lower_expr(range_node.children[1], bindings=bindings),
                lower_inclusive=node.right.lower_inclusive,
                upper_inclusive=node.right.upper_inclusive,
            )
        bound = _lower_expr(typed.children[1], bindings=bindings)
        return LogicalRank(
            input_plan,
            _lower_expr(call, bindings=bindings),
            direction,
            bound,
            input_plan.schema,
            comparator=node.op,
        )
    if typed.type is UNKNOWN:
        raise OfficialLoweringError("UNSUPPORTED_LOGICAL_LOWERING", "top-level expression has unknown type")
    predicate = _lower_expr(typed, bindings=bindings)
    if predicate.type is not BOOLEAN:
        raise OfficialLoweringError("UNSUPPORTED_LOGICAL_LOWERING", "top-level expression must be boolean")
    return LogicalFilter(input_plan, predicate, input_plan.schema)


def _contains_rank_comparison(typed: TypedNode) -> bool:
    node = typed.node
    if (
        isinstance(node, OfficialComparison)
        and isinstance(node.left, OfficialFunctionCall)
        and node.left.name == "rank"
    ):
        return True
    return any(_contains_rank_comparison(child) for child in typed.children)


def _lower_expr(
    typed: TypedNode,
    *,
    strip_count_exp: bool = False,
    bindings: Optional[Dict[int, BoundFunction]] = None,
):
    node = typed.node
    if typed.type is UNKNOWN:
        raise OfficialLoweringError("UNSUPPORTED_LOGICAL_LOWERING", "unknown expression type")
    if isinstance(node, OfficialLiteral):
        return LiteralExpr(node.value, typed.type)
    if isinstance(node, OfficialIdentifier):
        return FieldRef(node.name, typed.type)
    if isinstance(node, OfficialFunctionCall):
        binding = typed.binding
        domain_binding = bindings.get(id(node)) if bindings else None
        if binding is not None and domain_binding is not None:
            binding = FunctionBinding.create(
                binding.signature,
                normalize_function_slots(node.name, binding.slots),
            )
        if strip_count_exp and binding is not None and "count_exp" in binding.slots:
            slots = dict(binding.slots)
            slots["count_exp"] = ""
            if "date" in slots:
                slots["date"] = ""
            binding = FunctionBinding.create(binding.signature, slots)
        date_constraint = None
        market_expression = domain_binding.market_expression if domain_binding else None
        scope_expression = domain_binding.scope_expression if domain_binding else None
        if domain_binding is not None and not strip_count_exp:
            date_constraint = domain_binding.date_constraint
        return CallExpr(
            binding.signature.name if binding is not None else node.name,
            tuple(
                _lower_expr(
                    child,
                    strip_count_exp=strip_count_exp,
                    bindings=bindings,
                )
                for child in typed.children
            ),
            typed.type,
            binding,
            date_constraint,
            market_expression,
            scope_expression,
        )
    if isinstance(node, OfficialBinaryOp):
        return BinaryExpr(node.op, _lower_expr(typed.children[0], strip_count_exp=strip_count_exp, bindings=bindings), _lower_expr(typed.children[1], strip_count_exp=strip_count_exp, bindings=bindings), typed.type)
    if isinstance(node, OfficialComparison):
        return ComparisonExpr(node.op, _lower_expr(typed.children[0], strip_count_exp=strip_count_exp, bindings=bindings), _lower_expr(typed.children[1], strip_count_exp=strip_count_exp, bindings=bindings))
    if isinstance(node, OfficialRangeLiteral):
        element = typed.type.element_type if isinstance(typed.type, RangeType) else typed.children[0].type
        return RangeExpr(
            _lower_expr(typed.children[0], strip_count_exp=strip_count_exp, bindings=bindings),
            _lower_expr(typed.children[1], strip_count_exp=strip_count_exp, bindings=bindings),
            node.lower_inclusive,
            node.upper_inclusive,
            element,
        )
    raise OfficialLoweringError("UNSUPPORTED_LOGICAL_LOWERING", f"unsupported AST node {type(node).__name__}")


def _temporal_binding_for_stage(
    typed: TypedNode,
    bindings: Dict[int, BoundFunction],
) -> Optional[BoundFunction]:
    calls = [
        node
        for node in _walk_typed(typed)
        if isinstance(node.node, OfficialFunctionCall) and id(node.node) in bindings
    ]
    temporal_nodes = [node for node in calls if bindings[id(node.node)].temporal is not None]
    temporal = [bindings[id(node.node)] for node in temporal_nodes]
    if not temporal:
        return None
    temporal_signatures = {
        (
            item.temporal.mode,
            item.temporal.comparator,
            item.temporal.threshold,
            item.temporal.maximum,
            item.temporal.unit,
            item.temporal.every,
            item.temporal.trading_sequence,
        )
        for item in temporal
    }
    if len(temporal_signatures) != 1:
        raise OfficialLoweringError(
            "TEMPORAL_MULTI_PREDICATE_UNSUPPORTED",
            "one temporal predicate cannot mix different count_exp quantifiers",
        )
    if not isinstance(typed.node, OfficialComparison):
        raise OfficialLoweringError(
            "TEMPORAL_COMPOSITE_PREDICATE_UNSUPPORTED",
            "a single temporal contract must govern one comparison expression",
        )
    temporal_node = temporal_nodes[0]
    temporal_scope = temporal[0]
    reference_slots = temporal_node.binding.slots if temporal_node.binding else {}
    for call in calls:
        binding = bindings[id(call.node)]
        slots = call.binding.slots if call.binding else {}
        same_scope = (
            binding.market_scope.to_dict() == temporal_scope.market_scope.to_dict()
            and binding.date_constraint.to_dict() == temporal_scope.date_constraint.to_dict()
            and slots.get("filter_scope", "") == reference_slots.get("filter_scope", "")
            and slots.get("select_type", "") == reference_slots.get("select_type", "")
        )
        independent_querydata_aggregate = (
            call.node.name == "queryData"
            and binding.temporal is None
            and bool(str(slots.get("agg_func", "")).strip())
        )
        if not same_scope and not independent_querydata_aggregate:
            raise OfficialLoweringError(
                "TEMPORAL_SCOPE_MISMATCH",
                "all functions in a temporal arithmetic predicate must share market, date, filter and security scopes",
            )
    for item in temporal[1:]:
        if (
            (
                item.market_expression.to_dict()
                if item.market_expression
                else None
            )
            != (
                temporal_scope.market_expression.to_dict()
                if temporal_scope.market_expression
                else None
            )
            or (
                item.scope_expression.to_dict() if item.scope_expression else None
            )
            != (
                temporal_scope.scope_expression.to_dict()
                if temporal_scope.scope_expression
                else None
            )
        ):
            raise OfficialLoweringError(
                "TEMPORAL_SCOPE_MISMATCH",
                "aligned temporal calls must share identical market and security set expressions",
            )
    return temporal[0]


def _contains_temporal_binding(
    typed: TypedNode,
    bindings: Dict[int, BoundFunction],
) -> bool:
    return any(
        isinstance(node.node, OfficialFunctionCall)
        and id(node.node) in bindings
        and bindings[id(node.node)].temporal is not None
        for node in _walk_typed(typed)
    )

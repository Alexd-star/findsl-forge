from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from .context import CompileContext


ROUTE_KINDS = ("RAW", "PARTITION", "MV", "PREFIX")
_BASELINE_STRATEGIES = {
    "controlled_expression",
    "direct_column",
    "grouped_aggregate",
    "multi_resource_join",
}


@dataclass(frozen=True)
class QueryFeatures:
    function_families: Tuple[str, ...]
    indicator_ids: Tuple[str, ...]
    aggregate_functions: Tuple[str, ...]
    temporal_modes: Tuple[str, ...]
    date_kinds: Tuple[str, ...]
    scope_kinds: Tuple[str, ...]
    comparison_operators: Tuple[str, ...]
    boolean_operators: Tuple[str, ...]
    node_count: int
    stage_count: int
    has_rank: bool
    has_temporal: bool
    has_stage: bool
    has_scope: bool
    has_aggregate: bool
    has_interval: bool
    has_bitwise_alias: bool
    long_horizon: bool
    complexity_score: int

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        for key, value in tuple(payload.items()):
            if isinstance(value, tuple):
                payload[key] = list(value)
        return payload


@dataclass(frozen=True)
class RouteCandidate:
    route_kind: str
    candidate_id: str
    executable: bool
    eligible: bool
    selected: bool
    cost: Optional[float]
    cost_unit: str
    estimated: bool
    reason_code: str
    reason: str
    resource_id: Optional[str]
    strategy_id: str
    source: str
    fallback_to: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AdaptiveRoutePlan:
    planner: str
    selected_route: str
    selected_strategy: str
    candidates: Tuple[RouteCandidate, ...]
    fallback_chain: Tuple[str, ...]
    decision_basis: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "planner": self.planner,
            "selected_route": self.selected_route,
            "selected_strategy": self.selected_strategy,
            "candidates": [item.to_dict() for item in self.candidates],
            "fallback_chain": list(self.fallback_chain),
            "decision_basis": list(self.decision_basis),
        }


class AdaptiveRoutePlanner:
    """Projects physical planner decisions into four auditable route families.

    The physical planner remains the only component allowed to choose an executable
    plan. This layer never invents SQL. It makes generated and rejected alternatives
    explicit so an EXPLAIN consumer can distinguish a real candidate from a missing
    acceleration path.
    """

    def __init__(self, context: CompileContext):
        self.context = context

    def explain(
        self,
        physical: Mapping[str, Any],
        features: QueryFeatures,
    ) -> AdaptiveRoutePlan:
        candidates = [
            self._from_decision(item, features)
            for item in physical.get("decisions", ())
        ]
        selected_children = [item for item in candidates if item.selected]
        selected_strategy = str(physical.get("selected_strategy") or "")
        if len(selected_children) != 1 or (
            selected_children and selected_children[0].strategy_id != selected_strategy
        ):
            candidates = [
                replace(
                    item,
                    selected=False,
                    source=(
                        "physical_subplan_decision"
                        if item.selected
                        else item.source
                    ),
                )
                for item in candidates
            ]
            candidates.append(
                self._top_level_candidate(
                    physical,
                    features,
                    selected_children,
                )
            )
        candidates = self._add_raw_fallback(candidates)
        represented = {item.route_kind for item in candidates}
        for kind in ROUTE_KINDS:
            if kind not in represented:
                candidates.append(self._unavailable(kind, features, candidates))
        candidates.sort(key=lambda item: (ROUTE_KINDS.index(item.route_kind), item.candidate_id))
        selected = [item for item in candidates if item.selected]
        if len(selected) != 1:
            raise ValueError("adaptive route explanation requires exactly one selected candidate")
        selected_route = selected[0].route_kind
        fallback_chain_values = []
        for item in sorted(
            (
                item
                for item in candidates
                if item.eligible
                and item.executable
                and not item.selected
                and item.route_kind != selected_route
            ),
            key=lambda item: (
                float("inf") if item.cost is None else item.cost,
                ROUTE_KINDS.index(item.route_kind),
            ),
        ):
            if item.route_kind not in fallback_chain_values:
                fallback_chain_values.append(item.route_kind)
        fallback_chain = tuple(fallback_chain_values)
        basis = (
            f"query_complexity={features.complexity_score}",
            f"long_horizon={str(features.long_horizon).lower()}",
            f"date_constraints={','.join(features.date_kinds) or '<none>'}",
            "only physical decisions with proven semantic equivalence may be selected",
            "ineligible acceleration paths remain visible with deterministic reason codes",
        )
        return AdaptiveRoutePlan(
            planner="AdaptiveRoutePlanner/v1",
            selected_route=selected_route,
            selected_strategy=str(physical.get("selected_strategy") or selected[0].strategy_id),
            candidates=tuple(candidates),
            fallback_chain=fallback_chain,
            decision_basis=basis,
        )

    def _top_level_candidate(
        self,
        physical: Mapping[str, Any],
        features: QueryFeatures,
        selected_children: Iterable[RouteCandidate],
    ) -> RouteCandidate:
        strategy = str(physical.get("selected_strategy") or "composite_plan")
        resource_id = physical.get("selected_resource")
        route = _route_kind(strategy, resource_id, features, self.context)
        child_costs = [
            item.cost for item in selected_children if item.cost is not None
        ]
        return RouteCandidate(
            route_kind=route,
            candidate_id=f"{route.lower()}:top:{strategy}",
            executable=True,
            eligible=True,
            selected=True,
            cost=sum(child_costs) if child_costs else None,
            cost_unit="composite_child_cost" if child_costs else "not_comparable",
            estimated=any(item.estimated for item in selected_children),
            reason_code="COMPOSITE_ROUTE_SELECTED",
            reason=(
                "top-level route composes the selected child plans; child selections "
                "remain visible as subplan decisions"
            ),
            resource_id=None if resource_id is None else str(resource_id),
            strategy_id=strategy,
            source="physical_composite_decision",
            fallback_to="RAW" if route != "RAW" else None,
        )

    def _from_decision(
        self,
        raw: Mapping[str, Any],
        features: QueryFeatures,
    ) -> RouteCandidate:
        strategy = str(raw.get("strategy_id") or "direct_column")
        route = _route_kind(strategy, raw.get("resource_id"), features, self.context)
        return RouteCandidate(
            route_kind=route,
            candidate_id=f"{route.lower()}:{strategy}:{raw.get('resource_id') or 'none'}",
            executable=bool(raw.get("feasible")),
            eligible=bool(raw.get("selection_eligible", True) and raw.get("feasible")),
            selected=bool(raw.get("selected")),
            cost=_optional_float(raw.get("cost")),
            cost_unit=str(raw.get("cost_unit") or "unknown"),
            estimated=bool(raw.get("estimated")),
            reason_code=str(raw.get("reason_code") or "PHYSICAL_DECISION"),
            reason=str(raw.get("reason") or "physical planner decision"),
            resource_id=(None if raw.get("resource_id") is None else str(raw["resource_id"])),
            strategy_id=strategy,
            source="physical_decision",
            fallback_to="RAW" if route != "RAW" else None,
        )

    def _add_raw_fallback(
        self,
        candidates: list[RouteCandidate],
    ) -> list[RouteCandidate]:
        if any(item.route_kind == "RAW" for item in candidates):
            return candidates
        baseline = next(
            (
                item
                for item in candidates
                if item.strategy_id in _BASELINE_STRATEGIES
                or item.strategy_id.startswith(("limit_", "stage_", "set_"))
            ),
            None,
        )
        if baseline is None:
            return candidates
        try:
            stats = self.context.physical_statistics.resource(baseline.resource_id or "")
            raw_cost = float(stats.data_size_bytes)
            estimated = not stats.row_count_available
        except KeyError:
            raw_cost = baseline.cost
            estimated = True
        candidates.append(
            RouteCandidate(
                route_kind="RAW",
                candidate_id=f"raw:fallback:{baseline.resource_id or 'none'}",
                executable=True,
                eligible=True,
                selected=False,
                cost=raw_cost,
                cost_unit="bytes",
                estimated=estimated,
                reason_code="RAW_BASELINE_FALLBACK",
                reason="semantically equivalent base-table scan retained as the final fallback",
                resource_id=baseline.resource_id,
                strategy_id="raw_scan_fallback",
                source="derived_fallback_contract",
                fallback_to=None,
            )
        )
        return candidates

    def _unavailable(
        self,
        kind: str,
        features: QueryFeatures,
        candidates: Iterable[RouteCandidate],
    ) -> RouteCandidate:
        reasons = {
            "RAW": ("RAW_PLAN_NOT_GENERATED", "no executable base-table plan was generated"),
            "PARTITION": (
                "PARTITION_ROUTE_INELIGIBLE",
                "query has no exact date predicate and partition route cannot be proven selective"
                if not features.date_kinds
                else "no generated physical candidate exposes a partition-pruned resource",
            ),
            "MV": (
                "MV_ROUTE_INELIGIBLE",
                "no version-compatible materialized feature matches the query contract",
            ),
            "PREFIX": (
                "PREFIX_ROUTE_INELIGIBLE",
                "prefix algebra is unavailable for this function, window, or data resource",
            ),
        }
        code, reason = reasons[kind]
        raw_available = any(
            item.route_kind == "RAW" and item.executable for item in candidates
        )
        return RouteCandidate(
            route_kind=kind,
            candidate_id=f"{kind.lower()}:unavailable",
            executable=False,
            eligible=False,
            selected=False,
            cost=None,
            cost_unit="unavailable",
            estimated=False,
            reason_code=code,
            reason=reason,
            resource_id=None,
            strategy_id=f"{kind.lower()}_unavailable",
            source="eligibility_audit",
            fallback_to="RAW" if kind != "RAW" and raw_available else None,
        )


def extract_query_features(
    frontend: Mapping[str, Any],
    logical: Mapping[str, Any],
) -> QueryFeatures:
    ast = frontend.get("ast") or {}
    functions = []
    indicators = []
    aggregates = []
    comparisons = []
    booleans = []
    count_expressions = []
    scopes = []
    market_expressions = []
    nodes = 0

    def walk(value: Any) -> None:
        nonlocal nodes
        if isinstance(value, Mapping):
            nodes += 1
            if value.get("type") == "FunctionCall":
                name = str(value.get("name") or "")
                if name:
                    functions.append(name)
                args = value.get("args") or ()
                if name in {"indicator", "rank", "queryData"} and len(args) >= 3:
                    indicator = _literal_value(args[2])
                    if indicator:
                        indicators.append(indicator)
                    market = _literal_value(args[0])
                    if market:
                        market_expressions.append(market)
                        scopes.append("market_scope")
                if name in {"indicator", "rank"} and len(args) >= 7:
                    aggregate = _literal_value(args[5 if name == "indicator" else 6])
                    count_expression = _literal_value(args[6 if name == "indicator" else 7]) if len(args) >= (7 if name == "indicator" else 8) else ""
                    scope = _literal_value(args[1])
                    if aggregate:
                        aggregates.append(aggregate.upper())
                    if count_expression:
                        count_expressions.append(count_expression.upper())
                    if scope:
                        scopes.append("filter_scope")
                elif name == "belong_industry":
                    scopes.append("industry")
            if value.get("type") == "Comparison":
                comparisons.append(str(value.get("op") or ""))
            if value.get("type") == "BinaryOp":
                booleans.append(str(value.get("op") or "").lower())
            for child in value.values():
                walk(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                walk(child)

    walk(ast)
    date_kinds = []
    stage_count = 0
    logical_nodes = 0

    def walk_logical(value: Any) -> None:
        nonlocal stage_count, logical_nodes
        if isinstance(value, Mapping):
            logical_nodes += 1
            kind = str(value.get("kind") or "")
            if kind == "LogicalStage":
                stage_count += 1
            if kind == "DateConstraint":
                date_kind = str(value.get("constraint_kind") or "")
                if date_kind and date_kind != "unspecified":
                    date_kinds.append(date_kind)
            for child in value.values():
                walk_logical(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                walk_logical(child)

    walk_logical(logical.get("plan") or {})
    temporal = any(item.startswith(("CONS", "EXIST")) for item in count_expressions)
    temporal_modes = tuple(
        sorted(
            {
                mode
                for item in count_expressions
                for mode in ("CONS", "EXIST")
                if item.startswith(mode)
            }
        )
    )
    long_horizon = _has_long_horizon(logical)
    has_interval = "between" in comparisons
    bitwise = any("&" in item for item in market_expressions)
    score = min(
        100,
        nodes
        + logical_nodes // 2
        + len(functions) * 3
        + stage_count * 12
        + int(temporal) * 10
        + int(long_horizon) * 10,
    )
    return QueryFeatures(
        function_families=tuple(sorted(set(functions))),
        indicator_ids=tuple(sorted(set(indicators))),
        aggregate_functions=tuple(sorted(set(aggregates))),
        temporal_modes=temporal_modes,
        date_kinds=tuple(sorted(set(date_kinds))),
        scope_kinds=tuple(sorted(set(scopes))),
        comparison_operators=tuple(sorted(set(comparisons))),
        boolean_operators=tuple(sorted(set(booleans))),
        node_count=nodes + logical_nodes,
        stage_count=stage_count,
        has_rank="rank" in functions,
        has_temporal=temporal,
        has_stage=stage_count > 0,
        has_scope=bool(scopes),
        has_aggregate=bool(aggregates),
        has_interval=has_interval,
        has_bitwise_alias=bitwise,
        long_horizon=long_horizon,
        complexity_score=score,
    )


def _route_kind(
    strategy: str,
    resource_id: Any,
    features: QueryFeatures,
    context: CompileContext,
) -> str:
    folded = strategy.casefold()
    if "prefix" in folded:
        return "PREFIX"
    if "materialized" in folded:
        return "MV"
    if resource_id is not None:
        try:
            resource = context.physical_catalog.resource(str(resource_id))
        except KeyError:
            resource = None
        if resource is not None:
            capabilities = set(resource.capabilities)
            if "prefix" in capabilities and features.has_aggregate:
                return "PREFIX"
            if "materialized_aggregate" in capabilities and features.has_aggregate:
                return "MV"
            if resource.partition_key and features.date_kinds:
                return "PARTITION"
    return "RAW"


def _has_long_horizon(logical: Mapping[str, Any]) -> bool:
    stack = [logical.get("plan")]
    while stack:
        value = stack.pop()
        if isinstance(value, Mapping):
            if value.get("kind") == "DateConstraint":
                kind = value.get("constraint_kind")
                amount = value.get("amount")
                unit = value.get("unit")
                if kind in {"full_history", "year", "year_range"}:
                    return True
                if isinstance(amount, int) and (
                    (unit == "session" and amount >= 250)
                    or (unit == "day" and amount >= 365)
                    or (unit == "month" and amount >= 12)
                ):
                    return True
            stack.extend(value.values())
        elif isinstance(value, (list, tuple)):
            stack.extend(value)
    return False


def _literal_value(value: Any) -> str:
    if isinstance(value, Mapping) and value.get("type") == "Literal":
        return str(value.get("value") or "").strip()
    return ""


def _optional_float(value: Any) -> Optional[float]:
    return None if value is None else float(value)

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from time import perf_counter_ns
from typing import Any, Dict, Tuple

from .backend.doris import render_doris
from .frontend.antlr_frontend import AntlrOfficialFrontend
from .lowering import lower_official_ast
from .optimizer import DEFAULT_RULES, Optimizer
from .physical.catalog import default_physical_catalog
from .physical.expressions import default_physical_expressions
from .physical.planner import plan_physical
from .physical.statistics import default_physical_statistics
from .physical.strategies import default_physical_strategies
from .registry import default_official_registry
from .semantics import OfficialSemanticAnalyzer


@dataclass(frozen=True)
class OfficialPipelineOptions:
    use_statistics: bool = True
    use_strategies: bool = True
    allow_shadow_strategies: bool = False


class OfficialPipelineError(ValueError):
    def __init__(
        self,
        stage: str,
        code: str,
        message: str,
        *,
        partial: Dict[str, Any],
        diagnostics: Tuple[Dict[str, Any], ...] = (),
    ):
        super().__init__(message)
        self.stage = stage
        self.code = code
        self.partial = partial
        self.diagnostics = diagnostics

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": False,
            "stage": self.stage,
            "code": self.code,
            "message": str(self),
            "diagnostics": list(self.diagnostics),
            "partial": self.partial,
        }


@dataclass(frozen=True)
class OfficialPipelineResult:
    source: str
    frontend: Dict[str, Any]
    typed_ast: Dict[str, Any]
    logical: Dict[str, Any]
    optimized: Dict[str, Any]
    physical: Dict[str, Any]
    backend: Dict[str, Any]
    elapsed_ns: int

    @property
    def elapsed_ms(self) -> float:
        return round(self.elapsed_ns / 1_000_000, 4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "source": self.source,
            "frontend": self.frontend,
            "typed_ast": self.typed_ast,
            "logical": self.logical,
            "optimized": self.optimized,
            "physical": self.physical,
            "backend": self.backend,
            "elapsed_ms": self.elapsed_ms,
        }


def compile_official(
    source: str,
    options: OfficialPipelineOptions = OfficialPipelineOptions(),
) -> OfficialPipelineResult:
    started = perf_counter_ns()
    partial: Dict[str, Any] = {"source": source}

    frontend = AntlrOfficialFrontend().parse(str(source or ""), original_source=source)
    partial["frontend"] = frontend.to_dict()
    if not frontend.ok:
        diagnostic = frontend.diagnostics[0]
        raise OfficialPipelineError(
            "frontend",
            diagnostic.code,
            diagnostic.message,
            partial=partial,
            diagnostics=tuple(item.to_dict() for item in frontend.diagnostics),
        )

    registry = default_official_registry()
    try:
        typed = OfficialSemanticAnalyzer(registry.resolve_optional).analyze(frontend.ast)
    except Exception as exc:
        _raise_pipeline_error("typed", exc, partial)
    partial["typed_ast"] = typed.to_dict()

    try:
        logical = lower_official_ast(typed, strict=True, domain_registry=registry)
    except Exception as exc:
        _raise_pipeline_error("logical", exc, partial)
    partial["logical"] = logical.to_dict()

    optimized = Optimizer(DEFAULT_RULES).optimize(logical.plan)
    partial["optimized"] = optimized.to_dict()
    if optimized.diagnostics:
        raise OfficialPipelineError(
            "optimizer",
            "OFFICIAL_OPTIMIZER_DIAGNOSTIC",
            "; ".join(optimized.diagnostics),
            partial=partial,
            diagnostics=tuple({"message": item} for item in optimized.diagnostics),
        )
    optimized_lowering = replace(logical, plan=optimized.plan)

    catalog = default_physical_catalog()
    expressions = default_physical_expressions(catalog)
    statistics = default_physical_statistics(catalog) if options.use_statistics else None
    strategies = default_physical_strategies(catalog) if options.use_strategies else None
    try:
        physical = plan_physical(
            optimized_lowering,
            catalog,
            statistics=statistics,
            strategies=strategies,
            expressions=expressions,
            allow_shadow_strategies=options.allow_shadow_strategies,
        )
    except Exception as exc:
        decisions = tuple(asdict(item) for item in getattr(exc, "decisions", ()))
        _raise_pipeline_error("physical", exc, partial, diagnostics=decisions)
    partial["physical"] = _physical_payload(physical)

    try:
        rendered = render_doris(physical.plan, catalog, expressions)
    except Exception as exc:
        _raise_pipeline_error("backend", exc, partial)
    backend = {
        "sql": rendered.sql,
        "round_trip_stable": rendered.round_trip_stable,
        "validation_passed": rendered.ast_validation.passed,
        "validation_issues": list(rendered.ast_validation.issues),
        "safety_passed": rendered.validation.passed,
        "safety_issues": [item.to_dict() for item in rendered.validation.issues],
        "table_references": list(rendered.validation.table_references),
    }
    return OfficialPipelineResult(
        source,
        partial["frontend"],
        partial["typed_ast"],
        partial["logical"],
        partial["optimized"],
        partial["physical"],
        backend,
        perf_counter_ns() - started,
    )


def _physical_payload(result) -> Dict[str, Any]:
    return {
        "plan": result.plan.to_dict(),
        "plan_id": result.plan.node_id,
        "selected_resource": result.selected_resource,
        "selected_strategy": result.selected_strategy,
        "decisions": [asdict(item) for item in result.decisions],
    }


def _raise_pipeline_error(stage, exc, partial, diagnostics=()):
    raise OfficialPipelineError(
        stage,
        str(getattr(exc, "code", type(exc).__name__)),
        str(exc),
        partial=partial.copy(),
        diagnostics=tuple(diagnostics),
    ) from exc

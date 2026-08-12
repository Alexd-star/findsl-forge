from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from time import perf_counter_ns
from typing import Any, Dict, Tuple

from .backend.doris import render_doris
from .context import CompileContext, default_compile_context
from .explain import build_explain
from .frontend.antlr_frontend import AntlrOfficialFrontend
from .lowering import lower_official_ast
from .optimizer import DEFAULT_RULES, Optimizer
from .physical.planner import plan_physical
from .physical.runtime import use_physical_runtime
from .semantics import OfficialSemanticAnalyzer


@dataclass(frozen=True)
class OfficialPipelineOptions:
    use_statistics: bool = True
    use_strategies: bool = True
    allow_shadow_strategies: bool = False
    strategy_mode: str = "auto"
    verify_sql_round_trip: bool = False

    def __post_init__(self):
        if self.strategy_mode not in {"auto", "force_baseline", "force_candidate"}:
            raise ValueError("strategy_mode must be auto, force_baseline, or force_candidate")
        if self.strategy_mode == "force_candidate" and not self.use_strategies:
            raise ValueError("force_candidate requires physical strategies")


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
    explain: Dict[str, Any]
    compile_context: Dict[str, Any]
    timings_ns: Dict[str, int]
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
            "explain": self.explain,
            "compile_context": self.compile_context,
            "timings_ns": self.timings_ns,
            "elapsed_ms": self.elapsed_ms,
        }


def compile_official(
    source: str,
    options: OfficialPipelineOptions = OfficialPipelineOptions(),
    context: CompileContext | None = None,
) -> OfficialPipelineResult:
    started = perf_counter_ns()
    timings: Dict[str, int] = {}
    partial: Dict[str, Any] = {"source": source, "timings_ns": timings}
    stage_started = perf_counter_ns()
    try:
        compile_context = context or default_compile_context()
        compile_context.assert_current()
    except Exception as exc:
        _raise_pipeline_error("context", exc, partial)
    timings["context_preflight"] = perf_counter_ns() - stage_started
    partial["compile_context"] = compile_context.to_dict()

    stage_started = perf_counter_ns()
    frontend = AntlrOfficialFrontend().parse(str(source or ""), original_source=source)
    timings["frontend"] = perf_counter_ns() - stage_started
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

    registry = compile_context.registry
    stage_started = perf_counter_ns()
    try:
        typed = OfficialSemanticAnalyzer(
            registry.resolve_optional,
            compile_context.function_catalog,
        ).analyze(frontend.ast)
    except Exception as exc:
        _raise_pipeline_error("typed", exc, partial)
    timings["typed"] = perf_counter_ns() - stage_started
    partial["typed_ast"] = typed.to_dict()

    stage_started = perf_counter_ns()
    try:
        logical = lower_official_ast(typed, strict=True, domain_registry=registry)
    except Exception as exc:
        _raise_pipeline_error("logical", exc, partial)
    timings["logical"] = perf_counter_ns() - stage_started
    partial["logical"] = logical.to_dict()

    stage_started = perf_counter_ns()
    optimized = Optimizer(DEFAULT_RULES).optimize(logical.plan)
    timings["optimizer"] = perf_counter_ns() - stage_started
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

    catalog = compile_context.physical_catalog
    expressions = compile_context.physical_expressions
    statistics = compile_context.physical_statistics if options.use_statistics else None
    strategies = (
        compile_context.physical_strategies
        if options.use_strategies and options.strategy_mode != "force_baseline"
        else None
    )
    stage_started = perf_counter_ns()
    try:
        with use_physical_runtime(compile_context.physical_runtime):
            physical = plan_physical(
                optimized_lowering,
                catalog,
                statistics=statistics,
                strategies=strategies,
                expressions=expressions,
                allow_shadow_strategies=(
                    options.allow_shadow_strategies
                    or options.strategy_mode == "force_candidate"
                ),
            )
        if (
            options.strategy_mode == "force_candidate"
            and not any(
                item.selected and item.strategy_id not in {
                    "direct_column",
                    "controlled_expression",
                    "grouped_aggregate",
                }
                for item in physical.decisions
            )
        ):
            raise ValueError("no eligible non-baseline physical candidate exists")
    except Exception as exc:
        decisions = tuple(asdict(item) for item in getattr(exc, "decisions", ()))
        _raise_pipeline_error("physical", exc, partial, diagnostics=decisions)
    timings["physical"] = perf_counter_ns() - stage_started
    partial["physical"] = _physical_payload(physical, compile_context, options)

    stage_started = perf_counter_ns()
    try:
        with use_physical_runtime(compile_context.physical_runtime):
            rendered = render_doris(
                physical.plan,
                catalog,
                expressions,
                verify_round_trip=options.verify_sql_round_trip,
            )
    except Exception as exc:
        _raise_pipeline_error("backend", exc, partial)
    timings["backend"] = perf_counter_ns() - stage_started
    backend = {
        "sql": rendered.sql,
        "round_trip_checked": rendered.round_trip_checked,
        "round_trip_stable": rendered.round_trip_stable,
        "validation_passed": rendered.ast_validation.passed,
        "validation_issues": list(rendered.ast_validation.issues),
        "safety_passed": rendered.validation.passed,
        "safety_issues": [item.to_dict() for item in rendered.validation.issues],
        "table_references": list(rendered.validation.table_references),
    }
    stage_started = perf_counter_ns()
    try:
        compile_context.assert_current()
    except Exception as exc:
        _raise_pipeline_error("context", exc, partial)
    timings["context_postflight"] = perf_counter_ns() - stage_started
    stage_started = perf_counter_ns()
    explain = build_explain(
        source=source,
        frontend=partial["frontend"],
        typed_ast=partial["typed_ast"],
        logical=partial["logical"],
        optimized=partial["optimized"],
        physical=partial["physical"],
        backend=backend,
        context=compile_context,
    ).to_dict()
    timings["explain"] = perf_counter_ns() - stage_started
    elapsed_ns = perf_counter_ns() - started
    timings["total"] = elapsed_ns
    return OfficialPipelineResult(
        source,
        partial["frontend"],
        partial["typed_ast"],
        partial["logical"],
        partial["optimized"],
        partial["physical"],
        backend,
        explain,
        partial["compile_context"],
        dict(timings),
        elapsed_ns,
    )


def _physical_payload(
    result,
    context: CompileContext,
    options: OfficialPipelineOptions,
) -> Dict[str, Any]:
    return {
        "plan": result.plan.to_dict(),
        "physical_node_id": result.plan.node_id,
        "plan_id": context.versioned_plan_id(result.plan.node_id, asdict(options)),
        "catalog_snapshot_id": context.context_id,
        "policy_id": context.snapshot.policy_id,
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

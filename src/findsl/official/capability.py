from __future__ import annotations

from typing import Any, Dict, Mapping, Set

from .context import CompileContext
from .pipeline import OfficialPipelineError, OfficialPipelineResult


SUPPORTED = "SUPPORTED"
DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
INVALID_INPUT = "INVALID_INPUT"
CAPABILITY_GAP = "CAPABILITY_GAP"


def supported_capability_report(
    result: OfficialPipelineResult,
    context: CompileContext,
) -> Dict[str, Any]:
    explain = result.explain
    physical = result.physical
    rules = explain.get("applied_financial_rules") or ()
    return {
        "supported": True,
        "status": SUPPORTED,
        "stage": "complete",
        "code": "FINDSL_QUERY_SUPPORTED",
        "message": "DSL is supported by the active compiler and data profile",
        "remediation": "none",
        "context_id": context.context_id,
        "profile_id": context.snapshot.profile_id,
        "plan_id": physical["plan_id"],
        "selected_route": explain["adaptive_route"]["selected_route"],
        "selected_strategy": physical["selected_strategy"],
        "function_families": list(explain["query_features"]["function_families"]),
        "indicator_ids": list(explain["query_features"]["indicator_ids"]),
        "required_resources": sorted(_physical_resources(physical["plan"])),
        "applied_financial_rule_ids": [item["rule_id"] for item in rules],
        "compile_elapsed_ms": result.elapsed_ms,
    }


def rejected_capability_report(
    error: OfficialPipelineError,
    context: CompileContext,
) -> Dict[str, Any]:
    status = classify_pipeline_error(error)
    return {
        "supported": False,
        "status": status,
        "stage": error.stage,
        "code": error.code,
        "message": str(error),
        "remediation": _remediation(status),
        "context_id": context.context_id,
        "profile_id": context.snapshot.profile_id,
        "plan_id": None,
        "selected_route": None,
        "selected_strategy": None,
        "function_families": [],
        "indicator_ids": [],
        "required_resources": [],
        "applied_financial_rule_ids": [],
        "compile_elapsed_ms": _partial_elapsed_ms(error.partial),
    }


def classify_pipeline_error(error: OfficialPipelineError) -> str:
    code = str(error.code).upper()
    if "DATA_UNAVAILABLE" in code or code in {
        "PHYSICAL_SCOPE_DATA_UNAVAILABLE",
        "PHYSICAL_RESOURCE_DATA_UNAVAILABLE",
    }:
        return DATA_UNAVAILABLE
    if error.stage == "frontend":
        return INVALID_INPUT
    if error.stage in {"typed", "logical"} and not any(
        token in code for token in ("UNSUPPORTED", "UNAVAILABLE", "MISSING")
    ):
        return INVALID_INPUT
    return CAPABILITY_GAP


def _physical_resources(value: Any) -> Set[str]:
    resources: Set[str] = set()

    def walk(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                if key in {
                    "resource_id",
                    "lookup_resource_id",
                    "anchor_resource_id",
                } and isinstance(child, str):
                    resources.update(part for part in child.split("+") if part)
                walk(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                walk(child)

    walk(value)
    return resources


def _partial_elapsed_ms(partial: Mapping[str, Any]) -> float:
    timings = partial.get("timings_ns") or {}
    return round(sum(int(value) for value in timings.values()) / 1_000_000, 4)


def _remediation(status: str) -> str:
    if status == DATA_UNAVAILABLE:
        return (
            "load a versioned dataset registered for the active profile, or use an "
            "officially supported data scope"
        )
    if status == INVALID_INPUT:
        return "correct the DSL syntax, function signature, argument type or required slot"
    return (
        "use a supported capability or add a declarative mapping, controlled function "
        "template, optimizer rule or reviewed physical plugin"
    )

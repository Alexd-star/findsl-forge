from __future__ import annotations

import re
from typing import Any, Dict, Mapping, Set, Tuple

from .context import CompileContext
from .domain.binder import parse_date_constraint
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
    indicator_ids = list(explain["query_features"]["indicator_ids"])
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
        "indicator_ids": indicator_ids,
        "data_requirements": list(
            _domain_payloads(
                (
                    *_indicator_domain_definitions(indicator_ids, context),
                    *_target_domain_definitions(result.typed_ast, context),
                ),
                context,
            )
        ),
        "required_resources": sorted(_physical_resources(physical["plan"])),
        "applied_financial_rule_ids": [item["rule_id"] for item in rules],
        "compile_elapsed_ms": result.elapsed_ms,
        "clarification": None,
    }


def rejected_capability_report(
    error: OfficialPipelineError,
    context: CompileContext,
) -> Dict[str, Any]:
    requirements = _rejected_data_requirements(error, context)
    status = classify_pipeline_error(error, data_requirements=requirements)
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
        "data_requirements": list(requirements),
        "required_resources": [],
        "applied_financial_rule_ids": [],
        "compile_elapsed_ms": _partial_elapsed_ms(error.partial),
        "clarification": _clarification(error, status),
    }


def classify_pipeline_error(
    error: OfficialPipelineError,
    *,
    data_requirements: Tuple[Dict[str, Any], ...] = (),
) -> str:
    code = str(error.code).upper()
    if "DATA_UNAVAILABLE" in code or code in {
        "PHYSICAL_SCOPE_DATA_UNAVAILABLE",
        "PHYSICAL_RESOURCE_DATA_UNAVAILABLE",
    }:
        return DATA_UNAVAILABLE
    if any(
        item["profile"]["status"] in {"not_loaded", "private_required"}
        for item in data_requirements
    ):
        return DATA_UNAVAILABLE
    if _has_ambiguous_date(error):
        return INVALID_INPUT
    if _needs_date_clarification(error):
        return INVALID_INPUT
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


_INTRADAY_DATE = re.compile(
    r"(?:\d{1,2}[.:]\d{2}|分钟|早盘|尾盘|盘中|午盘|上午|下午|中午|日内|"
    r"盘前|盘后|开盘后|收盘后|集合竞价|两点半|刚刚|此时)"
)
_REPORTING_DATE = re.compile(r"(?:年报|季报|半年报|一季报|三季报|报告期)")
_LISTING_DATE = re.compile(r"(?:上市以来|上市后|上市的?第一个交易日)")
_AMBIGUOUS_DATE = {"最近", "近期", "前期", "当前阶段"}
_FUND_TYPES = re.compile(r"(?:ETF|LOF|基金|REITs|货币)", re.IGNORECASE)
_CROSS_MARKET_TYPES = re.compile(r"(?:港股|美股|期货|债券|可转债|(?:^|[|&])港(?:$|[|&])|(?:^|[|&])美(?:$|[|&]))")
_PRIVATE_TERMS = re.compile(r"(?:我的|自选股|持仓|账户|组合)")
_INTRADAY_INDICATOR = re.compile(
    r"(?:\d+分钟|分时|盘口|集合竞价|涨速|委比|委差|内盘|外盘)"
)


def _indicator_domain_definitions(indicator_ids, context):
    definitions = []
    for indicator_id in indicator_ids:
        definition = context.registry.resolve_optional(indicator_id)
        if definition is None:
            continue
        domain = context.data_domain_catalog.resolve_indicator_domain(definition.domain)
        if domain is not None:
            definitions.append(domain)
    return tuple(definitions)


def _rejected_data_requirements(error, context):
    definitions = []
    code = str(error.code).upper()
    if code in {
        "PHYSICAL_SCOPE_DATA_UNAVAILABLE",
        "PHYSICAL_INDUSTRY_DATA_UNAVAILABLE",
    }:
        definitions.append(context.data_domain_catalog.resolve("scope_membership"))
    if code == "PHYSICAL_MARKET_DATA_UNAVAILABLE":
        definitions.append(
            context.data_domain_catalog.resolve("cross_market_quote")
        )
    slots = tuple(_binding_slots(error.partial.get("typed_ast")))
    for item in slots:
        for key, value in item.items():
            if not key.startswith("indicator_name") or not str(value).strip():
                continue
            definition = context.registry.resolve_optional(str(value))
            if definition is None:
                continue
            domain = context.data_domain_catalog.resolve_indicator_domain(
                definition.domain
            )
            if domain is not None:
                definitions.append(domain)
            if _INTRADAY_INDICATOR.search(str(value)):
                definitions.append(
                    context.data_domain_catalog.resolve("intraday_quote")
                )
        date_value = str(item.get("date", item.get("period", ""))).strip()
        if _INTRADAY_DATE.search(date_value):
            definitions.append(context.data_domain_catalog.resolve("intraday_quote"))
        if _REPORTING_DATE.search(date_value):
            definitions.append(
                context.data_domain_catalog.resolve("financial_statement")
            )
        if _LISTING_DATE.search(date_value):
            definitions.append(context.data_domain_catalog.resolve("corporate_event"))
        market_value = str(item.get("market", "")).strip()
        if _CROSS_MARKET_TYPES.search(market_value):
            definitions.append(
                context.data_domain_catalog.resolve("cross_market_quote")
            )
        select_type = str(item.get("select_type", "")).strip()
        if _FUND_TYPES.search(select_type):
            definitions.append(context.data_domain_catalog.resolve("fund_reference"))
    definitions.extend(_target_domain_definitions(error.partial.get("typed_ast"), context))
    source = str(error.partial.get("source", ""))
    if _PRIVATE_TERMS.search(source):
        definitions.append(context.data_domain_catalog.resolve("private_account"))
    return _domain_payloads(definitions, context)


def _target_domain_definitions(typed_ast, context):
    definitions = []
    for slots in _binding_slots(typed_ast):
        try:
            target = context.entity_target_catalog.bind(
                str(slots.get("select_type", "")),
                data_domains=context.data_domain_catalog,
                profile_id=context.snapshot.profile_id,
            )
        except (KeyError, ValueError):
            continue
        definitions.extend(
            context.data_domain_catalog.resolve(domain_id)
            for domain_id in target.required_data_domains
        )
    return tuple(definitions)


def _domain_payloads(definitions, context):
    payloads = []
    seen = set()
    for definition in definitions:
        if definition.domain_id in seen:
            continue
        seen.add(definition.domain_id)
        payload = definition.to_dict(profile_id=context.snapshot.profile_id)
        profile = payload["profile"]
        provider_ids = tuple(
            dict.fromkeys(
                (*profile["active_provider_ids"], *profile["candidate_provider_ids"])
            )
        )
        payload["providers"] = [
            _provider_payload(context.external_source_registry.resolve(provider_id))
            for provider_id in provider_ids
        ]
        payloads.append(payload)
    return tuple(payloads)


def _provider_payload(provider):
    return {
        "provider_id": provider.provider_id,
        "authority_level": provider.authority_level,
        "temporal_model": provider.temporal_model,
        "redistribution": provider.redistribution,
        "source_url": provider.source_url,
    }


def _binding_slots(value):
    if isinstance(value, Mapping):
        binding = value.get("binding")
        if isinstance(binding, Mapping) and isinstance(binding.get("slots"), Mapping):
            yield binding["slots"]
        for child in value.values():
            yield from _binding_slots(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _binding_slots(child)


def _has_ambiguous_date(error):
    return any(
        str(slots.get("date", slots.get("period", ""))).strip()
        in _AMBIGUOUS_DATE
        for slots in _binding_slots(error.partial.get("typed_ast"))
    )


def _needs_date_clarification(error):
    if str(error.code).upper() != "PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED":
        return False
    message = str(error)
    if "all-history scalar requires an explicit aggregate" in message:
        return True
    for slots in _binding_slots(error.partial.get("typed_ast")):
        value = str(slots.get("date", slots.get("period", ""))).strip()
        if not value:
            continue
        try:
            constraint = parse_date_constraint(value)
        except ValueError:
            return True
        if constraint.kind == "expression":
            return True
    return False


def _clarification(error, status):
    if status != INVALID_INPUT or not (
        _has_ambiguous_date(error) or _needs_date_clarification(error)
    ):
        return None
    values = []
    for slots in _binding_slots(error.partial.get("typed_ast")):
        value = str(slots.get("date", slots.get("period", ""))).strip()
        if not value:
            continue
        try:
            unresolved = parse_date_constraint(value).kind == "expression"
        except ValueError:
            unresolved = True
        if value in _AMBIGUOUS_DATE or unresolved:
            values.append(value)
    values = sorted(set(values))
    return {
        "required": True,
        "field": "date",
        "values": values,
        "question": (
            "请明确日期的起止边界、年份或事件锚点；系统不会自行猜测并执行。"
        ),
    }

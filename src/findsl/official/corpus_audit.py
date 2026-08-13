from __future__ import annotations

import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from .ast import (
    OfficialBinaryOp,
    OfficialComparison,
    OfficialFunctionCall,
    OfficialLimit,
    OfficialLiteral,
    OfficialNode,
    OfficialRangeLiteral,
    walk,
)
from .frontend.antlr_frontend import AntlrOfficialFrontend
from .literals import is_numeric_percent_literal
from .repair import OfficialRepairCatalog
from .service import OfficialCompilerService


_AMBIGUOUS_DATES = {"最近", "近期", "前期", "当前阶段"}
_DATE_INDICATOR = re.compile(r"(?:日期|时间|时点|上市日|到期日|报告日)")
_PRIVATE_TERMS = re.compile(r"(?:我的|自选股|持仓|账户|组合)")
_CAPABILITY_FAMILIES = {
    "PHYSICAL_GROUP_BOUND_UNSUPPORTED": "group_bound",
    "PHYSICAL_GROUP_METRIC_POLICY_UNAVAILABLE": "group_metric_policy",
    "PHYSICAL_ENTITY_TARGET_MISMATCH": "entity_target",
    "PHYSICAL_ENTITY_MARKET_UNSUPPORTED": "entity_market",
    "PHYSICAL_ENTITY_INDICATOR_UNSUPPORTED": "entity_indicator",
    "PHYSICAL_ENTITY_SCOPE_UNSUPPORTED": "entity_scope",
    "PHYSICAL_GROUP_TEMPORAL_BUCKET_UNSUPPORTED": "group_temporal_bucket",
    "PHYSICAL_GROUP_TEMPORAL_PREDICATE_UNSUPPORTED": "group_temporal_predicate",
    "PHYSICAL_EVENT_PERIOD_UNSUPPORTED": "event_period",
    "PHYSICAL_GROUP_COMPOSITE_SCOPE_UNSUPPORTED": "group_composite_scope",
    "PHYSICAL_RANK_EXPRESSION_UNSUPPORTED": "rank_expression",
    "PHYSICAL_PLAN_UNAVAILABLE": "physical_plan",
    "DORIS_JOIN_SHAPE_UNSUPPORTED": "doris_join_shape",
    "PHYSICAL_EVENT_COMPOSITION_UNSUPPORTED": "event_composition",
    "PHYSICAL_GROUP_EXPRESSION_UNSUPPORTED": "group_expression",
    "PHYSICAL_GROUP_AGGREGATION_UNSUPPORTED": "group_aggregation",
    "PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED": "date_constraint",
}


def build_corpus_audit(
    funnel: Mapping[str, Any],
    service: OfficialCompilerService,
    *,
    repair_catalog: Optional[OfficialRepairCatalog] = None,
    baseline_status_by_row: Optional[Mapping[int, str]] = None,
) -> Dict[str, Any]:
    repair_catalog = repair_catalog or service.repair_catalog
    rows = []
    current_statuses: Counter[str] = Counter()
    baseline_statuses: Counter[str] = Counter()
    roots: Counter[str] = Counter()
    capability_families: Counter[str] = Counter()
    type_evidence: Dict[str, Counter[str]] = defaultdict(Counter)
    type_examples: Dict[str, Dict[str, list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for row in funnel["rows"]:
        source = str(row["source"])
        parsed = AntlrOfficialFrontend().parse(source, original_source=source)
        capability = service.negotiate(source)["capability"]
        bindings = _slot_bindings(parsed.ast, service) if parsed.ok else ()
        missing = _missing_indicators(bindings, service)
        constraints = _infer_indicator_constraints(parsed.ast, service) if parsed.ok else {}
        for name, expected in constraints.items():
            if name not in missing:
                continue
            for kind in expected:
                type_evidence[name][kind] += 1
                examples = type_examples[name][kind]
                if len(examples) < 5:
                    examples.append(int(row["excel_row"]))

        baseline_status = (
            str(baseline_status_by_row[int(row["excel_row"])])
            if baseline_status_by_row is not None
            else _classify_baseline(row, capability, bindings, source)
        )
        root_cause, resolution = _root_cause(
            row,
            capability,
            bindings,
            missing,
            constraints,
            repair_catalog.suggest(source),
        )
        family = _CAPABILITY_FAMILIES.get(str(row.get("terminal_code", "")))
        if baseline_status == "CAPABILITY_GAP" and family:
            capability_families[family] += 1
        current_statuses[capability["status"]] += 1
        baseline_statuses[baseline_status] += 1
        roots[root_cause] += 1
        rows.append(
            {
                "excel_row": int(row["excel_row"]),
                "source": source,
                "baseline_status": baseline_status,
                "baseline_stage": row.get("terminal_stage"),
                "baseline_code": row.get("terminal_code"),
                "current_status": capability["status"],
                "current_stage": capability["stage"],
                "current_code": capability["code"],
                "root_cause": root_cause,
                "resolution": resolution,
                "missing_indicators": list(missing),
                "indicator_type_evidence": {
                    name: sorted(constraints.get(name, ())) for name in missing
                },
                "data_requirements": [
                    {
                        "domain_id": item["domain_id"],
                        "profile_status": item["profile"]["status"],
                        "candidate_provider_ids": item["profile"][
                            "candidate_provider_ids"
                        ],
                    }
                    for item in capability["data_requirements"]
                ],
                "safe_repair": (
                    repair_catalog.suggest(source).to_dict()
                    if repair_catalog.suggest(source)
                    else None
                ),
                "must_reject_without_confirmation": capability["status"]
                != "SUPPORTED",
            }
        )

    indicator_contracts = []
    for name in sorted(type_evidence):
        evidence = type_evidence[name]
        kinds = sorted(evidence)
        indicator_contracts.append(
            {
                "indicator_name": name,
                "suggested_value_type": kinds[0] if len(kinds) == 1 else None,
                "status": "UNAMBIGUOUS" if len(kinds) == 1 else "CONFLICT",
                "evidence_counts": dict(sorted(evidence.items())),
                "example_rows": {
                    kind: type_examples[name][kind] for kind in kinds
                },
                "promotion_policy": (
                    "requires business definition, field lineage, dataset admission and "
                    "independent reference cases before compiler enablement"
                ),
            }
        )

    return {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "git_head": _git_head(),
        "baseline_git_head": funnel.get("git_head"),
        "profile_id": service.context.snapshot.profile_id,
        "source_sha256": funnel["source_sha256"],
        "row_count": funnel["row_count"],
        "baseline_status_counts": dict(sorted(baseline_statuses.items())),
        "current_status_counts": dict(sorted(current_statuses.items())),
        "root_cause_counts": dict(sorted(roots.items())),
        "baseline_capability_family_counts": dict(
            sorted(capability_families.items())
        ),
        "indicator_contracts": indicator_contracts,
        "rows": rows,
    }


def render_corpus_audit_markdown(report: Mapping[str, Any]) -> str:
    baseline = report["baseline_status_counts"]
    current = report["current_status_counts"]
    lines = [
        "# 官方 5799 条语料逐行根因审计",
        "",
        f"- 数据配置：`{report['profile_id']}`",
        f"- 当前代码：`{report['git_head']}`",
        f"- 历史基线代码：`{report['baseline_git_head']}`",
        f"- 语料指纹：`{report['source_sha256']}`",
        f"- 总行数：`{report['row_count']}`",
        "",
        "## 口径校正",
        "",
        "旧口径中的 `INVALID_INPUT` 混入了大量类型尚未定义的缺失指标。"
        "本次审计保留旧分类用于追溯，同时用 `unknown` 类型继续执行到数据绑定阶段，"
        "从而区分真正输入错误、缺数据、缺业务定义和编译能力缺口。",
        "",
        "| 分类 | 旧基线 | 当前根因化口径 |",
        "|---|---:|---:|",
    ]
    for status in sorted(set(baseline) | set(current)):
        lines.append(
            f"| `{status}` | {baseline.get(status, 0)} | {current.get(status, 0)} |"
        )
    lines.extend(
        [
            "",
            "## 根因分布",
            "",
            "| 根因 | 问句数 |",
            "|---|---:|",
        ]
    )
    for cause, count in report["root_cause_counts"].items():
        lines.append(f"| `{cause}` | {count} |")
    lines.extend(
        [
            "",
            "## 原 85 条能力缺口的能力族",
            "",
            "| 能力族 | 问句数 |",
            "|---|---:|",
        ]
    )
    for family, count in report["baseline_capability_family_counts"].items():
        lines.append(f"| `{family}` | {count} |")
    lines.extend(
        [
            "",
            "## 安全处置原则",
            "",
            "只有异常台账中原文和 SHA-256 完全匹配的 7 条语法异常才提供修复候选；"
            "候选仍需人工确认，修复接口不会启动 Doris 执行。缺失数据快照、业务定义"
            "或指标类型的问句保持确定性拒绝，不能为了覆盖率生成不可审计 SQL。",
            "",
            "逐行证据及指标类型上下文位于同名 JSON 的 `rows` 和 "
            "`indicator_contracts` 字段。",
        ]
    )
    return "\n".join(lines) + "\n"


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "<unknown>"


def _slot_bindings(
    ast: OfficialNode, service: OfficialCompilerService
) -> Tuple[Mapping[str, Any], ...]:
    items = []
    for node in walk(ast):
        if not isinstance(node, OfficialFunctionCall):
            continue
        signature = service.context.function_catalog.resolve(node.name)
        if signature is None or signature.argument_mode != "slot_literals":
            continue
        slots = {
            slot: arg.value
            for slot, arg in zip(signature.slots, node.args)
            if isinstance(arg, OfficialLiteral)
        }
        items.append({"function": node.name, "slots": slots})
    return tuple(items)


def _missing_indicators(
    bindings: Iterable[Mapping[str, Any]], service: OfficialCompilerService
) -> Tuple[str, ...]:
    names = set()
    for item in bindings:
        for slot, value in item["slots"].items():
            if not slot.startswith("indicator_name") or not str(value).strip():
                continue
            definition = service.context.registry.resolve_optional(str(value))
            if definition is not None and definition.availability == "missing":
                names.add(definition.canonical_name)
    return tuple(sorted(names))


def _infer_indicator_constraints(
    ast: OfficialNode, service: OfficialCompilerService
) -> Dict[str, Tuple[str, ...]]:
    constraints: Dict[str, set[str]] = defaultdict(set)

    def constrain(node: OfficialNode, kind: str) -> None:
        for name in _indicator_names(node, service):
            definition = service.context.registry.resolve_optional(name)
            if definition is not None and definition.availability == "missing":
                constraints[definition.canonical_name].add(kind)

    for node in walk(ast):
        if isinstance(node, OfficialBinaryOp) and node.op in {"+", "-", "*", "/"}:
            constrain(node.left, "numeric")
            constrain(node.right, "numeric")
        elif isinstance(node, OfficialComparison):
            right_kind = _expression_kind(node.right, service)
            left_kind = _expression_kind(node.left, service)
            if node.op in {">", "<", ">=", "<=", "~="}:
                if right_kind:
                    constrain(node.left, right_kind)
                if left_kind:
                    constrain(node.right, left_kind)
            elif node.op in {"=", "==", "!="}:
                if right_kind:
                    constrain(node.left, right_kind)
                if left_kind:
                    constrain(node.right, left_kind)
            elif node.op == "between" and isinstance(node.right, OfficialRangeLiteral):
                kind = _expression_kind(node.right.lower, service)
                if kind:
                    constrain(node.left, kind)
        elif isinstance(node, OfficialFunctionCall):
            signature = service.context.function_catalog.resolve(node.name)
            if signature is None or signature.argument_mode != "slot_literals":
                continue
            if node.name in {
                "rank",
                "cross_above",
                "cross_down",
                "close_together",
                "reset",
                "golden_cross",
                "record_high",
                "record_low",
                "position",
            }:
                constrain(node, "numeric")
    for name in tuple(constraints):
        if _DATE_INDICATOR.search(name):
            constraints[name].discard("string")
            constraints[name].add("time")
    return {name: tuple(sorted(kinds)) for name, kinds in constraints.items()}


def _indicator_names(
    node: OfficialNode, service: OfficialCompilerService
) -> Tuple[str, ...]:
    names = []
    for child in walk(node):
        if not isinstance(child, OfficialFunctionCall):
            continue
        signature = service.context.function_catalog.resolve(child.name)
        if signature is None or signature.argument_mode != "slot_literals":
            continue
        for slot, arg in zip(signature.slots, child.args):
            if (
                slot.startswith("indicator_name")
                and isinstance(arg, OfficialLiteral)
                and str(arg.value).strip()
            ):
                names.append(str(arg.value))
    return tuple(names)


def _expression_kind(
    node: OfficialNode, service: OfficialCompilerService
) -> Optional[str]:
    if isinstance(node, OfficialLiteral):
        if isinstance(node.value, bool):
            return "boolean"
        if isinstance(node.value, (int, float)) or (
            isinstance(node.value, str) and is_numeric_percent_literal(node.value)
        ):
            return "numeric"
        if isinstance(node.value, str):
            return "string"
    if isinstance(node, OfficialRangeLiteral):
        return _expression_kind(node.lower, service)
    if isinstance(node, OfficialBinaryOp) and node.op in {"+", "-", "*", "/"}:
        return "numeric"
    if isinstance(node, OfficialComparison):
        return "boolean"
    if isinstance(node, OfficialLimit):
        return _expression_kind(node.expr, service)
    if isinstance(node, OfficialFunctionCall):
        signature = service.context.function_catalog.resolve(node.name)
        if signature is None:
            return None
        if signature.result_kind != "dynamic":
            return signature.result_kind
        names = _indicator_names(node, service)
        if len(names) == 1:
            definition = service.context.registry.resolve_optional(names[0])
            if definition is not None and definition.value_type != "unknown":
                return definition.value_type
    return None


def _classify_baseline(row, capability, bindings, source: str) -> str:
    if row.get("new_backend_success"):
        return "SUPPORTED"
    code = str(row.get("terminal_code", "")).upper()
    stage = str(row.get("terminal_stage", ""))
    if "DATA_UNAVAILABLE" in code:
        return "DATA_UNAVAILABLE"
    # Frontend and typed failures in the historical pipeline had no Typed AST,
    # so only source-level private-data detection was available at that point.
    if _PRIVATE_TERMS.search(source):
        return "DATA_UNAVAILABLE"
    historical_requirements = [
        item
        for item in capability["data_requirements"]
        if item["domain_id"]
        not in {"intraday_quote", "cross_market_quote", "fund_reference"}
    ]
    if stage not in {"frontend", "typed"} and any(
        item["profile"]["status"] in {"not_loaded", "private_required"}
        for item in historical_requirements
    ):
        return "DATA_UNAVAILABLE"
    if any(
        str(item["slots"].get("date", item["slots"].get("period", ""))).strip()
        in _AMBIGUOUS_DATES
        for item in bindings
    ):
        return "INVALID_INPUT"
    if stage == "frontend":
        return "INVALID_INPUT"
    if stage in {"typed", "logical"} and not any(
        token in code for token in ("UNSUPPORTED", "UNAVAILABLE", "MISSING")
    ):
        return "INVALID_INPUT"
    return "CAPABILITY_GAP"


def _root_cause(
    row,
    capability,
    bindings,
    missing,
    constraints,
    repair_candidate,
):
    if capability["status"] == "SUPPORTED":
        return "supported", "none"
    if repair_candidate is not None:
        return "registered_syntax_anomaly", "confirm_ledger_repair"
    if capability["stage"] == "frontend":
        return "unregistered_syntax_error", "manual_correction_required"
    profiles = {
        item["profile"]["status"] for item in capability["data_requirements"]
    }
    if "private_required" in profiles:
        return "private_data_required", "inject_authorized_private_snapshot"
    if "not_loaded" in profiles:
        return "dataset_snapshot_required", "admit_versioned_external_snapshot"
    if missing:
        inferred = {kind for name in missing for kind in constraints.get(name, ())}
        if any(len(constraints.get(name, ())) > 1 for name in missing):
            return "ambiguous_indicator_contract", "business_review_required"
        if inferred:
            return "missing_indicator_contract", "define_lineage_type_and_reference"
        return "undefined_business_semantics", "business_definition_required"
    if any(
        str(item["slots"].get("date", item["slots"].get("period", ""))).strip()
        in _AMBIGUOUS_DATES
        for item in bindings
    ):
        return "ambiguous_date", "manual_date_disambiguation"
    if capability["code"] == "OFFICIAL_TYPE_ERROR":
        return "incompatible_known_types", "reject_invalid_input"
    family = _CAPABILITY_FAMILIES.get(str(row.get("terminal_code", "")))
    if family:
        return f"capability_{family}", "implement_family_or_keep_safe_rejection"
    if "unsupported" in profiles:
        return "undefined_business_semantics", "business_definition_required"
    return "unclassified_rejection", "manual_review_required"

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any, Dict, Mapping, Tuple

from .adaptive import AdaptiveRoutePlanner, extract_query_features
from .context import CompileContext
from .optimizer import rule_contract_catalog


@dataclass(frozen=True)
class ExplainStage:
    stage: str
    status: str
    artifact_id: str
    summary: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FindslExplain:
    schema_version: int
    source: str
    query_features: Dict[str, Any]
    stages: Tuple[ExplainStage, ...]
    adaptive_route: Dict[str, Any]
    applied_financial_rules: Tuple[Dict[str, Any], ...]
    optimizer_rule_contracts: Tuple[Dict[str, Any], ...]
    guarantees: Tuple[str, ...]
    non_guarantees: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source": self.source,
            "query_features": self.query_features,
            "stages": [item.to_dict() for item in self.stages],
            "adaptive_route": self.adaptive_route,
            "applied_financial_rules": list(self.applied_financial_rules),
            "optimizer_rule_contracts": list(self.optimizer_rule_contracts),
            "guarantees": list(self.guarantees),
            "non_guarantees": list(self.non_guarantees),
        }


def build_explain(
    *,
    source: str,
    frontend: Mapping[str, Any],
    typed_ast: Mapping[str, Any],
    logical: Mapping[str, Any],
    optimized: Mapping[str, Any],
    physical: Mapping[str, Any],
    backend: Mapping[str, Any],
    context: CompileContext,
) -> FindslExplain:
    features = extract_query_features(frontend, logical)
    route = AdaptiveRoutePlanner(context).explain(physical, features)
    feature_payload = features.to_dict()
    financial_rules = tuple(
        item.to_dict() for item in context.financial_rules.select(feature_payload)
    )
    rewrite_trace = optimized.get("trace") or ()
    sql = str(backend.get("sql") or "")
    stages = (
        ExplainStage(
            "Parser",
            "PASS",
            _short_hash(frontend.get("ast")),
            "ANTLR4 completed deterministic parsing and source normalization.",
            {
                "frontend": frontend.get("frontend"),
                "normalized_source": frontend.get("normalized_source"),
                "repairs": frontend.get("repairs") or [],
                "diagnostics": frontend.get("diagnostics") or [],
            },
        ),
        ExplainStage(
            "Semantic",
            "PASS",
            _short_hash(typed_ast),
            "Function signatures, slot types, indicators, dates, markets and scopes are bound.",
            {
                "result_type": typed_ast.get("type"),
                "function_families": list(features.function_families),
                "indicator_ids": list(features.indicator_ids),
            },
        ),
        ExplainStage(
            "Logical IR",
            "PASS",
            str(logical.get("plan_id") or _short_hash(logical.get("plan"))),
            "Financial semantics are represented without SQL table or column names.",
            {
                "plan_kind": (logical.get("plan") or {}).get("kind"),
                "required_functions": logical.get("required_functions") or [],
                "validation_passed": logical.get("validation_passed"),
            },
        ),
        ExplainStage(
            "Rewrite",
            "PASS",
            str(optimized.get("plan_id") or _short_hash(optimized.get("plan"))),
            "Only contract-backed equivalence rules may replace the logical plan.",
            {
                "rules_fired": [item.get("rule_id") for item in rewrite_trace],
                "rewrite_count": len(rewrite_trace),
                "trace": list(rewrite_trace),
            },
        ),
        ExplainStage(
            "Route",
            "PASS",
            str(physical.get("plan_id") or _short_hash(physical.get("plan"))),
            "AdaptiveRoutePlanner records generated, rejected and fallback routes.",
            {
                "selected_route": route.selected_route,
                "selected_strategy": route.selected_strategy,
                "selected_candidate_id": route.selected_candidate_id,
                "selection_reason_code": route.selection_reason_code,
                "selection_reason": route.selection_reason,
                "selected_resource": physical.get("selected_resource"),
                "candidate_count": len(route.candidates),
                "fallback_chain": list(route.fallback_chain),
                "fallback_candidates": list(route.fallback_candidates),
            },
        ),
        ExplainStage(
            "Doris SQL",
            "PASS" if backend.get("safety_passed") and backend.get("validation_passed") else "FAIL",
            hashlib.sha256(sql.encode("utf-8")).hexdigest(),
            "The selected physical plan is rendered to validated, read-only Doris SQL.",
            {
                "table_references": backend.get("table_references") or [],
                "ast_validation_passed": backend.get("validation_passed"),
                "safety_passed": backend.get("safety_passed"),
                "sql_chars": len(sql),
            },
        ),
    )
    return FindslExplain(
        schema_version=2,
        source=source,
        query_features=feature_payload,
        stages=stages,
        adaptive_route=route.to_dict(),
        applied_financial_rules=financial_rules,
        optimizer_rule_contracts=tuple(
            item.to_dict() for item in rule_contract_catalog()
        ),
        guarantees=(
            "Only executable physical decisions produced by the canonical planner can be selected.",
            "Every applied optimizer rewrite has an explicit precondition, invariant and fallback contract.",
            "Missing data or an ineligible acceleration path is reported and never silently approximated.",
            "Generated SQL passes physical AST validation and read-only safety validation.",
        ),
        non_guarantees=(
            "Compile success alone does not prove result correctness on an unavailable data domain.",
            "Estimated cost is a routing signal, not a promise of wall-clock latency.",
            "Execution under ten seconds must be established by Doris runtime evidence for the workload.",
        ),
    )


def render_explain_markdown(explain: Mapping[str, Any]) -> str:
    route = explain["adaptive_route"]
    fallback = " -> ".join(route["fallback_chain"]) or "<none>"
    lines = [
        "# FINDSL EXPLAIN",
        "",
        f"- 选择路由：`{route['selected_route']}`",
        f"- 选择策略：`{route['selected_strategy']}`",
        f"- 选择候选：`{route['selected_candidate_id']}`",
        f"- 选择原因：`{route['selection_reason_code']}` - {_md(route['selection_reason'])}",
        f"- 回退顺序：`{fallback}`",
        f"- 查询复杂度：`{explain['query_features']['complexity_score']}`",
        "",
        "## 查询特征",
        "",
        "| 特征 | 值 |",
        "|---|---|",
    ]
    for key, value in explain["query_features"].items():
        lines.append(f"| `{key}` | {_md(_display(value))} |")
    lines.extend(
        [
            "",
            "## 编译阶段",
            "",
            "| 阶段 | 状态 | 产物标识 | 摘要 |",
            "|---|---|---|---|",
        ]
    )
    for stage in explain["stages"]:
        lines.append(
            f"| {stage['stage']} | {stage['status']} | "
            f"`{stage['artifact_id'][:16]}` | {_md(stage['summary'])} |"
        )
    lines.extend(
        [
            "",
            "## 自适应候选路由",
            "",
            "| 路由 | 策略 | 可执行 | 可选 | 已选择 | 成本 | 成本分解 | 语义等价 | 水位 | 未选原因 | 原因码 | 回退 |",
            "|---|---|---:|---:|---:|---:|---|---|---|---|---|---|",
        ]
    )
    for item in route["candidates"]:
        cost = (
            "-"
            if item["cost"] is None
            else f"{item['cost']:.3f} {item['cost_unit']}"
        )
        components = ", ".join(
            f"{name}={value:.6g}"
            for name, value in item.get("cost_components", ())
        ) or "-"
        lines.append(
            f"| {item['route_kind']} | `{item['strategy_id']}` | "
            f"{item['executable']} | {item['eligible']} | {item['selected']} | "
            f"{cost} | {_md(components)} | `{item['semantic_equivalence']}` | "
            f"`{item['watermark_status']}` | "
            f"`{item['rejection_category'] or '-'}` | `{item['reason_code']}` | "
            f"`{item['fallback_to'] or '-'}` |"
        )
    lines.extend(
        [
            "",
            "## 候选资格检查",
            "",
            "| 候选 | 检查项 | 状态 | 依据 |",
            "|---|---|---|---|",
        ]
    )
    for item in route["candidates"]:
        for check in item.get("eligibility_checks", ()):
            lines.append(
                f"| `{item['candidate_id']}` | `{check['check_id']}` | "
                f"{check['status']} | {_md(check['detail'])} |"
            )
    lines.extend(
        [
            "",
            "## 路由决策依据",
            "",
        ]
    )
    lines.extend(f"- {_md(item)}" for item in route["decision_basis"])
    lines.extend(
        [
            "",
            "## 生效的金融规则",
            "",
            "| 规则 | 类别 | 前置条件 | 语义不变量 | 回退码 | 回退行为 |",
            "|---|---|---|---|---|---|",
        ]
    )
    for item in explain["applied_financial_rules"]:
        lines.append(
            f"| `{item['rule_id']}` | {item['category']} | "
            f"{_md('; '.join(item['preconditions']))} | "
            f"{_md(item['semantic_invariant'])} | `{item['fallback_code']}` | "
            f"{_md(item['fallback_behavior'])} |"
        )
    lines.extend(
        [
            "",
            "## 优化规则契约",
            "",
            "| 规则 | 前置条件 | 语义不变量 | 回退 | 验证方法 |",
            "|---|---|---|---|---|",
        ]
    )
    for item in explain["optimizer_rule_contracts"]:
        lines.append(
            f"| `{item['rule_id']}` | {_md('; '.join(item['preconditions']))} | "
            f"{_md(item['semantic_invariant'])} | {_md(item['fallback'])} | "
            f"{_md(item['validation_strategy'])} |"
        )
    lines.extend(["", "## 能证明什么", ""])
    lines.extend(f"- {_md(item)}" for item in explain["guarantees"])
    lines.extend(["", "## 不能证明什么", ""])
    lines.extend(f"- {_md(item)}" for item in explain["non_guarantees"])
    return "\n".join(lines) + "\n"


def _display(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value) or "<none>"
    return str(value)


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

def _short_hash(value: Any) -> str:
    return hashlib.sha256(repr(value).encode("utf-8")).hexdigest()[:16]

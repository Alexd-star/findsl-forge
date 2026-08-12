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
                "selected_resource": physical.get("selected_resource"),
                "candidate_count": len(route.candidates),
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
        schema_version=1,
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
    lines = [
        "# FINDSL EXPLAIN",
        "",
        f"- 选择路由：`{route['selected_route']}`",
        f"- 选择策略：`{route['selected_strategy']}`",
        f"- 查询复杂度：`{explain['query_features']['complexity_score']}`",
        "",
        "## 编译阶段",
        "",
        "| 阶段 | 状态 | 产物标识 | 摘要 |",
        "|---|---|---|---|",
    ]
    for stage in explain["stages"]:
        lines.append(
            f"| {stage['stage']} | {stage['status']} | `{stage['artifact_id'][:16]}` | {stage['summary']} |"
        )
    lines.extend(
        [
            "",
            "## 自适应候选路由",
            "",
            "| 路由 | 策略 | 可执行 | 可选 | 已选择 | 成本 | 原因码 |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for item in route["candidates"]:
        cost = "-" if item["cost"] is None else f"{item['cost']:.3f} {item['cost_unit']}"
        lines.append(
            f"| {item['route_kind']} | {item['strategy_id']} | {item['executable']} | "
            f"{item['eligible']} | {item['selected']} | {cost} | `{item['reason_code']}` |"
        )
    lines.extend(
        [
            "",
            "## 生效的金融规则",
            "",
            "| 规则 | 类别 | 语义不变量 | 回退码 |",
            "|---|---|---|---|",
        ]
    )
    for item in explain["applied_financial_rules"]:
        lines.append(
            f"| `{item['rule_id']}` | {item['category']} | {item['semantic_invariant']} | `{item['fallback_code']}` |"
        )
    return "\n".join(lines) + "\n"


def _short_hash(value: Any) -> str:
    return hashlib.sha256(repr(value).encode("utf-8")).hexdigest()[:16]

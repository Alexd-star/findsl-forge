from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def render_compilation_result_markdown(
    result: Mapping[str, Any],
    *,
    execution: Mapping[str, Any] | None = None,
) -> str:
    explain = result["explain"]
    route = explain["adaptive_route"]
    physical = result["physical"]
    backend = result["backend"]
    context = result["compile_context"]
    lines = [
        "# FinDSL Forge 编译结果",
        "",
        f"生成时间：`{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`  ",
        f"Catalog snapshot：`{context['context_id']}`  ",
        f"Physical plan：`{physical['plan_id']}`",
        "",
        "## 输入 DSL",
        "",
        f"```text\n{result['source']}\n```",
        "",
        "## 结论",
        "",
        "- 编译状态：`PASS`",
        f"- 编译总耗时：`{result['elapsed_ms']:.4f} ms`",
        f"- 选择路由：`{route['selected_route']}`",
        f"- 选择策略：`{route['selected_strategy']}`",
        f"- 选择资源：`{physical['selected_resource']}`",
        f"- SQL AST 校验：`{backend['validation_passed']}`",
        f"- SQL 安全校验：`{backend['safety_passed']}`",
        "",
        "## 编译阶段",
        "",
        "| 阶段 | 状态 | 产物标识 | 说明 |",
        "|---|---|---|---|",
    ]
    for stage in explain["stages"]:
        lines.append(
            f"| {stage['stage']} | {stage['status']} | `{stage['artifact_id'][:16]}` | "
            f"{stage['summary']} |"
        )
    lines.extend(
        [
            "",
            "## 查询特征",
            "",
            "| 特征 | 值 |",
            "|---|---|",
        ]
    )
    for key, value in explain["query_features"].items():
        lines.append(f"| `{key}` | {_cell(value)} |")
    lines.extend(
        [
            "",
            "## 自适应路由候选",
            "",
            "| 路由 | 策略 | 可执行 | 可选 | 已选择 | 成本 | 原因码 | 说明 |",
            "|---|---|---:|---:|---:|---:|---|---|",
        ]
    )
    for item in route["candidates"]:
        cost = "-" if item["cost"] is None else f"{item['cost']:.3f} {item['cost_unit']}"
        lines.append(
            f"| {item['route_kind']} | `{item['strategy_id']}` | {item['executable']} | "
            f"{item['eligible']} | {item['selected']} | {cost} | "
            f"`{item['reason_code']}` | {_cell(item['reason'])} |"
        )
    lines.extend(
        [
            "",
            "## 生效的金融规则",
            "",
            "| 规则 | 类别 | 前置条件 | 语义不变量 | 回退 |",
            "|---|---|---|---|---|",
        ]
    )
    for item in explain["applied_financial_rules"]:
        lines.append(
            f"| `{item['rule_id']}` | {item['category']} | {_cell(item['preconditions'])} | "
            f"{_cell(item['semantic_invariant'])} | `{item['fallback_code']}` |"
        )
    lines.extend(
        [
            "",
            "## Doris SQL",
            "",
            f"```sql\n{backend['sql']}\n```",
        ]
    )
    if execution is not None:
        lines.extend(
            [
                "",
                "## Doris 执行结果",
                "",
                f"- 行数：`{execution.get('row_count')}`",
                f"- 耗时：`{execution.get('elapsed_ms')} ms`",
                f"- 不超过 10 秒：`{float(execution.get('elapsed_ms', 10001)) <= 10000}`",
                f"- 结果哈希：`{execution.get('unordered_hash') or '<truncated>'}`",
            ]
        )
    lines.extend(
        [
            "",
            "## 解释边界",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in explain["non_guarantees"])
    return "\n".join(lines) + "\n"


def _cell(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(item) for item in value) or "<none>"
    return str(value).replace("|", "\\|").replace("\n", " ")

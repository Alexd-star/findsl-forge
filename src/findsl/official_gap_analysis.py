from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, Mapping, Tuple


DATA_UNAVAILABLE_CODES = frozenset(
    {
        "DOMAIN_DATA_UNAVAILABLE",
        "PHYSICAL_MARKET_DATA_UNAVAILABLE",
        "PHYSICAL_QUERYDATA_SCALAR_DATA_UNAVAILABLE",
        "PHYSICAL_SCOPE_DATA_UNAVAILABLE",
    }
)
INVALID_INPUT_CODES = frozenset(
    {
        "OFFICIAL_ANTLR_LEX_ERROR",
        "OFFICIAL_ANTLR_PARSE_ERROR",
        "OFFICIAL_TYPE_ERROR",
    }
)


@dataclass(frozen=True)
class GapCluster:
    code: str
    category: str
    row_count: int
    function_families: Tuple[str, ...]
    sample_rows: Tuple[int, ...]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def classify_terminal_code(code: str) -> str:
    if code == "PASS":
        return "passed"
    if code in DATA_UNAVAILABLE_CODES:
        return "data_unavailable"
    if code in INVALID_INPUT_CODES:
        return "invalid_input"
    return "capability_gap"


def analyze_official_funnel(payload: Mapping[str, Any]) -> Dict[str, Any]:
    rows = tuple(payload.get("rows") or ())
    expected = int(payload.get("row_count", len(rows)))
    if expected != len(rows):
        raise ValueError(f"funnel row_count={expected} but rows contains {len(rows)} entries")

    category_counts: Counter[str] = Counter()
    code_rows: Dict[str, list] = defaultdict(list)
    code_functions: Dict[str, set] = defaultdict(set)
    for row in rows:
        code = str(row.get("terminal_code") or "UNKNOWN")
        category_counts[classify_terminal_code(code)] += 1
        code_rows[code].append(int(row.get("excel_row", 0)))
        code_functions[code].update(str(item) for item in row.get("functions") or ())

    clusters = tuple(
        GapCluster(
            code=code,
            category=classify_terminal_code(code),
            row_count=len(code_rows[code]),
            function_families=tuple(sorted(code_functions[code])),
            sample_rows=tuple(item for item in code_rows[code][:5] if item > 0),
        )
        for code in sorted(code_rows, key=lambda item: (-len(code_rows[item]), item))
        if code != "PASS"
    )
    accounted = sum(category_counts.values())
    if accounted != expected:
        raise ValueError(f"gap analysis accounted for {accounted}/{expected} rows")

    migration_gaps = tuple(payload.get("migration_gaps") or ())
    migration_gap_count = sum(int(item.get("count", 0)) for item in migration_gaps)
    migration_gap_codes = tuple(
        sorted(str(item.get("code", "UNKNOWN")) for item in migration_gaps)
    )
    return {
        "schema_version": 1,
        "source_sha256": payload.get("source_sha256"),
        "source_git_head": payload.get("git_head"),
        "row_count": expected,
        "category_counts": dict(sorted(category_counts.items())),
        "migration_gap_count": migration_gap_count,
        "migration_gap_codes": list(migration_gap_codes),
        "clusters": [item.to_dict() for item in clusters],
        "development_policy": {
            "unit": "capability_cluster",
            "row_level_patches_allowed": False,
            "priority": [
                "architecture_convergence",
                "eligible_correctness",
                "capability_gap",
                "versioned_data_provider",
            ],
        },
    }


def gap_analysis_markdown(report: Mapping[str, Any]) -> str:
    counts = report["category_counts"]
    lines = [
        "# 官方语料缺口能力聚类",
        "",
        "> 本报告按能力族统计，不把 Excel 行当作独立开发任务。",
        "",
        "## 总体分类",
        "",
        "| 分类 | 行数 | 处理原则 |",
        "|---|---:|---|",
        f"| 已通过 | {counts.get('passed', 0)} | 保持回归，不重复开发 |",
        f"| 数据不可用 | {counts.get('data_unavailable', 0)} | 通过版本化数据目录或结构化拒绝处理 |",
        f"| 非法输入 | {counts.get('invalid_input', 0)} | 严格模式继续拒绝 |",
        f"| 能力缺口 | {counts.get('capability_gap', 0)} | 按通用规则聚类开发 |",
        "",
        f"旧成功集迁移缺口：**{report['migration_gap_count']} 条**；错误码："
        + ", ".join(report["migration_gap_codes"] or ["无"])
        + "。",
        "",
        "## 能力聚类",
        "",
        "| 错误码 | 分类 | 行数 | 涉及函数族 | 代表行 |",
        "|---|---|---:|---|---|",
    ]
    for cluster in report["clusters"]:
        lines.append(
            "| {code} | {category} | {row_count} | {functions} | {samples} |".format(
                code=cluster["code"],
                category=cluster["category"],
                row_count=cluster["row_count"],
                functions=", ".join(cluster["function_families"]) or "无",
                samples=", ".join(str(item) for item in cluster["sample_rows"]) or "无",
            )
        )
    lines.extend(
        [
            "",
            "## 开发门禁",
            "",
            "每个能力族必须先确定根因层级，再实现通用规则，并批量回归全部匹配语料。禁止根据完整 DSL 文本或单个 Excel 行添加生产分支。",
            "",
        ]
    )
    return "\n".join(lines)


def rows_for_category(
    payload: Mapping[str, Any], category: str
) -> Iterable[Mapping[str, Any]]:
    return (
        row
        for row in payload.get("rows") or ()
        if classify_terminal_code(str(row.get("terminal_code") or "UNKNOWN"))
        == category
    )

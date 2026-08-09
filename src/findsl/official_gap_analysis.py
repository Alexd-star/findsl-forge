from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import re
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
    semantic_rows: Dict[Tuple[str, str], list] = defaultdict(list)
    semantic_codes: Dict[Tuple[str, str], set] = defaultdict(set)
    semantic_examples: Dict[Tuple[str, str], list] = defaultdict(list)
    for row in rows:
        code = str(row.get("terminal_code") or "UNKNOWN")
        category_counts[classify_terminal_code(code)] += 1
        code_rows[code].append(int(row.get("excel_row", 0)))
        code_functions[code].update(str(item) for item in row.get("functions") or ())
        source = str(row.get("source") or "")
        semantic_key, semantic_category = _semantic_subcluster(code, source)
        semantic_rows[(semantic_key, semantic_category)].append(int(row.get("excel_row", 0)))
        semantic_codes[(semantic_key, semantic_category)].add(code)
        if source and len(semantic_examples[(semantic_key, semantic_category)]) < 2:
            semantic_examples[(semantic_key, semantic_category)].append(source)

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
        "semantic_subclusters": [
            {
                "key": key,
                "category": category,
                "row_count": len(semantic_rows[(key, category)]),
                "terminal_codes": sorted(semantic_codes[(key, category)]),
                "sample_rows": [item for item in semantic_rows[(key, category)][:5] if item > 0],
                "examples": semantic_examples[(key, category)],
            }
            for key, category in sorted(
                semantic_rows,
                key=lambda item: (-len(semantic_rows[item]), item[0]),
            )
            if key != "passed"
        ],
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
            "## 语义根因子类",
            "",
            "| 根因 | 分类 | 行数 | 错误码 | 代表行 |",
            "|---|---|---:|---|---|",
        ]
    )
    for cluster in report.get("semantic_subclusters", []):
        lines.append(
            f"| {cluster['key']} | {cluster['category']} | {cluster['row_count']} | "
            f"{', '.join(cluster['terminal_codes'])} | "
            f"{', '.join(str(item) for item in cluster['sample_rows']) or '无'} |"
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


def _semantic_subcluster(code: str, source: str) -> Tuple[str, str]:
    if code == "PASS":
        return "passed", "passed"
    if code == "PHYSICAL_CONSTRAINT_UNSUPPORTED" and re.search(
        r"场内基金|场外基金|公募基金|ETF|LOF|REITs|可转债|债券|期货|港股|基金",
        source,
        flags=re.IGNORECASE,
    ):
        return "unsupported_asset_domain", "data_unavailable"
    if code == "PHYSICAL_DATE_CONSTRAINT_UNSUPPORTED":
        if re.search(r"分钟|盘前|盘中|开盘|收盘后|分时", source):
            return "intraday_data_domain", "data_unavailable"
        if re.search(r"年报|季报|财报|季度", source):
            return "fundamental_reporting_calendar", "data_unavailable"
        if re.search(
            r"(?:本周|上周|上上周)[一二三四五六日天](?:到|至)(?:(?:本周|上周|上上周)|周)?[一二三四五六日天]",
            source,
        ):
            return "deterministic_weekday_range", "capability_gap"
        if re.search(r"最近|近期", source):
            return "ambiguous_recent_date", "invalid_input"
        return "other_date_algebra", "capability_gap"
    if code in DATA_UNAVAILABLE_CODES:
        return "declared_data_unavailable", "data_unavailable"
    if code in INVALID_INPUT_CODES:
        return "invalid_dsl_or_type", "invalid_input"
    return code.lower(), classify_terminal_code(code)


def rows_for_category(
    payload: Mapping[str, Any], category: str
) -> Iterable[Mapping[str, Any]]:
    return (
        row
        for row in payload.get("rows") or ()
        if classify_terminal_code(str(row.get("terminal_code") or "UNKNOWN"))
        == category
    )

from __future__ import annotations

import hashlib
import json
import argparse
from pathlib import Path

from findsl.official_slot import (
    INDICATORS,
    _indicator_names_from_call,
    _iter_function_calls,
    classify_official_indicator_domain,
    parse_official_slot,
)


ROOT = Path(__file__).resolve().parents[1]


def _domain(table: str) -> str:
    if "technical" in table or "prefix" in table:
        return "technical"
    if table.endswith("_ext"):
        return "order_book"
    if table.endswith("code_info"):
        return "security_master"
    return "quote"


def _unit(name: str, kind: str) -> str:
    if kind != "numeric":
        return "flag" if kind == "boolean" else "text"
    if any(token in name for token in ("率", "幅", "比", "RSI", "KDJ")):
        return "ratio_percent"
    if any(token in name for token in ("价", "均线")):
        return "price"
    if any(token in name for token in ("额", "流入", "流出")):
        return "amount"
    if any(token in name for token in ("量", "股")):
        return "shares"
    return "count"


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate static and official-workbook indicators")
    parser.add_argument("--workbook", default=None)
    args = parser.parse_args()
    values = []
    for name, meta in sorted(INDICATORS.items()):
        derived = bool(meta.expression or meta.true_condition or meta.false_condition or "technical" in meta.table or "prefix" in meta.table)
        logical_field = meta.column or "derived_" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
        capabilities = []
        if meta.kind == "numeric":
            capabilities.extend(["ordered", "approximate", "aggregate"])
        if derived:
            capabilities.append("derived")
        values.append({
            "canonical_name": name, "aliases": [], "value_type": meta.kind,
            "domain": _domain(meta.table), "logical_field": logical_field,
            "unit": _unit(name, meta.kind), "scale": 1.0 if meta.kind == "numeric" else None,
            "nullable": True, "availability": "derived" if derived else "official_provided",
            "capabilities": sorted(set(capabilities)),
        })
    output = ROOT / "configs" / "official" / "indicators.json"
    existing_missing = {}
    if output.exists():
        existing_missing = {
            item["canonical_name"]: item
            for item in json.loads(output.read_text(encoding="utf-8"))
            if item.get("availability") == "missing"
        }
    missing_names = set(existing_missing)
    if args.workbook:
        import pandas as pd

        frame = pd.read_excel(args.workbook, sheet_name="训练语料", usecols=["slot_dsl"])
        for source in frame["slot_dsl"]:
            ast = parse_official_slot(str(source), mode="recovery")
            for call in _iter_function_calls(ast):
                for name in _indicator_names_from_call(call):
                    if name not in INDICATORS:
                        missing_names.add(name)
    domain_map = {
        "指数成分与权重数据缺失": "index",
        "基金产品与持仓数据缺失": "fund",
        "财务报表数据缺失": "financial",
        "用户账户与持仓数据缺失": "account",
        "概念板块与主题成分数据缺失": "concept",
        "龙虎榜与异常交易统计缺失": "trading_activity",
        "交易规则与跨市场标的属性缺失": "cross_market",
        "高级形态/相似度模型数据缺失": "advanced_pattern",
        "官方三表未覆盖的其他指标": "missing_other",
    }
    for name in sorted(missing_names):
        if name in existing_missing:
            values.append(existing_missing[name])
            continue
        domain = domain_map.get(classify_official_indicator_domain(name), "missing_other")
        values.append({
            "canonical_name": name, "aliases": [], "value_type": "numeric",
            "domain": domain, "logical_field": "missing_" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:12],
            "unit": "unknown", "scale": None, "nullable": True,
            "availability": "missing", "capabilities": [],
        })
    deduplicated = {}
    for item in values:
        item["aliases"] = [
            alias for alias in item["aliases"]
            if alias.casefold() != item["canonical_name"].casefold()
        ]
        folded = item["canonical_name"].casefold()
        if folded not in deduplicated:
            deduplicated[folded] = item
            continue
        target = deduplicated[folded]
        if target["value_type"] != item["value_type"]:
            raise ValueError(f"case-insensitive indicator type conflict: {target['canonical_name']} / {item['canonical_name']}")
        # Case-only variants resolve through the casefold index and need no alias entry.
    values = sorted(deduplicated.values(), key=lambda item: item["canonical_name"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

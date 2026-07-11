from __future__ import annotations

import hashlib
import json
from pathlib import Path

from findsl.official_slot import INDICATORS


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
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

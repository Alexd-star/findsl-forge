from __future__ import annotations

import json
from pathlib import Path

from findsl.official_slot import INDICATORS


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_IDS = {
    "hsj_stock_hq_basic": "official_basic",
    "hsj_stock_hq_ext": "official_ext",
    "hsj_stock_code_info": "official_security",
    "hsj_stock_hq_basic_technical": "official_technical",
}


def main() -> None:
    resources = []
    for table, resource_id in RESOURCE_IDS.items():
        capabilities = ["scan"]
        if "technical" in table:
            capabilities.append("technical")
        resources.append({
            "resource_id": resource_id, "database": "newzl", "table": table,
            "logical_entity": "market_observation", "partition_key": None if resource_id == "official_security" else "bizdate",
            "distribution_key": "tgtcode", "capabilities": capabilities,
            "stable_keys": ["mktcode", "tgtcode"] if resource_id == "official_security" else ["mktcode", "tgtcode", "bizdate"],
            "anchor_resource_id": None if resource_id == "official_basic" else "official_basic",
            "priority": 10 if resource_id == "official_basic" else 20,
        })
    fields = []
    seen = set()
    for name, meta in sorted(INDICATORS.items()):
        if not meta.column or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        fields.append({
            "indicator_id": name, "resource_id": RESOURCE_IDS[meta.table],
            "column": meta.column, "value_type": meta.kind, "scale": 1.0,
            "nullable": True,
        })
    output = ROOT / "configs" / "official" / "physical_catalog.json"
    output.write_text(json.dumps({"resources": resources, "fields": fields}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

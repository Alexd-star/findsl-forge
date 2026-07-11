from __future__ import annotations

import json
from pathlib import Path

from findsl.official.physical.catalog import default_physical_catalog


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    catalog = default_physical_catalog()
    strategies = []
    for window in (3, 5, 10, 20, 30, 60, 120, 200, 250):
        strategies.append(_strategy(f"{window}日均线", f"ma{window}_prefix_average", "close", window, 10000.0))
    for window in (5, 10, 20, 30, 60):
        strategies.append(_strategy(f"{window}日均量线", f"volume_avg_{window}_prefix_average", "volume", window, 1.0))
    payload = {
        "schema_version": 1,
        "catalog_sha256": catalog.fingerprint,
        "strategies": sorted(strategies, key=lambda item: item["strategy_id"]),
    }
    path = ROOT / "configs" / "official" / "physical_strategies.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _strategy(indicator_id, strategy_id, prefix, window, scale_divisor):
    return {
        "strategy_id": strategy_id,
        "indicator_id": indicator_id,
        "kind": "prefix_average",
        "scan_resource_id": "official_basic",
        "prefix_resource_id": "official_basic_prefix",
        "sum_column": f"{prefix}_prefix",
        "count_column": f"{prefix}_count_prefix",
        "window": window,
        "scale_divisor": scale_divisor,
        "value_type": "numeric",
        "selection_mode": "shadow",
    }


if __name__ == "__main__":
    main()

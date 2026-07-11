import json

import pytest

from findsl.official.physical.catalog import default_physical_catalog
from findsl.official.physical.strategies import (
    PhysicalStrategyError,
    PhysicalStrategyRegistry,
    default_physical_strategies,
)


def test_default_registry_exposes_controlled_prefix_average_candidate():
    strategies = default_physical_strategies(default_physical_catalog()).strategies_for("5日均线")

    assert len(strategies) == 1
    strategy = strategies[0]
    assert strategy.strategy_id == "ma5_prefix_average"
    assert strategy.scan_resource_id == "official_basic"
    assert strategy.prefix_resource_id == "official_basic_prefix"
    assert strategy.sum_column == "close_prefix"
    assert strategy.count_column == "close_count_prefix"
    assert strategy.window == 5
    assert strategy.scale_divisor == 10000.0
    assert strategy.selection_mode == "shadow"


def test_strategy_registry_is_cached_and_orders_candidates_deterministically():
    catalog = default_physical_catalog()
    first = default_physical_strategies(catalog)
    second = default_physical_strategies(catalog)

    assert first is second
    assert first.strategies == tuple(sorted(first.strategies, key=lambda item: item.strategy_id))


def test_strategy_registry_rejects_unknown_resources_and_sql_fragments(tmp_path):
    payload = {
        "schema_version": 1,
        "catalog_sha256": default_physical_catalog().fingerprint,
        "strategies": [
            {
                "strategy_id": "bad",
                "indicator_id": "5日均线",
                "kind": "prefix_average",
                "scan_resource_id": "missing",
                "prefix_resource_id": "official_basic_prefix",
                "sum_column": "close_prefix; DROP TABLE x",
                "count_column": "close_count_prefix",
                "window": 5,
                "scale_divisor": 10000.0,
                "value_type": "numeric"
            }
        ]
    }
    path = tmp_path / "strategies.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(PhysicalStrategyError):
        PhysicalStrategyRegistry.load(path, default_physical_catalog())

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Dict, Tuple

from .catalog import PhysicalCatalog


class PhysicalStrategyError(ValueError):
    pass


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


@dataclass(frozen=True)
class PhysicalPrefixAverageStrategy:
    strategy_id: str
    indicator_id: str
    kind: str
    scan_resource_id: str
    prefix_resource_id: str
    sum_column: str
    count_column: str
    window: int
    scale_divisor: float
    value_type: str
    selection_mode: str


class PhysicalStrategyRegistry:
    def __init__(self, *, schema_version, catalog_sha256, strategies, catalog):
        if schema_version != 1:
            raise PhysicalStrategyError(f"unsupported strategy schema version: {schema_version}")
        if catalog_sha256 != catalog.fingerprint:
            raise PhysicalStrategyError("strategy catalog fingerprint does not match physical catalog")
        by_id = {}
        by_indicator: Dict[str, list] = {}
        for strategy in strategies:
            if strategy.strategy_id in by_id:
                raise PhysicalStrategyError(f"duplicate physical strategy: {strategy.strategy_id}")
            try:
                scan = catalog.resource(strategy.scan_resource_id)
                prefix = catalog.resource(strategy.prefix_resource_id)
            except KeyError as exc:
                raise PhysicalStrategyError(f"unknown resource in strategy {strategy.strategy_id}") from exc
            if "scan" not in scan.capabilities or "prefix" not in prefix.capabilities:
                raise PhysicalStrategyError(f"invalid resource capability in strategy {strategy.strategy_id}")
            if scan.logical_entity != prefix.logical_entity:
                raise PhysicalStrategyError(f"strategy resource entity mismatch: {strategy.strategy_id}")
            by_id[strategy.strategy_id] = strategy
            by_indicator.setdefault(strategy.indicator_id.casefold(), []).append(strategy)
        self.schema_version = schema_version
        self.catalog_sha256 = catalog_sha256
        self._by_id = MappingProxyType(by_id)
        self._by_indicator = MappingProxyType(
            {key: tuple(sorted(values, key=lambda item: item.strategy_id)) for key, values in by_indicator.items()}
        )

    @property
    def strategies(self) -> Tuple[PhysicalPrefixAverageStrategy, ...]:
        return tuple(self._by_id[key] for key in sorted(self._by_id))

    def strategies_for(self, indicator_id: str) -> Tuple[PhysicalPrefixAverageStrategy, ...]:
        return self._by_indicator.get(str(indicator_id).casefold(), ())

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "catalog_sha256": self.catalog_sha256,
            "strategies": [asdict(item) for item in self.strategies],
        }

    @classmethod
    def load(cls, path: Path, catalog: PhysicalCatalog) -> "PhysicalStrategyRegistry":
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PhysicalStrategyError(f"cannot load physical strategies: {exc}") from exc
        if not isinstance(raw, dict) or set(raw) != {"schema_version", "catalog_sha256", "strategies"}:
            raise PhysicalStrategyError("invalid physical strategy root fields")
        return cls(
            schema_version=raw["schema_version"],
            catalog_sha256=str(raw["catalog_sha256"]),
            strategies=tuple(_strategy(item) for item in raw["strategies"]),
            catalog=catalog,
        )


def _strategy(raw) -> PhysicalPrefixAverageStrategy:
    expected = {
        "strategy_id", "indicator_id", "kind", "scan_resource_id", "prefix_resource_id",
        "sum_column", "count_column", "window", "scale_divisor", "value_type",
        "selection_mode",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise PhysicalStrategyError("invalid physical strategy fields")
    for key in ("strategy_id", "scan_resource_id", "prefix_resource_id", "sum_column", "count_column"):
        if not _IDENTIFIER.fullmatch(str(raw[key])):
            raise PhysicalStrategyError(f"invalid strategy identifier {key}: {raw[key]}")
    if raw["kind"] != "prefix_average" or raw["value_type"] != "numeric":
        raise PhysicalStrategyError("unsupported physical strategy kind or value type")
    if raw["selection_mode"] not in {"shadow", "active"}:
        raise PhysicalStrategyError("physical strategy selection mode must be shadow or active")
    if isinstance(raw["window"], bool) or not isinstance(raw["window"], int) or raw["window"] <= 0:
        raise PhysicalStrategyError("prefix strategy window must be a positive integer")
    if isinstance(raw["scale_divisor"], bool) or not isinstance(raw["scale_divisor"], (int, float)) or raw["scale_divisor"] <= 0:
        raise PhysicalStrategyError("prefix strategy scale divisor must be positive")
    return PhysicalPrefixAverageStrategy(
        strategy_id=str(raw["strategy_id"]),
        indicator_id=str(raw["indicator_id"]),
        kind=str(raw["kind"]),
        scan_resource_id=str(raw["scan_resource_id"]),
        prefix_resource_id=str(raw["prefix_resource_id"]),
        sum_column=str(raw["sum_column"]),
        count_column=str(raw["count_column"]),
        window=raw["window"],
        scale_divisor=float(raw["scale_divisor"]),
        value_type=str(raw["value_type"]),
        selection_mode=str(raw["selection_mode"]),
    )


@lru_cache(maxsize=1)
def default_physical_strategies(catalog=None) -> PhysicalStrategyRegistry:
    if catalog is None:
        from .catalog import default_physical_catalog

        catalog = default_physical_catalog()
    root = Path(__file__).resolve().parents[4]
    return PhysicalStrategyRegistry.load(root / "configs" / "official" / "physical_strategies.json", catalog)

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Dict, Tuple, Union

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


@dataclass(frozen=True)
class PhysicalPrefixAggregateStrategy:
    strategy_id: str
    indicator_id: str
    kind: str
    scan_resource_id: str
    prefix_resource_id: str
    sum_column: str
    count_column: str
    functions: Tuple[str, ...]
    min_window: int
    max_window: int
    scale_divisor: float
    access_fraction_hint: float
    selection_mode: str


@dataclass(frozen=True)
class PhysicalMaterializedAggregateStrategy:
    strategy_id: str
    indicator_id: str
    kind: str
    scan_resource_id: str
    materialized_resource_id: str
    feature_column: str
    function: str
    window: int
    scale_divisor: float
    partition_fraction_hint: float
    selection_mode: str


PhysicalStrategy = Union[
    PhysicalPrefixAverageStrategy,
    PhysicalPrefixAggregateStrategy,
    PhysicalMaterializedAggregateStrategy,
]


class PhysicalStrategyRegistry:
    def __init__(self, *, schema_version, catalog_sha256, strategies, catalog):
        if schema_version != 1:
            raise PhysicalStrategyError(f"unsupported strategy schema version: {schema_version}")
        if catalog_sha256 != catalog.fingerprint:
            raise PhysicalStrategyError("strategy catalog fingerprint does not match physical catalog")
        by_id = {}
        by_indicator: Dict[str, list[PhysicalPrefixAverageStrategy]] = {}
        aggregate_by_indicator: Dict[
            str,
            list[Union[PhysicalPrefixAggregateStrategy, PhysicalMaterializedAggregateStrategy]],
        ] = {}
        for strategy in strategies:
            if strategy.strategy_id in by_id:
                raise PhysicalStrategyError(f"duplicate physical strategy: {strategy.strategy_id}")
            scan, acceleration = _strategy_resources(strategy, catalog)
            if "scan" not in scan.capabilities:
                raise PhysicalStrategyError(
                    f"invalid scan resource capability in strategy {strategy.strategy_id}"
                )
            required_capability = (
                "materialized_aggregate"
                if isinstance(strategy, PhysicalMaterializedAggregateStrategy)
                else "prefix"
            )
            if required_capability not in acceleration.capabilities:
                raise PhysicalStrategyError(
                    f"invalid acceleration resource capability in strategy {strategy.strategy_id}"
                )
            if scan.logical_entity != acceleration.logical_entity:
                raise PhysicalStrategyError(
                    f"strategy resource entity mismatch: {strategy.strategy_id}"
                )
            by_id[strategy.strategy_id] = strategy
            if isinstance(strategy, PhysicalPrefixAverageStrategy):
                by_indicator.setdefault(strategy.indicator_id.casefold(), []).append(strategy)
            else:
                aggregate_by_indicator.setdefault(
                    strategy.indicator_id.casefold(), []
                ).append(strategy)
        self.schema_version = schema_version
        self.catalog_sha256 = catalog_sha256
        self._by_id = MappingProxyType(by_id)
        self._by_indicator = MappingProxyType(
            {key: tuple(sorted(values, key=lambda item: item.strategy_id)) for key, values in by_indicator.items()}
        )
        self._aggregate_by_indicator = MappingProxyType(
            {
                key: tuple(sorted(values, key=lambda item: item.strategy_id))
                for key, values in aggregate_by_indicator.items()
            }
        )

    @property
    def strategies(self) -> Tuple[PhysicalStrategy, ...]:
        return tuple(self._by_id[key] for key in sorted(self._by_id))

    def strategies_for(self, indicator_id: str) -> Tuple[PhysicalPrefixAverageStrategy, ...]:
        return self._by_indicator.get(str(indicator_id).casefold(), ())

    def aggregate_strategies_for(
        self,
        indicator_id: str,
    ) -> Tuple[
        Union[PhysicalPrefixAggregateStrategy, PhysicalMaterializedAggregateStrategy],
        ...,
    ]:
        return self._aggregate_by_indicator.get(str(indicator_id).casefold(), ())

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


def _strategy(raw) -> PhysicalStrategy:
    if not isinstance(raw, dict):
        raise PhysicalStrategyError("invalid physical strategy fields")
    kind = raw.get("kind")
    if kind == "prefix_average":
        return _prefix_average_strategy(raw)
    if kind == "prefix_aggregate":
        return _prefix_aggregate_strategy(raw)
    if kind == "materialized_aggregate":
        return _materialized_aggregate_strategy(raw)
    raise PhysicalStrategyError(f"unsupported physical strategy kind: {kind}")


def _prefix_average_strategy(raw) -> PhysicalPrefixAverageStrategy:
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
    if raw["value_type"] != "numeric":
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


def _prefix_aggregate_strategy(raw) -> PhysicalPrefixAggregateStrategy:
    expected = {
        "strategy_id", "indicator_id", "kind", "scan_resource_id",
        "prefix_resource_id", "sum_column", "count_column", "functions",
        "min_window", "max_window", "scale_divisor", "access_fraction_hint",
        "selection_mode",
    }
    if set(raw) != expected:
        raise PhysicalStrategyError("invalid prefix aggregate strategy fields")
    _validate_identifiers(
        raw,
        ("strategy_id", "scan_resource_id", "prefix_resource_id", "sum_column", "count_column"),
    )
    functions = tuple(sorted({str(item).upper() for item in raw["functions"]}))
    if not functions or not set(functions).issubset({"SUM", "AVG"}):
        raise PhysicalStrategyError("prefix aggregate functions must be SUM and/or AVG")
    min_window = _positive_int(raw["min_window"], "prefix aggregate min_window")
    max_window = _positive_int(raw["max_window"], "prefix aggregate max_window")
    if max_window < min_window:
        raise PhysicalStrategyError("prefix aggregate window range is reversed")
    return PhysicalPrefixAggregateStrategy(
        strategy_id=str(raw["strategy_id"]),
        indicator_id=str(raw["indicator_id"]),
        kind="prefix_aggregate",
        scan_resource_id=str(raw["scan_resource_id"]),
        prefix_resource_id=str(raw["prefix_resource_id"]),
        sum_column=str(raw["sum_column"]),
        count_column=str(raw["count_column"]),
        functions=functions,
        min_window=min_window,
        max_window=max_window,
        scale_divisor=_positive_number(raw["scale_divisor"], "prefix aggregate scale_divisor"),
        access_fraction_hint=_fraction(raw["access_fraction_hint"], "prefix aggregate access_fraction_hint"),
        selection_mode=_selection_mode(raw["selection_mode"]),
    )


def _materialized_aggregate_strategy(raw) -> PhysicalMaterializedAggregateStrategy:
    expected = {
        "strategy_id", "indicator_id", "kind", "scan_resource_id",
        "materialized_resource_id", "feature_column", "function", "window",
        "scale_divisor", "partition_fraction_hint", "selection_mode",
    }
    if set(raw) != expected:
        raise PhysicalStrategyError("invalid materialized aggregate strategy fields")
    _validate_identifiers(
        raw,
        ("strategy_id", "scan_resource_id", "materialized_resource_id", "feature_column"),
    )
    function = str(raw["function"]).upper()
    if function not in {"SUM", "AVG"}:
        raise PhysicalStrategyError("materialized aggregate function must be SUM or AVG")
    return PhysicalMaterializedAggregateStrategy(
        strategy_id=str(raw["strategy_id"]),
        indicator_id=str(raw["indicator_id"]),
        kind="materialized_aggregate",
        scan_resource_id=str(raw["scan_resource_id"]),
        materialized_resource_id=str(raw["materialized_resource_id"]),
        feature_column=str(raw["feature_column"]),
        function=function,
        window=_positive_int(raw["window"], "materialized aggregate window"),
        scale_divisor=_positive_number(raw["scale_divisor"], "materialized aggregate scale_divisor"),
        partition_fraction_hint=_fraction(
            raw["partition_fraction_hint"],
            "materialized aggregate partition_fraction_hint",
        ),
        selection_mode=_selection_mode(raw["selection_mode"]),
    )


def _strategy_resources(strategy: PhysicalStrategy, catalog: PhysicalCatalog):
    try:
        scan = catalog.resource(strategy.scan_resource_id)
        if isinstance(strategy, PhysicalMaterializedAggregateStrategy):
            acceleration = catalog.resource(strategy.materialized_resource_id)
        else:
            acceleration = catalog.resource(strategy.prefix_resource_id)
    except KeyError as exc:
        raise PhysicalStrategyError(
            f"unknown resource in strategy {strategy.strategy_id}"
        ) from exc
    return scan, acceleration


def _validate_identifiers(raw, keys) -> None:
    for key in keys:
        if not _IDENTIFIER.fullmatch(str(raw[key])):
            raise PhysicalStrategyError(f"invalid strategy identifier {key}: {raw[key]}")


def _positive_int(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PhysicalStrategyError(f"{label} must be a positive integer")
    return value


def _positive_number(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise PhysicalStrategyError(f"{label} must be positive")
    return float(value)


def _fraction(value, label: str) -> float:
    result = _positive_number(value, label)
    if result > 1:
        raise PhysicalStrategyError(f"{label} must not exceed 1")
    return result


def _selection_mode(value) -> str:
    result = str(value)
    if result not in {"shadow", "active"}:
        raise PhysicalStrategyError("physical strategy selection mode must be shadow or active")
    return result


@lru_cache(maxsize=1)
def default_physical_strategies(catalog=None) -> PhysicalStrategyRegistry:
    if catalog is None:
        from .catalog import default_physical_catalog

        catalog = default_physical_catalog()
    root = Path(__file__).resolve().parents[4]
    return PhysicalStrategyRegistry.load(root / "configs" / "official" / "physical_strategies.json", catalog)

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Tuple


class GroupMetricCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class GroupTargetPolicy:
    target_id: str
    scope_types: Tuple[str, ...]
    preferred_sources: Tuple[str, ...]
    minimum_member_count: int


@dataclass(frozen=True)
class GroupMetricPolicy:
    indicator_id: str
    default_aggregation: str
    allowed_aggregations: Tuple[str, ...]
    allowed_target_ids: Tuple[str, ...]
    null_policy: str
    rationale: str


class GroupMetricPolicyCatalog:
    def __init__(
        self,
        *,
        catalog_id: str,
        membership_resource_id: str,
        targets: Tuple[GroupTargetPolicy, ...],
        metrics: Tuple[GroupMetricPolicy, ...],
    ) -> None:
        target_map = {item.target_id: item for item in targets}
        metric_map = {item.indicator_id.casefold(): item for item in metrics}
        if len(target_map) != len(targets) or len(metric_map) != len(metrics):
            raise GroupMetricCatalogError("duplicate group target or metric policy")
        unknown_targets = {
            target_id
            for metric in metrics
            for target_id in metric.allowed_target_ids
            if target_id not in target_map
        }
        if unknown_targets:
            raise GroupMetricCatalogError(
                f"group metric policy references unknown targets: {sorted(unknown_targets)}"
            )
        self.catalog_id = catalog_id
        self.membership_resource_id = membership_resource_id
        self._targets: Mapping[str, GroupTargetPolicy] = MappingProxyType(target_map)
        self._metrics: Mapping[str, GroupMetricPolicy] = MappingProxyType(metric_map)

    @property
    def targets(self) -> Tuple[GroupTargetPolicy, ...]:
        return tuple(self._targets.values())

    @property
    def metrics(self) -> Tuple[GroupMetricPolicy, ...]:
        return tuple(self._metrics.values())

    def target(self, target_id: str) -> GroupTargetPolicy:
        try:
            return self._targets[str(target_id)]
        except KeyError as exc:
            raise GroupMetricCatalogError(
                f"group target has no aggregation policy: {target_id}"
            ) from exc

    def metric(self, indicator_id: str, target_ids: Tuple[str, ...]) -> GroupMetricPolicy:
        try:
            policy = self._metrics[str(indicator_id).casefold()]
        except KeyError as exc:
            raise GroupMetricCatalogError(
                f"group metric has no approved aggregation policy: {indicator_id}"
            ) from exc
        unsupported = sorted(set(target_ids) - set(policy.allowed_target_ids))
        if unsupported:
            raise GroupMetricCatalogError(
                f"group metric {indicator_id} is not approved for targets: {unsupported}"
            )
        return policy

    def combined_target(self, target_ids: Tuple[str, ...]) -> GroupTargetPolicy:
        policies = tuple(self.target(target_id) for target_id in target_ids)
        return GroupTargetPolicy(
            target_id="|".join(target_ids),
            scope_types=tuple(
                dict.fromkeys(value for item in policies for value in item.scope_types)
            ),
            preferred_sources=tuple(
                dict.fromkeys(
                    value for item in policies for value in item.preferred_sources
                )
            ),
            minimum_member_count=max(
                item.minimum_member_count for item in policies
            ),
        )

    @classmethod
    def load(cls, path: Path) -> "GroupMetricPolicyCatalog":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        expected = {
            "schema_version",
            "catalog_id",
            "membership_resource_id",
            "targets",
            "metrics",
        }
        if set(raw) != expected or raw["schema_version"] != 1:
            raise GroupMetricCatalogError("invalid group metric policy catalog root")
        targets = tuple(_target_policy(item) for item in raw["targets"])
        metrics = tuple(_metric_policy(item) for item in raw["metrics"])
        return cls(
            catalog_id=_text(raw["catalog_id"], "catalog_id"),
            membership_resource_id=_text(
                raw["membership_resource_id"], "membership_resource_id"
            ),
            targets=targets,
            metrics=metrics,
        )


def _target_policy(raw) -> GroupTargetPolicy:
    expected = {
        "target_id",
        "scope_types",
        "preferred_sources",
        "minimum_member_count",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise GroupMetricCatalogError("invalid group target policy")
    minimum = raw["minimum_member_count"]
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
        raise GroupMetricCatalogError("group minimum member count must be positive")
    return GroupTargetPolicy(
        _text(raw["target_id"], "target_id"),
        _texts(raw["scope_types"], "scope_types"),
        _texts(raw["preferred_sources"], "preferred_sources"),
        minimum,
    )


def _metric_policy(raw) -> GroupMetricPolicy:
    expected = {
        "indicator_id",
        "default_aggregation",
        "allowed_aggregations",
        "allowed_target_ids",
        "null_policy",
        "rationale",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise GroupMetricCatalogError("invalid group metric policy")
    allowed = _texts(raw["allowed_aggregations"], "allowed_aggregations")
    default = _text(raw["default_aggregation"], "default_aggregation").lower()
    supported = {
        "sum",
        "avg",
        "max",
        "min",
        "float_market_cap_weighted_return",
        "float_market_cap_weighted_loss",
    }
    if default not in allowed or any(item not in supported for item in allowed):
        raise GroupMetricCatalogError("invalid group aggregation contract")
    null_policy = _text(raw["null_policy"], "null_policy")
    if null_policy not in {"ignore", "reject_group"}:
        raise GroupMetricCatalogError("invalid group null policy")
    return GroupMetricPolicy(
        _text(raw["indicator_id"], "indicator_id"),
        default,
        allowed,
        _texts(raw["allowed_target_ids"], "allowed_target_ids"),
        null_policy,
        _text(raw["rationale"], "rationale"),
    )


def _text(value, label: str) -> str:
    result = str(value).strip()
    if not result:
        raise GroupMetricCatalogError(f"{label} cannot be empty")
    return result


def _texts(values, label: str) -> Tuple[str, ...]:
    if not isinstance(values, list):
        raise GroupMetricCatalogError(f"{label} must be a list")
    result = tuple(dict.fromkeys(_text(value, label) for value in values))
    if not result:
        raise GroupMetricCatalogError(f"{label} cannot be empty")
    return result


@lru_cache(maxsize=1)
def default_group_metric_policy_catalog() -> GroupMetricPolicyCatalog:
    root = Path(__file__).resolve().parents[3]
    return GroupMetricPolicyCatalog.load(
        root / "configs" / "official" / "group_metric_policies.json"
    )

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Dict, Optional, Tuple

from .models import normalize_catalog_name
from .policy import ScopeSemanticPolicy, ScopeSemanticPolicyCatalog


class ExternalScopeRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class ExternalScopeOption:
    scope_type: str
    scope_code: str
    scope_name: str
    source: str
    as_of_date: str
    snapshot_id: str


@dataclass(frozen=True)
class ResolvedExternalScope:
    source: str
    option: ExternalScopeOption
    policy: Optional[ScopeSemanticPolicy] = None


@dataclass(frozen=True)
class ExternalMembershipPolicy:
    resource_id: str
    snapshot_id: str
    source: str
    as_of_date: str
    classification_system: str = ""
    industry_level: str = ""


@dataclass(frozen=True)
class ExternalDataPolicy:
    industry: ExternalMembershipPolicy
    instrument_rule: ExternalMembershipPolicy

    @classmethod
    def from_dict(cls, raw) -> "ExternalDataPolicy":
        if set(raw) != {"schema_version", "industry", "instrument_rule"}:
            raise ExternalScopeRuntimeError("invalid external data policy root")
        if raw["schema_version"] != 1:
            raise ExternalScopeRuntimeError("unsupported external data policy version")
        return cls(
            _membership_policy(raw["industry"], industry=True),
            _membership_policy(raw["instrument_rule"], industry=False),
        )

    @classmethod
    def load(cls, path: Path) -> "ExternalDataPolicy":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass(frozen=True)
class ExternalIndexQuoteOption:
    scope_code: str
    snapshot_id: str
    source: str
    as_of_date: str


@dataclass(frozen=True)
class BenchmarkPolicyOption:
    alias: str
    market: str
    index_code: str
    index_name: str
    policy_id: str
    source: str
    effective_from: str
    rationale_url: str


class BenchmarkPolicyCatalog:
    def __init__(self, entries, *, resource_id: str):
        by_alias: Dict[str, list[BenchmarkPolicyOption]] = {}
        required = {
            "alias",
            "normalized_alias",
            "market",
            "index_code",
            "index_name",
            "policy_id",
            "source",
            "effective_from",
            "rationale_url",
        }
        for entry in entries:
            if set(entry) != required:
                raise ExternalScopeRuntimeError("invalid benchmark policy entry")
            option = BenchmarkPolicyOption(
                alias=str(entry["alias"]),
                market=str(entry["market"]),
                index_code=str(entry["index_code"]),
                index_name=str(entry["index_name"]),
                policy_id=str(entry["policy_id"]),
                source=str(entry["source"]),
                effective_from=str(entry["effective_from"]),
                rationale_url=str(entry["rationale_url"]),
            )
            by_alias.setdefault(str(entry["normalized_alias"]), []).append(option)
        self.resource_id = resource_id
        self._by_alias = MappingProxyType(
            {key: tuple(value) for key, value in by_alias.items()}
        )

    def resolve(self, alias: str, market: str = "") -> BenchmarkPolicyOption:
        source = str(alias).strip()
        options = self._by_alias.get(normalize_catalog_name(source), ())
        exact = tuple(item for item in options if item.market == str(market).strip())
        fallback = tuple(item for item in options if not item.market)
        selected = exact or fallback
        if len(selected) != 1:
            raise KeyError(source)
        return selected[0]

    @classmethod
    def from_dict(cls, raw) -> "BenchmarkPolicyCatalog":
        if set(raw) != {"schema_version", "resource_id", "entries"}:
            raise ExternalScopeRuntimeError("invalid benchmark policy root")
        if raw["schema_version"] != 1:
            raise ExternalScopeRuntimeError("unsupported benchmark policy version")
        return cls(raw["entries"], resource_id=str(raw["resource_id"]))

    @classmethod
    def load(cls, path: Path) -> "BenchmarkPolicyCatalog":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


class ExternalIndexQuoteCatalog:
    def __init__(self, entries, *, resource_id: str):
        self.resource_id = resource_id
        self._entries = MappingProxyType(
            {
                str(item["scope_code"]): ExternalIndexQuoteOption(
                    str(item["scope_code"]),
                    str(item["snapshot_id"]),
                    str(item["source"]),
                    str(item["as_of_date"]),
                )
                for item in entries
            }
        )

    def resolve(self, scope_code: str) -> ExternalIndexQuoteOption:
        try:
            return self._entries[str(scope_code)]
        except KeyError as exc:
            raise KeyError(str(scope_code)) from exc

    @classmethod
    def from_dict(cls, raw) -> "ExternalIndexQuoteCatalog":
        if set(raw) != {"schema_version", "resource_id", "entries"}:
            raise ExternalScopeRuntimeError("invalid external index quote catalog root")
        if raw["schema_version"] != 1:
            raise ExternalScopeRuntimeError("unsupported external index quote catalog version")
        required = {"scope_code", "snapshot_id", "source", "as_of_date"}
        if any(set(item) != required for item in raw["entries"]):
            raise ExternalScopeRuntimeError("invalid external index quote entry")
        return cls(raw["entries"], resource_id=str(raw["resource_id"]))

    @classmethod
    def load(cls, path: Path) -> "ExternalIndexQuoteCatalog":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


class ExternalScopeRuntimeCatalog:
    def __init__(
        self,
        entries,
        *,
        membership_resource_id: str,
        semantic_policies: Optional[ScopeSemanticPolicyCatalog] = None,
    ):
        by_alias: Dict[str, list[ExternalScopeOption]] = {}
        for entry in entries:
            expected = {
                "scope_type",
                "scope_code",
                "scope_name",
                "alias",
                "normalized_alias",
                "source",
                "as_of_date",
                "snapshot_id",
            }
            if set(entry) != expected:
                raise ExternalScopeRuntimeError("invalid external runtime scope entry")
            option = ExternalScopeOption(
                str(entry["scope_type"]),
                str(entry["scope_code"]),
                str(entry["scope_name"]),
                str(entry["source"]),
                str(entry["as_of_date"]),
                str(entry["snapshot_id"]),
            )
            by_alias.setdefault(str(entry["normalized_alias"]), []).append(option)
        self._by_alias = MappingProxyType(
            {
                alias: tuple(_dedupe_options(options))
                for alias, options in by_alias.items()
            }
        )
        self.membership_resource_id = membership_resource_id
        self.semantic_policies = semantic_policies

    def resolve(self, atom: str) -> ResolvedExternalScope:
        source = str(atom).strip()
        options = self._by_alias.get(normalize_catalog_name(source), ())
        if not options:
            raise KeyError(source)
        policy = None
        if self.semantic_policies is not None:
            try:
                policy = self.semantic_policies.resolve(source)
            except KeyError:
                pass
            else:
                options = tuple(
                    option
                    for option in options
                    if option.scope_code == policy.scope_code
                )
                if not options:
                    raise ExternalScopeRuntimeError(
                        "semantic policy target is absent from runtime catalog: "
                        f"{policy.policy_id}/{policy.scope_code}"
                    )
        selected = min(options, key=lambda item: _option_priority(source, item))
        return ResolvedExternalScope(source, selected, policy)

    @classmethod
    def from_dict(cls, raw) -> "ExternalScopeRuntimeCatalog":
        if set(raw) != {"schema_version", "membership_resource_id", "entries"}:
            raise ExternalScopeRuntimeError("invalid external runtime catalog root")
        if raw["schema_version"] != 1:
            raise ExternalScopeRuntimeError("unsupported external runtime catalog version")
        return cls(
            raw["entries"],
            membership_resource_id=str(raw["membership_resource_id"]),
        )

    @classmethod
    def load(cls, path: Path) -> "ExternalScopeRuntimeCatalog":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _dedupe_options(options) -> Tuple[ExternalScopeOption, ...]:
    latest = {}
    for option in options:
        key = (option.scope_type, option.scope_code, option.source)
        existing = latest.get(key)
        if existing is None or option.as_of_date > existing.as_of_date:
            latest[key] = option
    return tuple(latest.values())


def _option_priority(source: str, option: ExternalScopeOption):
    text = source.casefold()
    if "指数" in text:
        type_priority = 0 if option.scope_type == "index" else 10
    elif "行业" in text or text.endswith("类"):
        type_priority = 0 if option.scope_type == "industry" else 10
    elif "概念" in text or "板块" in text:
        type_priority = 0 if option.scope_type == "concept" else 10
    else:
        type_priority = {"concept": 0, "industry": 1, "index": 2}.get(
            option.scope_type, 9
        )
    source_priority = {
        "eastmoney": 0,
        "eastmoney-security-profile": 1,
        "csindex": 2,
        "cnindex": 3,
        "akshare-eastmoney-index": 4,
    }.get(
        option.source, 9
    )
    return type_priority, source_priority, option.scope_code


def _membership_policy(raw, *, industry: bool) -> ExternalMembershipPolicy:
    required = {"resource_id", "snapshot_id", "source", "as_of_date"}
    allowed = required | (
        {"classification_system", "industry_level"} if industry else set()
    )
    if set(raw) != allowed or not all(str(raw[key]).strip() for key in required):
        raise ExternalScopeRuntimeError("invalid external membership policy")
    return ExternalMembershipPolicy(
        resource_id=str(raw["resource_id"]),
        snapshot_id=str(raw["snapshot_id"]),
        source=str(raw["source"]),
        as_of_date=str(raw["as_of_date"]),
        classification_system=str(raw.get("classification_system", "")),
        industry_level=str(raw.get("industry_level", "")),
    )


@lru_cache(maxsize=1)
def default_external_scope_catalog() -> ExternalScopeRuntimeCatalog:
    root = Path(__file__).resolve().parents[4]
    runtime = json.loads(
        (root / "configs" / "official" / "external_scope_runtime.json").read_text(
            encoding="utf-8"
        )
    )
    policies = ScopeSemanticPolicyCatalog.load(
        root / "configs" / "official" / "scope_semantic_policies.json"
    )
    if set(runtime) != {"schema_version", "membership_resource_id", "entries"}:
        raise ExternalScopeRuntimeError("invalid external runtime catalog root")
    if runtime["schema_version"] != 1:
        raise ExternalScopeRuntimeError("unsupported external runtime catalog version")
    return ExternalScopeRuntimeCatalog(
        runtime["entries"],
        membership_resource_id=str(runtime["membership_resource_id"]),
        semantic_policies=policies,
    )


@lru_cache(maxsize=1)
def default_external_data_policy() -> ExternalDataPolicy:
    root = Path(__file__).resolve().parents[4]
    return ExternalDataPolicy.load(
        root / "configs" / "official" / "external_data_policy.json"
    )


@lru_cache(maxsize=1)
def default_external_index_quote_catalog() -> ExternalIndexQuoteCatalog:
    root = Path(__file__).resolve().parents[4]
    return ExternalIndexQuoteCatalog.load(
        root / "configs" / "official" / "external_index_quotes.json"
    )


@lru_cache(maxsize=1)
def default_benchmark_policy_catalog() -> BenchmarkPolicyCatalog:
    root = Path(__file__).resolve().parents[4]
    return BenchmarkPolicyCatalog.load(
        root / "configs" / "official" / "benchmark_policy.json"
    )

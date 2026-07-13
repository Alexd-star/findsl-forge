from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Dict, Tuple

from .models import normalize_catalog_name


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
    def __init__(self, entries, *, membership_resource_id: str):
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

    def resolve(self, atom: str) -> ResolvedExternalScope:
        source = str(atom).strip()
        options = self._by_alias.get(normalize_catalog_name(source), ())
        if not options:
            raise KeyError(source)
        selected = min(options, key=lambda item: _option_priority(source, item))
        return ResolvedExternalScope(source, selected)

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
    return ExternalScopeRuntimeCatalog.load(
        root / "configs" / "official" / "external_scope_runtime.json"
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

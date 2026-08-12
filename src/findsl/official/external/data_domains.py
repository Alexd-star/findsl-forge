from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Dict, Mapping, Tuple

from .source_registry import ExternalSourceRegistry


class DataDomainCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class DataDomainProfile:
    profile_id: str
    status: str
    active_provider_ids: Tuple[str, ...]
    candidate_provider_ids: Tuple[str, ...]
    reason: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "status": self.status,
            "active_provider_ids": list(self.active_provider_ids),
            "candidate_provider_ids": list(self.candidate_provider_ids),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class DataDomainDefinition:
    domain_id: str
    indicator_domains: Tuple[str, ...]
    provider_domain_ids: Tuple[str, ...]
    description: str
    granularity: str
    temporal_model: str
    primary_keys: Tuple[str, ...]
    quality_gates: Tuple[str, ...]
    profiles: Mapping[str, DataDomainProfile]

    def for_profile(self, profile_id: str) -> DataDomainProfile:
        try:
            return self.profiles[profile_id]
        except KeyError as exc:
            raise DataDomainCatalogError(
                f"data domain {self.domain_id} has no profile binding for {profile_id}"
            ) from exc

    def to_dict(self, *, profile_id: str | None = None) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "domain_id": self.domain_id,
            "indicator_domains": list(self.indicator_domains),
            "provider_domain_ids": list(self.provider_domain_ids),
            "description": self.description,
            "granularity": self.granularity,
            "temporal_model": self.temporal_model,
            "primary_keys": list(self.primary_keys),
            "quality_gates": list(self.quality_gates),
        }
        if profile_id is None:
            payload["profiles"] = [
                self.profiles[key].to_dict() for key in sorted(self.profiles)
            ]
        else:
            payload["profile"] = self.for_profile(profile_id).to_dict()
        return payload


class DataDomainCatalog:
    STATUSES = {
        "available",
        "derived",
        "not_loaded",
        "unsupported",
        "private_required",
    }
    GRANULARITIES = {
        "static",
        "event",
        "reporting_period",
        "daily",
        "intraday",
        "mixed",
    }
    TEMPORAL_MODELS = {
        "timeless",
        "historical_series",
        "effective_dated",
        "dated_snapshot",
        "current_snapshot",
        "request_scoped",
        "derived",
    }

    def __init__(self, definitions: Tuple[DataDomainDefinition, ...]):
        by_id: Dict[str, DataDomainDefinition] = {}
        by_indicator_domain: Dict[str, DataDomainDefinition] = {}
        for definition in definitions:
            if definition.domain_id in by_id:
                raise DataDomainCatalogError(
                    f"duplicate data domain: {definition.domain_id}"
                )
            by_id[definition.domain_id] = definition
            for indicator_domain in definition.indicator_domains:
                if indicator_domain in by_indicator_domain:
                    raise DataDomainCatalogError(
                        f"duplicate indicator-domain binding: {indicator_domain}"
                    )
                by_indicator_domain[indicator_domain] = definition
        self._by_id = MappingProxyType(by_id)
        self._by_indicator_domain = MappingProxyType(by_indicator_domain)

    def resolve(self, domain_id: str) -> DataDomainDefinition:
        try:
            return self._by_id[str(domain_id).strip()]
        except KeyError as exc:
            raise DataDomainCatalogError(f"unknown data domain: {domain_id}") from exc

    def resolve_indicator_domain(
        self, indicator_domain: str
    ) -> DataDomainDefinition | None:
        return self._by_indicator_domain.get(str(indicator_domain).strip())

    def definitions(self) -> Tuple[DataDomainDefinition, ...]:
        return tuple(self._by_id[key] for key in sorted(self._by_id))

    def profile_summary(self, profile_id: str) -> Tuple[Dict[str, object], ...]:
        return tuple(
            definition.to_dict(profile_id=profile_id)
            for definition in self.definitions()
        )

    @classmethod
    def from_dict(
        cls,
        raw,
        *,
        source_registry: ExternalSourceRegistry,
    ) -> "DataDomainCatalog":
        if set(raw) != {"schema_version", "domains"}:
            raise DataDomainCatalogError("invalid data domain catalog root")
        if raw["schema_version"] != 1:
            raise DataDomainCatalogError("unsupported data domain catalog version")
        definitions = tuple(
            _definition(item, index, cls, source_registry)
            for index, item in enumerate(raw["domains"])
        )
        if not definitions:
            raise DataDomainCatalogError("data domain catalog cannot be empty")
        return cls(definitions)

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        source_registry: ExternalSourceRegistry,
    ) -> "DataDomainCatalog":
        return cls.from_dict(
            json.loads(Path(path).read_text(encoding="utf-8")),
            source_registry=source_registry,
        )


def _definition(raw, index, catalog_type, source_registry):
    required = {
        "domain_id",
        "indicator_domains",
        "provider_domain_ids",
        "description",
        "granularity",
        "temporal_model",
        "primary_keys",
        "quality_gates",
        "profiles",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise DataDomainCatalogError(f"invalid data domain entry {index}")
    domain_id = _text(raw["domain_id"], f"domains[{index}].domain_id")
    indicator_domains = _texts(
        raw["indicator_domains"],
        f"domains[{index}].indicator_domains",
        allow_empty=True,
    )
    provider_domain_ids = _texts(
        raw["provider_domain_ids"],
        f"domains[{index}].provider_domain_ids",
    )
    granularity = _choice(
        raw["granularity"], catalog_type.GRANULARITIES, "granularity"
    )
    temporal_model = _choice(
        raw["temporal_model"], catalog_type.TEMPORAL_MODELS, "temporal_model"
    )
    primary_keys = _texts(raw["primary_keys"], "primary_keys")
    quality_gates = _texts(raw["quality_gates"], "quality_gates")
    profiles: Dict[str, DataDomainProfile] = {}
    for profile_index, item in enumerate(raw["profiles"]):
        profile = _profile(
            item,
            profile_index,
            catalog_type=catalog_type,
            source_registry=source_registry,
            provider_domain_ids=provider_domain_ids,
        )
        if profile.profile_id in profiles:
            raise DataDomainCatalogError(
                f"duplicate profile {profile.profile_id} in data domain {domain_id}"
            )
        profiles[profile.profile_id] = profile
    required_profiles = {"competition-v1", "competition-official-only-v1"}
    missing_profiles = required_profiles - set(profiles)
    if missing_profiles:
        raise DataDomainCatalogError(
            f"data domain {domain_id} misses profiles: {sorted(missing_profiles)}"
        )
    return DataDomainDefinition(
        domain_id=domain_id,
        indicator_domains=indicator_domains,
        provider_domain_ids=provider_domain_ids,
        description=_text(raw["description"], "description"),
        granularity=granularity,
        temporal_model=temporal_model,
        primary_keys=primary_keys,
        quality_gates=quality_gates,
        profiles=MappingProxyType(profiles),
    )


def _profile(
    raw,
    index,
    *,
    catalog_type,
    source_registry,
    provider_domain_ids,
):
    required = {
        "profile_id",
        "status",
        "active_provider_ids",
        "candidate_provider_ids",
        "reason",
    }
    if not isinstance(raw, dict) or set(raw) != required:
        raise DataDomainCatalogError(f"invalid data domain profile entry {index}")
    status = _choice(raw["status"], catalog_type.STATUSES, "status")
    active = _texts(raw["active_provider_ids"], "active_provider_ids", allow_empty=True)
    candidates = _texts(
        raw["candidate_provider_ids"], "candidate_provider_ids", allow_empty=True
    )
    if status in {"available", "derived"} and not active:
        raise DataDomainCatalogError(f"{status} data domain must have an active provider")
    if status not in {"available", "derived"} and active:
        raise DataDomainCatalogError(f"{status} data domain cannot have an active provider")
    for provider_id in (*active, *candidates):
        provider = source_registry.resolve(provider_id)
        if not set(provider_domain_ids).intersection(provider.data_domains):
            raise DataDomainCatalogError(
                f"provider {provider_id} does not declare any of {provider_domain_ids}"
            )
    return DataDomainProfile(
        profile_id=_text(raw["profile_id"], "profile_id"),
        status=status,
        active_provider_ids=active,
        candidate_provider_ids=candidates,
        reason=_text(raw["reason"], "reason"),
    )


def _text(value, label):
    text = str(value).strip()
    if not text:
        raise DataDomainCatalogError(f"{label} cannot be empty")
    return text


def _texts(value, label, *, allow_empty=False):
    if not isinstance(value, list):
        raise DataDomainCatalogError(f"{label} must be an array")
    values = tuple(dict.fromkeys(_text(item, label) for item in value))
    if not values and not allow_empty:
        raise DataDomainCatalogError(f"{label} cannot be empty")
    return values


def _choice(value, choices, label):
    text = _text(value, label)
    if text not in choices:
        raise DataDomainCatalogError(f"unsupported {label}: {text}")
    return text

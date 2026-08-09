from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Dict, Protocol, Tuple, runtime_checkable
from urllib.parse import urlparse


class ExternalSourceRegistryError(ValueError):
    pass


@runtime_checkable
class ExternalProvider(Protocol):
    source: str
    source_url: str
    license_note: str


@dataclass(frozen=True)
class ExternalSource:
    provider_id: str
    source: str
    source_url: str
    authority_level: str
    data_domains: Tuple[str, ...]
    temporal_model: str
    redistribution: str
    terms_url: str
    enabled_profiles: Tuple[str, ...]
    notes: str


class ExternalSourceRegistry:
    AUTHORITY_LEVELS = {
        "competition_official",
        "official_publisher",
        "licensed_data_service",
        "public_data_service",
        "public_information_platform",
        "open_source_adapter",
        "project_curated",
    }
    TEMPORAL_MODELS = {
        "effective_dated",
        "dated_snapshot",
        "current_snapshot",
        "historical_series",
        "project_policy",
    }
    REDISTRIBUTION_POLICIES = {
        "bundled_by_organizer",
        "review_required",
        "derived_snapshot_only",
        "academic_only",
        "not_redistributed",
    }

    def __init__(self, entries: Tuple[ExternalSource, ...]):
        by_id: Dict[str, ExternalSource] = {}
        by_source: Dict[str, ExternalSource] = {}
        for entry in entries:
            if entry.provider_id in by_id or entry.source in by_source:
                raise ExternalSourceRegistryError(
                    f"duplicate external source: {entry.provider_id}/{entry.source}"
                )
            by_id[entry.provider_id] = entry
            by_source[entry.source] = entry
        self._by_id = MappingProxyType(by_id)
        self._by_source = MappingProxyType(by_source)

    def resolve(self, provider_id: str) -> ExternalSource:
        try:
            return self._by_id[str(provider_id).strip()]
        except KeyError as exc:
            raise ExternalSourceRegistryError(
                f"unregistered external provider: {provider_id}"
            ) from exc

    def resolve_source(self, source: str) -> ExternalSource:
        try:
            return self._by_source[str(source).strip()]
        except KeyError as exc:
            raise ExternalSourceRegistryError(
                f"unregistered external snapshot source: {source}"
            ) from exc

    def entries(self) -> Tuple[ExternalSource, ...]:
        return tuple(self._by_id[key] for key in sorted(self._by_id))

    def assert_provider(self, provider_id: str, provider: ExternalProvider) -> ExternalSource:
        entry = self.resolve(provider_id)
        if not isinstance(provider, ExternalProvider):
            raise ExternalSourceRegistryError(
                f"provider {provider_id} does not expose source provenance"
            )
        if str(provider.source).strip() != entry.source:
            raise ExternalSourceRegistryError(
                f"provider source mismatch: {provider.source}/{entry.source}"
            )
        if _normalized_url(str(provider.source_url)) != _normalized_url(entry.source_url):
            raise ExternalSourceRegistryError(
                f"provider URL mismatch: {provider.source_url}/{entry.source_url}"
            )
        if not str(provider.license_note).strip():
            raise ExternalSourceRegistryError(
                f"provider {provider_id} has no license note"
            )
        return entry

    @classmethod
    def from_dict(cls, raw) -> "ExternalSourceRegistry":
        if set(raw) != {"schema_version", "sources"}:
            raise ExternalSourceRegistryError("invalid external source registry root")
        if raw["schema_version"] != 1:
            raise ExternalSourceRegistryError("unsupported external source registry version")
        required = {
            "provider_id",
            "source",
            "source_url",
            "authority_level",
            "data_domains",
            "temporal_model",
            "redistribution",
            "terms_url",
            "enabled_profiles",
            "notes",
        }
        entries = []
        for index, item in enumerate(raw["sources"]):
            if not isinstance(item, dict) or set(item) != required:
                raise ExternalSourceRegistryError(
                    f"invalid external source registry entry {index}"
                )
            entry = ExternalSource(
                provider_id=_required_text(item["provider_id"], "provider_id"),
                source=_required_text(item["source"], "source"),
                source_url=_required_url(item["source_url"], "source_url"),
                authority_level=_required_choice(
                    item["authority_level"], cls.AUTHORITY_LEVELS, "authority_level"
                ),
                data_domains=_required_text_tuple(item["data_domains"], "data_domains"),
                temporal_model=_required_choice(
                    item["temporal_model"], cls.TEMPORAL_MODELS, "temporal_model"
                ),
                redistribution=_required_choice(
                    item["redistribution"],
                    cls.REDISTRIBUTION_POLICIES,
                    "redistribution",
                ),
                terms_url=_optional_url(item["terms_url"], "terms_url"),
                enabled_profiles=_required_text_tuple(
                    item["enabled_profiles"], "enabled_profiles"
                ),
                notes=_required_text(item["notes"], "notes"),
            )
            entries.append(entry)
        return cls(tuple(entries))

    @classmethod
    def load(cls, path: Path) -> "ExternalSourceRegistry":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _required_text(value, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise ExternalSourceRegistryError(f"{label} cannot be empty")
    return text


def _required_text_tuple(value, label: str) -> Tuple[str, ...]:
    if not isinstance(value, list):
        raise ExternalSourceRegistryError(f"{label} must be an array")
    items = tuple(dict.fromkeys(_required_text(item, label) for item in value))
    if not items:
        raise ExternalSourceRegistryError(f"{label} cannot be empty")
    return items


def _required_choice(value, choices, label: str) -> str:
    text = _required_text(value, label)
    if text not in choices:
        raise ExternalSourceRegistryError(f"unsupported {label}: {text}")
    return text


def _required_url(value, label: str) -> str:
    text = _required_text(value, label)
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ExternalSourceRegistryError(f"{label} must be an HTTP(S) URL")
    return text


def _optional_url(value, label: str) -> str:
    text = str(value).strip()
    return _required_url(text, label) if text else ""


def _normalized_url(value: str) -> str:
    return str(value).strip().rstrip("/").casefold()

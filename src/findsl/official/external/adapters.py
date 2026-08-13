from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Dict, Mapping, Protocol, Tuple, runtime_checkable

from .admission import (
    DomainSnapshotAdmissionError,
    DomainSnapshotManifest,
    audit_domain_snapshot,
)
from .data_domains import DataDomainCatalog
from .contracts import DomainTableContractCatalog, default_domain_table_contracts
from .source_registry import ExternalProvider, ExternalSourceRegistry


class DomainAdapterError(ValueError):
    pass


@dataclass(frozen=True)
class DomainAdapterRequest:
    domain_id: str
    profile_id: str
    as_of_date: str


@dataclass(frozen=True)
class DomainSnapshotArtifact:
    manifest: DomainSnapshotManifest
    data_path: Path
    data_format: str


@runtime_checkable
class DomainAdapter(ExternalProvider, Protocol):
    provider_id: str
    domain_id: str

    def fetch(self, request: DomainAdapterRequest) -> DomainSnapshotArtifact:
        ...


class DomainAdapterRegistry:
    def __init__(self, adapters: Tuple[DomainAdapter, ...] = ()) -> None:
        by_key: Dict[Tuple[str, str], DomainAdapter] = {}
        for adapter in adapters:
            key = (str(adapter.provider_id).strip(), str(adapter.domain_id).strip())
            if not all(key) or key in by_key:
                raise DomainAdapterError(
                    f"duplicate or invalid domain adapter: {key[0]}/{key[1]}"
                )
            by_key[key] = adapter
        self._adapters: Mapping[Tuple[str, str], DomainAdapter] = MappingProxyType(
            by_key
        )

    def register(self, adapter: DomainAdapter) -> "DomainAdapterRegistry":
        return DomainAdapterRegistry((*self._adapters.values(), adapter))

    def resolve(self, provider_id: str, domain_id: str) -> DomainAdapter:
        key = (str(provider_id).strip(), str(domain_id).strip())
        try:
            return self._adapters[key]
        except KeyError as exc:
            raise DomainAdapterError(
                f"no adapter registered for {key[0]}/{key[1]}"
            ) from exc

    @property
    def keys(self) -> Tuple[Tuple[str, str], ...]:
        return tuple(sorted(self._adapters))


class DomainAdapterRunner:
    def __init__(
        self,
        *,
        adapters: DomainAdapterRegistry,
        data_domains: DataDomainCatalog,
        sources: ExternalSourceRegistry,
        contracts: DomainTableContractCatalog | None = None,
    ) -> None:
        self.adapters = adapters
        self.data_domains = data_domains
        self.sources = sources
        self.contracts = contracts or default_domain_table_contracts()

    def fetch_and_audit(
        self,
        provider_id: str,
        request: DomainAdapterRequest,
    ) -> Tuple[DomainSnapshotArtifact, Mapping[str, object]]:
        adapter = self.adapters.resolve(provider_id, request.domain_id)
        self.sources.assert_provider(provider_id, adapter)
        artifact = adapter.fetch(request)
        if artifact.manifest.provider_id != provider_id:
            raise DomainAdapterError("adapter manifest provider_id changed during fetch")
        if artifact.manifest.domain_id != request.domain_id:
            raise DomainAdapterError("adapter manifest domain_id changed during fetch")
        if artifact.manifest.profile_id != request.profile_id:
            raise DomainAdapterError("adapter manifest profile_id changed during fetch")
        if artifact.manifest.as_of_date != request.as_of_date:
            raise DomainAdapterError("adapter manifest as_of_date changed during fetch")
        observed = inspect_tabular_artifact(
            artifact.data_path,
            artifact.data_format,
        )
        if observed["content_sha256"] != artifact.manifest.content_sha256:
            raise DomainAdapterError("adapter artifact SHA-256 differs from manifest")
        if observed["row_count"] != artifact.manifest.row_count:
            raise DomainAdapterError("adapter artifact row count differs from manifest")
        if tuple(observed["columns"]) != artifact.manifest.columns:
            raise DomainAdapterError("adapter artifact columns differ from manifest")
        report = audit_domain_snapshot(
            artifact.manifest,
            data_domains=self.data_domains,
            sources=self.sources,
            contracts=self.contracts,
        )
        if not report["passed"]:
            raise DomainSnapshotAdmissionError("; ".join(report["errors"]))
        return artifact, MappingProxyType(report)


@dataclass(frozen=True)
class LocalTabularDomainAdapter:
    provider_id: str
    domain_id: str
    source: str
    source_url: str
    license_note: str
    temporal_model: str
    data_path: Path
    data_format: str
    license_accepted: bool = False

    def fetch(self, request: DomainAdapterRequest) -> DomainSnapshotArtifact:
        if request.domain_id != self.domain_id:
            raise DomainAdapterError(
                f"adapter domain mismatch: {request.domain_id}/{self.domain_id}"
            )
        path = Path(self.data_path).resolve()
        observed = inspect_tabular_artifact(path, self.data_format)
        snapshot_id = (
            f"{self.provider_id}-{request.as_of_date}-"
            f"{observed['content_sha256'][:12]}"
        )
        manifest = DomainSnapshotManifest.from_dict(
            {
                "schema_version": 1,
                "provider_id": self.provider_id,
                "domain_id": self.domain_id,
                "profile_id": request.profile_id,
                "snapshot_id": snapshot_id,
                "source_uri": path.as_uri(),
                "retrieved_at": datetime.now(timezone.utc)
                .replace(microsecond=0)
                .isoformat(),
                "as_of_date": request.as_of_date,
                "content_sha256": observed["content_sha256"],
                "row_count": observed["row_count"],
                "columns": list(observed["columns"]),
                "temporal_model": self.temporal_model,
                "license_accepted": self.license_accepted,
            }
        )
        return DomainSnapshotArtifact(manifest, path, self.data_format.lower())


def inspect_tabular_artifact(path: Path, data_format: str) -> Mapping[str, object]:
    source = Path(path)
    if not source.is_file():
        raise DomainAdapterError(f"adapter artifact does not exist: {source}")
    normalized_format = str(data_format).strip().lower()
    if normalized_format == "csv":
        columns, row_count = _inspect_csv(source)
    elif normalized_format in {"jsonl", "ndjson"}:
        columns, row_count = _inspect_jsonl(source)
    else:
        raise DomainAdapterError(
            f"unsupported adapter artifact format: {data_format}"
        )
    if row_count <= 0:
        raise DomainAdapterError("adapter artifact contains no data rows")
    return MappingProxyType(
        {
            "content_sha256": _sha256(source),
            "row_count": row_count,
            "columns": columns,
        }
    )


def _inspect_csv(path: Path) -> Tuple[Tuple[str, ...], int]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = tuple(str(value).strip() for value in (reader.fieldnames or ()))
        if not columns or any(not value for value in columns) or len(set(columns)) != len(columns):
            raise DomainAdapterError("CSV header is empty, duplicated or invalid")
        count = 0
        for row in reader:
            if None in row:
                raise DomainAdapterError("CSV row contains more values than the header")
            count += 1
    return columns, count


def _inspect_jsonl(path: Path) -> Tuple[Tuple[str, ...], int]:
    columns = None
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise DomainAdapterError(
                    f"JSONL row {line_number} is invalid"
                ) from exc
            if not isinstance(row, dict) or not row:
                raise DomainAdapterError(
                    f"JSONL row {line_number} must be a non-empty object"
                )
            row_columns = tuple(str(value).strip() for value in row)
            if columns is None:
                columns = row_columns
            elif row_columns != columns:
                raise DomainAdapterError(
                    f"JSONL row {line_number} changes the column contract"
                )
            count += 1
    return columns or (), count


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

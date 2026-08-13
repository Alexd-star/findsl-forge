from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

from .data_domains import DataDomainCatalog
from .source_registry import ExternalSourceRegistry
from .contracts import DomainTableContractCatalog


class DomainSnapshotAdmissionError(ValueError):
    pass


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SECRET_QUERY_KEY = re.compile(
    r"(?:token|secret|password|passwd|access_key|api_key)=", re.IGNORECASE
)


@dataclass(frozen=True)
class DomainSnapshotManifest:
    provider_id: str
    domain_id: str
    profile_id: str
    snapshot_id: str
    source_uri: str
    retrieved_at: str
    as_of_date: str
    content_sha256: str
    row_count: int
    columns: Tuple[str, ...]
    temporal_model: str
    license_accepted: bool

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "DomainSnapshotManifest":
        required = {
            "schema_version",
            "provider_id",
            "domain_id",
            "profile_id",
            "snapshot_id",
            "source_uri",
            "retrieved_at",
            "as_of_date",
            "content_sha256",
            "row_count",
            "columns",
            "temporal_model",
            "license_accepted",
        }
        if not isinstance(raw, dict) or set(raw) != required:
            raise DomainSnapshotAdmissionError("invalid domain snapshot manifest root")
        if raw["schema_version"] != 1:
            raise DomainSnapshotAdmissionError(
                "unsupported domain snapshot manifest version"
            )
        text = {
            key: str(raw[key]).strip()
            for key in (
                "provider_id",
                "domain_id",
                "profile_id",
                "snapshot_id",
                "source_uri",
                "retrieved_at",
                "as_of_date",
                "content_sha256",
                "temporal_model",
            )
        }
        if not all(text.values()):
            raise DomainSnapshotAdmissionError(
                "domain snapshot identity fields cannot be empty"
            )
        try:
            datetime.fromisoformat(text["retrieved_at"].replace("Z", "+00:00"))
            date.fromisoformat(text["as_of_date"])
        except ValueError as exc:
            raise DomainSnapshotAdmissionError(
                "snapshot dates must use ISO-8601"
            ) from exc
        if not _SHA256.fullmatch(text["content_sha256"]):
            raise DomainSnapshotAdmissionError(
                "content_sha256 must be a lowercase SHA-256 digest"
            )
        if isinstance(raw["row_count"], bool) or int(raw["row_count"]) <= 0:
            raise DomainSnapshotAdmissionError("row_count must be positive")
        if not isinstance(raw["columns"], list):
            raise DomainSnapshotAdmissionError("columns must be an array")
        columns = tuple(
            dict.fromkeys(str(column).strip() for column in raw["columns"])
        )
        if not columns or not all(columns):
            raise DomainSnapshotAdmissionError("columns cannot contain empty names")
        uri = urlparse(text["source_uri"])
        if uri.scheme not in {"https", "file"}:
            raise DomainSnapshotAdmissionError(
                "source_uri must use https or an offline file URI"
            )
        if uri.scheme == "https" and not uri.netloc:
            raise DomainSnapshotAdmissionError("source_uri has no host")
        if _SECRET_QUERY_KEY.search(text["source_uri"]):
            raise DomainSnapshotAdmissionError(
                "source_uri must not contain credentials or API tokens"
            )
        return cls(
            provider_id=text["provider_id"],
            domain_id=text["domain_id"],
            profile_id=text["profile_id"],
            snapshot_id=text["snapshot_id"],
            source_uri=text["source_uri"],
            retrieved_at=text["retrieved_at"],
            as_of_date=text["as_of_date"],
            content_sha256=text["content_sha256"],
            row_count=int(raw["row_count"]),
            columns=columns,
            temporal_model=text["temporal_model"],
            license_accepted=bool(raw["license_accepted"]),
        )

    @classmethod
    def load(cls, path: Path) -> "DomainSnapshotManifest":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def audit_domain_snapshot(
    manifest: DomainSnapshotManifest,
    *,
    data_domains: DataDomainCatalog,
    sources: ExternalSourceRegistry,
    contracts: DomainTableContractCatalog | None = None,
) -> Dict[str, Any]:
    errors = []
    warnings = []
    try:
        domain = data_domains.resolve(manifest.domain_id)
        profile = domain.for_profile(manifest.profile_id)
    except Exception as exc:  # noqa: BLE001 - audit returns all admission failures.
        return _report(manifest, "REJECTED", (str(exc),), ())
    try:
        provider = sources.resolve(manifest.provider_id)
    except Exception as exc:  # noqa: BLE001 - audit returns all admission failures.
        return _report(manifest, "REJECTED", (str(exc),), ())

    if not set(domain.provider_domain_ids).intersection(provider.data_domains):
        errors.append("provider does not declare the requested data-domain capability")
    if manifest.temporal_model != provider.temporal_model:
        errors.append("snapshot temporal_model differs from the provider registry")
    missing_keys = sorted(set(domain.primary_keys) - set(manifest.columns))
    if missing_keys:
        errors.append(f"snapshot columns miss primary keys: {missing_keys}")
    if manifest.provider_id not in {
        *profile.active_provider_ids,
        *profile.candidate_provider_ids,
    }:
        errors.append("provider is not admitted by the selected data profile")
    if not manifest.license_accepted:
        errors.append("source terms or license have not been explicitly accepted")
    if manifest.provider_id in profile.candidate_provider_ids:
        warnings.append(
            "candidate snapshot passed structural admission but requires reviewed "
            "promotion before the compiler can select it"
        )
    contract_report = None
    if contracts is not None:
        contract_report = dict(
            contracts.audit(manifest.domain_id, manifest.columns)
        )
        if not contract_report["passed"]:
            errors.append(
                "snapshot columns do not match any admitted domain table variant"
            )
    if provider.redistribution in {"not_redistributed", "review_required"}:
        warnings.append(
            f"redistribution policy is {provider.redistribution}; keep restricted raw "
            "data outside the repository and submission package"
        )
    status = "REJECTED" if errors else "CANDIDATE" if warnings else "ACTIVE_READY"
    report = _report(manifest, status, tuple(errors), tuple(warnings))
    report["table_contract"] = contract_report
    return report


def _report(manifest, status, errors, warnings):
    return {
        "schema_version": 1,
        "status": status,
        "passed": not errors,
        "provider_id": manifest.provider_id,
        "domain_id": manifest.domain_id,
        "profile_id": manifest.profile_id,
        "snapshot_id": manifest.snapshot_id,
        "content_sha256": manifest.content_sha256,
        "row_count": manifest.row_count,
        "errors": list(errors),
        "warnings": list(warnings),
    }

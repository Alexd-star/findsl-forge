from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Tuple

from findsl.official.external.adapters import (
    DomainAdapterRegistry,
    DomainAdapterRequest,
    DomainAdapterRunner,
    LocalTabularDomainAdapter,
)
from findsl.official.external.contracts import DomainTableContractCatalog
from findsl.official.external.data_domains import DataDomainCatalog
from findsl.official.external.source_registry import ExternalSourceRegistry


def admit_local_snapshot(
    *,
    source_registry_path: Path,
    data_domains_path: Path,
    contracts_path: Path,
    provider_id: str,
    domain_id: str,
    profile_id: str,
    as_of_date: str,
    data_path: Path,
    data_format: str,
    license_note: str,
    license_accepted: bool,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    sources = ExternalSourceRegistry.load(source_registry_path)
    domains = DataDomainCatalog.load(
        data_domains_path,
        source_registry=sources,
    )
    contracts = DomainTableContractCatalog.load(contracts_path)
    source = sources.resolve(provider_id)
    adapter = LocalTabularDomainAdapter(
        provider_id=provider_id,
        domain_id=domain_id,
        source=source.source,
        source_url=source.source_url,
        license_note=license_note,
        temporal_model=source.temporal_model,
        data_path=data_path,
        data_format=data_format,
        license_accepted=license_accepted,
    )
    runner = DomainAdapterRunner(
        adapters=DomainAdapterRegistry((adapter,)),
        data_domains=domains,
        sources=sources,
        contracts=contracts,
    )
    artifact, report = runner.fetch_and_audit(
        provider_id,
        DomainAdapterRequest(domain_id, profile_id, as_of_date),
    )
    manifest = {"schema_version": 1, **asdict(artifact.manifest)}
    manifest["columns"] = list(artifact.manifest.columns)
    return manifest, dict(report)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Admit a downloaded domain snapshot without network access"
    )
    parser.add_argument("--provider-id", required=True)
    parser.add_argument("--domain-id", required=True)
    parser.add_argument("--profile-id", default="competition-v1")
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--format", choices=("csv", "jsonl"), required=True)
    parser.add_argument("--license-note", required=True)
    parser.add_argument("--accept-license", action="store_true")
    parser.add_argument("--manifest-output", required=True, type=Path)
    parser.add_argument("--audit-output", required=True, type=Path)
    parser.add_argument(
        "--source-registry",
        type=Path,
        default=Path("configs/official/external_source_registry.json"),
    )
    parser.add_argument(
        "--data-domains",
        type=Path,
        default=Path("configs/official/data_domains.json"),
    )
    parser.add_argument(
        "--table-contracts",
        type=Path,
        default=Path("configs/official/domain_table_contracts.json"),
    )
    args = parser.parse_args()
    manifest, report = admit_local_snapshot(
        source_registry_path=args.source_registry,
        data_domains_path=args.data_domains,
        contracts_path=args.table_contracts,
        provider_id=args.provider_id,
        domain_id=args.domain_id,
        profile_id=args.profile_id,
        as_of_date=args.as_of_date,
        data_path=args.data,
        data_format=args.format,
        license_note=args.license_note,
        license_accepted=args.accept_license,
    )
    for path, payload in (
        (args.manifest_output, manifest),
        (args.audit_output, report),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

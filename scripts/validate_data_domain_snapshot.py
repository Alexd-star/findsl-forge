from __future__ import annotations

import argparse
import json
from pathlib import Path

from findsl.official.external.admission import (
    DomainSnapshotManifest,
    audit_domain_snapshot,
)
from findsl.official.external.data_domains import DataDomainCatalog
from findsl.official.external.source_registry import ExternalSourceRegistry
from findsl.official.external.contracts import DomainTableContractCatalog


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument(
        "--data-domains",
        type=Path,
        default=Path("configs/official/data_domains.json"),
    )
    parser.add_argument(
        "--source-registry",
        type=Path,
        default=Path("configs/official/external_source_registry.json"),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--table-contracts",
        type=Path,
        default=Path("configs/official/domain_table_contracts.json"),
    )
    args = parser.parse_args()

    sources = ExternalSourceRegistry.load(args.source_registry)
    domains = DataDomainCatalog.load(
        args.data_domains,
        source_registry=sources,
    )
    report = audit_domain_snapshot(
        DomainSnapshotManifest.load(args.manifest),
        data_domains=domains,
        sources=sources,
        contracts=DomainTableContractCatalog.load(args.table_contracts),
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

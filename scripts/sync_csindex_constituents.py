from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests

from findsl.official.external import ExternalCatalog
from findsl.official.external.index_sync import build_index_snapshot
from findsl.official.external.providers.indexes import CsindexProvider, IndexDefinition


class _RequestsHttp:
    def __init__(self, *, timeout_seconds: float, trust_environment_proxy: bool):
        self.session = requests.Session()
        self.session.trust_env = trust_environment_proxy
        self.timeout_seconds = timeout_seconds

    def get(self, url):
        response = self.session.get(url, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response


class _TargetedCsindexProvider:
    source = CsindexProvider.source
    source_url = CsindexProvider.source_url
    license_note = CsindexProvider.license_note

    def __init__(self, definition: IndexDefinition, provider: CsindexProvider):
        self.definition = definition
        self.provider = provider

    def list_indices(self):
        return (self.definition,)

    def list_constituents(self, index):
        return self.provider.list_constituents(index)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--full-name", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--expected-count", type=int, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--trust-environment-proxy", action="store_true")
    args = parser.parse_args()

    definition = IndexDefinition("csindex", args.code, args.name, args.full_name)
    http = _RequestsHttp(
        timeout_seconds=args.timeout_seconds,
        trust_environment_proxy=args.trust_environment_proxy,
    )
    provider = _TargetedCsindexProvider(
        definition,
        CsindexProvider(http=http),
    )
    result = build_index_snapshot(
        [args.name],
        provider=provider,
        as_of_date=args.as_of_date,
    )
    if result is None or result.unresolved or result.failed:
        raise RuntimeError("targeted CSI synchronization did not produce a complete snapshot")
    actual_count = len(result.snapshot.scope_memberships)
    if actual_count != args.expected_count:
        raise RuntimeError(
            f"CSI constituent count mismatch: {actual_count} != {args.expected_count}"
        )

    catalog = ExternalCatalog(Path(args.catalog))
    # A targeted snapshot contains one index only. Replacing every snapshot from
    # the same source and date would delete other indices synchronized that day.
    # Replace only an identical snapshot id so independent targeted imports coexist.
    catalog.import_snapshot(result.snapshot, replace=True)
    runtime = catalog.export_runtime_manifest(Path(args.runtime))
    payload = {
        **result.to_dict(),
        "status": "PASS",
        "expected_count": args.expected_count,
        "actual_count": actual_count,
        "runtime_entries": len(runtime["entries"]),
        "catalog_summary": catalog.summary(),
    }
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

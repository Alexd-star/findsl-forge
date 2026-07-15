from __future__ import annotations

import argparse
import json
from pathlib import Path

from findsl.official.external import ExternalCatalog
from findsl.official.external.profile_sync import (
    build_baidu_classification_snapshot,
)
from findsl.official.external.providers import BaiduRelatedBlockProvider


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument(
        "--runtime", default="configs/official/external_scope_runtime.json"
    )
    parser.add_argument("--identity-source", default="akshare-security-identity")
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--backoff-seconds", type=float, default=0.5)
    parser.add_argument("--request-interval-seconds", type=float, default=0.1)
    parser.add_argument("--trust-environment-proxy", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    catalog = ExternalCatalog(Path(args.catalog))
    identities = catalog.latest_security_identities(args.identity_source)
    provider = BaiduRelatedBlockProvider(
        cache_dir=Path(args.cache_dir) if args.cache_dir else None,
        timeout_seconds=args.timeout_seconds,
        max_attempts=args.max_attempts,
        backoff_seconds=args.backoff_seconds,
        request_interval_seconds=args.request_interval_seconds,
        trust_environment_proxy=args.trust_environment_proxy,
    )
    classifications = provider.list_classifications(
        (item["tgtcode"], item["scope_name"]) for item in identities
    )
    snapshot = build_baidu_classification_snapshot(
        classifications, as_of_date=args.as_of_date
    )
    catalog.import_snapshot(snapshot, replace=args.replace)
    runtime = catalog.export_runtime_manifest(Path(args.runtime))
    scope_counts = {}
    for item in snapshot.scope_memberships:
        scope_counts[item.scope_type] = scope_counts.get(item.scope_type, 0) + 1
    payload = {
        "schema_version": 1,
        "snapshot_id": snapshot.snapshot_id,
        "source": snapshot.source,
        "source_url": snapshot.source_url,
        "as_of_date": snapshot.as_of_date,
        "content_sha256": snapshot.content_sha256,
        "identity_source": args.identity_source,
        "identity_snapshot_id": identities[0]["snapshot_id"],
        "requested_securities": len(identities),
        "classified_securities": len(classifications),
        "scope_memberships": len(snapshot.scope_memberships),
        "industry_memberships": len(snapshot.industry_memberships),
        "scope_type_counts": scope_counts,
        "runtime_entries": len(runtime["entries"]),
        "catalog_summary": catalog.summary(),
        "complete": len(classifications) == len(identities),
    }
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

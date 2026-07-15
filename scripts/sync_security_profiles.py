from __future__ import annotations

import argparse
import json
from pathlib import Path

from findsl.official.external import ExternalCatalog
from findsl.official.external.profile_sync import build_security_profile_snapshot
from findsl.official.external.providers import EastmoneyBoardProvider


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument(
        "--runtime", default="configs/official/external_scope_runtime.json"
    )
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--trust-environment-proxy", action="store_true")
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--backoff-seconds", type=float, default=0.5)
    parser.add_argument("--request-interval-seconds", type=float, default=0.1)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    provider = EastmoneyBoardProvider(
        timeout_seconds=args.timeout_seconds,
        max_attempts=args.max_attempts,
        backoff_seconds=args.backoff_seconds,
        trust_environment_proxy=args.trust_environment_proxy,
        cache_dir=Path(args.cache_dir) if args.cache_dir else None,
        request_interval_seconds=args.request_interval_seconds,
    )
    profiles = provider.list_security_profiles()
    snapshot = build_security_profile_snapshot(
        profiles, as_of_date=args.as_of_date
    )
    catalog = ExternalCatalog(Path(args.catalog))
    catalog.import_snapshot(snapshot, replace=args.replace)
    runtime = catalog.export_runtime_manifest(Path(args.runtime))
    concepts = {item for profile in profiles for item in profile.concepts}
    industries = {
        profile.industry
        for profile in profiles
        if profile.industry and profile.industry != "-"
    }
    regions = {
        profile.region
        for profile in profiles
        if profile.region and profile.region != "-"
    }
    payload = {
        "schema_version": 1,
        "snapshot_id": snapshot.snapshot_id,
        "source": snapshot.source,
        "source_url": snapshot.source_url,
        "as_of_date": snapshot.as_of_date,
        "content_sha256": snapshot.content_sha256,
        "profiles": len(profiles),
        "concepts": len(concepts),
        "industries": len(industries),
        "regions": len(regions),
        "scope_memberships": len(snapshot.scope_memberships),
        "runtime_entries": len(runtime["entries"]),
        "runtime_membership_resource_id": runtime["membership_resource_id"],
        "catalog_summary": catalog.summary(),
    }
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

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
    parser.add_argument("--as-of-date", default=None)
    args = parser.parse_args()

    provider = EastmoneyBoardProvider(trust_environment_proxy=True)
    profiles = provider.list_security_profiles()
    snapshot = build_security_profile_snapshot(
        profiles, as_of_date=args.as_of_date
    )
    catalog = ExternalCatalog(Path(args.catalog))
    catalog.import_snapshot(snapshot, replace=True)
    payload = {
        "snapshot_id": snapshot.snapshot_id,
        "source": snapshot.source,
        "profiles": len(profiles),
        "scope_memberships": len(snapshot.scope_memberships),
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

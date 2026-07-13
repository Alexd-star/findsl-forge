from __future__ import annotations

import argparse
import json
from pathlib import Path

from findsl.official.external import ExternalCatalog
from findsl.official.external.profile_sync import build_security_identity_snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--as-of-date", default=None)
    args = parser.parse_args()

    import akshare as ak

    frame = ak.stock_info_a_code_name()
    snapshot = build_security_identity_snapshot(
        ((row["code"], row["name"]) for row in frame.to_dict("records")),
        as_of_date=args.as_of_date,
    )
    catalog = ExternalCatalog(Path(args.catalog))
    catalog.import_snapshot(snapshot, replace=True)
    payload = {
        "schema_version": 1,
        "snapshot_id": snapshot.snapshot_id,
        "source": snapshot.source,
        "scope_memberships": len(snapshot.scope_memberships),
        "catalog_summary": catalog.summary(),
    }
    Path(args.report).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

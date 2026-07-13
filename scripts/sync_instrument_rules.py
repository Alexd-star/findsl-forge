from __future__ import annotations

import argparse
import json
from pathlib import Path

from findsl.official.external import ExternalCatalog
from findsl.official.external.instrument_sync import build_official_stock_t0_snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--securities", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--as-of-date", default=None)
    args = parser.parse_args()
    snapshot = build_official_stock_t0_snapshot(
        Path(args.securities), as_of_date=args.as_of_date
    )
    catalog = ExternalCatalog(Path(args.catalog))
    catalog.import_snapshot(snapshot, replace=True)
    payload = {
        "snapshot_id": snapshot.snapshot_id,
        "instrument_rules": len(snapshot.instrument_rules),
        "t0_eligible": sum(item.t0_eligible for item in snapshot.instrument_rules),
        "catalog_summary": catalog.summary(),
    }
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

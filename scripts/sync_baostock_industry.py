from __future__ import annotations

import argparse
import json
from pathlib import Path

from findsl.official.external import ExternalCatalog
from findsl.official.external.industry_sync import build_baostock_industry_snapshot
from findsl.official.external.providers.baostock import BaoStockIndustryProvider


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--as-of-date", default=None)
    args = parser.parse_args()

    snapshot, classification = build_baostock_industry_snapshot(
        BaoStockIndustryProvider(),
        as_of_date=args.as_of_date,
    )
    catalog = ExternalCatalog(Path(args.catalog))
    catalog.import_snapshot(snapshot)

    policy_path = Path(args.policy)
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["industry"] = {
        "resource_id": "external_industry_membership",
        "snapshot_id": snapshot.snapshot_id,
        "source": snapshot.source,
        "as_of_date": snapshot.as_of_date,
        "classification_system": classification,
        "industry_level": "industry",
    }
    policy_path.write_text(
        json.dumps(policy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report = {
        "schema_version": 1,
        "snapshot_id": snapshot.snapshot_id,
        "source": snapshot.source,
        "as_of_date": snapshot.as_of_date,
        "classification_system": classification,
        "classified_securities": len(snapshot.industry_memberships),
        "catalog_summary": catalog.summary(),
    }
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

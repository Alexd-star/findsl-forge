from __future__ import annotations

import argparse
import json
from pathlib import Path

from findsl.official.external import ExternalCatalog
from findsl.official.external.providers.sina import SinaSectorProvider
from findsl.official.external.sina_sync import build_sina_sector_snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument(
        "--runtime", default="configs/official/external_scope_runtime.json"
    )
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--request-interval-seconds", type=float, default=0.05)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()

    provider = SinaSectorProvider(
        cache_dir=Path(args.cache),
        request_interval_seconds=args.request_interval_seconds,
    )
    result = build_sina_sector_snapshot(provider=provider, as_of_date=args.as_of_date)
    report = result.to_dict()
    report["complete"] = not result.failed_sectors
    report["imported"] = not (args.require_complete and not report["complete"])
    catalog = ExternalCatalog(Path(args.catalog))
    if report["imported"]:
        catalog.import_snapshot(result.snapshot, replace=True)
        runtime = catalog.export_runtime_manifest(Path(args.runtime))
        report["runtime"] = {
            "path": str(Path(args.runtime).resolve()),
            "entries": len(runtime["entries"]),
            "membership_resource_id": runtime["membership_resource_id"],
        }
        report["catalog_summary"] = catalog.summary()
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["imported"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

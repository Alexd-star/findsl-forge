from __future__ import annotations

import argparse
import json
from pathlib import Path

from findsl.official.external import ExternalCatalog
from findsl.official.external.index_sync import build_index_snapshot
from findsl.official.external.matching import canonical_scope_name
from findsl.official.external.providers.indexes import (
    AkshareCsindexProvider,
    AkshareIndexProvider,
    CniProvider,
    CsindexProvider,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--as-of-date", default=None)
    args = parser.parse_args()
    target_payload = json.loads(Path(args.targets).read_text(encoding="utf-8"))
    targets = [item["name"] for item in target_payload["targets"]]
    aliases = {
        canonical_scope_name(key): value
        for key, value in target_payload.get("index_aliases", {}).items()
    }
    catalog = ExternalCatalog(Path(args.catalog))
    results = []
    for provider in (
        CsindexProvider(),
        CniProvider(),
        AkshareCsindexProvider(),
        AkshareIndexProvider(),
    ):
        result = build_index_snapshot(
            targets,
            provider=provider,
            aliases=aliases,
            as_of_date=args.as_of_date,
        )
        if result is None:
            continue
        catalog.import_snapshot(result.snapshot, replace=True)
        results.append(result.to_dict())
    runtime = catalog.export_runtime_manifest(
        Path("configs/official/external_scope_runtime.json")
    )
    payload = {
        "results": results,
        "runtime_entries": len(runtime["entries"]),
        "catalog_summary": catalog.summary(),
    }
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

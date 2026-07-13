from __future__ import annotations

import argparse
import json
from pathlib import Path

from findsl.official.external import ExternalCatalog
from findsl.official.external.providers import EastmoneyBoardProvider
from findsl.official.external.sync import build_eastmoney_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synchronize a complete public Eastmoney industry membership snapshot"
    )
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--trust-environment-proxy", action="store_true")
    args = parser.parse_args()

    provider = EastmoneyBoardProvider(
        trust_environment_proxy=args.trust_environment_proxy,
        max_attempts=8,
        backoff_seconds=1.0,
    )
    targets = tuple(board.name for board in provider.list_boards("industry"))
    result = build_eastmoney_snapshot(
        targets,
        provider=provider,
        as_of_date=args.as_of_date,
    )
    catalog = ExternalCatalog(Path(args.catalog))
    catalog.import_snapshot(result.snapshot)
    runtime = catalog.export_runtime_manifest(Path(args.runtime))
    report = result.to_dict()
    report["requested_industries"] = len(targets)
    report["runtime_entries"] = len(runtime["entries"])
    report["catalog_summary"] = catalog.summary()
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

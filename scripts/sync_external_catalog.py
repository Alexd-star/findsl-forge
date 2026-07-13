from __future__ import annotations

import argparse
import json
from pathlib import Path

from findsl.official.external import ExternalCatalog
from findsl.official.external.matching import canonical_scope_name
from findsl.official.external.providers import EastmoneyBoardProvider
from findsl.official.external.sync import build_eastmoney_snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--trust-environment-proxy", action="store_true")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    target_payload = json.loads(Path(args.targets).read_text(encoding="utf-8"))
    targets = [item["name"] for item in target_payload["targets"]]
    aliases = {
        canonical_scope_name(key): value
        for key, value in target_payload.get("aliases", {}).items()
    }
    provider = EastmoneyBoardProvider(
        trust_environment_proxy=args.trust_environment_proxy
    )
    result = build_eastmoney_snapshot(
        targets,
        provider=provider,
        aliases=aliases,
        as_of_date=args.as_of_date,
    )
    catalog = ExternalCatalog(Path(args.catalog))
    catalog.import_snapshot(result.snapshot, replace=args.replace)
    report = result.to_dict()
    report["catalog"] = str(Path(args.catalog).resolve())
    report["catalog_summary"] = catalog.summary()
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

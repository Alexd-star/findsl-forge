from __future__ import annotations

import argparse
import json
from pathlib import Path

from findsl.official.external import ExternalCatalog, ExternalSourceRegistry
from findsl.official.external.matching import canonical_scope_name
from findsl.official.external.providers import EastmoneyBoardProvider
from findsl.official.external.sync import (
    build_eastmoney_snapshot,
    build_full_eastmoney_snapshot,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--targets")
    mode.add_argument("--all-boards", action="store_true")
    parser.add_argument("--only-target", action="append", default=[])
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
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument(
        "--source-registry",
        default="configs/official/external_source_registry.json",
    )
    args = parser.parse_args()
    provider = EastmoneyBoardProvider(
        timeout_seconds=args.timeout_seconds,
        max_attempts=args.max_attempts,
        backoff_seconds=args.backoff_seconds,
        trust_environment_proxy=args.trust_environment_proxy,
        cache_dir=Path(args.cache_dir) if args.cache_dir else None,
        request_interval_seconds=args.request_interval_seconds,
    )
    source_registry = ExternalSourceRegistry.load(Path(args.source_registry))
    source_registry.assert_provider("eastmoney", provider)
    if args.all_boards:
        result = build_full_eastmoney_snapshot(
            provider=provider,
            as_of_date=args.as_of_date,
        )
    else:
        target_payload = json.loads(Path(args.targets).read_text(encoding="utf-8"))
        targets = [item["name"] for item in target_payload["targets"]]
        if args.only_target:
            requested = tuple(dict.fromkeys(str(item).strip() for item in args.only_target))
            unknown = sorted(set(requested) - set(targets))
            if unknown:
                raise ValueError(
                    f"requested targets are absent from the target manifest: {', '.join(unknown)}"
                )
            targets = list(requested)
        aliases = {
            canonical_scope_name(key): value
            for key, value in target_payload.get("aliases", {}).items()
        }
        result = build_eastmoney_snapshot(
            targets,
            provider=provider,
            aliases=aliases,
            as_of_date=args.as_of_date,
        )
    catalog = ExternalCatalog(Path(args.catalog))
    report = result.to_dict()
    report["catalog"] = str(Path(args.catalog).resolve())
    report["source_complete"] = not result.failed_boards
    report["target_coverage_complete"] = (
        not result.failed_boards and not result.unresolved
    )
    report["complete"] = report["target_coverage_complete"]
    report["imported"] = result.snapshot is not None and not (
        args.require_complete and not report["complete"]
    )
    if report["imported"]:
        assert result.snapshot is not None
        catalog.import_snapshot(result.snapshot, replace=args.replace)
        runtime = catalog.export_runtime_manifest(Path(args.runtime))
        report["runtime"] = {
            "path": str(Path(args.runtime).resolve()),
            "entries": len(runtime["entries"]),
            "membership_resource_id": runtime["membership_resource_id"],
        }
        report["catalog_summary"] = catalog.summary()
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["imported"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

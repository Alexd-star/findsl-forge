from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from findsl.official.external import ExternalCatalog, ExternalSourceRegistry
from findsl.official.external.profiles import DataProfileCatalog


def build_inventory(catalog, registry, profiles, *, git_head: str, catalog_sha256: str):
    snapshots = []
    totals = Counter()
    by_source = Counter()
    for item in catalog.snapshot_inventory():
        registered = registry.resolve_source(item["source"])
        counts = {
            "scope_memberships": int(item["scope_memberships"]),
            "industry_memberships": int(item["industry_memberships"]),
            "instrument_rules": int(item["instrument_rules"]),
        }
        totals.update(counts)
        by_source[item["source"]] += sum(counts.values())
        snapshots.append(
            {
                **item,
                "counts": counts,
                "authority_level": registered.authority_level,
                "temporal_model": registered.temporal_model,
                "redistribution": registered.redistribution,
                "enabled_profiles": list(registered.enabled_profiles),
            }
        )
        for key in ("scope_memberships", "industry_memberships", "instrument_rules"):
            snapshots[-1].pop(key)
    return {
        "schema_version": 1,
        "verified_source_head": git_head,
        "catalog_sha256": catalog_sha256,
        "summary": {
            "snapshot_count": len(snapshots),
            "registered_source_count": len(by_source),
            "all_snapshot_sources_registered": True,
            "counts": dict(sorted(totals.items())),
            "rows_by_source": dict(sorted(by_source.items())),
        },
        "data_profiles": [profile.__dict__ for profile in profiles.profiles()],
        "snapshots": snapshots,
    }


def render_markdown(inventory) -> str:
    summary = inventory["summary"]
    counts = summary["counts"]
    lines = [
        "# 外部补充数据清单与来源审计",
        "",
        f"- 已验证源码 HEAD：`{inventory['verified_source_head']}`",
        f"- 数据目录 SHA-256：`{inventory['catalog_sha256']}`",
        f"- 快照：`{summary['snapshot_count']}` 个",
        f"- 已登记来源：`{summary['registered_source_count']}` 个",
        f"- 范围成员：`{counts.get('scope_memberships', 0)}` 行",
        f"- 行业成员：`{counts.get('industry_memberships', 0)}` 行",
        f"- 交易规则：`{counts.get('instrument_rules', 0)}` 行",
        "",
        "## 运行模式",
        "",
        "| 模式 | 使用外部数据 | 离线可复现 | 说明 |",
        "|---|---|---|---|",
    ]
    for profile in inventory["data_profiles"]:
        lines.append(
            f"| `{profile['profile_id']}` | {profile['uses_external_data']} | "
            f"{profile['offline_reproducible']} | {profile['description']} |"
        )
    lines.extend(
        [
            "",
            "## 快照明细",
            "",
            "| 来源 | 日期 | 范围成员 | 行业成员 | 交易规则 | 时间模型 | 权威等级 | 再分发处理 |",
            "|---|---|---:|---:|---:|---|---|---|",
        ]
    )
    for item in inventory["snapshots"]:
        counts = item["counts"]
        lines.append(
            f"| `{item['source']}` | {item['as_of_date']} | "
            f"{counts['scope_memberships']} | {counts['industry_memberships']} | "
            f"{counts['instrument_rules']} | `{item['temporal_model']}` | "
            f"`{item['authority_level']}` | `{item['redistribution']}` |"
        )
    lines.extend(
        [
            "",
            "> `official_only` 不引用这些外部表，可以随官方数据包离线复现。`enriched_public` 的编译请求不会临时访问网络，但干净环境执行前必须按许可同步并装载对应快照；当前成员不得倒推为采集日前的历史成员。",
            "",
        ]
    )
    return "\n".join(lines)


def _git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument(
        "--source-registry",
        default="configs/official/external_source_registry.json",
    )
    parser.add_argument(
        "--data-profiles", default="configs/official/data_profiles.json"
    )
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()
    catalog_path = Path(args.catalog)
    inventory = build_inventory(
        ExternalCatalog(catalog_path),
        ExternalSourceRegistry.load(Path(args.source_registry)),
        DataProfileCatalog.load(Path(args.data_profiles)),
        git_head=_git_head(),
        catalog_sha256=hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
    )
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    output_md.write_text(render_markdown(inventory), encoding="utf-8")
    print(json.dumps(inventory["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

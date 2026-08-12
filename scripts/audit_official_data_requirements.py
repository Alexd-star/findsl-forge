from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from findsl.official.context import CompileContext
from findsl.official.service import OfficialCompilerService


def build_audit(funnel, service: OfficialCompilerService):
    statuses = Counter()
    domains = Counter()
    providers = Counter()
    examples = defaultdict(list)
    no_requirement = Counter()
    for row in funnel["rows"]:
        if row["new_backend_success"]:
            statuses["SUPPORTED"] += 1
            continue
        capability = service.negotiate(row["source"])["capability"]
        status = capability["status"]
        statuses[status] += 1
        requirements = capability["data_requirements"]
        if not requirements:
            no_requirement[status] += 1
        for requirement in requirements:
            domain_id = requirement["domain_id"]
            domains[(status, domain_id, requirement["profile"]["status"])] += 1
            if len(examples[domain_id]) < 5:
                examples[domain_id].append(
                    {
                        "excel_row": row["excel_row"],
                        "status": status,
                        "terminal_code": capability["code"],
                        "source": row["source"],
                    }
                )
            for provider in requirement["providers"]:
                providers[(domain_id, provider["provider_id"])] += 1
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "git_head": _git_head(),
        "profile_id": service.context.snapshot.profile_id,
        "source_sha256": funnel["source_sha256"],
        "row_count": funnel["row_count"],
        "status_counts": dict(sorted(statuses.items())),
        "data_domain_counts": [
            {
                "capability_status": status,
                "domain_id": domain_id,
                "profile_status": profile_status,
                "query_count": count,
            }
            for (status, domain_id, profile_status), count in sorted(domains.items())
        ],
        "provider_demand_counts": [
            {
                "domain_id": domain_id,
                "provider_id": provider_id,
                "query_count": count,
            }
            for (domain_id, provider_id), count in sorted(providers.items())
        ],
        "without_data_requirement": dict(sorted(no_requirement.items())),
        "examples": dict(sorted(examples.items())),
    }


def render_markdown(report):
    lines = [
        "# 官方语料数据域与能力需求审计",
        "",
        f"- Git HEAD：`{report['git_head']}`",
        f"- 数据配置：`{report['profile_id']}`",
        f"- 语料行数：`{report['row_count']}`",
        "",
        "## 能力分类",
        "",
        "| 分类 | 条数 |",
        "|---|---:|",
    ]
    lines.extend(
        f"| `{status}` | {count} |"
        for status, count in report["status_counts"].items()
    )
    lines.extend(
        [
            "",
            "## 数据域需求",
            "",
            "| 能力分类 | 数据域 | 当前状态 | 涉及问句 |",
            "|---|---|---|---:|",
        ]
    )
    lines.extend(
        f"| `{item['capability_status']}` | `{item['domain_id']}` | "
        f"`{item['profile_status']}` | {item['query_count']} |"
        for item in report["data_domain_counts"]
    )
    lines.extend(
        [
            "",
            "> 同一问句可能同时需要多个数据域，因此本表不能横向求和。"
            " `not_loaded` 表示已有明确契约但当前没有合规快照；"
            " `unsupported` 表示还缺业务定义或编译能力，不能靠下载数据解决。",
            "",
            "## 无数据域依赖的剩余能力",
            "",
        ]
    )
    for status, count in report["without_data_requirement"].items():
        lines.append(f"- `{status}`：{count} 条。")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--funnel", required=True, type=Path)
    parser.add_argument("--profile", default="enriched_public")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    args = parser.parse_args()
    context = CompileContext.load(data_profile=args.profile)
    report = build_audit(
        json.loads(args.funnel.read_text(encoding="utf-8")),
        OfficialCompilerService(context=context),
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.output_md.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["status_counts"], ensure_ascii=False, indent=2))


def _git_head():
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


if __name__ == "__main__":
    main()

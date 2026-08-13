from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from findsl.official.external.source_registry import ExternalSourceRegistry
from findsl.official.frontend.antlr_frontend import AntlrOfficialFrontend


SCOPE_SLOT_FUNCTIONS = {
    "indicator",
    "rank",
    "cross_above",
    "cross_down",
    "close_together",
    "reset",
    "golden_cross",
    "record_high",
    "record_low",
    "position",
    "belong_industry",
    "queryData",
}


def build_audit(funnel, targets, adjudications, source_registry, *, git_head: str):
    if targets["source_sha256"] != funnel["source_sha256"]:
        raise ValueError("target manifest and funnel use different official corpora")
    if adjudications["source_sha256"] != targets["source_sha256"]:
        raise ValueError("adjudications do not match the target manifest")
    target_counts = {item["name"]: int(item["occurrences"]) for item in targets["targets"]}
    decisions = {item["name"]: item for item in adjudications["entries"]}
    missing = sorted(set(target_counts) - set(decisions))
    extra = sorted(set(decisions) - set(target_counts))
    if missing or extra:
        raise ValueError(f"adjudication coverage mismatch: missing={missing}, extra={extra}")
    for item in decisions.values():
        for provider_id in item["candidate_sources"]:
            source_registry.resolve(provider_id)

    parser = AntlrOfficialFrontend()
    target_rows = defaultdict(list)
    row_audits = []
    for row in funnel["rows"]:
        if not (
            row["legacy_strict_success"]
            and not row["new_backend_success"]
            and row["terminal_code"] == "PHYSICAL_SCOPE_DATA_UNAVAILABLE"
        ):
            continue
        parsed = parser.parse(row["source"])
        atoms = tuple(dict.fromkeys(_scope_atoms(parsed.ast)))
        unresolved = tuple(atom for atom in atoms if atom in target_counts)
        if not unresolved:
            raise ValueError(f"migration gap row {row['excel_row']} has no audited target")
        for atom in unresolved:
            target_rows[atom].append(int(row["excel_row"]))
        row_audits.append(
            {
                "excel_row": int(row["excel_row"]),
                "source": row["source"],
                "unresolved_targets": list(unresolved),
                "decisions": sorted(
                    {decisions[atom]["competition_decision"] for atom in unresolved}
                ),
            }
        )

    category_counts = Counter()
    decision_counts = Counter()
    audited_targets = []
    for name, occurrences in target_counts.items():
        item = dict(decisions[name])
        item["occurrences"] = occurrences
        item["affected_excel_rows"] = sorted(set(target_rows[name]))
        category_counts[item["category"]] += 1
        decision_counts[item["competition_decision"]] += 1
        audited_targets.append(item)

    return {
        "schema_version": 1,
        "verified_source_head": git_head,
        "official_source_sha256": funnel["source_sha256"],
        "summary": {
            "migration_gap_rows": len(row_audits),
            "unresolved_targets": len(audited_targets),
            "unresolved_occurrences": sum(target_counts.values()),
            "categories": dict(sorted(category_counts.items())),
            "competition_decisions": dict(sorted(decision_counts.items())),
            "forced_fuzzy_mappings": 0,
        },
        "targets": audited_targets,
        "rows": sorted(row_audits, key=lambda item: item["excel_row"]),
    }


def render_markdown(audit) -> str:
    summary = audit["summary"]
    lines = [
        "# 官方语料数据缺口逐条审计",
        "",
        f"- 已验证源码 HEAD：`{audit['verified_source_head']}`",
        f"- 严格迁移缺口：`{summary['migration_gap_rows']}` 条问句",
        f"- 未解析范围词：`{summary['unresolved_targets']}` 个，累计 `{summary['unresolved_occurrences']}` 次",
        "- 强制模糊映射：`0`",
        "",
        "> 本报告把数据缺失、事件语义、域外资产、歧义名称和疑似错误分开。确定性拒绝不是编译成功，也不计入正确率，但能防止生成语义错误的 SQL。",
        "",
        "## 决策汇总",
        "",
        "| 决策 | 范围词数 |",
        "|---|---:|",
    ]
    for decision, count in summary["competition_decisions"].items():
        lines.append(f"| `{decision}` | {count} |")
    lines.extend(
        [
            "",
            "## 逐项裁决",
            "",
            "| 范围词 | 出现次数 | 分类 | 竞赛处理 | 涉及Excel行 | 原因与下一步 |",
            "|---|---:|---|---|---|---|",
        ]
    )
    for item in audit["targets"]:
        rows = ", ".join(str(value) for value in item["affected_excel_rows"])
        detail = f"{item['reason']} {item['next_action']}".replace("|", "\\|")
        lines.append(
            f"| {item['name']} | {item['occurrences']} | `{item['category']}` | "
            f"`{item['competition_decision']}` | {rows} | {detail} |"
        )
    lines.extend(
        [
            "",
            "## 使用规则",
            "",
            "1. `pending_external_dataset` 只有取得完整成员、时间版本和来源许可后才能转为已解决。",
            "2. `implement_derived_rule` 应实现为行情或事件算子，禁止写入静态成员表。",
            "3. `optional_domain_extension` 属于基金、港股等额外资产域，不影响官方A股基线。",
            "4. `reject_ambiguous` 和 `reject_invalid` 保持确定性拒绝，不使用字符串相似度猜测。",
            "",
        ]
    )
    return "\n".join(lines)


def _scope_atoms(node):
    if node.__class__.__name__ == "OfficialFunctionCall" and node.name in SCOPE_SLOT_FUNCTIONS:
        value = getattr(node.args[1], "value", "") if len(node.args) > 1 else ""
        atom = ""
        for character in str(value or "") + "|":
            if character in "|&^":
                if atom.strip():
                    yield atom.strip()
                atom = ""
            else:
                atom += character
    for attribute in ("left", "right", "expr"):
        child = getattr(node, attribute, None)
        if child is not None:
            yield from _scope_atoms(child)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--funnel", required=True)
    parser.add_argument(
        "--targets", default="configs/official/scope_gap_targets.json"
    )
    parser.add_argument(
        "--adjudications",
        default="configs/official/scope_gap_adjudications.json",
    )
    parser.add_argument(
        "--source-registry",
        default="configs/official/external_source_registry.json",
    )
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()
    paths = {
        "funnel": Path(args.funnel),
        "targets": Path(args.targets),
        "adjudications": Path(args.adjudications),
        "source_registry": Path(args.source_registry),
    }
    audit = build_audit(
        _load(paths["funnel"]),
        _load(paths["targets"]),
        _load(paths["adjudications"]),
        ExternalSourceRegistry.load(paths["source_registry"]),
        git_head=_git_head(),
    )
    audit["input_sha256"] = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in paths.items()
    }
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    output_md.write_text(render_markdown(audit), encoding="utf-8")
    print(json.dumps(audit["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

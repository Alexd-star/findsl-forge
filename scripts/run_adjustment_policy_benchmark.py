from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from findsl.official.adjustment import (
    AdjustmentPolicy,
    adjusted_price,
    load_adjustment_fixture,
    render_adjustment_fixture_sql,
)
from findsl.official.backend.executor import DorisExecutionConfig, execute_doris_query


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the nontrivial price-adjustment policy benchmark")
    parser.add_argument("--policy", type=Path, default=Path("configs/official/adjustment_validation_policy.json"))
    parser.add_argument("--fixture", type=Path, default=Path("data/official_correctness/adjustment_policy_fixture.json"))
    parser.add_argument("--json-output", type=Path, default=Path("reports/adjustment_policy_doris.json"))
    parser.add_argument("--report-output", type=Path, default=Path("reports/adjustment_policy_doris.md"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password-env", default="DORIS_PASSWORD")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--client", default="mysql")
    args = parser.parse_args()
    policy = AdjustmentPolicy.load(args.policy)
    fixture = load_adjustment_fixture(args.fixture)
    sql = render_adjustment_fixture_sql(policy, fixture)
    result = execute_doris_query(
        DorisExecutionConfig(
            args.host, args.port, args.user, os.getenv(args.password_env, ""), args.database, args.client
        ),
        sql,
    )
    actual = {row[0]: Decimal(row[1]) for row in result.rows}
    cases = []
    for item in fixture:
        expected = adjusted_price(
            policy,
            asset_class=str(item["asset_class"]),
            raw_price=Decimal(str(item["raw_price"])),
            multiplier=Decimal(str(item["multiplier"])),
            additive=Decimal(str(item["additive"])),
        )
        declared = Decimal(str(item["expected"]))
        matched = expected == declared == actual.get(str(item["case_id"]))
        cases.append({
            "case_id": item["case_id"],
            "asset_class": item["asset_class"],
            "raw_price": str(item["raw_price"]),
            "multiplier": str(item["multiplier"]),
            "additive": str(item["additive"]),
            "expected": str(expected),
            "doris_actual": str(actual.get(str(item["case_id"]))),
            "matched": matched,
        })
    passed = len(result.rows) == len(fixture) and all(item["matched"] for item in cases)
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "git_head": _git_head(),
        "policy_id": policy.policy_id,
        "policy_sha256": _sha256(args.policy),
        "fixture_sha256": _sha256(args.fixture),
        "official_data_policy_unchanged": "official-semantic-policy-v1 remains official_raw_price because official factors are not auditable/nontrivial",
        "status": "PASS" if passed else "FAIL",
        "matched": sum(1 for item in cases if item["matched"]),
        "total": len(cases),
        "execute_ms": result.elapsed_ms,
        "cases": cases,
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 非平凡复权策略 Doris 基准",
        "",
        f"- 状态：`{report['status']}`",
        f"- 策略：`{policy.policy_id}`",
        f"- 完整匹配：`{report['matched']}/{report['total']}`",
        "- 官方数据口径：继续使用原始价；本基准只验证接入有效复权因子后的配置行为，不冒充官方数据效果。",
        "",
        "| Case | 资产 | 原始价 | 乘数 | 加数 | 期望 | Doris | 匹配 |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in cases:
        lines.append(
            f"| {item['case_id']} | {item['asset_class']} | {item['raw_price']} | {item['multiplier']} | "
            f"{item['additive']} | {item['expected']} | {item['doris_actual']} | {'PASS' if item['matched'] else 'FAIL'} |"
        )
    args.report_output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"status={report['status']} matched={report['matched']}/{report['total']}")
    return 0 if passed else 2


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _git_head() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from findsl.doris_profile import explain_partition_ratios, parse_profile_summary


BASELINE_SQL = """
SELECT w.mktcode,w.tgtcode,w.bizdate
FROM (
  SELECT
    base.mktcode,
    base.tgtcode,
    base.bizdate,
    SUM(base.volume) OVER (
      PARTITION BY base.mktcode,base.tgtcode
      ORDER BY base.bizdate
      ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
    ) AS volume_sum_20
  FROM newzl.hsj_stock_hq_basic AS base
) AS w
WHERE w.bizdate = DATE '2026-04-14'
  AND w.volume_sum_20 > 10000000
ORDER BY w.mktcode,w.tgtcode,w.bizdate
""".strip()


OPTIMIZED_SQL = """
SELECT p.mktcode,p.tgtcode,p.bizdate
FROM newzl.hsj_stock_hq_basic_rollup AS p
WHERE p.bizdate = DATE '2026-04-14'
  AND p.volume_sum_20 > 10000000
ORDER BY p.mktcode,p.tgtcode,p.bizdate
""".strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--http-port", type=int, default=8030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="")
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--min-speedup", type=float, default=10.0)
    parser.add_argument("--expected-rows", type=int, default=13650347)
    parser.add_argument("--json-output", required=True)
    parser.add_argument("--report-output", required=True)
    args = parser.parse_args()

    if args.warmups < 0 or args.repeats < 3:
        raise ValueError("warmups must be non-negative and repeats must be at least 3")
    mysql = shutil.which("mysql")
    if not mysql:
        raise RuntimeError("mysql client is unavailable")

    context = {"args": args, "mysql": mysql}
    table_evidence = _table_evidence(context)
    if table_evidence["base_rows"] != args.expected_rows:
        raise RuntimeError("official base row count does not match the evidence contract")
    if table_evidence["rollup_rows"] != args.expected_rows:
        raise RuntimeError("partitioned rollup row count does not match the base table")

    explains = {
        "baseline": _mysql(context, "EXPLAIN " + BASELINE_SQL),
        "optimized": _mysql(context, "EXPLAIN " + OPTIMIZED_SQL),
    }
    partition_ratios = {
        name: explain_partition_ratios(value) for name, value in explains.items()
    }
    if not partition_ratios["optimized"] or not any(
        selected == 1 and total > 1
        for selected, total in partition_ratios["optimized"]
    ):
        raise RuntimeError("optimized EXPLAIN does not prove single-partition pruning")

    profile_dir = Path(args.json_output).parent / "phase42_query_profiles"
    profile_dir.mkdir(parents=True, exist_ok=True)
    for index in range(args.warmups):
        _profiled_query(context, BASELINE_SQL, profile_dir / f"warmup_baseline_{index + 1}.txt")
        _profiled_query(context, OPTIMIZED_SQL, profile_dir / f"warmup_optimized_{index + 1}.txt")

    results = {"baseline": [], "optimized": []}
    canonical_hashes = {"baseline": set(), "optimized": set()}
    row_counts = {"baseline": set(), "optimized": set()}
    for index in range(args.repeats):
        order = ("baseline", "optimized") if index % 2 == 0 else ("optimized", "baseline")
        for name in order:
            sql = BASELINE_SQL if name == "baseline" else OPTIMIZED_SQL
            evidence = _profiled_query(
                context,
                sql,
                profile_dir / f"{name}_{index + 1}.txt",
            )
            results[name].append(evidence)
            canonical_hashes[name].add(evidence["sha256"])
            row_counts[name].add(evidence["row_count"])

    if any(len(values) != 1 for values in canonical_hashes.values()):
        raise RuntimeError("a query variant produced unstable complete-result hashes")
    if any(len(values) != 1 for values in row_counts.values()):
        raise RuntimeError("a query variant produced unstable row counts")
    baseline_hash = next(iter(canonical_hashes["baseline"]))
    optimized_hash = next(iter(canonical_hashes["optimized"]))
    if baseline_hash != optimized_hash:
        raise RuntimeError("baseline and optimized complete-result hashes differ")

    summaries = {
        name: _timing_summary(items) for name, items in results.items()
    }
    speedup = summaries["baseline"]["median_ms"] / summaries["optimized"]["median_ms"]
    passed = speedup >= args.min_speedup
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_head": _git_head(),
        "status": "PASS" if passed else "FAIL",
        "target_speedup": args.min_speedup,
        "speedup": round(speedup, 6),
        "target_met": passed,
        "warmups": args.warmups,
        "repeats": args.repeats,
        "table_evidence": table_evidence,
        "row_count_match": True,
        "complete_result_hash_match": True,
        "result_row_count": next(iter(row_counts["baseline"])),
        "result_sha256": baseline_hash,
        "partition_ratios": {
            key: [list(item) for item in value]
            for key, value in partition_ratios.items()
        },
        "baseline": {
            "sql": BASELINE_SQL,
            "explain": explains["baseline"],
            **summaries["baseline"],
            "runs": results["baseline"],
        },
        "optimized": {
            "sql": OPTIMIZED_SQL,
            "explain": explains["optimized"],
            **summaries["optimized"],
            "runs": results["optimized"],
        },
        "measurement_policy": {
            "clock": "Doris Query Profile Summary.Total",
            "query_cache": "disabled and verified as uncached in every profile",
            "ordering": "alternating baseline/optimized order",
            "correctness": "complete ordered result SHA-256",
            "plan_check": "EXPLAIN partition ratios",
        },
    }
    json_path = Path(args.json_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report_path = Path(args.report_output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_markdown(payload), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not passed:
        raise SystemExit(2)


def _table_evidence(context):
    output = _mysql(
        context,
        """
SELECT COUNT(*),MIN(bizdate),MAX(bizdate) FROM newzl.hsj_stock_hq_basic;
SELECT COUNT(*),MIN(bizdate),MAX(bizdate) FROM newzl.hsj_stock_hq_basic_rollup;
SELECT COUNT(*) FROM information_schema.partitions
WHERE table_schema='newzl' AND table_name='hsj_stock_hq_basic_rollup';
SELECT @@version_comment;
""".strip(),
    ).splitlines()
    if len(output) != 4:
        raise RuntimeError(f"unexpected table evidence shape: {output}")
    base = output[0].split("\t")
    rollup = output[1].split("\t")
    return {
        "base_rows": int(base[0]),
        "base_first_date": base[1],
        "base_last_date": base[2],
        "rollup_rows": int(rollup[0]),
        "rollup_first_date": rollup[1],
        "rollup_last_date": rollup[2],
        "rollup_partition_count": int(output[2]),
        "doris_version": output[3],
    }


def _profiled_query(context, sql, profile_path: Path):
    output = _mysql(
        context,
        "\n".join(
            (
                "SET enable_profile=true;",
                "SET profile_level=2;",
                "SET enable_sql_cache=false;",
                sql.rstrip(";") + ";",
                "SELECT LAST_QUERY_ID();",
            )
        ),
    ).splitlines()
    if not output or not re.fullmatch(r"[0-9a-f]+-[0-9a-f]+", output[-1]):
        raise RuntimeError("profiled query did not return a Doris query id")
    query_id = output[-1]
    rows = output[:-1]
    canonical = "\n".join(rows).encode("utf-8")
    profile = _fetch_profile(context, query_id)
    summary = parse_profile_summary(profile)
    if summary.task_state != "OK" or summary.is_cached:
        raise RuntimeError(
            f"invalid profile state for {query_id}: {summary.task_state}, cached={summary.is_cached}"
        )
    profile_path.write_text(profile, encoding="utf-8")
    return {
        "query_id": query_id,
        "total_ms": round(summary.total_ms, 6),
        "total_text": summary.total_text,
        "row_count": len(rows),
        "sha256": hashlib.sha256(canonical).hexdigest(),
        "is_cached": summary.is_cached,
        "task_state": summary.task_state,
        "profile_path": str(profile_path),
    }


def _fetch_profile(context, query_id: str) -> str:
    args = context["args"]
    url = (
        f"http://{args.host}:{args.http_port}"
        f"/rest/v2/manager/query/profile/text/{query_id}"
    )
    token = base64.b64encode(f"{args.user}:{args.password}".encode()).decode()
    request = urllib.request.Request(url, headers={"Authorization": f"Basic {token}"})
    last_error = None
    for _ in range(20):
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
            profile = payload.get("data", {}).get("profile", "")
            if profile:
                return profile
        except Exception as exc:
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"Doris profile is unavailable for {query_id}: {last_error}")


def _mysql(context, sql: str) -> str:
    args = context["args"]
    command = [
        context["mysql"],
        "-h",
        args.host,
        "-P",
        str(args.port),
        "-u",
        args.user,
        "--batch",
        "--raw",
        "--skip-column-names",
        "-e",
        sql,
    ]
    environment = os.environ.copy()
    if args.password:
        environment["MYSQL_PWD"] = args.password
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout.strip()


def _timing_summary(runs):
    values = [float(item["total_ms"]) for item in runs]
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, max(0, int(len(ordered) * 0.95 + 0.999999) - 1))
    return {
        "median_ms": round(statistics.median(values), 6),
        "p95_ms": round(ordered[p95_index], 6),
        "min_ms": round(min(values), 6),
        "max_ms": round(max(values), 6),
    }


def _git_head():
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _markdown(payload):
    base = payload["baseline"]
    optimized = payload["optimized"]
    tables = payload["table_evidence"]
    return "\n".join(
        (
            "# Phase 42 官方 20 年数据长周期加速证据",
            "",
            f"- 状态：`{payload['status']}`",
            f"- Git HEAD：`{payload['git_head']}`",
            f"- 官方基础行情：`{tables['base_rows']}` 行，`{tables['base_first_date']}` 至 `{tables['base_last_date']}`",
            f"- 月分区滚动特征表：`{tables['rollup_rows']}` 行，`{tables['rollup_partition_count']}` 个分区",
            f"- 完整结果集：`{payload['result_row_count']}` 行，SHA-256 一致 `{payload['complete_result_hash_match']}`",
            f"- 基线中位耗时：`{base['median_ms']}` ms",
            f"- 优化中位耗时：`{optimized['median_ms']}` ms",
            f"- 实测加速：`{payload['speedup']:.3f}x`，目标 `>={payload['target_speedup']:.1f}x`",
            "",
            "## 测量口径",
            "",
            "耗时取自 Doris Query Profile 的 `Summary.Total`，每次查询均关闭 SQL Cache，并在 Profile 中反向确认 `Is Cached: No`。基线与优化查询交替执行，避免固定先后顺序造成系统偏差。正确性使用完整、有序结果集 SHA-256，而非只比较行数。",
            "",
            "## 计划证据",
            "",
            f"- 基线分区比：`{payload['partition_ratios']['baseline']}`",
            f"- 优化分区比：`{payload['partition_ratios']['optimized']}`",
            "- 优化查询命中交易月单分区；基线必须扫描全量 20 年行情并执行排序与窗口聚合。",
            "",
            "## 基线 SQL",
            "",
            "```sql",
            base["sql"],
            "```",
            "",
            "## 优化 SQL",
            "",
            "```sql",
            optimized["sql"],
            "```",
            "",
        )
    )


if __name__ == "__main__":
    main()

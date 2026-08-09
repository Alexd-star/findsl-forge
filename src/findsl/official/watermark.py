from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Mapping

from .backend.executor import DorisExecutionConfig, DorisExecutionResult, execute_doris_query


REQUIRED_WATERMARK_RESOURCES = (
    "official_basic",
    "official_technical",
    "official_basic_prefix",
    "official_ext_prefix",
    "official_basic_rollup",
)


class OfficialWatermarkError(ValueError):
    pass


@dataclass(frozen=True)
class ResourceWatermark:
    resource_id: str
    table: str
    row_count: int
    distinct_dates: int
    min_date: str
    max_date: str
    expected_row_count: int
    expected_distinct_dates: int
    expected_min_date: str
    expected_max_date: str
    matched_statistics: bool


def collect_official_watermarks(
    *,
    statistics_path: Path,
    catalog_path: Path,
    doris: DorisExecutionConfig,
    executor: Callable[[DorisExecutionConfig, str], DorisExecutionResult] = execute_doris_query,
) -> Dict[str, Any]:
    statistics = _read_json(statistics_path)
    catalog = _read_json(catalog_path)
    expected = {item["resource_id"]: item for item in statistics.get("resources", [])}
    resources = {item["resource_id"]: item for item in catalog.get("resources", [])}
    missing = [
        resource_id
        for resource_id in REQUIRED_WATERMARK_RESOURCES
        if resource_id not in expected or resource_id not in resources
    ]
    if missing:
        raise OfficialWatermarkError(f"watermark resources are not configured: {missing}")

    observed = []
    for resource_id in REQUIRED_WATERMARK_RESOURCES:
        resource = resources[resource_id]
        expected_item = expected[resource_id]
        table = f"`{resource['database']}`.`{resource['table']}`"
        result = executor(
            doris,
            f"SELECT COUNT(*),COUNT(DISTINCT bizdate),MIN(bizdate),MAX(bizdate) FROM {table}",
        )
        if len(result.rows) != 1 or len(result.rows[0]) != 4:
            raise OfficialWatermarkError(f"unexpected watermark result for {resource_id}")
        row = result.rows[0]
        item = ResourceWatermark(
            resource_id=resource_id,
            table=f"{resource['database']}.{resource['table']}",
            row_count=int(row[0]),
            distinct_dates=int(row[1]),
            min_date=str(row[2]),
            max_date=str(row[3]),
            expected_row_count=int(expected_item["row_count"]),
            expected_distinct_dates=int(expected_item["partition_value_count"]),
            expected_min_date=str(expected_item["partition_min"]),
            expected_max_date=str(expected_item["partition_max"]),
            matched_statistics=(
                int(row[0]) == int(expected_item["row_count"])
                and int(row[1]) == int(expected_item["partition_value_count"])
                and str(row[2]) == str(expected_item["partition_min"])
                and str(row[3]) == str(expected_item["partition_max"])
            ),
        )
        observed.append(item)

    signatures = {
        (item.row_count, item.distinct_dates, item.min_date, item.max_date)
        for item in observed
    }
    coherent = len(signatures) == 1
    passed = coherent and all(item.matched_statistics for item in observed)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "git_head": _git_head(),
        "statistics_collected_at": statistics.get("collected_at"),
        "statistics_catalog_sha256": statistics.get("catalog_sha256"),
        "resources": [asdict(item) for item in observed],
        "cross_resource_watermark_coherent": coherent,
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
    }


def assert_official_watermarks(report: Mapping[str, Any]) -> None:
    if not report.get("passed"):
        failed = [
            item.get("resource_id")
            for item in report.get("resources", [])
            if not item.get("matched_statistics")
        ]
        raise OfficialWatermarkError(
            "official Doris watermark gate failed; "
            f"statistics_mismatch={failed}, coherent={report.get('cross_resource_watermark_coherent')}"
        )


def write_official_watermark_report(
    report: Mapping[str, Any], json_path: Path, markdown_path: Path
) -> None:
    Path(json_path).parent.mkdir(parents=True, exist_ok=True)
    Path(markdown_path).parent.mkdir(parents=True, exist_ok=True)
    Path(json_path).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# 官方 Doris 数据水位门禁",
        "",
        f"- 状态：`{report.get('status')}`",
        f"- Git HEAD：`{report.get('git_head')}`",
        f"- 各物化路径水位一致：`{report.get('cross_resource_watermark_coherent')}`",
        f"- 统计快照时间：`{report.get('statistics_collected_at')}`",
        "",
        "| 资源 | 表 | 行数 | 交易日数 | 最早日期 | 最新日期 | 冻结统计一致 |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for item in report.get("resources", []):
        lines.append(
            f"| {item['resource_id']} | {item['table']} | {item['row_count']} | "
            f"{item['distinct_dates']} | {item['min_date']} | {item['max_date']} | "
            f"{'PASS' if item['matched_statistics'] else 'FAIL'} |"
        )
    Path(markdown_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OfficialWatermarkError(f"cannot read {path}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise OfficialWatermarkError(f"{path} must contain a JSON object")
    return payload


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"

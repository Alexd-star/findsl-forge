from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping

from findsl.versioning import resolve_release_head


class PerformanceEvidenceError(ValueError):
    pass


_REQUIRED_METRIC_FIELDS = {
    "metric_id",
    "workload",
    "dataset",
    "source",
    "value_path",
    "unit",
    "comparator",
    "threshold",
    "score_gate",
    "claim",
}
_REQUIRED_SCORE_GATES = {
    "official_long_horizon_min_speedup",
    "official_full_matrix_max_p95",
    "official_compile_p95",
}
_COMPARATORS = {
    "gt": lambda value, threshold: value > threshold,
    "gte": lambda value, threshold: value >= threshold,
    "lt": lambda value, threshold: value < threshold,
    "lte": lambda value, threshold: value <= threshold,
}


def validate_performance_evidence_registry(
    registry_path: Path, *, root: Path = Path(".")
) -> Dict[str, Any]:
    registry = _read_json(registry_path)
    expected = {"schema_version", "registry_id", "metrics"}
    if set(registry) != expected or registry["schema_version"] != 2:
        raise PerformanceEvidenceError("invalid performance evidence registry")
    metrics = registry["metrics"]
    if not isinstance(metrics, list) or len(metrics) < 5:
        raise PerformanceEvidenceError("performance evidence registry is incomplete")
    ids = [str(item.get("metric_id")) for item in metrics]
    if len(ids) != len(set(ids)):
        raise PerformanceEvidenceError("duplicate performance metric_id")
    for item in metrics:
        if not isinstance(item, Mapping) or set(item) != _REQUIRED_METRIC_FIELDS:
            raise PerformanceEvidenceError("invalid performance metric contract")
        if not isinstance(item["score_gate"], bool) or not str(item["unit"]).strip():
            raise PerformanceEvidenceError("invalid performance metric gate or unit")
    score_gate_ids = {
        str(item.get("metric_id")) for item in metrics if item.get("score_gate")
    }
    if score_gate_ids != _REQUIRED_SCORE_GATES:
        raise PerformanceEvidenceError(
            "performance score gates must cover long-horizon speedup, execution P95, and compile P95"
        )

    packaging_head = _git_head()
    results = []
    for item in metrics:
        comparator_name = str(item.get("comparator"))
        comparator = _COMPARATORS.get(comparator_name)
        if comparator is None:
            raise PerformanceEvidenceError(f"unsupported comparator: {comparator_name}")
        source_path = (Path(root) / str(item["source"])).resolve()
        source = _read_json(source_path)
        actual = float(_resolve_path(source, str(item["value_path"])))
        threshold = float(item["threshold"])
        evidence_head = _evidence_head(source)
        threshold_met = bool(comparator(actual, threshold))
        source_head_matches = evidence_head == packaging_head
        results.append(
            {
                **item,
                "value": actual,
                "source_value": actual,
                "threshold_met": threshold_met,
                "evidence_git_head": evidence_head,
                "source_head_matches_packaging": source_head_matches,
                "source_value_matched": threshold_met and source_head_matches,
            }
        )
    passed = all(item["source_value_matched"] for item in results)
    return {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "registry_id": registry["registry_id"],
        "packaging_git_head": packaging_head,
        "all_source_heads_match_packaging": all(
            item["source_head_matches_packaging"] for item in results
        ),
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "metrics": results,
    }


def write_performance_evidence_report(
    report: Mapping[str, Any], json_path: Path, markdown_path: Path
) -> None:
    Path(json_path).parent.mkdir(parents=True, exist_ok=True)
    Path(markdown_path).parent.mkdir(parents=True, exist_ok=True)
    Path(json_path).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# 性能证据口径注册表",
        "",
        f"- 校验状态：`{report.get('status')}`",
        f"- 当前打包 HEAD：`{report.get('packaging_git_head')}`",
        f"- 全部证据源与当前 HEAD 一致：`{report.get('all_source_heads_match_packaging')}`",
        "- 每项指标绑定独立工作负载、单位、比较符和阈值；不同实验结果不得互相替代。",
        "",
        "| 指标 | 工作负载 | 实测值 | 门槛 | 赛题门禁 | HEAD一致 | 结论 | 可证明范围 |",
        "|---|---|---:|---:|---|---|---|---|",
    ]
    for item in report.get("metrics", []):
        unit = item["unit"]
        lines.append(
            f"| {item['metric_id']} | {item['workload']} | {item['value']:.6f}{unit} | "
            f"`{item['comparator']} {item['threshold']}{unit}` | "
            f"{'是' if item['score_gate'] else '否'} | "
            f"{'PASS' if item['source_head_matches_packaging'] else 'FAIL'} | "
            f"{'PASS' if item['source_value_matched'] else 'FAIL'} | {item['claim']} |"
        )
    Path(markdown_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _evidence_head(source: Mapping[str, Any]) -> str:
    return str(
        source.get("git_head")
        or source.get("verified_source_head")
        or (source.get("summary") or {}).get("git_head")
        or ""
    )


def _resolve_path(payload: Mapping[str, Any], path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            raise PerformanceEvidenceError(f"missing evidence value path: {path}")
        value = value[part]
    return value


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PerformanceEvidenceError(f"cannot read evidence {path}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise PerformanceEvidenceError(f"evidence {path} must be an object")
    return value


def _git_head() -> str:
    return resolve_release_head()

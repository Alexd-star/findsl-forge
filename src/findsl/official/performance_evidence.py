from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping


class PerformanceEvidenceError(ValueError):
    pass


def validate_performance_evidence_registry(
    registry_path: Path, *, root: Path = Path(".")
) -> Dict[str, Any]:
    registry = _read_json(registry_path)
    expected = {"schema_version", "registry_id", "metrics"}
    if set(registry) != expected or registry["schema_version"] != 1:
        raise PerformanceEvidenceError("invalid performance evidence registry")
    metrics = registry["metrics"]
    if not isinstance(metrics, list) or len(metrics) < 5:
        raise PerformanceEvidenceError("performance evidence registry is incomplete")
    ids = [str(item.get("metric_id")) for item in metrics]
    if len(ids) != len(set(ids)):
        raise PerformanceEvidenceError("duplicate performance metric_id")
    score_gates = [item for item in metrics if item.get("score_gate")]
    if [item.get("metric_id") for item in score_gates] != ["official_long_horizon_gate"]:
        raise PerformanceEvidenceError("only the official long-horizon workload may be the speedup score gate")

    results = []
    for item in metrics:
        source_path = (Path(root) / str(item["source"])).resolve()
        source = _read_json(source_path)
        actual = _resolve_path(source, str(item["value_path"]))
        speedup = float(actual)
        matched = speedup > 0 and (not item.get("score_gate") or speedup >= 10.0)
        results.append(
            {
                **item,
                "speedup": speedup,
                "source_value": speedup,
                "source_value_matched": matched,
                "evidence_git_head": source.get("git_head") or (source.get("summary") or {}).get("git_head"),
            }
        )
    passed = all(item["source_value_matched"] for item in results)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "registry_id": registry["registry_id"],
        "packaging_git_head": _git_head(),
        "verified_source_heads_are_historical": True,
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "metrics": results,
    }


def write_performance_evidence_report(
    report: Mapping[str, Any], json_path: Path, markdown_path: Path
) -> None:
    Path(json_path).parent.mkdir(parents=True, exist_ok=True)
    Path(markdown_path).parent.mkdir(parents=True, exist_ok=True)
    Path(json_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 性能证据口径注册表",
        "",
        f"- 校验状态：`{report.get('status')}`",
        f"- 当前打包 HEAD：`{report.get('packaging_git_head')}`",
        "- 证据源 HEAD 是各实验执行时的已验证版本；打包 HEAD 表示本报告生成版本，两者不可混写。",
        "",
        "| 指标 | 工作负载 | 加速比 | 赛题门禁 | 源值一致 | 可证明范围 |",
        "|---|---|---:|---|---|---|",
    ]
    for item in report.get("metrics", []):
        lines.append(
            f"| {item['metric_id']} | {item['workload']} | {item['speedup']:.6f}x | "
            f"{'是' if item['score_gate'] else '否'} | {'PASS' if item['source_value_matched'] else 'FAIL'} | {item['claim']} |"
        )
    Path(markdown_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


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
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple


class EvidenceContractError(ValueError):
    """Raised when an evidence contract or evidence package is invalid."""


@dataclass(frozen=True)
class MetricContract:
    metric_id: str
    metric_type: str
    numerator_path: Optional[str]
    denominator_path: Optional[str]
    value_path: Optional[str]
    denominator_set: str
    proves: str
    does_not_prove: str
    required: bool


@dataclass(frozen=True)
class DatasetContract:
    dataset_id: str
    fingerprint_path: str
    required: bool


@dataclass(frozen=True)
class EvidenceContract:
    contract_id: str
    schema_version: int
    required_git_paths: Tuple[str, ...]
    datasets: Tuple[DatasetContract, ...]
    metrics: Tuple[MetricContract, ...]

    @classmethod
    def load(cls, path: Path) -> "EvidenceContract":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "EvidenceContract":
        expected = {
            "schema_version",
            "contract_id",
            "required_git_paths",
            "datasets",
            "metrics",
        }
        if set(raw) != expected:
            raise EvidenceContractError(
                f"evidence contract root fields must be {sorted(expected)}"
            )
        if raw["schema_version"] != 1:
            raise EvidenceContractError("unsupported evidence contract schema version")
        contract_id = _non_empty(raw["contract_id"], "contract_id")
        git_paths = _string_tuple(raw["required_git_paths"], "required_git_paths")
        if not git_paths:
            raise EvidenceContractError("required_git_paths cannot be empty")

        datasets = tuple(_dataset(item, index) for index, item in enumerate(raw["datasets"]))
        metrics = tuple(_metric(item, index) for index, item in enumerate(raw["metrics"]))
        _ensure_unique((item.dataset_id for item in datasets), "dataset_id")
        _ensure_unique((item.metric_id for item in metrics), "metric_id")
        return cls(contract_id, 1, git_paths, datasets, metrics)


def audit_evidence_metadata(
    metadata: Mapping[str, Any],
    contract: EvidenceContract,
    *,
    expected_git_head: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate provenance and metric semantics without changing the evidence."""
    errors = []
    warnings = []
    observed_heads: Dict[str, Optional[str]] = {}

    for path in contract.required_git_paths:
        value = _path_value(metadata, path)
        head = str(value).strip() if value not in (None, "") else None
        observed_heads[path] = head
        if head is None:
            errors.append(f"missing required Git HEAD: {path}")

    target_head = str(expected_git_head or "").strip() or next(
        (head for head in observed_heads.values() if head), None
    )
    if target_head:
        for path, head in observed_heads.items():
            if head and not _same_commit(head, target_head):
                errors.append(
                    f"mixed Git HEAD at {path}: observed {head}, expected {target_head}"
                )
    else:
        errors.append("no authoritative Git HEAD is available")

    dataset_results: Dict[str, Dict[str, Any]] = {}
    for item in contract.datasets:
        value = _path_value(metadata, item.fingerprint_path)
        present = value not in (None, "", {}, [])
        dataset_results[item.dataset_id] = {
            "fingerprint_path": item.fingerprint_path,
            "fingerprint": value,
            "present": present,
            "required": item.required,
        }
        if item.required and not present:
            errors.append(
                f"missing required dataset fingerprint: {item.dataset_id} "
                f"({item.fingerprint_path})"
            )

    metric_results: Dict[str, Dict[str, Any]] = {}
    for item in contract.metrics:
        result = _audit_metric(metadata, item)
        metric_results[item.metric_id] = result
        if item.required and not result["available"]:
            errors.append(f"required metric is unavailable: {item.metric_id}")
        if result.get("error"):
            errors.append(f"{item.metric_id}: {result['error']}")

    metric_types = {item.metric_id: item.metric_type for item in contract.metrics}
    migration_type = metric_types.get("legacy_migration_coverage")
    correctness_type = metric_types.get("sql_correctness")
    if migration_type == "correctness":
        errors.append("legacy migration coverage must not be typed as SQL correctness")
    if correctness_type and correctness_type != "correctness":
        errors.append("sql_correctness must use metric_type=correctness")
    if "sql_correctness" not in metric_types:
        warnings.append("formal SQL correctness metric is not declared")

    return {
        "schema_version": 1,
        "contract_id": contract.contract_id,
        "passed": not errors,
        "expected_git_head": target_head,
        "observed_git_heads": observed_heads,
        "datasets": dataset_results,
        "metrics": metric_results,
        "errors": errors,
        "warnings": warnings,
    }


def assert_evidence_contract(
    metadata: Mapping[str, Any],
    contract: EvidenceContract,
    *,
    expected_git_head: Optional[str] = None,
) -> Dict[str, Any]:
    audit = audit_evidence_metadata(
        metadata,
        contract,
        expected_git_head=expected_git_head,
    )
    if not audit["passed"]:
        raise EvidenceContractError("; ".join(audit["errors"]))
    return audit


def _audit_metric(metadata: Mapping[str, Any], item: MetricContract) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "metric_type": item.metric_type,
        "required": item.required,
        "denominator_set": item.denominator_set,
        "proves": item.proves,
        "does_not_prove": item.does_not_prove,
        "available": False,
    }
    if item.value_path:
        value = _path_value(metadata, item.value_path)
        result.update({"value_path": item.value_path, "value": value})
        result["available"] = value is not None
        return result

    numerator = _path_value(metadata, item.numerator_path or "")
    denominator = _path_value(metadata, item.denominator_path or "")
    result.update(
        {
            "numerator_path": item.numerator_path,
            "denominator_path": item.denominator_path,
            "numerator": numerator,
            "denominator": denominator,
        }
    )
    if numerator is None or denominator is None:
        return result
    if not isinstance(numerator, (int, float)) or not isinstance(denominator, (int, float)):
        result["error"] = "numerator and denominator must be numeric"
        return result
    if denominator <= 0:
        result["error"] = "denominator must be positive"
        return result
    if numerator < 0 or numerator > denominator:
        result["error"] = "numerator must be between zero and denominator"
        return result
    result["available"] = True
    result["ratio"] = numerator / denominator
    return result


def _dataset(raw: Any, index: int) -> DatasetContract:
    expected = {"dataset_id", "fingerprint_path", "required"}
    if not isinstance(raw, Mapping) or set(raw) != expected:
        raise EvidenceContractError(f"dataset {index} fields must be {sorted(expected)}")
    return DatasetContract(
        _non_empty(raw["dataset_id"], f"datasets[{index}].dataset_id"),
        _non_empty(raw["fingerprint_path"], f"datasets[{index}].fingerprint_path"),
        _strict_bool(raw["required"], f"datasets[{index}].required"),
    )


def _metric(raw: Any, index: int) -> MetricContract:
    expected = {
        "metric_id",
        "metric_type",
        "numerator_path",
        "denominator_path",
        "value_path",
        "denominator_set",
        "proves",
        "does_not_prove",
        "required",
    }
    if not isinstance(raw, Mapping) or set(raw) != expected:
        raise EvidenceContractError(f"metric {index} fields must be {sorted(expected)}")
    metric_type = _non_empty(raw["metric_type"], f"metrics[{index}].metric_type")
    if metric_type not in {"coverage", "migration", "correctness", "latency", "performance", "gate"}:
        raise EvidenceContractError(f"unsupported metric_type: {metric_type}")
    numerator = _optional_path(raw["numerator_path"], f"metrics[{index}].numerator_path")
    denominator = _optional_path(raw["denominator_path"], f"metrics[{index}].denominator_path")
    value_path = _optional_path(raw["value_path"], f"metrics[{index}].value_path")
    if bool(value_path) == bool(numerator or denominator):
        raise EvidenceContractError(
            f"metric {index} must declare either value_path or numerator/denominator"
        )
    if bool(numerator) != bool(denominator):
        raise EvidenceContractError(f"metric {index} requires both numerator and denominator")
    return MetricContract(
        _non_empty(raw["metric_id"], f"metrics[{index}].metric_id"),
        metric_type,
        numerator,
        denominator,
        value_path,
        _non_empty(raw["denominator_set"], f"metrics[{index}].denominator_set"),
        _non_empty(raw["proves"], f"metrics[{index}].proves"),
        _non_empty(raw["does_not_prove"], f"metrics[{index}].does_not_prove"),
        _strict_bool(raw["required"], f"metrics[{index}].required"),
    )


def _path_value(payload: Mapping[str, Any], path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        if not part or not isinstance(value, Mapping) or part not in value:
            return None
        value = value[part]
    return value


def _same_commit(left: str, right: str) -> bool:
    left = left.strip().lower()
    right = right.strip().lower()
    return len(left) >= 7 and len(right) >= 7 and (
        left.startswith(right) or right.startswith(left)
    )


def _non_empty(value: Any, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise EvidenceContractError(f"{label} cannot be empty")
    return text


def _optional_path(value: Any, label: str) -> Optional[str]:
    if value is None:
        return None
    return _non_empty(value, label)


def _strict_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise EvidenceContractError(f"{label} must be boolean")
    return value


def _string_tuple(value: Any, label: str) -> Tuple[str, ...]:
    if not isinstance(value, list):
        raise EvidenceContractError(f"{label} must be an array")
    return tuple(_non_empty(item, f"{label}[]") for item in value)


def _ensure_unique(values: Any, label: str) -> None:
    seen = set()
    for value in values:
        if value in seen:
            raise EvidenceContractError(f"duplicate {label}: {value}")
        seen.add(value)

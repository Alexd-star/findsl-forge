from __future__ import annotations

import json
import math
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Tuple

from .backend.executor import DorisExecutionConfig, DorisExecutionResult, execute_doris_query
from .context import CompileContext, default_compile_context
from .pipeline import compile_official


class CorrectnessContractError(ValueError):
    pass


OFFICIAL_FUNCTION_FAMILIES = frozenset(
    {
        "indicator",
        "rank",
        "belong_industry",
        "queryData",
        "cross_above",
        "cross_down",
        "close_together",
        "reset",
        "golden_cross",
        "record_high",
        "record_low",
        "position",
    }
)


@dataclass(frozen=True)
class CorrectnessCase:
    case_id: str
    dsl: str
    function_families: Tuple[str, ...]
    plan_family: str
    eligibility: str
    eligibility_reason: str
    policy_id: str
    dataset_snapshot_id: str
    expected_non_empty: bool
    reference_sql_path: str
    review_status: str
    reviewer: str
    ordered: bool

    @property
    def score_eligible(self) -> bool:
        return self.eligibility == "eligible" and self.review_status == "approved"


@dataclass(frozen=True)
class CorrectnessCaseResult:
    case_id: str
    status: str
    matched: bool
    generated_row_count: int
    reference_row_count: int
    generated_hash: str
    reference_hash: str
    compile_ms: float
    generated_execute_ms: float
    reference_execute_ms: float
    function_families: Tuple[str, ...]
    plan_family: str
    error: str = ""


def load_correctness_manifest(path: Path) -> Tuple[CorrectnessCase, ...]:
    cases = []
    seen = set()
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CorrectnessContractError(f"invalid JSON at line {line_number}: {exc}") from exc
        case = _case(raw, line_number)
        if case.case_id in seen:
            raise CorrectnessContractError(f"duplicate correctness case_id: {case.case_id}")
        seen.add(case.case_id)
        cases.append(case)
    if not cases:
        raise CorrectnessContractError("correctness manifest is empty")
    return tuple(cases)


def validate_correctness_manifest(
    cases: Iterable[CorrectnessCase],
    *,
    root: Path,
    expected_policy_id: Optional[str] = None,
    expected_snapshot_id: Optional[str] = None,
) -> Dict[str, Any]:
    errors = []
    warnings = []
    eligible = 0
    pending = 0
    for case in cases:
        if case.score_eligible:
            eligible += 1
            reference = (Path(root) / case.reference_sql_path).resolve()
            if Path(root).resolve() not in reference.parents or not reference.is_file():
                errors.append(f"{case.case_id}: approved reference SQL is missing")
            if not case.reviewer.strip():
                errors.append(f"{case.case_id}: approved case has no reviewer")
        else:
            pending += 1
        if expected_policy_id and case.score_eligible and case.policy_id != expected_policy_id:
            errors.append(f"{case.case_id}: policy_id mismatch")
        if expected_snapshot_id and case.score_eligible and case.dataset_snapshot_id != expected_snapshot_id:
            errors.append(f"{case.case_id}: dataset_snapshot_id mismatch")
        if case.eligibility == "eligible" and case.review_status != "approved":
            errors.append(f"{case.case_id}: eligible case must be approved")
        if case.review_status == "approved" and case.eligibility != "eligible":
            errors.append(f"{case.case_id}: approved case must be eligible")
    if eligible < 240:
        warnings.append(f"formal benchmark has {eligible} eligible cases; target is at least 240")
    return {
        "passed": not errors,
        "eligible": eligible,
        "pending": pending,
        "errors": errors,
        "warnings": warnings,
    }


def run_correctness_benchmark(
    cases: Iterable[CorrectnessCase],
    *,
    manifest_root: Path,
    doris: DorisExecutionConfig,
    context: CompileContext | None = None,
    executor: Callable[[DorisExecutionConfig, str], DorisExecutionResult] = execute_doris_query,
    compiler: Callable[..., Any] = compile_official,
) -> Dict[str, Any]:
    compile_context = context or default_compile_context()
    case_list = tuple(cases)
    snapshot_ids = {
        case.dataset_snapshot_id for case in case_list if case.score_eligible
    }
    if len(snapshot_ids) != 1:
        raise CorrectnessContractError(
            "formal benchmark must use exactly one dataset snapshot"
        )
    dataset_snapshot_id = next(iter(snapshot_ids))
    contract = validate_correctness_manifest(
        case_list,
        root=manifest_root,
        expected_policy_id=compile_context.snapshot.policy_id,
        expected_snapshot_id=dataset_snapshot_id,
    )
    if not contract["passed"]:
        raise CorrectnessContractError("; ".join(contract["errors"]))
    results = []
    for case in case_list:
        if not case.score_eligible:
            continue
        results.append(
            _run_case(
                case,
                manifest_root=manifest_root,
                doris=doris,
                context=compile_context,
                executor=executor,
                compiler=compiler,
            )
        )
    matched = sum(1 for result in results if result.matched)
    total = len(results)
    groups = _group_summary(results)
    family_groups = groups["function_family"]
    all_families_covered = OFFICIAL_FUNCTION_FAMILIES.issubset(family_groups)
    family_target_met = bool(family_groups) and all(
        item["accuracy"] >= 0.95 for item in family_groups.values()
    )
    accuracy = matched / total if total else None
    official_target_met = bool(
        total
        and accuracy is not None
        and accuracy >= 0.95
        and all_families_covered
        and family_target_met
    )
    internal_target_met = bool(
        total >= 240
        and accuracy is not None
        and accuracy >= 0.98
        and all_families_covered
        and family_target_met
        and all(item["total"] >= 12 for item in family_groups.values())
    )
    lower, upper = wilson_interval(matched, total)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "git_head": _git_head(),
        "catalog_snapshot_id": compile_context.context_id,
        "policy_id": compile_context.snapshot.policy_id,
        "dataset_snapshot_id": dataset_snapshot_id,
        "eligible_total": total,
        "matched": matched,
        "mismatched": total - matched,
        "accuracy": accuracy,
        "wilson_95": {"lower": lower, "upper": upper},
        "target_accuracy": 0.95,
        "internal_target_accuracy": 0.98,
        "all_12_function_families_covered": all_families_covered,
        "function_family_target_met": family_target_met,
        "target_met": official_target_met,
        "internal_target_met": internal_target_met,
        "contract": contract,
        "groups": groups,
        "results": [asdict(item) for item in results],
    }


def write_correctness_report(report: Mapping[str, Any], json_path: Path, markdown_path: Path) -> None:
    Path(json_path).parent.mkdir(parents=True, exist_ok=True)
    Path(markdown_path).parent.mkdir(parents=True, exist_ok=True)
    Path(json_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 官方 SQL 正确率冻结基准",
        "",
        f"- Git HEAD：`{report.get('git_head')}`",
        f"- Catalog snapshot：`{report.get('catalog_snapshot_id')}`",
        f"- Policy：`{report.get('policy_id')}`",
        f"- Dataset snapshot：`{report.get('dataset_snapshot_id')}`",
        f"- Eligible：`{report.get('eligible_total')}`",
        f"- 完整行集一致：`{report.get('matched')}`",
        f"- 正确率：`{_percent(report.get('accuracy'))}`",
        f"- Wilson 95% 下界：`{_percent((report.get('wilson_95') or {}).get('lower'))}`",
        f"- 95% 门禁：`{'PASS' if report.get('target_met') else 'FAIL'}`",
        f"- 十二类函数覆盖：`{report.get('all_12_function_families_covered')}`",
        f"- 内部 240 条/98% 门禁：`{'PASS' if report.get('internal_target_met') else 'FAIL'}`",
        "",
        "## 分层结果",
        "",
        "| 维度 | 分组 | 匹配 | 总数 | 正确率 |",
        "|---|---|---:|---:|---:|",
    ]
    for dimension, values in (report.get("groups") or {}).items():
        for name, value in values.items():
            lines.append(
                f"| {dimension} | {name} | {value['matched']} | {value['total']} | {_percent(value['accuracy'])} |"
            )
    lines.extend(["", "## 逐例结果", "", "| Case | 状态 | 匹配 | Generated rows | Reference rows | 错误 |", "|---|---|---:|---:|---:|---|"])
    for item in report.get("results") or []:
        lines.append(
            f"| {item['case_id']} | {item['status']} | {item['matched']} | "
            f"{item['generated_row_count']} | {item['reference_row_count']} | "
            f"{_markdown_cell(item.get('error') or '')} |"
        )
    Path(markdown_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> Tuple[Optional[float], Optional[float]]:
    if total <= 0:
        return None, None
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(
        proportion * (1 - proportion) / total + z * z / (4 * total * total)
    ) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def _run_case(case, *, manifest_root, doris, context, executor, compiler) -> CorrectnessCaseResult:
    try:
        compiled = compiler(case.dsl, context=context)
        generated = executor(doris, compiled.backend["sql"])
        reference_sql = (Path(manifest_root) / case.reference_sql_path).read_text(encoding="utf-8")
        reference = executor(doris, reference_sql)
        generated_hash = generated.ordered_hash if case.ordered else generated.unordered_hash
        reference_hash = reference.ordered_hash if case.ordered else reference.unordered_hash
        non_empty_ok = not case.expected_non_empty or reference.rows
        matched = bool(
            non_empty_ok
            and len(generated.rows) == len(reference.rows)
            and generated_hash == reference_hash
        )
        return CorrectnessCaseResult(
            case.case_id,
            "PASS" if matched else "FAIL",
            matched,
            len(generated.rows),
            len(reference.rows),
            generated_hash,
            reference_hash,
            compiled.elapsed_ms,
            generated.elapsed_ms,
            reference.elapsed_ms,
            case.function_families,
            case.plan_family,
            "" if non_empty_ok else "reference result is empty but expected_non_empty=true",
        )
    except Exception as exc:  # noqa: BLE001 - the benchmark must preserve per-case failures.
        return CorrectnessCaseResult(
            case.case_id,
            "ERROR",
            False,
            0,
            0,
            "",
            "",
            0.0,
            0.0,
            0.0,
            case.function_families,
            case.plan_family,
            f"{type(exc).__name__}: {exc}",
        )


def _case(raw: Mapping[str, Any], line_number: int) -> CorrectnessCase:
    expected = {
        "case_id",
        "dsl",
        "function_families",
        "plan_family",
        "eligibility",
        "eligibility_reason",
        "policy_id",
        "dataset_snapshot_id",
        "expected_non_empty",
        "reference_sql_path",
        "review_status",
        "reviewer",
        "ordered",
    }
    if not isinstance(raw, Mapping) or set(raw) != expected:
        raise CorrectnessContractError(f"invalid correctness fields at line {line_number}")
    eligibility = str(raw["eligibility"])
    review = str(raw["review_status"])
    if eligibility not in {"eligible", "ineligible", "review_pending"}:
        raise CorrectnessContractError(f"invalid eligibility at line {line_number}")
    if review not in {"approved", "rejected", "pending"}:
        raise CorrectnessContractError(f"invalid review_status at line {line_number}")
    families = tuple(sorted({str(item) for item in raw["function_families"] if str(item)}))
    if not str(raw["case_id"]).strip() or not str(raw["dsl"]).strip() or not families:
        raise CorrectnessContractError(f"case identity, DSL and families are required at line {line_number}")
    return CorrectnessCase(
        str(raw["case_id"]),
        str(raw["dsl"]),
        families,
        str(raw["plan_family"]),
        eligibility,
        str(raw["eligibility_reason"]),
        str(raw["policy_id"]),
        str(raw["dataset_snapshot_id"]),
        bool(raw["expected_non_empty"]),
        str(raw["reference_sql_path"]),
        review,
        str(raw["reviewer"]),
        bool(raw["ordered"]),
    )


def _group_summary(results: Iterable[CorrectnessCaseResult]) -> Dict[str, Dict[str, Any]]:
    groups: Dict[str, Dict[str, list]] = {"function_family": {}, "plan_family": {}}
    for result in results:
        for family in result.function_families:
            groups["function_family"].setdefault(family, []).append(result.matched)
        groups["plan_family"].setdefault(result.plan_family, []).append(result.matched)
    return {
        dimension: {
            name: {
                "matched": sum(values),
                "total": len(values),
                "accuracy": sum(values) / len(values),
            }
            for name, values in sorted(entries.items())
        }
        for dimension, entries in groups.items()
    }


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def _percent(value: Any) -> str:
    return f"{float(value) * 100:.2f}%" if value is not None else "<unavailable>"


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

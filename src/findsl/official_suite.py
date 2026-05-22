from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

from .compiler import Compiler
from .diagnostics import diagnose_exception
from .equivalence import verify_sql_equivalence


DEFAULT_POSITIVE_CASES = Path("data/samples/official_positive_cases.jsonl")
DEFAULT_NEGATIVE_CASES = Path("data/samples/official_negative_cases.jsonl")


@dataclass(frozen=True)
class OfficialPositiveCaseResult:
    name: str
    scenario: str
    dsl: str
    passed: bool
    compile_elapsed_ms: float
    equivalence_passed: bool
    sql_row_count: int
    reference_row_count: int
    missing_sql_fragments: List[str]
    missing_trace_fragments: List[str]
    missing_explain_rules: List[str]
    error: str = ""


@dataclass(frozen=True)
class OfficialNegativeCaseResult:
    name: str
    dsl: str
    passed: bool
    expected_code: str
    actual_code: str
    suggestion_count: int
    missing_suggestion_fragments: List[str]
    error: str = ""


@dataclass(frozen=True)
class OfficialSuiteResult:
    positive_cases: List[OfficialPositiveCaseResult]
    negative_cases: List[OfficialNegativeCaseResult]
    output_path: Path

    @property
    def positive_total(self) -> int:
        return len(self.positive_cases)

    @property
    def positive_passed(self) -> int:
        return sum(1 for case in self.positive_cases if case.passed)

    @property
    def negative_total(self) -> int:
        return len(self.negative_cases)

    @property
    def negative_passed(self) -> int:
        return sum(1 for case in self.negative_cases if case.passed)

    @property
    def passed(self) -> bool:
        return (
            self.positive_total > 0
            and self.negative_total > 0
            and self.positive_passed == self.positive_total
            and self.negative_passed == self.negative_total
        )

    def to_markdown(self) -> str:
        lines = [
            "# Official-Style Coverage Suite",
            "",
            "## Summary",
            "",
            f"- Suite passed: {self.passed}",
            f"- Positive cases passed: {self.positive_passed}/{self.positive_total}",
            f"- Negative diagnostic cases passed: {self.negative_passed}/{self.negative_total}",
            "",
            "## Positive Cases",
            "",
            "| Case | Scenario | Passed | Equivalence | SQL rows | Reference rows | Missing evidence |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
        for case in self.positive_cases:
            missing = _join_missing(
                case.missing_sql_fragments,
                case.missing_trace_fragments,
                case.missing_explain_rules,
                [case.error] if case.error else [],
            )
            lines.append(
                f"| {case.name} | {case.scenario} | {case.passed} | {case.equivalence_passed} | "
                f"{case.sql_row_count} | {case.reference_row_count} | {missing or '<none>'} |"
            )
        lines.extend(
            [
                "",
                "## Negative Diagnostic Cases",
                "",
                "| Case | Passed | Expected code | Actual code | Suggestions | Missing suggestion evidence |",
                "|---|---:|---|---|---:|---|",
            ]
        )
        for case in self.negative_cases:
            missing = _join_missing(case.missing_suggestion_fragments, [case.error] if case.error else [])
            lines.append(
                f"| {case.name} | {case.passed} | {case.expected_code} | {case.actual_code or '<none>'} | "
                f"{case.suggestion_count} | {missing or '<none>'} |"
            )
        lines.extend(
            [
                "",
                "## Evidence Policy",
                "",
                "- Positive cases must compile, match SQL fragments, match trace fragments, expose expected explain rules, and match the independent SQL/reference result.",
                "- Negative cases must fail safely with the expected diagnostic code and actionable repair suggestions.",
            ]
        )
        return "\n".join(lines)


def run_official_suite(
    positive_cases_path: Path = DEFAULT_POSITIVE_CASES,
    negative_cases_path: Path = DEFAULT_NEGATIVE_CASES,
    data_dir: Path = Path("data/samples"),
    output_path: Path = Path("reports/official_suite_report.md"),
) -> OfficialSuiteResult:
    compiler = Compiler()
    positive_results = [
        _run_positive_case(case, data_dir=data_dir, compiler=compiler)
        for case in _load_jsonl(Path(positive_cases_path))
    ]
    negative_results = [
        _run_negative_case(case, compiler=compiler)
        for case in _load_jsonl(Path(negative_cases_path))
    ]
    result = OfficialSuiteResult(
        positive_cases=positive_results,
        negative_cases=negative_results,
        output_path=Path(output_path),
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.to_markdown(), encoding="utf-8")
    return result


def _run_positive_case(case: Dict[str, object], data_dir: Path, compiler: Compiler) -> OfficialPositiveCaseResult:
    name = str(case.get("name", "<unnamed>"))
    scenario = str(case.get("scenario", "<none>"))
    dsl = str(case.get("dsl", ""))
    try:
        compiled = compiler.compile(dsl)
        trace_blob = "\n".join(compiled.trace)
        explain_rules = {str(step.get("rule")) for step in compiled.explain}
        missing_sql = _missing_fragments(compiled.sql, _string_list(case.get("expected_sql_fragments", [])))
        missing_trace = _missing_fragments(trace_blob, _string_list(case.get("expected_trace_fragments", [])))
        missing_explain = [
            rule for rule in _string_list(case.get("expected_explain_rules", [])) if rule not in explain_rules
        ]
        equivalence = verify_sql_equivalence(dsl, data_dir, compiler=compiler)
        passed = (
            equivalence.passed
            and not missing_sql
            and not missing_trace
            and not missing_explain
        )
        return OfficialPositiveCaseResult(
            name=name,
            scenario=scenario,
            dsl=dsl,
            passed=passed,
            compile_elapsed_ms=compiled.elapsed_ms,
            equivalence_passed=equivalence.passed,
            sql_row_count=equivalence.sql_row_count,
            reference_row_count=equivalence.reference_row_count,
            missing_sql_fragments=missing_sql,
            missing_trace_fragments=missing_trace,
            missing_explain_rules=missing_explain,
        )
    except Exception as exc:  # noqa: BLE001 - coverage reports should preserve case failures.
        return OfficialPositiveCaseResult(
            name=name,
            scenario=scenario,
            dsl=dsl,
            passed=False,
            compile_elapsed_ms=0.0,
            equivalence_passed=False,
            sql_row_count=0,
            reference_row_count=0,
            missing_sql_fragments=[],
            missing_trace_fragments=[],
            missing_explain_rules=[],
            error=f"{type(exc).__name__}: {exc}",
        )


def _run_negative_case(case: Dict[str, object], compiler: Compiler) -> OfficialNegativeCaseResult:
    name = str(case.get("name", "<unnamed>"))
    dsl = str(case.get("dsl", ""))
    expected_code = str(case.get("expected_code", ""))
    expected_fragments = _string_list(case.get("expected_suggestion_fragments", []))
    try:
        compiler.compile(dsl)
        return OfficialNegativeCaseResult(
            name=name,
            dsl=dsl,
            passed=False,
            expected_code=expected_code,
            actual_code="",
            suggestion_count=0,
            missing_suggestion_fragments=expected_fragments,
            error="invalid DSL unexpectedly compiled",
        )
    except Exception as exc:  # noqa: BLE001 - asserting diagnostics for every compiler failure class.
        diagnostics = diagnose_exception(exc)
        actual_code = diagnostics[0].code if diagnostics else ""
        suggestions = [suggestion for item in diagnostics for suggestion in item.suggestions]
        suggestion_blob = "\n".join(suggestions)
        missing = _missing_fragments(suggestion_blob, expected_fragments)
        passed = actual_code == expected_code and bool(suggestions) and not missing
        return OfficialNegativeCaseResult(
            name=name,
            dsl=dsl,
            passed=passed,
            expected_code=expected_code,
            actual_code=actual_code,
            suggestion_count=len(suggestions),
            missing_suggestion_fragments=missing,
            error="" if passed else f"{type(exc).__name__}: {exc}",
        )


def _load_jsonl(path: Path) -> List[Dict[str, object]]:
    cases: List[Dict[str, object]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
    return cases


def _missing_fragments(blob: str, fragments: Sequence[str]) -> List[str]:
    return [fragment for fragment in fragments if fragment not in blob]


def _string_list(value: object) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _join_missing(*groups: Sequence[str]) -> str:
    return "<br>".join(item for group in groups for item in group if item)

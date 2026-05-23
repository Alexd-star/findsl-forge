from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

from .compiler import Compiler
from .demo import DEFAULT_NL_REQUEST, analyze_dsl, suggest_from_text
from .diagnostics import diagnose_exception
from .doris import render_doris_assets
from .evaluation import evaluate_file, load_cases
from .llm_adapter import DEFAULT_LLM_CANDIDATE_RESPONSE, validate_llm_candidates
from .official_suite import DEFAULT_NEGATIVE_CASES, DEFAULT_POSITIVE_CASES, run_official_suite


@dataclass(frozen=True)
class DefenseCheck:
    name: str
    scoring_point: str
    demo_action: str
    expected_signal: str
    passed: bool
    evidence: List[str]


@dataclass(frozen=True)
class DefensePackageResult:
    checks: List[DefenseCheck]
    output_path: Path

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def passed_count(self) -> int:
        return sum(1 for check in self.checks if check.passed)

    @property
    def passed(self) -> bool:
        return self.total > 0 and self.passed_count == self.total

    def to_markdown(self) -> str:
        lines = [
            "# FinDSL Forge Defense Package",
            "",
            "## Summary",
            "",
            f"- Package passed: {self.passed}",
            f"- Checks passed: {self.passed_count}/{self.total}",
            "- Scope: local reproducible evidence for live defense; real Doris 10x proof still requires a running Doris cluster.",
            "",
            "## Live Walkthrough",
            "",
            "1. Start the demo with `powershell -ExecutionPolicy Bypass -File .\\scripts\\serve_demo.ps1`.",
            "2. Let the default Chinese request produce a validated DSL candidate and SQL/reference PASS.",
            "3. Select `Official positive: 主力净流入3日滚动求和走资金流前缀表 [money_flow_prefix_sum]` and run it.",
            "4. Confirm the UI shows verification PASS, optimizer `Applied`, and SQL containing `dwd_stock_money_flow_prefix`.",
            "5. Select `Diagnostic negative: 未知指标名 [UNKNOWN_INDICATOR]` and run it.",
            "6. Confirm the UI shows `Diagnostic`, expected/actual `UNKNOWN_INDICATOR`, and the `indicator(\"close\")` repair hint.",
            "7. Run `python -m findsl.cli validate-llm-candidates --response-file data\\samples\\llm_candidate_response.json --json` to prove the LLM path accepts only compiler-validated DSL.",
            "8. Run `scripts\\official_suite.ps1` and `scripts\\submission_readiness.ps1` to show repeatable report evidence.",
            "",
            "## Score Mapping",
            "",
            "| Check | Scoring point | Passed | Demo action | Expected signal | Evidence |",
            "|---|---|---:|---|---|---|",
        ]
        for check in self.checks:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(check.name),
                        _cell(check.scoring_point),
                        str(check.passed),
                        _cell(check.demo_action),
                        _cell(check.expected_signal),
                        _cell("<br>".join(check.evidence) or "<none>"),
                    ]
                )
                + " |"
            )
        lines.extend(
            [
                "",
                "## Submission Narrative",
                "",
                "- Deterministic compiler path keeps correctness auditable: DSL -> AST -> semantic validation -> Doris SQL.",
                "- AI assistance is constrained to NL2DSL/LLM DSL candidates; every candidate must compile and match the independent reference oracle.",
                "- The LLM adapter rejects direct SQL and invalid DSL with stable diagnostic evidence before any SQL reaches Doris.",
                "- Prefix-sum optimization is visible in SQL, structured explain records, and benchmark/readiness evidence.",
                "- Negative cases demonstrate controlled, repairable failure rather than uncaught exceptions.",
                "- Generated Doris assets and runbooks keep deployment aligned with the same registry used by the compiler.",
            ]
        )
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "passed_count": self.passed_count,
            "total": self.total,
            "output": str(self.output_path),
            "checks": [
                {
                    "name": check.name,
                    "scoring_point": check.scoring_point,
                    "demo_action": check.demo_action,
                    "expected_signal": check.expected_signal,
                    "passed": check.passed,
                    "evidence": list(check.evidence),
                }
                for check in self.checks
            ],
        }


def generate_defense_package(
    output_path: Path = Path("reports/defense_package.md"),
    data_dir: Path = Path("data/samples"),
    cases_path: Path = Path("data/samples/queries.jsonl"),
    official_positive_path: Path = DEFAULT_POSITIVE_CASES,
    official_negative_path: Path = DEFAULT_NEGATIVE_CASES,
    llm_response_path: Path = DEFAULT_LLM_CANDIDATE_RESPONSE,
    repo_root: Path = Path("."),
) -> DefensePackageResult:
    output_path = Path(output_path)
    reports_dir = output_path.parent
    repo_root = Path(repo_root)
    checks = [
        _check_nl2dsl(data_dir),
        _check_llm_candidate_safety(data_dir, _resolve_repo_path(repo_root, llm_response_path)),
        _check_money_flow_prefix(data_dir, official_positive_path),
        _check_unknown_indicator_diagnostic(official_negative_path),
        _check_official_suite(data_dir, official_positive_path, official_negative_path, reports_dir),
        _check_evaluation_report(cases_path, reports_dir),
        _check_doris_assets(repo_root, data_dir),
    ]
    result = DefensePackageResult(checks=checks, output_path=output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.to_markdown(), encoding="utf-8")
    return result


def _check_nl2dsl(data_dir: Path) -> DefenseCheck:
    try:
        result = suggest_from_text(DEFAULT_NL_REQUEST, data_dir=data_dir, verify=True)
        candidates = result.get("candidates", [])
        top = candidates[0] if candidates else {}
        analysis = top.get("analysis") or {}
        verification = analysis.get("verification") or {}
        passed = bool(top.get("validated")) and bool(verification.get("passed"))
        return DefenseCheck(
            name="NL2DSL validated candidate",
            scoring_point="AI-assisted entry without SQL hallucination",
            demo_action="Use the default Chinese request in the Web Demo.",
            expected_signal="Candidate is validated and verification is PASS.",
            passed=passed,
            evidence=[
                f"candidate_count={len(candidates)}",
                f"top_dsl={top.get('dsl', '<none>')}",
                f"sql_rows={verification.get('sql_row_count', 0)}",
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "NL2DSL validated candidate",
            "AI-assisted entry without SQL hallucination",
            "Use the default Chinese request in the Web Demo.",
            "Candidate is validated and verification is PASS.",
            exc,
        )


def _check_llm_candidate_safety(data_dir: Path, response_path: Path) -> DefenseCheck:
    try:
        result = validate_llm_candidates(
            text="近3日成交量累计大于300",
            payload=response_path.read_text(encoding="utf-8"),
            data_dir=data_dir,
            verify=True,
        )
        rejected_codes = [
            str(diagnostic.get("code", ""))
            for candidate in result.candidates
            if not candidate.accepted
            for diagnostic in candidate.diagnostics
        ]
        accepted_verified = any(
            candidate.accepted
            and bool((candidate.analysis or {}).get("verification", {}).get("passed"))
            for candidate in result.candidates
        )
        passed = (
            accepted_verified
            and result.accepted_count >= 1
            and "UNSAFE_DIRECT_SQL" in rejected_codes
            and "UNKNOWN_INDICATOR" in rejected_codes
        )
        return DefenseCheck(
            name="LLM candidate safety loop",
            scoring_point="LLM assistance with deterministic compiler guardrails",
            demo_action="Run validate-llm-candidates against data\\samples\\llm_candidate_response.json.",
            expected_signal="One valid DSL is accepted, direct SQL is rejected, and misspelled indicators produce diagnostics.",
            passed=passed,
            evidence=[
                f"accepted={result.accepted_count}",
                f"rejected={result.rejected_count}",
                f"rejected_codes={', '.join(rejected_codes) or '<none>'}",
                f"response={response_path}",
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "LLM candidate safety loop",
            "LLM assistance with deterministic compiler guardrails",
            "Run validate-llm-candidates against data\\samples\\llm_candidate_response.json.",
            "One valid DSL is accepted, direct SQL is rejected, and misspelled indicators produce diagnostics.",
            exc,
        )


def _check_money_flow_prefix(data_dir: Path, positive_path: Path) -> DefenseCheck:
    try:
        case = _find_case(load_cases(Path(positive_path)), "scenario", "money_flow_prefix_sum")
        result = analyze_dsl(case["dsl"], data_dir=data_dir, enable_prefix_sum=True, verify=True)
        explain = result["compile"]["explain"]
        sql = result["compile"]["sql"]
        verification = result["verification"] or {}
        prefix_applied = any(step.get("rule") == "PREFIX_SUM" and step.get("status") == "applied" for step in explain)
        passed = (
            bool(verification.get("passed"))
            and prefix_applied
            and "dwd_stock_money_flow_prefix" in sql
        )
        return DefenseCheck(
            name="Official prefix-sum positive preset",
            scoring_point="Long-window optimization with explainable SQL rewrite",
            demo_action="Select the money_flow_prefix_sum official positive preset and run it.",
            expected_signal="Verification PASS, optimizer Applied, and money-flow prefix table in SQL.",
            passed=passed,
            evidence=[
                f"case={case.get('name', '<unnamed>')}",
                f"compile_ms={result['compile']['elapsed_ms']:.3f}",
                f"sql_rows={verification.get('sql_row_count', 0)}",
                "sql_contains=dwd_stock_money_flow_prefix",
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "Official prefix-sum positive preset",
            "Long-window optimization with explainable SQL rewrite",
            "Select the money_flow_prefix_sum official positive preset and run it.",
            "Verification PASS, optimizer Applied, and money-flow prefix table in SQL.",
            exc,
        )


def _check_unknown_indicator_diagnostic(negative_path: Path) -> DefenseCheck:
    try:
        case = _find_case(load_cases(Path(negative_path)), "expected_code", "UNKNOWN_INDICATOR")
        try:
            Compiler().compile(case["dsl"])
            diagnostics = []
        except Exception as exc:  # noqa: BLE001 - this case is expected to fail diagnostically.
            diagnostics = diagnose_exception(exc)
        actual_code = diagnostics[0].code if diagnostics else ""
        suggestions = [hint for item in diagnostics for hint in item.suggestions]
        passed = (
            actual_code == "UNKNOWN_INDICATOR"
            and any('indicator("close")' in hint for hint in suggestions)
        )
        return DefenseCheck(
            name="Official diagnostic negative preset",
            scoring_point="Interactive error explainability and repair guidance",
            demo_action="Select the UNKNOWN_INDICATOR negative preset and run it.",
            expected_signal="Expected and actual diagnostic codes match, with a close-indicator repair hint.",
            passed=passed,
            evidence=[
                f"case={case.get('name', '<unnamed>')}",
                f"expected=UNKNOWN_INDICATOR",
                f"actual={actual_code or '<none>'}",
                f"suggestions={len(suggestions)}",
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "Official diagnostic negative preset",
            "Interactive error explainability and repair guidance",
            "Select the UNKNOWN_INDICATOR negative preset and run it.",
            "Expected and actual diagnostic codes match, with a close-indicator repair hint.",
            exc,
        )


def _check_official_suite(
    data_dir: Path,
    positive_path: Path,
    negative_path: Path,
    reports_dir: Path,
) -> DefenseCheck:
    try:
        result = run_official_suite(
            positive_cases_path=Path(positive_path),
            negative_cases_path=Path(negative_path),
            data_dir=Path(data_dir),
            output_path=reports_dir / "official_suite_report.md",
        )
        return DefenseCheck(
            name="Official-style coverage suite",
            scoring_point="Representative task coverage and negative-case proof",
            demo_action="Run scripts\\official_suite.ps1.",
            expected_signal="Positive 11/11 and negative 8/8 pass.",
            passed=result.passed,
            evidence=[
                f"positive={result.positive_passed}/{result.positive_total}",
                f"negative={result.negative_passed}/{result.negative_total}",
                f"report={result.output_path}",
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "Official-style coverage suite",
            "Representative task coverage and negative-case proof",
            "Run scripts\\official_suite.ps1.",
            "Positive 11/11 and negative 8/8 pass.",
            exc,
        )


def _check_evaluation_report(cases_path: Path, reports_dir: Path) -> DefenseCheck:
    try:
        result = evaluate_file(Path(cases_path), reports_dir / "evaluation_report.md")
        passed = (
            result.failed == 0
            and result.compile_success_rate == 1.0
            and result.fragment_accuracy == 1.0
            and result.p95_elapsed_ms < 50
        )
        return DefenseCheck(
            name="Compiler accuracy and latency",
            scoring_point="Correct SQL generation under compile P95 target",
            demo_action="Run scripts\\evaluate.ps1 or submission_readiness.ps1.",
            expected_signal="100% compile/fragment accuracy and P95 below 50 ms.",
            passed=passed,
            evidence=[
                f"cases={result.passed}/{result.total}",
                f"fragments={result.fragment_accuracy:.2%}",
                f"p95_ms={result.p95_elapsed_ms:.3f}",
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "Compiler accuracy and latency",
            "Correct SQL generation under compile P95 target",
            "Run scripts\\evaluate.ps1 or submission_readiness.ps1.",
            "100% compile/fragment accuracy and P95 below 50 ms.",
            exc,
        )


def _check_doris_assets(repo_root: Path, data_dir: Path) -> DefenseCheck:
    try:
        expected_assets = render_doris_assets(Path(data_dir)).files()
        asset_dir = Path(repo_root).resolve() / "deploy" / "doris"
        matched = []
        missing = []
        for filename, expected in expected_assets.items():
            path = asset_dir / filename
            if path.exists() and path.read_text(encoding="utf-8") == expected:
                matched.append(filename)
            else:
                missing.append(filename)
        passed = not missing and len(matched) == len(expected_assets)
        return DefenseCheck(
            name="Doris deployment asset integrity",
            scoring_point="Reproducible Doris deployment path",
            demo_action="Run scripts\\generate_doris_assets.ps1, then inspect deploy\\doris.",
            expected_signal="All generated Doris SQL assets match the registry-driven generator.",
            passed=passed,
            evidence=[
                f"matched={len(matched)}/{len(expected_assets)}",
                f"missing={', '.join(missing) or '<none>'}",
                f"asset_dir={asset_dir}",
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "Doris deployment asset integrity",
            "Reproducible Doris deployment path",
            "Run scripts\\generate_doris_assets.ps1, then inspect deploy\\doris.",
            "All generated Doris SQL assets match the registry-driven generator.",
            exc,
        )


def _find_case(cases: Sequence[Dict[str, Any]], key: str, value: str) -> Dict[str, Any]:
    for case in cases:
        if case.get(key) == value:
            return case
    raise ValueError(f"Missing case where {key}={value}")


def _failed_check(
    name: str,
    scoring_point: str,
    demo_action: str,
    expected_signal: str,
    exc: Exception,
) -> DefenseCheck:
    return DefenseCheck(
        name=name,
        scoring_point=scoring_point,
        demo_action=demo_action,
        expected_signal=expected_signal,
        passed=False,
        evidence=[f"{type(exc).__name__}: {exc}"],
    )


def _cell(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _resolve_repo_path(repo_root: Path, path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else Path(repo_root).resolve() / path

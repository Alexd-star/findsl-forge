from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .benchmark import PrefixSumBenchmarkResult, benchmark_prefix_sum_file
from .compiler import Compiler
from .defense_package import DefensePackageResult, generate_defense_package
from .diagnostics import diagnose_exception
from .demo import DEFAULT_DEMO_DSL, DEFAULT_NL_REQUEST, analyze_dsl, suggest_from_text
from .doris import render_doris_assets
from .equivalence import EquivalenceResult, verify_sql_equivalence
from .evaluation import EvaluationResult, evaluate_file
from .llm_adapter import DEFAULT_LLM_CANDIDATE_RESPONSE, validate_llm_candidates
from .official_suite import OfficialSuiteResult, run_official_suite


DEFAULT_EQUIVALENCE_DSL = (
    'then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), '
    'rank(indicator("turnover_rate"), desc, top=100))'
)
DEFAULT_BENCHMARK_DSL = 'filter(SUM(indicator("volume"), 3) > 300)'


@dataclass(frozen=True)
class CommandCheck:
    name: str
    command: List[str]
    exit_code: int
    elapsed_ms: float
    stdout_tail: str
    stderr_tail: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


@dataclass(frozen=True)
class GitState:
    is_repo: bool
    branch: str
    commit: str
    commit_subject: str
    dirty_entries: List[str]

    @property
    def is_clean(self) -> bool:
        return self.is_repo and not self.dirty_entries


@dataclass(frozen=True)
class DorisAssetCheck:
    filename: str
    path: Path
    exists: bool
    matches_generated: bool
    byte_count: int

    @property
    def passed(self) -> bool:
        return self.exists and self.matches_generated


@dataclass(frozen=True)
class EvidenceFileCheck:
    name: str
    path: Path
    exists: bool
    byte_count: int
    matched_markers: List[str]
    missing_markers: List[str]

    @property
    def passed(self) -> bool:
        return self.exists and not self.missing_markers


@dataclass(frozen=True)
class DemoSmokeCheck:
    dsl: str
    passed: bool
    compile_elapsed_ms: float
    verification_passed: bool
    sql_row_count: int
    error: str = ""


@dataclass(frozen=True)
class NL2DSLSmokeCheck:
    text: str
    passed: bool
    candidate_count: int
    top_dsl: str
    top_validated: bool
    verification_passed: bool
    sql_row_count: int
    error: str = ""


@dataclass(frozen=True)
class DiagnosticsSmokeCheck:
    dsl: str
    passed: bool
    diagnostic_count: int
    first_code: str
    suggestion_count: int
    error: str = ""


@dataclass(frozen=True)
class LLMSafetySmokeCheck:
    response_path: Path
    passed: bool
    raw_candidate_count: int
    accepted_count: int
    rejected_count: int
    rejected_codes: List[str]
    accepted_verified: bool
    error: str = ""


@dataclass(frozen=True)
class ReadinessGate:
    name: str
    level: str
    passed: bool
    evidence: str

    @property
    def status_icon(self) -> str:
        return "PASS" if self.passed else "WARN" if self.level == "warning" else "FAIL"


@dataclass(frozen=True)
class ReadinessReport:
    generated_at: str
    repo_root: Path
    output_path: Path
    reports_dir: Path
    git: GitState
    pytest: Optional[CommandCheck]
    evaluation: EvaluationResult
    equivalence: EquivalenceResult
    benchmark: PrefixSumBenchmarkResult
    doris_assets: List[DorisAssetCheck]
    scale_report: EvidenceFileCheck
    doris_cluster_report: EvidenceFileCheck
    demo_smoke: DemoSmokeCheck
    nl2dsl_smoke: NL2DSLSmokeCheck
    llm_safety_smoke: LLMSafetySmokeCheck
    diagnostics_smoke: DiagnosticsSmokeCheck
    official_suite: OfficialSuiteResult
    defense_package: DefensePackageResult
    gates: List[ReadinessGate]

    @property
    def blocking_passed(self) -> bool:
        return all(gate.passed for gate in self.gates if gate.level == "required")

    @property
    def warning_count(self) -> int:
        return sum(1 for gate in self.gates if gate.level == "warning" and not gate.passed)

    def to_markdown(self) -> str:
        lines = [
            "# FinDSL Forge Submission Readiness Report",
            "",
            "## Decision Summary",
            "",
            f"- Generated at: {self.generated_at}",
            f"- Repository root: `{self.repo_root}`",
            f"- Git HEAD: `{self.git.commit}` {self.git.commit_subject}",
            f"- Git branch: `{self.git.branch}`",
            f"- Blocking gates passed: {self.blocking_passed}",
            f"- Warning count: {self.warning_count}",
            "",
            "## Gate Matrix",
            "",
            "| Gate | Level | Status | Evidence |",
            "|---|---|---|---|",
        ]
        for gate in self.gates:
            lines.append(f"| {gate.name} | {gate.level} | {gate.status_icon} | {gate.evidence} |")

        lines.extend(
            [
                "",
                "## Competition Metrics",
                "",
                f"- Compile success rate: {self.evaluation.compile_success_rate:.2%}",
                f"- SQL fragment accuracy: {self.evaluation.fragment_accuracy:.2%}",
                f"- Compile P95 latency: {self.evaluation.p95_elapsed_ms:.3f} ms",
                f"- Evaluation cases passed: {self.evaluation.passed}/{self.evaluation.total}",
                f"- SQL/reference equivalence: {self.equivalence.passed}",
                f"- Equivalence SQL rows: {self.equivalence.sql_row_count}",
                f"- Equivalence reference rows: {self.equivalence.reference_row_count}",
                f"- Prefix optimized matches reference: {self.benchmark.optimized_matches_reference}",
                f"- Prefix optimized matches baseline: {self.benchmark.optimized_matches_baseline}",
                f"- Local prefix benchmark speedup: {self.benchmark.local_speedup:.2f}x",
                f"- Baseline window frames: {self.benchmark.baseline_window_frames}",
                f"- Optimized prefix table references: {self.benchmark.optimized_prefix_joins}",
                f"- Demo API smoke: {self.demo_smoke.passed}",
                f"- NL2DSL smoke: {self.nl2dsl_smoke.passed}",
                f"- LLM safety smoke: {self.llm_safety_smoke.passed}",
                f"- Diagnostics smoke: {self.diagnostics_smoke.passed}",
                f"- Official-style positive cases: {self.official_suite.positive_passed}/{self.official_suite.positive_total}",
                f"- Official-style negative diagnostics: {self.official_suite.negative_passed}/{self.official_suite.negative_total}",
                f"- Defense package checks: {self.defense_package.passed_count}/{self.defense_package.total}",
                "",
                "## Evidence Artifacts",
                "",
                f"- Readiness report: `{self.output_path}`",
                f"- Evaluation report: `{self.reports_dir / 'evaluation_report.md'}`",
                f"- SQL equivalence report: `{self.reports_dir / 'sql_equivalence_report.md'}`",
                f"- Official-style coverage suite report: `{self.official_suite.output_path}`",
                f"- Defense package report: `{self.defense_package.output_path}`",
                f"- Prefix benchmark report: `{self.reports_dir / 'prefix_sum_benchmark.md'}`",
                f"- Long-window scale benchmark report: `{self.scale_report.path}`",
                f"- Doris cluster evidence report: `{self.doris_cluster_report.path}`",
                f"- Doris deployment directory: `{self.repo_root / 'deploy' / 'doris'}`",
                "",
                "## Official-Style Coverage Suite",
                "",
                f"- Suite passed: {self.official_suite.passed}",
                f"- Positive cases passed: {self.official_suite.positive_passed}/{self.official_suite.positive_total}",
                f"- Negative diagnostic cases passed: {self.official_suite.negative_passed}/{self.official_suite.negative_total}",
                f"- Report: `{self.official_suite.output_path}`",
                "",
                "## Defense Package",
                "",
                f"- Package passed: {self.defense_package.passed}",
                f"- Checks passed: {self.defense_package.passed_count}/{self.defense_package.total}",
                f"- Report: `{self.defense_package.output_path}`",
                "",
                "## Long-Window Scale Evidence",
                "",
                f"- Scale report exists: {self.scale_report.exists}",
                f"- Scale report marker check: {self.scale_report.passed}",
                f"- Scale report bytes: {self.scale_report.byte_count}",
                f"- Matched markers: {', '.join(self.scale_report.matched_markers) or '<none>'}",
                f"- Missing markers: {', '.join(self.scale_report.missing_markers) or '<none>'}",
                "",
                "## Doris Cluster Evidence",
                "",
                f"- Doris cluster report exists: {self.doris_cluster_report.exists}",
                f"- Doris cluster marker check: {self.doris_cluster_report.passed}",
                f"- Doris cluster report bytes: {self.doris_cluster_report.byte_count}",
                f"- Matched markers: {', '.join(self.doris_cluster_report.matched_markers) or '<none>'}",
                f"- Missing markers: {', '.join(self.doris_cluster_report.missing_markers) or '<none>'}",
                "",
                "## Demo Smoke Test",
                "",
                f"- Passed: {self.demo_smoke.passed}",
                f"- Verification passed: {self.demo_smoke.verification_passed}",
                f"- Compile latency: {self.demo_smoke.compile_elapsed_ms:.3f} ms",
                f"- SQL rows: {self.demo_smoke.sql_row_count}",
                f"- Error: {self.demo_smoke.error or '<none>'}",
                "",
                "## NL2DSL Smoke Test",
                "",
                f"- Passed: {self.nl2dsl_smoke.passed}",
                f"- Candidate count: {self.nl2dsl_smoke.candidate_count}",
                f"- Top validated: {self.nl2dsl_smoke.top_validated}",
                f"- Verification passed: {self.nl2dsl_smoke.verification_passed}",
                f"- SQL rows: {self.nl2dsl_smoke.sql_row_count}",
                f"- Top DSL: `{self.nl2dsl_smoke.top_dsl or '<none>'}`",
                f"- Error: {self.nl2dsl_smoke.error or '<none>'}",
                "",
                "## LLM Candidate Safety Smoke Test",
                "",
                f"- Passed: {self.llm_safety_smoke.passed}",
                f"- Response file: `{self.llm_safety_smoke.response_path}`",
                f"- Raw candidates: {self.llm_safety_smoke.raw_candidate_count}",
                f"- Accepted candidates: {self.llm_safety_smoke.accepted_count}",
                f"- Rejected candidates: {self.llm_safety_smoke.rejected_count}",
                f"- Accepted candidate verified: {self.llm_safety_smoke.accepted_verified}",
                f"- Rejected diagnostic codes: {', '.join(self.llm_safety_smoke.rejected_codes) or '<none>'}",
                f"- Error: {self.llm_safety_smoke.error or '<none>'}",
                "",
                "## Diagnostics Smoke Test",
                "",
                f"- Passed: {self.diagnostics_smoke.passed}",
                f"- DSL: `{self.diagnostics_smoke.dsl}`",
                f"- Diagnostic count: {self.diagnostics_smoke.diagnostic_count}",
                f"- First code: {self.diagnostics_smoke.first_code or '<none>'}",
                f"- Suggestion count: {self.diagnostics_smoke.suggestion_count}",
                f"- Error: {self.diagnostics_smoke.error or '<none>'}",
                "",
                "## Doris Asset Integrity",
                "",
                "| File | Exists | Matches generator | Bytes |",
                "|---|---:|---:|---:|",
            ]
        )
        for asset in self.doris_assets:
            lines.append(
                f"| `{asset.path}` | {asset.exists} | {asset.matches_generated} | {asset.byte_count} |"
            )

        lines.extend(
            [
                "",
                "## Git Rollback State",
                "",
                f"- Repository detected: {self.git.is_repo}",
                f"- Clean working tree: {self.git.is_clean}",
            ]
        )
        if self.git.dirty_entries:
            lines.append("- Dirty entries:")
            lines.extend(f"  - `{entry}`" for entry in self.git.dirty_entries[:30])
        else:
            lines.append("- Dirty entries: none")

        lines.extend(
            [
                "",
                "## Pytest Evidence",
                "",
            ]
        )
        if self.pytest:
            lines.extend(
                [
                    f"- Command: `{' '.join(self.pytest.command)}`",
                    f"- Exit code: {self.pytest.exit_code}",
                    f"- Elapsed: {self.pytest.elapsed_ms:.1f} ms",
                    "",
                    "```text",
                    self.pytest.stdout_tail or "<no stdout>",
                    "```",
                ]
            )
            if self.pytest.stderr_tail:
                lines.extend(["", "stderr:", "", "```text", self.pytest.stderr_tail, "```"])
        else:
            lines.append("- Pytest was skipped for this report run.")

        lines.extend(
            [
                "",
                "## Award-Readiness Differentiators",
                "",
                "- Deterministic typed compiler path instead of LLM-only SQL generation.",
                "- Independent Pandas reference oracle plus SQLite SQL execution regression.",
                "- Config-driven indicators and functions for low-cost business expansion.",
                "- Safe date-range and window-aware upper-bound pruning expose partition-pruning-friendly `trade_date` predicates.",
                "- Prefix-sum rewrite path for long rolling windows with baseline/optimized evidence.",
                "- Structured optimizer explain records for defense and UI visualization.",
                "- Local Web Demo/API exposes DSL, AST, SQL, explain, and SQL/reference verification in one workflow.",
                "- NL2DSL candidate layer turns natural-language requests into compiler-validated DSL rather than free-form SQL.",
                "- Optional LLM adapter validates model-proposed DSL, rejects direct SQL, and records diagnostic evidence for unsafe outputs.",
                "- Structured diagnostics convert invalid DSL into stable error codes and repair hints.",
                "- Doris DDL includes trade-date auto partitions and colocated stock-code distribution for pruning and local prefix joins.",
                "- Doris sample data, prefix-table build SQL, and smoke queries are generated from the same registry.",
                "",
                "## Remaining High-Value Work",
                "",
                "- Re-run Doris-cluster EXPLAIN and latency evidence whenever scale data, table layout, or optimizer rules change.",
                "- Capture final Web Demo screenshots and a one-minute defense video from the official positive and diagnostic negative presets.",
                "- Broaden the DSL corpus with more official-style questions and negative/error cases.",
                "- Connect the optional LLM adapter to a real provider only after preserving the same deterministic validation contract.",
            ]
        )
        return "\n".join(lines)


def generate_readiness_report(
    repo_root: Path = Path("."),
    output_path: Path = Path("reports/submission_readiness.md"),
    reports_dir: Path = Path("reports"),
    cases_path: Path = Path("data/samples/queries.jsonl"),
    data_dir: Path = Path("data/samples"),
    equivalence_dsl: str = DEFAULT_EQUIVALENCE_DSL,
    benchmark_dsl: str = DEFAULT_BENCHMARK_DSL,
    benchmark_iterations: int = 20,
    run_pytest: bool = True,
) -> ReadinessReport:
    repo_root = Path(repo_root).resolve()
    output_path = _resolve(repo_root, output_path)
    reports_dir = _resolve(repo_root, reports_dir)
    cases_path = _resolve(repo_root, cases_path)
    data_dir = _resolve(repo_root, data_dir)

    reports_dir.mkdir(parents=True, exist_ok=True)
    git = _git_state(repo_root)
    pytest_check = _run_pytest(repo_root) if run_pytest else None
    evaluation = evaluate_file(cases_path, reports_dir / "evaluation_report.md")
    equivalence = verify_sql_equivalence(equivalence_dsl, data_dir)
    (reports_dir / "sql_equivalence_report.md").write_text(equivalence.to_markdown(), encoding="utf-8")
    benchmark = benchmark_prefix_sum_file(
        benchmark_dsl,
        data_dir,
        reports_dir / "prefix_sum_benchmark.md",
        iterations=benchmark_iterations,
    )
    doris_assets = _check_doris_assets(repo_root, data_dir)
    scale_report = _check_evidence_file(
        "long-window scale benchmark",
        reports_dir / "prefix_sum_scale_benchmark.md",
        [
            "Prefix-Sum Scale Benchmark",
            "Optimized matches Pandas reference: True",
            "Optimized matches baseline: True",
            "Long-window feature-access reduction estimate",
        ],
    )
    doris_cluster_report = _check_evidence_file(
        "Doris cluster evidence",
        reports_dir / "doris_cluster_evidence.md",
        [
            "Doris Cluster Evidence",
            "Evidence source: Apache Doris MySQL-compatible query port",
            "Evidence passed: True",
            "Baseline success: True",
            "Optimized success: True",
            "Row counts match: True",
            "Minimum Doris speedup target: 10.00x",
            "Doris speedup target met: True",
            "Optimized plan contains prefix table: True",
            "Baseline plan contains window: True",
        ],
    )
    demo_smoke = _check_demo_smoke(data_dir)
    nl2dsl_smoke = _check_nl2dsl_smoke(data_dir)
    llm_safety_smoke = _check_llm_safety_smoke(repo_root, data_dir)
    diagnostics_smoke = _check_diagnostics_smoke()
    official_suite = run_official_suite(
        positive_cases_path=repo_root / "data" / "samples" / "official_positive_cases.jsonl",
        negative_cases_path=repo_root / "data" / "samples" / "official_negative_cases.jsonl",
        data_dir=data_dir,
        output_path=reports_dir / "official_suite_report.md",
    )
    defense_package = generate_defense_package(
        output_path=reports_dir / "defense_package.md",
        data_dir=data_dir,
        cases_path=cases_path,
        official_positive_path=repo_root / "data" / "samples" / "official_positive_cases.jsonl",
        official_negative_path=repo_root / "data" / "samples" / "official_negative_cases.jsonl",
        repo_root=repo_root,
    )
    report = ReadinessReport(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        repo_root=repo_root,
        output_path=output_path,
        reports_dir=reports_dir,
        git=git,
        pytest=pytest_check,
        evaluation=evaluation,
        equivalence=equivalence,
        benchmark=benchmark,
        doris_assets=doris_assets,
        scale_report=scale_report,
        doris_cluster_report=doris_cluster_report,
        demo_smoke=demo_smoke,
        nl2dsl_smoke=nl2dsl_smoke,
        llm_safety_smoke=llm_safety_smoke,
        diagnostics_smoke=diagnostics_smoke,
        official_suite=official_suite,
        defense_package=defense_package,
        gates=_build_gates(
            git,
            pytest_check,
            evaluation,
            equivalence,
            benchmark,
            doris_assets,
            scale_report,
            doris_cluster_report,
            demo_smoke,
            nl2dsl_smoke,
            llm_safety_smoke,
            diagnostics_smoke,
            official_suite,
            defense_package,
            run_pytest,
        ),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.to_markdown(), encoding="utf-8")
    return report


def _build_gates(
    git: GitState,
    pytest_check: Optional[CommandCheck],
    evaluation: EvaluationResult,
    equivalence: EquivalenceResult,
    benchmark: PrefixSumBenchmarkResult,
    doris_assets: List[DorisAssetCheck],
    scale_report: EvidenceFileCheck,
    doris_cluster_report: EvidenceFileCheck,
    demo_smoke: DemoSmokeCheck,
    nl2dsl_smoke: NL2DSLSmokeCheck,
    llm_safety_smoke: LLMSafetySmokeCheck,
    diagnostics_smoke: DiagnosticsSmokeCheck,
    official_suite: OfficialSuiteResult,
    defense_package: DefensePackageResult,
    run_pytest: bool,
) -> List[ReadinessGate]:
    gates = [
        ReadinessGate(
            "Pytest regression suite",
            "required" if run_pytest else "warning",
            pytest_check.passed if pytest_check else False,
            _pytest_evidence(pytest_check, run_pytest),
        ),
        ReadinessGate(
            "Compiler accuracy and latency",
            "required",
            evaluation.failed == 0
            and evaluation.compile_success_rate == 1.0
            and evaluation.fragment_accuracy == 1.0
            and evaluation.p95_elapsed_ms < 50,
            (
                f"{evaluation.passed}/{evaluation.total} cases, "
                f"fragments {evaluation.fragment_accuracy:.2%}, "
                f"P95 {evaluation.p95_elapsed_ms:.3f} ms"
            ),
        ),
        ReadinessGate(
            "SQL/reference equivalence",
            "required",
            equivalence.passed,
            (
                f"SQL rows {equivalence.sql_row_count}, reference rows {equivalence.reference_row_count}, "
                f"missing {len(equivalence.missing_keys)}, extra {len(equivalence.extra_keys)}"
            ),
        ),
        ReadinessGate(
            "Prefix optimizer correctness",
            "required",
            benchmark.optimized_matches_reference and benchmark.optimized_matches_baseline,
            (
                f"matches reference {benchmark.optimized_matches_reference}, "
                f"matches baseline {benchmark.optimized_matches_baseline}"
            ),
        ),
        ReadinessGate(
            "Prefix optimizer plan shape",
            "required",
            benchmark.baseline_window_frames >= 1 and benchmark.optimized_prefix_joins >= 1,
            (
                f"baseline window frames {benchmark.baseline_window_frames}, "
                f"optimized prefix references {benchmark.optimized_prefix_joins}"
            ),
        ),
        ReadinessGate(
            "Demo API smoke",
            "required",
            demo_smoke.passed,
            (
                f"verification {demo_smoke.verification_passed}, "
                f"compile {demo_smoke.compile_elapsed_ms:.3f} ms, rows {demo_smoke.sql_row_count}"
            )
            if demo_smoke.passed
            else demo_smoke.error,
        ),
        ReadinessGate(
            "NL2DSL validated candidate",
            "required",
            nl2dsl_smoke.passed,
            (
                f"candidates {nl2dsl_smoke.candidate_count}, "
                f"validated {nl2dsl_smoke.top_validated}, "
                f"verification {nl2dsl_smoke.verification_passed}, rows {nl2dsl_smoke.sql_row_count}"
            )
            if nl2dsl_smoke.passed
            else nl2dsl_smoke.error,
        ),
        ReadinessGate(
            "LLM candidate safety loop",
            "required",
            llm_safety_smoke.passed,
            (
                f"accepted {llm_safety_smoke.accepted_count}, "
                f"rejected {llm_safety_smoke.rejected_count}, "
                f"codes {', '.join(llm_safety_smoke.rejected_codes) or '<none>'}"
            )
            if llm_safety_smoke.passed
            else llm_safety_smoke.error,
        ),
        ReadinessGate(
            "Structured diagnostics repair hints",
            "required",
            diagnostics_smoke.passed,
            (
                f"diagnostics {diagnostics_smoke.diagnostic_count}, "
                f"first code {diagnostics_smoke.first_code}, "
                f"suggestions {diagnostics_smoke.suggestion_count}"
            )
            if diagnostics_smoke.passed
            else diagnostics_smoke.error,
        ),
        ReadinessGate(
            "Official-style coverage suite",
            "required",
            official_suite.passed,
            (
                f"positive {official_suite.positive_passed}/{official_suite.positive_total}, "
                f"negative {official_suite.negative_passed}/{official_suite.negative_total}"
            ),
        ),
        ReadinessGate(
            "Defense package walkthrough",
            "required",
            defense_package.passed,
            f"checks {defense_package.passed_count}/{defense_package.total}, report {defense_package.output_path}",
        ),
        ReadinessGate(
            "Doris asset integrity",
            "required",
            all(asset.passed for asset in doris_assets),
            f"{sum(1 for asset in doris_assets if asset.passed)}/{len(doris_assets)} generated assets match",
        ),
        ReadinessGate(
            "Long-window scale benchmark evidence",
            "warning",
            scale_report.passed,
            "report exists with correctness markers"
            if scale_report.passed
            else f"missing markers: {', '.join(scale_report.missing_markers) or 'file missing'}",
        ),
        ReadinessGate(
            "Git rollback cleanliness",
            "warning",
            git.is_clean,
            "clean working tree" if git.is_clean else f"{len(git.dirty_entries)} dirty entries before commit",
        ),
        ReadinessGate(
            "Doris-scale performance proof",
            "warning",
            doris_cluster_report.passed,
            "cluster EXPLAIN/latency and 10x speedup evidence captured"
            if doris_cluster_report.passed
            else f"missing markers: {', '.join(doris_cluster_report.missing_markers) or 'file missing'}",
        ),
    ]
    return gates


def _pytest_evidence(pytest_check: Optional[CommandCheck], run_pytest: bool) -> str:
    if not run_pytest:
        return "skipped for this run"
    if pytest_check is None:
        return "not executed"
    return f"exit {pytest_check.exit_code}, elapsed {pytest_check.elapsed_ms:.1f} ms"


def _run_pytest(repo_root: Path) -> CommandCheck:
    command = [sys.executable, "-m", "pytest"]
    env = os.environ.copy()
    src_path = str(repo_root / "src")
    env["PYTHONPATH"] = src_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    return CommandCheck(
        name="pytest",
        command=command,
        exit_code=completed.returncode,
        elapsed_ms=elapsed_ms,
        stdout_tail=_tail(completed.stdout),
        stderr_tail=_tail(completed.stderr),
    )


def _check_doris_assets(repo_root: Path, data_dir: Path) -> List[DorisAssetCheck]:
    assets = render_doris_assets(data_dir)
    asset_dir = repo_root / "deploy" / "doris"
    checks = []
    for filename, expected in assets.files().items():
        path = asset_dir / filename
        exists = path.exists()
        actual = path.read_text(encoding="utf-8") if exists else ""
        checks.append(
            DorisAssetCheck(
                filename=filename,
                path=path,
                exists=exists,
                matches_generated=exists and actual == expected,
                byte_count=path.stat().st_size if exists else 0,
            )
        )
    return checks


def _check_demo_smoke(data_dir: Path) -> DemoSmokeCheck:
    try:
        result = analyze_dsl(DEFAULT_DEMO_DSL, data_dir=data_dir, enable_prefix_sum=True, verify=True)
        verification = result["verification"] or {}
        verification_passed = bool(verification.get("passed"))
        compile_elapsed_ms = float(result["compile"]["elapsed_ms"])
        sql_row_count = int(verification.get("sql_row_count", 0))
        return DemoSmokeCheck(
            dsl=DEFAULT_DEMO_DSL,
            passed=bool(result.get("ok")) and verification_passed,
            compile_elapsed_ms=compile_elapsed_ms,
            verification_passed=verification_passed,
            sql_row_count=sql_row_count,
        )
    except Exception as exc:  # noqa: BLE001 - readiness should report smoke failures.
        return DemoSmokeCheck(
            dsl=DEFAULT_DEMO_DSL,
            passed=False,
            compile_elapsed_ms=0.0,
            verification_passed=False,
            sql_row_count=0,
            error=f"{type(exc).__name__}: {exc}",
        )


def _check_nl2dsl_smoke(data_dir: Path) -> NL2DSLSmokeCheck:
    try:
        result = suggest_from_text(DEFAULT_NL_REQUEST, data_dir=data_dir, enable_prefix_sum=True, verify=True)
        candidates = result.get("candidates", [])
        top = candidates[0] if candidates else {}
        analysis = top.get("analysis") or {}
        verification = analysis.get("verification") or {}
        top_validated = bool(top.get("validated"))
        verification_passed = bool(verification.get("passed"))
        sql_row_count = int(verification.get("sql_row_count", 0))
        return NL2DSLSmokeCheck(
            text=DEFAULT_NL_REQUEST,
            passed=bool(result.get("ok")) and bool(candidates) and top_validated and verification_passed,
            candidate_count=len(candidates),
            top_dsl=str(top.get("dsl", "")),
            top_validated=top_validated,
            verification_passed=verification_passed,
            sql_row_count=sql_row_count,
        )
    except Exception as exc:  # noqa: BLE001 - readiness should report smoke failures.
        return NL2DSLSmokeCheck(
            text=DEFAULT_NL_REQUEST,
            passed=False,
            candidate_count=0,
            top_dsl="",
            top_validated=False,
            verification_passed=False,
            sql_row_count=0,
            error=f"{type(exc).__name__}: {exc}",
        )


def _check_llm_safety_smoke(repo_root: Path, data_dir: Path) -> LLMSafetySmokeCheck:
    response_path = _resolve(repo_root, DEFAULT_LLM_CANDIDATE_RESPONSE)
    try:
        result = validate_llm_candidates(
            text="近3日成交量累计大于300",
            payload=response_path.read_text(encoding="utf-8"),
            data_dir=data_dir,
            enable_prefix_sum=True,
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
            result.raw_candidate_count >= 3
            and result.accepted_count >= 1
            and result.rejected_count >= 2
            and accepted_verified
            and "UNSAFE_DIRECT_SQL" in rejected_codes
            and "UNKNOWN_INDICATOR" in rejected_codes
        )
        return LLMSafetySmokeCheck(
            response_path=response_path,
            passed=passed,
            raw_candidate_count=result.raw_candidate_count,
            accepted_count=result.accepted_count,
            rejected_count=result.rejected_count,
            rejected_codes=rejected_codes,
            accepted_verified=accepted_verified,
            error="" if passed else "LLM safety sample did not cover accept/reject/diagnostic evidence",
        )
    except Exception as exc:  # noqa: BLE001 - readiness should report smoke failures.
        return LLMSafetySmokeCheck(
            response_path=response_path,
            passed=False,
            raw_candidate_count=0,
            accepted_count=0,
            rejected_count=0,
            rejected_codes=[],
            accepted_verified=False,
            error=f"{type(exc).__name__}: {exc}",
        )


def _check_diagnostics_smoke() -> DiagnosticsSmokeCheck:
    dsl = 'filter(indicator("clos") > 10)'
    try:
        Compiler().compile(dsl)
        return DiagnosticsSmokeCheck(
            dsl=dsl,
            passed=False,
            diagnostic_count=0,
            first_code="",
            suggestion_count=0,
            error="invalid DSL unexpectedly compiled",
        )
    except Exception as exc:  # noqa: BLE001 - readiness should report diagnostic failures.
        diagnostics = diagnose_exception(exc)
        suggestions = [hint for item in diagnostics for hint in item.suggestions]
        first_code = diagnostics[0].code if diagnostics else ""
        passed = (
            first_code == "UNKNOWN_INDICATOR"
            and bool(suggestions)
            and any('indicator("close")' in hint for hint in suggestions)
        )
        return DiagnosticsSmokeCheck(
            dsl=dsl,
            passed=passed,
            diagnostic_count=len(diagnostics),
            first_code=first_code,
            suggestion_count=len(suggestions),
            error="" if passed else f"{type(exc).__name__}: {exc}",
        )


def _check_evidence_file(name: str, path: Path, markers: List[str]) -> EvidenceFileCheck:
    exists = path.exists()
    content = path.read_text(encoding="utf-8") if exists else ""
    matched = [marker for marker in markers if marker in content]
    missing = [marker for marker in markers if marker not in content]
    return EvidenceFileCheck(
        name=name,
        path=path,
        exists=exists,
        byte_count=path.stat().st_size if exists else 0,
        matched_markers=matched,
        missing_markers=missing,
    )


def _git_state(repo_root: Path) -> GitState:
    branch = _git(repo_root, ["branch", "--show-current"]).strip()
    commit = _git(repo_root, ["rev-parse", "--short", "HEAD"]).strip()
    subject = _git(repo_root, ["log", "-1", "--pretty=%s"]).strip()
    status = _git(repo_root, ["status", "--short"]).splitlines()
    is_repo = bool(commit)
    return GitState(
        is_repo=is_repo,
        branch=branch or "<detached>",
        commit=commit or "<unknown>",
        commit_subject=subject,
        dirty_entries=status,
    )


def _git(repo_root: Path, args: List[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout


def _resolve(repo_root: Path, path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else repo_root / path


def _tail(text: str, max_lines: int = 40) -> str:
    lines = text.strip().splitlines()
    return "\n".join(lines[-max_lines:])

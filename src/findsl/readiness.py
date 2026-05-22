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
from .doris import render_doris_assets
from .equivalence import EquivalenceResult, verify_sql_equivalence
from .evaluation import EvaluationResult, evaluate_file


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
                "",
                "## Evidence Artifacts",
                "",
                f"- Readiness report: `{self.output_path}`",
                f"- Evaluation report: `{self.reports_dir / 'evaluation_report.md'}`",
                f"- SQL equivalence report: `{self.reports_dir / 'sql_equivalence_report.md'}`",
                f"- Prefix benchmark report: `{self.reports_dir / 'prefix_sum_benchmark.md'}`",
                f"- Doris deployment directory: `{self.repo_root / 'deploy' / 'doris'}`",
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
                "- Prefix-sum rewrite path for long rolling windows with baseline/optimized evidence.",
                "- Structured optimizer explain records for defense and UI visualization.",
                "- Doris DDL, sample data, prefix-table build SQL, and smoke queries generated from the same registry.",
                "",
                "## Remaining High-Value Work",
                "",
                "- Capture Doris-cluster EXPLAIN and latency on larger synthetic or official-scale data before claiming 10x production acceleration.",
                "- Add a UI or API demo that visualizes DSL, AST, SQL, optimizer explain, and result tables for judges.",
                "- Broaden the DSL corpus with more official-style questions and negative/error cases.",
                "- Add an NL2DSL assistant layer that proposes DSL while the deterministic compiler remains the correctness gate.",
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
        gates=_build_gates(git, pytest_check, evaluation, equivalence, benchmark, doris_assets, run_pytest),
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
            "Doris asset integrity",
            "required",
            all(asset.passed for asset in doris_assets),
            f"{sum(1 for asset in doris_assets if asset.passed)}/{len(doris_assets)} generated assets match",
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
            False,
            "local SQLite benchmark exists; cluster EXPLAIN/latency evidence still needed",
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

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .ast_nodes import BinaryOp, Comparison, FunctionCall, NamedArg, Node
from .benchmark import PrefixSumBenchmarkResult, benchmark_prefix_sum
from .parser import parse
from .synthetic import SyntheticDataset, write_synthetic_dataset


DEFAULT_SCALE_DSL_TEMPLATE = 'filter(SUM(indicator("volume"), {window}) > {threshold})'


@dataclass(frozen=True)
class ScaleBenchmarkResult:
    dataset: SyntheticDataset
    dsl: str
    benchmark: PrefixSumBenchmarkResult
    output_path: Path

    @property
    def max_sum_window(self) -> int:
        return _max_sum_window(self.dsl)

    @property
    def estimated_feature_work_reduction(self) -> float:
        window = self.max_sum_window
        if window <= 0:
            return 1.0
        return window / 2

    def to_markdown(self) -> str:
        lines = [
            "# Prefix-Sum Scale Benchmark",
            "",
            "## Dataset",
            "",
            f"- Data directory: `{self.dataset.output_dir}`",
            f"- Stock count: {self.dataset.stock_count}",
            f"- Day count: {self.dataset.day_count}",
            f"- Rows per base table: {self.dataset.row_count}",
            f"- Seed: {self.dataset.seed}",
            f"- Start date: {self.dataset.start_date}",
            "",
            "## Query",
            "",
            "```text",
            self.dsl,
            "```",
            "",
            "## Correctness Gates",
            "",
            f"- Baseline matches Pandas reference: {self.benchmark.baseline_matches_reference}",
            f"- Optimized matches Pandas reference: {self.benchmark.optimized_matches_reference}",
            f"- Optimized matches baseline: {self.benchmark.optimized_matches_baseline}",
            "",
            "## Performance Signals",
            "",
            f"- Iterations: {self.benchmark.iterations}",
            f"- Local SQLite speedup smoke: {self.benchmark.local_speedup:.2f}x",
            f"- Baseline avg execute ms: {self.benchmark.baseline.avg_execute_ms:.3f}",
            f"- Optimized avg execute ms: {self.benchmark.optimized.avg_execute_ms:.3f}",
            f"- Baseline P95 execute ms: {self.benchmark.baseline.p95_execute_ms:.3f}",
            f"- Optimized P95 execute ms: {self.benchmark.optimized.p95_execute_ms:.3f}",
            f"- Baseline window frame count: {self.benchmark.baseline_window_frames}",
            f"- Optimized prefix table references: {self.benchmark.optimized_prefix_joins}",
            f"- Long-window feature-access reduction estimate: {self.estimated_feature_work_reduction:.1f}x",
            "",
            "Local SQLite timing is a smoke/regression and plan-shape signal. The reduction estimate compares a "
            "window-length rolling scan with two prefix-table lookups per row; final 10x production claims "
            "must be backed by Doris EXPLAIN and cluster latency.",
            "",
            "## Variant Metrics",
            "",
            "| Variant | Compile ms | Avg execute ms | P50 execute ms | P95 execute ms | Rows |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for variant in [self.benchmark.baseline, self.benchmark.optimized]:
            lines.append(
                f"| {variant.name} | {variant.compile_ms:.3f} | {variant.avg_execute_ms:.3f} | "
                f"{variant.p50_execute_ms:.3f} | {variant.p95_execute_ms:.3f} | {variant.row_count} |"
            )
        lines.extend(["", "## Optimizer Explain", ""])
        for variant in [self.benchmark.baseline, self.benchmark.optimized]:
            lines.append(f"### {variant.name}")
            if variant.explain:
                lines.extend(
                    f"- `{step['rule']}` {step['status']}: {step['message']}" for step in variant.explain
                )
            else:
                lines.append("- <none>")
            lines.append("")
        lines.extend(
            [
                "## Generated SQL",
                "",
                "### baseline_window",
                "",
                "```sql",
                self.benchmark.baseline.sql,
                "```",
                "",
                "### optimized_prefix_sum",
                "",
                "```sql",
                self.benchmark.optimized.sql,
                "```",
            ]
        )
        return "\n".join(lines)


def run_scale_benchmark(
    output_path: Path,
    data_dir: Path = Path("data/generated/scale"),
    stock_count: int = 300,
    day_count: int = 260,
    start_date: str = "2025-01-01",
    seed: int = 2026,
    window: int = 120,
    threshold: Optional[int] = None,
    iterations: int = 5,
    dsl: Optional[str] = None,
) -> ScaleBenchmarkResult:
    if window <= 0:
        raise ValueError("window must be positive")
    if threshold is None:
        threshold = window * 3500
    dataset = write_synthetic_dataset(
        output_dir=Path(data_dir),
        stock_count=stock_count,
        day_count=day_count,
        start_date=start_date,
        seed=seed,
    )
    query = dsl or DEFAULT_SCALE_DSL_TEMPLATE.format(window=window, threshold=threshold)
    benchmark = benchmark_prefix_sum(query, dataset.output_dir, iterations=iterations)
    result = ScaleBenchmarkResult(
        dataset=dataset,
        dsl=query,
        benchmark=benchmark,
        output_path=Path(output_path),
    )
    result.output_path.parent.mkdir(parents=True, exist_ok=True)
    result.output_path.write_text(result.to_markdown(), encoding="utf-8")
    return result


def _max_sum_window(dsl: str) -> int:
    ast = parse(dsl)
    windows = []

    def visit(node: Node) -> None:
        if isinstance(node, FunctionCall):
            if node.name.upper() == "SUM" and len(node.args) >= 2:
                window = node.args[1]
                value = getattr(window, "value", None)
                if isinstance(value, int):
                    windows.append(value)
            for arg in node.args:
                visit(arg)
            for named in node.named_args or []:
                visit_named(named)
        elif isinstance(node, (BinaryOp, Comparison)):
            visit(node.left)
            visit(node.right)

    def visit_named(named: NamedArg) -> None:
        visit(named.value)

    visit(ast)
    return max(windows) if windows else 0

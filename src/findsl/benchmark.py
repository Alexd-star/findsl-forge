from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, List, Tuple

from .compiler import Compiler
from .evaluation import _percentile
from .executor import SQLiteSampleExecutor
from .reference import PandasReferenceEvaluator

ResultKey = Tuple[str, str]


@dataclass(frozen=True)
class BenchmarkVariant:
    name: str
    sql: str
    trace: List[str]
    explain: List[Dict[str, Any]]
    compile_ms: float
    execute_ms: List[float]
    keys: List[ResultKey]

    @property
    def row_count(self) -> int:
        return len(self.keys)

    @property
    def avg_execute_ms(self) -> float:
        return mean(self.execute_ms) if self.execute_ms else 0.0

    @property
    def p50_execute_ms(self) -> float:
        return median(self.execute_ms) if self.execute_ms else 0.0

    @property
    def p95_execute_ms(self) -> float:
        return _percentile(self.execute_ms, 95) if self.execute_ms else 0.0


@dataclass(frozen=True)
class PrefixSumBenchmarkResult:
    dsl: str
    iterations: int
    baseline: BenchmarkVariant
    optimized: BenchmarkVariant
    reference_keys: List[ResultKey]

    @property
    def baseline_matches_reference(self) -> bool:
        return self.baseline.keys == self.reference_keys

    @property
    def optimized_matches_reference(self) -> bool:
        return self.optimized.keys == self.reference_keys

    @property
    def optimized_matches_baseline(self) -> bool:
        return self.optimized.keys == self.baseline.keys

    @property
    def local_speedup(self) -> float:
        if self.optimized.avg_execute_ms <= 0:
            return 0.0
        return self.baseline.avg_execute_ms / self.optimized.avg_execute_ms

    @property
    def baseline_window_frames(self) -> int:
        return self.baseline.sql.count("ROWS BETWEEN")

    @property
    def optimized_prefix_joins(self) -> int:
        return self.optimized.sql.count("_prefix")

    def to_markdown(self) -> str:
        lines = [
            "# Prefix-Sum Benchmark Report",
            "",
            "## Summary",
            "",
            f"- Iterations: {self.iterations}",
            f"- Baseline matches reference: {self.baseline_matches_reference}",
            f"- Optimized matches reference: {self.optimized_matches_reference}",
            f"- Optimized matches baseline: {self.optimized_matches_baseline}",
            f"- Local SQLite speedup: {self.local_speedup:.2f}x",
            f"- Baseline window frame count: {self.baseline_window_frames}",
            f"- Optimized prefix table references: {self.optimized_prefix_joins}",
            "",
            "Local SQLite timing is a regression signal, not a Doris-scale performance claim.",
            "The plan-level comparison shows whether the compiler replaced rolling window aggregation with prefix lookups.",
            "",
            "## DSL",
            "",
            "```text",
            self.dsl,
            "```",
            "",
            "## Variant Metrics",
            "",
            "| Variant | Compile ms | Avg execute ms | P50 execute ms | P95 execute ms | Rows |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for variant in [self.baseline, self.optimized]:
            lines.append(
                f"| {variant.name} | {variant.compile_ms:.3f} | {variant.avg_execute_ms:.3f} | "
                f"{variant.p50_execute_ms:.3f} | {variant.p95_execute_ms:.3f} | {variant.row_count} |"
            )
        lines.extend(["", "## Generated SQL", ""])
        for variant in [self.baseline, self.optimized]:
            lines.extend(
                [
                    f"### {variant.name}",
                    "",
                    "```sql",
                    variant.sql,
                    "```",
                    "",
                    "Trace:",
                ]
            )
            lines.extend(f"- {item}" for item in variant.trace)
            lines.append("")
            lines.append("Explain:")
            if variant.explain:
                lines.extend(
                    f"- `{step['rule']}` {step['status']}: {step['message']}" for step in variant.explain
                )
            else:
                lines.append("- <none>")
            lines.append("")
        return "\n".join(lines)


def benchmark_prefix_sum(dsl: str, data_dir: Path, iterations: int = 20) -> PrefixSumBenchmarkResult:
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    reference_keys = sorted(PandasReferenceEvaluator(data_dir).evaluate(dsl).keys())
    baseline = _measure_variant("baseline_window", dsl, data_dir, enable_prefix_sum=False, iterations=iterations)
    optimized = _measure_variant("optimized_prefix_sum", dsl, data_dir, enable_prefix_sum=True, iterations=iterations)
    return PrefixSumBenchmarkResult(
        dsl=dsl,
        iterations=iterations,
        baseline=baseline,
        optimized=optimized,
        reference_keys=reference_keys,
    )


def benchmark_prefix_sum_file(
    dsl: str,
    data_dir: Path,
    output_path: Path,
    iterations: int = 20,
) -> PrefixSumBenchmarkResult:
    result = benchmark_prefix_sum(dsl, data_dir, iterations=iterations)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.to_markdown(), encoding="utf-8")
    return result


def _measure_variant(
    name: str,
    dsl: str,
    data_dir: Path,
    enable_prefix_sum: bool,
    iterations: int,
) -> BenchmarkVariant:
    compiler = Compiler(enable_prefix_sum=enable_prefix_sum)
    compiled = compiler.compile(dsl)
    execute_ms = []
    keys: List[ResultKey] = []
    with SQLiteSampleExecutor(data_dir, compiler.registry) as executor:
        for _ in range(iterations):
            started = time.perf_counter()
            result = executor.execute(compiled.sql)
            execute_ms.append((time.perf_counter() - started) * 1000)
            keys = sorted(result.keys())
    return BenchmarkVariant(
        name=name,
        sql=compiled.sql,
        trace=compiled.trace,
        explain=compiled.explain,
        compile_ms=compiled.elapsed_ms,
        execute_ms=execute_ms,
        keys=keys,
    )

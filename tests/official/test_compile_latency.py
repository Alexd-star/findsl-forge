from pathlib import Path
from types import SimpleNamespace

from findsl.official.compile_latency import run_compile_latency_benchmark
from findsl.official.context import CompileContext
from findsl.official.performance import PerformanceCase


ROOT = Path(__file__).resolve().parents[2]


def test_compile_latency_gate_uses_canonical_case_and_stage_timings() -> None:
    calls = 0

    def compiler(dsl, *, context):
        nonlocal calls
        calls += 1
        elapsed = float((calls % 4) + 1)
        return SimpleNamespace(
            elapsed_ms=elapsed,
            timings_ns={"frontend": 250_000, "backend": 500_000, "total": int(elapsed * 1_000_000)},
            physical={"selected_strategy": "direct_column"},
        )

    report = run_compile_latency_benchmark(
        (
            PerformanceCase(
                "P1",
                "dsl",
                ("indicator",),
                "direct_column",
                "light",
                "ref.sql",
                True,
            ),
        ),
        context=CompileContext.load(ROOT),
        compiler=compiler,
        warmups=1,
        repeats=4,
        target_p95_ms=5.0,
    )

    assert report["target_met"] is True
    assert report["case_count"] == 1
    assert report["sample_count"] == 4
    assert report["p95_ms"] == 4.0
    assert report["stage_p95_ms"]["backend"] == 0.5
    assert report["results"][0]["selected_strategy"] == "direct_column"

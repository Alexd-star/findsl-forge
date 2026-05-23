from pathlib import Path

from findsl.benchmark import benchmark_prefix_sum, benchmark_prefix_sum_file


DATA_DIR = Path("data/samples")


def test_prefix_sum_benchmark_compares_baseline_and_optimized_sql(tmp_path):
    result = benchmark_prefix_sum(
        'filter(SUM(indicator("volume"), 3) > 300)',
        DATA_DIR,
        iterations=2,
    )
    assert result.baseline_matches_reference
    assert result.optimized_matches_reference
    assert result.optimized_matches_baseline
    assert "SUM(volume) OVER" in result.baseline.sql
    assert "dwd_stock_daily_quote_prefix" in result.optimized.sql
    assert result.baseline_window_frames >= 1
    assert result.optimized_prefix_joins >= 1
    assert result.baseline.explain[0]["rule"] == "PREFIX_SUM"
    assert result.baseline.explain[0]["status"] == "skipped"
    assert result.optimized.explain[0]["rule"] == "PREFIX_SUM"
    assert result.optimized.explain[0]["status"] == "applied"

    output = tmp_path / "prefix_sum_benchmark.md"
    written = benchmark_prefix_sum_file(
        'filter(SUM(indicator("volume"), 3) > 300)',
        DATA_DIR,
        output,
        iterations=1,
    )
    assert written.optimized_matches_baseline
    report = output.read_text(encoding="utf-8")
    assert "Prefix-Sum Benchmark Report" in report
    assert "Local SQLite speedup smoke" in report
    assert "`PREFIX_SUM` applied" in report

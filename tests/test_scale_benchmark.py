from findsl.scale_benchmark import run_scale_benchmark


def test_run_scale_benchmark_generates_long_window_report(tmp_path):
    output = tmp_path / "scale_report.md"
    result = run_scale_benchmark(
        output_path=output,
        data_dir=tmp_path / "scale_data",
        stock_count=6,
        day_count=16,
        window=8,
        threshold=12000,
        iterations=1,
        seed=11,
    )

    assert result.dataset.row_count == 96
    assert result.benchmark.baseline_matches_reference
    assert result.benchmark.optimized_matches_reference
    assert result.benchmark.optimized_matches_baseline
    assert result.benchmark.baseline_window_frames >= 1
    assert result.benchmark.optimized_prefix_joins >= 1
    assert result.max_sum_window == 8
    assert result.estimated_feature_work_reduction == 4.0
    assert output.exists()

    report = output.read_text(encoding="utf-8")
    assert "Prefix-Sum Scale Benchmark" in report
    assert "Long-window feature-access reduction estimate: 4.0x" in report
    assert "must be backed by Doris EXPLAIN" in report

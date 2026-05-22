from pathlib import Path

from findsl.evaluation import evaluate_file


def test_sample_evaluation_passes(tmp_path):
    output = tmp_path / "report.md"
    result = evaluate_file(Path("data/samples/queries.jsonl"), output)
    assert result.total >= 4
    assert result.failed == 0
    assert result.compile_success_rate == 1.0
    assert result.fragment_accuracy == 1.0
    assert result.p95_elapsed_ms < 50
    assert output.exists()
    report = output.read_text(encoding="utf-8")
    assert "FinDSL Forge Evaluation Report" in report
    assert "Explain:" in report
    assert "`PREFIX_SUM` applied" in report

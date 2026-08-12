from __future__ import annotations

from pathlib import Path

from findsl.official.backend.executor import DorisExecutionResult, DorisExplainResult
from findsl.official.hero import run_hero_query, write_hero_report


def test_hero_query_covers_the_declared_complex_capabilities() -> None:
    report = run_hero_query(Path("data/hero/hero_query.json").resolve())

    assert report["gate"]["compile_and_feature_gate"]
    assert report["query_features"]["temporal_modes"] == ["CONS", "EXIST"]
    assert report["query_features"]["has_interval"]
    assert report["query_features"]["has_bitwise_alias"]
    assert report["selected_strategy"] == "stage_rank"


def test_hero_query_requires_full_row_set_equivalence_and_runtime_target() -> None:
    rows = (("1", "600000", "2026-04-14"),)
    result = DorisExecutionResult(rows, 12.0, "ordered", "same-hash")
    report = run_hero_query(
        Path("data/hero/hero_query.json").resolve(),
        doris=object(),
        executor=lambda _config, _sql: result,
        explainer=lambda _config, _sql: DorisExplainResult("PLAN FRAGMENT", 1.0),
    )

    assert report["execution"]["result_equivalent"]
    assert report["execution"]["under_10_seconds"]
    assert report["gate"]["passed"]

def test_hero_query_source_and_report_preserve_readable_chinese(tmp_path: Path) -> None:
    report = run_hero_query(Path("data/hero/hero_query.json").resolve())
    json_path = tmp_path / "hero.json"
    markdown_path = tmp_path / "hero.md"

    write_hero_report(report, json_path, markdown_path)

    content = markdown_path.read_text(encoding="utf-8")
    assert report["title"] == "双时间量词筛选后的分阶段稳定排名"
    assert "成交量" in report["dsl"]
    assert "Hero Query 端到端证据" in content
    assert "复杂能力核验" in content
    assert not any(token in content for token in ("Ã", "Â", "å", "æ—"))

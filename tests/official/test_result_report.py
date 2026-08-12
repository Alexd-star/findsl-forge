from __future__ import annotations

from findsl.official.pipeline import compile_official
from findsl.official.result_report import render_compilation_result_markdown


def test_product_markdown_result_contains_auditable_compiler_evidence() -> None:
    result = compile_official(
        "indicator('', '', '成交量', '近5000日', '', 'SUM', '') > 10000000"
    )

    markdown = render_compilation_result_markdown(result.to_dict())

    assert "# FinDSL Forge 编译结果" in markdown
    assert "## 自适应路由候选" in markdown
    assert "PREFIX" in markdown
    assert "FR-ROUTE-001" in markdown
    assert "```sql" in markdown
    assert "执行时间不超过" not in markdown


def test_product_markdown_result_includes_runtime_target_when_executed() -> None:
    result = compile_official(
        "indicator('', '', '成交量', '今日', '', '', '') > 0"
    )

    markdown = render_compilation_result_markdown(
        result.to_dict(),
        execution={"row_count": 3, "elapsed_ms": 25.0, "unordered_hash": "abc"},
    )

    assert "## Doris 执行结果" in markdown
    assert "不超过 10 秒：`True`" in markdown

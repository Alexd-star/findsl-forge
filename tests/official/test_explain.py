from __future__ import annotations

from findsl.official.explain import render_explain_markdown
from findsl.official.optimizer import DEFAULT_RULES, validate_rule_contracts
from findsl.official.pipeline import compile_official


def test_findsl_explain_covers_all_compiler_stages_and_route_families() -> None:
    result = compile_official(
        "indicator('', '', '成交量', '近5000日', '', 'SUM', '') > 10000000"
    )
    explain = result.explain

    assert [item["stage"] for item in explain["stages"]] == [
        "Parser",
        "Semantic",
        "Logical IR",
        "Rewrite",
        "Route",
        "Doris SQL",
    ]
    route = explain["adaptive_route"]
    assert route["selected_route"] == "PREFIX"
    assert {item["route_kind"] for item in route["candidates"]} == {
        "RAW",
        "PARTITION",
        "MV",
        "PREFIX",
    }
    assert sum(bool(item["selected"]) for item in route["candidates"]) == 1
    assert route["planner"] == "AdaptiveRoutePlanner/v2"
    assert route["fallback_chain"] == ["PARTITION", "RAW"]
    assert route["selection_reason_code"] == "PHYSICAL_AGGREGATE_ACCELERATION_SELECTED"
    assert route["selected_candidate_id"].startswith("prefix:")
    selected = next(item for item in route["candidates"] if item["selected"])
    assert selected["semantic_equivalence"] == "proven_equivalent"
    assert selected["watermark_status"] == "compatible"
    assert selected["cost_components"]
    assert {check["check_id"] for check in selected["eligibility_checks"]} == {
        "physical_plan_generated",
        "semantic_equivalence",
        "freshness_watermark",
        "selection_policy",
    }
    assert all(check["status"] == "PASS" for check in selected["eligibility_checks"])
    assert any(
        item["rule_id"] == "FR-ROUTE-001"
        for item in explain["applied_financial_rules"]
    )
    assert result.timings_ns["explain"] > 0


def test_findsl_explain_models_composite_subplans_as_one_top_level_route() -> None:
    result = compile_official(
        "cross_above('', '', '5日均线', '20日均线', '今日', '', '') = True "
        "and indicator('', '', '成交量', '昨日', '', '', '') > 0"
    )
    candidates = result.explain["adaptive_route"]["candidates"]

    assert sum(bool(item["selected"]) for item in candidates) == 1
    selected = next(item for item in candidates if item["selected"])
    assert selected["source"] == "physical_composite_decision"
    assert any(item["source"] == "physical_subplan_decision" for item in candidates)
    assert result.explain["adaptive_route"]["fallback_candidates"] == []
    assert result.explain["adaptive_route"]["fallback_chain"] == []
    assert all(
        item["rejection_category"] == "subplan_component"
        for item in candidates
        if item["source"] == "physical_subplan_decision"
    )


def test_explain_markdown_contains_route_and_financial_rule_tables() -> None:
    explain = compile_official(
        "rank('', '', '成交量', 'desc', '今日', '', '', '') <= 10"
    ).explain

    markdown = render_explain_markdown(explain)

    assert "# FINDSL EXPLAIN" in markdown
    assert "## 查询特征" in markdown
    assert "## 自适应候选路由" in markdown
    assert "## 候选资格检查" in markdown
    assert "## 路由决策依据" in markdown
    assert "## 优化规则契约" in markdown
    assert "## 能证明什么" in markdown
    assert "## 不能证明什么" in markdown
    assert "FR-RANK-001" in markdown


def test_every_optimizer_rule_has_a_complete_contract() -> None:
    contracts = validate_rule_contracts(DEFAULT_RULES)

    assert len(contracts) == len(DEFAULT_RULES)
    assert all(item.preconditions for item in contracts)
    assert all(item.semantic_invariant for item in contracts)
    assert all(item.fallback for item in contracts)
    assert all(item.validation_strategy for item in contracts)

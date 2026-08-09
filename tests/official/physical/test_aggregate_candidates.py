import pytest

from findsl.official.pipeline import (
    OfficialPipelineError,
    OfficialPipelineOptions,
    compile_official,
)


def _source(window=20, function="SUM", indicator="成交量"):
    return (
        f"indicator('', '', '{indicator}', '近{window}日', '', "
        f"'{function}', '') > 10000000"
    )


def test_auto_rejects_row_window_materialization_for_global_session_semantics():
    result = compile_official(_source()).to_dict()

    assert result["physical"]["selected_strategy"] == "grouped_aggregate"
    materialized = next(
        item
        for item in result["physical"]["decisions"]
        if item["strategy_id"] == "volume_sum_20_materialized"
    )
    assert materialized["selection_eligible"] is False
    assert "SUM(`q`.`volume`)" in result["backend"]["sql"]
    assert result["backend"]["validation_passed"] is True


def test_long_window_uses_generic_prefix_endpoint_candidate():
    result = compile_official(_source(window=5000)).to_dict()

    assert result["physical"]["selected_strategy"] == "volume_prefix_aggregate"
    assert result["physical"]["plan"]["kind"] == "PhysicalPrefixAggregate"
    assert result["physical"]["plan"]["full_history"] is True
    assert "hsj_stock_hq_basic_rollup" in result["backend"]["sql"]
    assert "prefix_previous" not in result["backend"]["sql"]
    assert "`q`.`volume_prefix` > 10000000" in result["backend"]["sql"]
    assert "GROUP BY" not in result["backend"]["sql"]
    selected = next(
        decision
        for decision in result["physical"]["decisions"]
        if decision["selected"]
    )
    assert selected["cost_components"][-1] == ("access_multiplier", 1.0)
    assert "one partition-pruned full-history" in selected["reason"]


def test_force_candidate_exposes_short_window_candidate_for_validation_only():
    result = compile_official(
        _source(window=30, function="AVG"),
        OfficialPipelineOptions(strategy_mode="force_candidate"),
    ).to_dict()
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "volume_prefix_aggregate"
    assert "volume_count_prefix" in sql
    assert "NULLIF" in sql


def test_force_baseline_keeps_equivalent_grouped_plan():
    result = compile_official(
        _source(),
        OfficialPipelineOptions(strategy_mode="force_baseline"),
    ).to_dict()

    assert result["physical"]["selected_strategy"] == "grouped_aggregate"
    assert result["physical"]["plan"]["kind"] == "PhysicalGroupedAggregate"
    assert "SUM(`q`.`volume`)" in result["backend"]["sql"]
    assert "hsj_stock_hq_basic_rollup" not in result["backend"]["sql"]


def test_force_candidate_requires_a_non_baseline_candidate():
    with pytest.raises(ValueError):
        OfficialPipelineOptions(
            use_strategies=False,
            strategy_mode="force_candidate",
        )

    with pytest.raises(OfficialPipelineError) as excinfo:
        compile_official(
            "indicator('', '', '成交量', '2006年', '', 'SUM', '') > 0",
            OfficialPipelineOptions(strategy_mode="force_candidate"),
        )
    assert "no eligible non-baseline physical candidate" in str(excinfo.value)


def test_materialized_plan_retains_market_constraint():
    result = compile_official(
        "indicator('沪', '', '成交量', '近20日', '', 'SUM', '') > 100",
        OfficialPipelineOptions(strategy_mode="force_candidate"),
    ).to_dict()
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "volume_sum_20_materialized"
    assert "`q`.`mktcode` IN (1)" in sql


def test_candidate_decisions_preserve_baseline_and_rejected_alternatives():
    result = compile_official(_source()).to_dict()
    decisions = result["physical"]["decisions"]

    assert [item["strategy_id"] for item in decisions] == [
        "grouped_aggregate",
        "volume_sum_20_materialized",
        "volume_prefix_aggregate",
    ]
    assert sum(item["selected"] for item in decisions) == 1
    assert all(item["cost"] is not None for item in decisions)

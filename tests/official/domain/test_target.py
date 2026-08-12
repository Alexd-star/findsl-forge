from pathlib import Path

import pytest
import sqlglot
from sqlglot import exp

from findsl.official.context import CompileContext
from findsl.official.domain.target import (
    TargetAnd,
    TargetNot,
    TargetOr,
    TargetParseError,
    parse_target_expression,
)
from findsl.official.pipeline import OfficialPipelineError, compile_official


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_target_expression_preserves_union_intersection_and_exclusion() -> None:
    context = CompileContext.load(REPO_ROOT)
    expression = parse_target_expression(
        "ETF|LOF&^场内基金",
        {item.token: item for item in context.entity_target_catalog.definitions},
    )

    assert isinstance(expression, TargetOr)
    assert isinstance(expression.right, TargetAnd)
    assert isinstance(expression.right.right, TargetNot)
    assert expression.atoms == ("ETF", "LOF", "场内基金")


@pytest.mark.parametrize("source", ["ETF|", "ETF&&LOF", "未知资产"])
def test_target_expression_rejects_malformed_or_unknown_tokens(source) -> None:
    context = CompileContext.load(REPO_ROOT)

    with pytest.raises(TargetParseError):
        parse_target_expression(
            source,
            {item.token: item for item in context.entity_target_catalog.definitions},
        )


def test_target_catalog_exposes_typed_data_and_execution_contract() -> None:
    context = CompileContext.load(REPO_ROOT)
    target = context.entity_target_catalog.bind(
        "ETF&^场内基金",
        data_domains=context.data_domain_catalog,
        profile_id=context.snapshot.profile_id,
    )

    assert target.target_ids == ("etf", "exchange_fund")
    assert target.logical_entities == ("fund_observation",)
    assert target.execution_modes == ("fund_scan",)
    assert target.data_domain_statuses == (("fund_market_data", "not_loaded"),)


@pytest.mark.parametrize(
    "source,code",
    [
        (
            "indicator('', '', '涨幅', '今日', 'ETF', '', '') > 0",
            "PHYSICAL_ENTITY_DATA_UNAVAILABLE",
        ),
    ],
)
def test_pipeline_rejects_non_security_targets_with_precise_contract(source, code) -> None:
    context = CompileContext.load(REPO_ROOT)

    with pytest.raises(OfficialPipelineError) as excinfo:
        compile_official(source, context=context)

    assert excinfo.value.stage == "physical"
    assert excinfo.value.code == code


def test_index_target_reuses_registered_snapshot_and_index_codes() -> None:
    context = CompileContext.load(REPO_ROOT)
    result = compile_official(
        "indicator('', '', '涨幅', '今日', '指数', '', '') > 0",
        context=context,
    )

    assert result.physical["selected_resource"] == "external_index_quote_shape"
    sql = result.backend["sql"]
    assert "`findsl_ext`.`index_quote_security_shape`" in sql
    assert "`q`.`snapshot_id` IN" in sql
    assert "`q`.`tgtcode` IN ('000001', '000300', '399001')" in sql


def test_index_target_rejects_unmapped_indicator_instead_of_using_stock_field() -> None:
    context = CompileContext.load(REPO_ROOT)

    with pytest.raises(OfficialPipelineError) as excinfo:
        compile_official(
            "indicator('', '', '总市值', '今日', '指数', '', '') > 0",
            context=context,
        )

    assert excinfo.value.code == "PHYSICAL_ENTITY_INDICATOR_UNSUPPORTED"


def test_official_only_profile_rejects_index_target_as_missing_data() -> None:
    context = CompileContext.load(REPO_ROOT, data_profile="official_only")

    with pytest.raises(OfficialPipelineError) as excinfo:
        compile_official(
            "indicator('', '', '涨幅', '今日', '指数', '', '') > 0",
            context=context,
        )

    assert excinfo.value.code == "PHYSICAL_ENTITY_DATA_UNAVAILABLE"


def test_group_target_uses_explicit_metric_and_effective_membership_policy() -> None:
    context = CompileContext.load(REPO_ROOT)
    result = compile_official(
        "indicator('', '', '成交量', '今日', '行业', '', '') > 1000000",
        context=context,
    )

    assert result.physical["plan"]["kind"] == "PhysicalGroupEntityMetric"
    assert result.physical["selected_strategy"] == "group_entity_aggregate"
    sql = result.backend["sql"]
    assert "`findsl_ext`.`scope_membership`" in sql
    assert "SUM(`q`.`volume`)" in sql
    assert "`group_member`.`scope_type` IN ('industry')" in sql
    assert "`group_member`.`effective_from` <= `q`.`bizdate`" in sql
    assert "`group_member`.`effective_to` >= `q`.`bizdate`" in sql
    assert "`group_metrics`.`member_count` >= 2" in sql


def test_group_return_uses_float_market_cap_weighting_not_plain_average() -> None:
    context = CompileContext.load(REPO_ROOT)
    result = compile_official(
        "indicator('', '', '涨幅', '今日', '行业', '', '') > 0",
        context=context,
    )

    sql = result.backend["sql"]
    assert "SUM(CASE WHEN" in sql
    assert "(`q`.`lastPx` - `q`.`preClosePx`) * `q`.`listedShare`" in sql
    assert "`q`.`preClosePx` * `q`.`listedShare`" in sql
    assert "`q`.`preClosePx` <> 0" in sql
    assert "AVG(" not in sql


def test_group_rank_returns_group_keys_and_deterministic_tie_breakers() -> None:
    context = CompileContext.load(REPO_ROOT)
    result = compile_official(
        "rank('', '', '成交额', 'desc', '今日', '概念', '', '') <= 10",
        context=context,
    )

    sql = result.backend["sql"]
    assert "`ranked_groups`.`group_type`" in sql
    assert "`ranked_groups`.`group_code`" in sql
    assert "ROW_NUMBER() OVER" in sql
    assert "`group_metrics`.`group_type` ASC" in sql
    assert "`group_metrics`.`group_code` ASC" in sql


def test_group_boolean_composition_uses_group_identity_set_keys() -> None:
    context = CompileContext.load(REPO_ROOT)
    result = compile_official(
        "indicator('', '', '总股本', '', '行业', '', '') >= 100000000 and "
        "indicator('', '', '总市值', '', '行业', '', '') <= 200000000",
        context=context,
    )

    plan = result.physical["plan"]
    assert plan["kind"] == "PhysicalSetOperation"
    assert plan["operation"] == "intersect"
    assert plan["key_columns"] == [
        "group_type",
        "group_code",
        "group_name",
        "bizdate",
    ]
    assert result.physical["selected_strategy"] == "group_set_intersect"
    sql = result.backend["sql"]
    assert " INTERSECT " in sql
    assert "`left_set_input`.`group_code`" in sql
    assert "`right_set_input`.`group_code`" in sql
    assert "metric_value` INTERSECT" not in sql


def test_group_stage_ranks_only_the_prior_candidate_population() -> None:
    context = CompileContext.load(REPO_ROOT)
    result = compile_official(
        "indicator('', '', '主力净流出', '', '行业', '', '') = 1000000000 "
        "then rank('', '', '主力净流出', 'desc', '', '行业', '', '') = 1",
        context=context,
    )

    plan = result.physical["plan"]
    assert plan["kind"] == "PhysicalGroupEntityMetric"
    assert plan["candidate_input"]["kind"] == "PhysicalGroupEntityMetric"
    assert result.physical["selected_strategy"] == "group_stage_1"
    sql = result.backend["sql"]
    parsed = sqlglot.parse_one(sql, read="doris")
    ranked_select = next(
        select
        for select in parsed.find_all(exp.Select)
        if any(item.alias_or_name == "__rank_value" for item in select.expressions)
    )
    assert any(
        join.this.alias_or_name == "group_candidates"
        for join in ranked_select.args.get("joins", ())
    )
    assert "`group_metrics`.`group_code` = `group_candidates`.`group_code`" in sql


def test_group_universe_is_supported_without_inventing_a_metric() -> None:
    context = CompileContext.load(REPO_ROOT)
    result = compile_official(
        "indicator('', '', '', '', '板块', '', '') = 'all' limit 0,10",
        context=context,
    )

    sql = result.backend["sql"]
    assert result.physical["plan"]["kind"] == "PhysicalLimit"
    assert "MAX(1) AS `metric_value`" in sql
    assert "`group_member`.`scope_type` IN ('concept', 'industry')" in sql


def test_group_scope_resolves_to_versioned_group_identity() -> None:
    context = CompileContext.load(REPO_ROOT)
    result = compile_official(
        "indicator('', 'MSIC', '', '', '板块', '', '') = 'all'",
        context=context,
    )

    sql = result.backend["sql"]
    assert "`group_member`.`scope_code` IN ('BK0821')" in sql
    assert "eastmoney-2026-07-30-c33dad9203c8" in sql


def test_unloaded_group_taxonomy_is_a_data_gap_not_invented_semantics() -> None:
    context = CompileContext.load(REPO_ROOT)

    with pytest.raises(OfficialPipelineError) as excinfo:
        compile_official(
            "indicator('', '申万一级行业', '', '', '行业', '', '') = 'all'",
            context=context,
        )

    assert excinfo.value.code == "PHYSICAL_GROUP_TAXONOMY_DATA_UNAVAILABLE"


def test_official_only_profile_rejects_group_target_without_membership() -> None:
    context = CompileContext.load(REPO_ROOT, data_profile="official_only")

    with pytest.raises(OfficialPipelineError) as excinfo:
        compile_official(
            "indicator('', '', '成交量', '今日', '行业', '', '') > 0",
            context=context,
        )

    assert excinfo.value.code == "PHYSICAL_ENTITY_DATA_UNAVAILABLE"


def test_pipeline_rejects_mixed_result_entities_before_physical_lowering() -> None:
    context = CompileContext.load(REPO_ROOT)
    source = (
        "indicator('', '', '涨幅', '今日', 'ETF', '', '') > 0 and "
        "indicator('', '', '成交量', '今日', '', '', '') > 0"
    )

    with pytest.raises(OfficialPipelineError) as excinfo:
        compile_official(source, context=context)

    assert excinfo.value.code == "PHYSICAL_ENTITY_TARGET_MISMATCH"

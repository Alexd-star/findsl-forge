from pathlib import Path

import pytest

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
        (
            "indicator('', '', '涨幅', '今日', '行业', '', '') > 0",
            "PHYSICAL_ENTITY_SEMANTICS_UNAVAILABLE",
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


def test_pipeline_rejects_mixed_result_entities_before_physical_lowering() -> None:
    context = CompileContext.load(REPO_ROOT)
    source = (
        "indicator('', '', '涨幅', '今日', 'ETF', '', '') > 0 and "
        "indicator('', '', '成交量', '今日', '', '', '') > 0"
    )

    with pytest.raises(OfficialPipelineError) as excinfo:
        compile_official(source, context=context)

    assert excinfo.value.code == "PHYSICAL_ENTITY_TARGET_MISMATCH"

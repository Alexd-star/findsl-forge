import pytest

from findsl.official import (
    OFFICIAL_FUNCTION_SIGNATURES,
    CompileMode,
    FunctionSignature,
    SourceRepair,
)
from findsl.official_slot import OfficialSlotCompiler, OfficialSlotError


def test_compile_mode_parses_cli_values():
    assert CompileMode.parse("strict") is CompileMode.STRICT
    assert CompileMode.parse("recovery") is CompileMode.RECOVERY


def test_source_repair_serializes_for_evidence():
    repair = SourceRepair(code="TRAILING_QUOTE", message="remove trailing quote", position=12)

    assert repair.to_dict() == {
        "code": "TRAILING_QUOTE",
        "message": "remove trailing quote",
        "position": 12,
    }


def test_all_twelve_official_functions_have_exact_signatures():
    expected = {
        "indicator": (
            (
                "market",
                "filter_scope",
                "indicator_name",
                "date",
                "select_type",
                "agg_func",
                "count_exp",
            ),
            "dynamic",
        ),
        "rank": (
            (
                "market",
                "filter_scope",
                "indicator_name",
                "direction",
                "date",
                "select_type",
                "agg_func",
                "count_exp",
            ),
            "numeric",
        ),
        "belong_industry": (
            ("market", "filter_scope", "indicator_name", "date", "agg_func"),
            "dynamic",
        ),
        "queryData": (
            ("market", "keywords", "indicator_name", "date", "agg_func"),
            "dynamic",
        ),
        "cross_above": (
            (
                "market",
                "filter_scope",
                "indicator_name_1",
                "indicator_name_2",
                "date",
                "select_type",
                "count_exp",
            ),
            "boolean",
        ),
        "cross_down": (
            (
                "market",
                "filter_scope",
                "indicator_name_1",
                "indicator_name_2",
                "date",
                "select_type",
                "count_exp",
            ),
            "boolean",
        ),
        "close_together": (
            (
                "market",
                "filter_scope",
                "indicator_name_1",
                "indicator_name_2",
                "date",
                "select_type",
                "count_exp",
            ),
            "boolean",
        ),
        "reset": (
            (
                "market",
                "filter_scope",
                "indicator_name_1",
                "indicator_name_2",
                "date",
                "select_type",
                "count_exp",
            ),
            "boolean",
        ),
        "golden_cross": (
            (
                "market",
                "filter_scope",
                "indicator_name_1",
                "indicator_name_2",
                "date",
                "select_type",
                "count_exp",
            ),
            "boolean",
        ),
        "record_high": (
            (
                "market",
                "filter_scope",
                "indicator_name",
                "period",
                "date",
                "select_type",
                "agg_func",
                "count_exp",
            ),
            "boolean",
        ),
        "record_low": (
            (
                "market",
                "filter_scope",
                "indicator_name",
                "period",
                "date",
                "select_type",
                "agg_func",
                "count_exp",
            ),
            "boolean",
        ),
        "position": (
            (
                "market",
                "filter_scope",
                "indicator_name",
                "period",
                "date",
                "select_type",
                "agg_func",
                "count_exp",
            ),
            "string",
        ),
    }

    assert set(OFFICIAL_FUNCTION_SIGNATURES) == set(expected)
    for name, (slots, result_kind) in expected.items():
        signature = OFFICIAL_FUNCTION_SIGNATURES[name]
        assert signature.name == name
        assert signature.slots == slots
        assert signature.arity == len(slots)
        assert signature.result_kind == result_kind


def test_official_signature_registry_is_immutable():
    with pytest.raises(TypeError):
        OFFICIAL_FUNCTION_SIGNATURES["indicator"] = FunctionSignature(
            name="indicator",
            slots=(),
            result_kind="dynamic",
        )


def test_semantics_rejects_extra_indicator_argument():
    with pytest.raises(OfficialSlotError) as excinfo:
        OfficialSlotCompiler().compile(
            "indicator('', '', '收盘价', '', '', '', '', 'EXTRA') > 1"
        )

    assert excinfo.value.code == "OFFICIAL_SLOT_ARITY_ERROR"


def test_semantics_rejects_non_string_slot_argument():
    with pytest.raises(OfficialSlotError) as excinfo:
        OfficialSlotCompiler().compile(
            "indicator('', '', '收盘价', '', '', '', 1) > 1"
        )

    assert excinfo.value.code == "OFFICIAL_SLOT_ARG_ERROR"


@pytest.mark.parametrize("operator", [">", "="])
def test_semantics_rejects_numeric_string_comparison(operator):
    with pytest.raises(OfficialSlotError) as excinfo:
        OfficialSlotCompiler().compile(
            f"indicator('', '', '收盘价', '', '', '', '') {operator} 'abc'"
        )

    assert excinfo.value.code == "OFFICIAL_TYPE_ERROR"


def test_semantics_rejects_string_arithmetic():
    with pytest.raises(OfficialSlotError) as excinfo:
        OfficialSlotCompiler().compile(
            "indicator('', '', '股票名称', '', '', '', '') + 1 > 2"
        )

    assert excinfo.value.code == "OFFICIAL_TYPE_ERROR"


def test_semantics_accepts_grounded_numeric_boolean_string_and_time_comparisons():
    compiler = OfficialSlotCompiler()

    compiler.compile("indicator('', '', '收盘价', '', '', '', '') >= 10")
    compiler.compile("indicator('', '', '涨停', '', '', '', '') = True")
    compiler.compile("indicator('', '', '股票名称', '', '', '', '') = '平安银行'")
    compiler.compile("indicator('', '', '涨停时间', '', '', '', '') >= '09:30'")


def test_semantics_leaves_unknown_indicator_to_grounding_diagnostic():
    with pytest.raises(OfficialSlotError) as excinfo:
        OfficialSlotCompiler().compile(
            "indicator('', '', '不存在的官方指标', '', '', '', '') > 1"
        )

    assert excinfo.value.code == "UNSUPPORTED_OFFICIAL_INDICATOR"


@pytest.mark.parametrize("source", ["foo + 1 > 2", "foo > 'abc'", "foo = 1"])
def test_semantics_rejects_bare_identifiers(source):
    with pytest.raises(OfficialSlotError) as excinfo:
        OfficialSlotCompiler().compile(source)

    assert excinfo.value.code == "OFFICIAL_TYPE_ERROR"


def test_semantics_rejects_between_without_range_literal():
    with pytest.raises(OfficialSlotError) as excinfo:
        OfficialSlotCompiler().compile(
            "indicator('', '', '收盘价', '', '', '', '') between 10"
        )

    assert excinfo.value.code == "OFFICIAL_TYPE_ERROR"


def test_semantics_rejects_approximate_boolean_comparison():
    with pytest.raises(OfficialSlotError) as excinfo:
        OfficialSlotCompiler().compile(
            "indicator('', '', '涨停', '', '', '', '') ~= True"
        )

    assert excinfo.value.code == "OFFICIAL_TYPE_ERROR"


@pytest.mark.parametrize(
    "source",
    [
        "indicator('', '', '收盘价', '', '', '', '') > ' 5% '",
        "indicator('', '', '涨停时间', '', '', '', '') > ' 09:30 '",
    ],
)
def test_semantics_rejects_whitespace_padded_numeric_or_time_literals(source):
    with pytest.raises(OfficialSlotError) as excinfo:
        OfficialSlotCompiler().compile(source)

    assert excinfo.value.code == "OFFICIAL_TYPE_ERROR"


def test_whitespace_padded_percent_remains_a_quoted_string_pattern():
    result = OfficialSlotCompiler().compile(
        "indicator('', '', '股票名称', '', '', '', '') = ' 5% '"
    )

    assert "LIKE ' 5% '" in result.sql

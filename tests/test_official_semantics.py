import pytest

from findsl.official import (
    OFFICIAL_FUNCTION_SIGNATURES,
    CompileMode,
    FunctionSignature,
    SourceRepair,
)


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

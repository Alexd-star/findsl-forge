import pytest

from findsl.official.types import (
    BOOLEAN,
    NUMERIC,
    STRING,
    TIME,
    UNKNOWN,
    OfficialTypeError,
    RangeType,
    arithmetic_result,
    require_approximate,
    require_boolean,
    require_ordered,
)


def test_official_types_have_stable_legacy_names_and_serialization():
    assert NUMERIC.legacy_name == "numeric"
    assert RangeType(NUMERIC).to_dict() == {"kind": "range", "element_type": {"kind": "numeric"}}
    assert UNKNOWN.to_dict() == {"kind": "unknown"}


def test_type_compatibility_rules_are_centralized():
    assert arithmetic_result(NUMERIC, UNKNOWN) is UNKNOWN
    assert arithmetic_result(NUMERIC, NUMERIC) is NUMERIC
    assert require_boolean(BOOLEAN, BOOLEAN) is BOOLEAN
    assert require_ordered(TIME, TIME) is BOOLEAN
    assert require_approximate(STRING, STRING) is BOOLEAN


@pytest.mark.parametrize(
    "operation",
    [
        lambda: arithmetic_result(STRING, NUMERIC),
        lambda: require_boolean(NUMERIC, BOOLEAN),
        lambda: require_ordered(STRING, STRING),
        lambda: require_approximate(TIME, TIME),
    ],
)
def test_incompatible_types_raise_stable_type_error(operation):
    with pytest.raises(OfficialTypeError) as excinfo:
        operation()
    assert excinfo.value.code == "OFFICIAL_TYPE_ERROR"

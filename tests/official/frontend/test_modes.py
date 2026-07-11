import pytest

from findsl.official_slot import (
    OfficialSlotError,
    parse_official_slot,
    parse_official_slot_with_diagnostics,
)


def test_recovery_repairs_are_frontend_independent():
    source = "and indicator('', '', '涨幅', '', '', '', '') > 1"
    old = parse_official_slot_with_diagnostics(source, mode="recovery", frontend="handwritten")
    new = parse_official_slot_with_diagnostics(source, mode="recovery", frontend="antlr")

    assert new.ast.to_dict() == old.ast.to_dict()
    assert new.repairs == old.repairs


def test_strict_antlr_does_not_repair_source():
    source = "and indicator('', '', '涨幅', '', '', '', '') > 1"
    with pytest.raises(OfficialSlotError) as excinfo:
        parse_official_slot(source, mode="strict", frontend="antlr")

    assert excinfo.value.code == "OFFICIAL_ANTLR_PARSE_ERROR"


def test_recovery_does_not_delete_exclusive_range_closing_parenthesis():
    result = parse_official_slot_with_diagnostics("x between [1, 4)", frontend="antlr")

    assert result.normalized_source == "x between [1, 4)"
    assert result.repairs == ()
    assert result.ast.to_dict()["right"]["upper_inclusive"] is False

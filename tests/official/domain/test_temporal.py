import pytest

from findsl.official.domain.temporal import (
    TemporalParseError,
    evaluate_calendar_bucket_matches,
    evaluate_temporal_matches,
    parse_temporal_quantifier,
)


@pytest.mark.parametrize(
    "source,expected",
    [
        ("CONS=3日", ("CONS", "=", 3, None, "日", False)),
        ("EXIST>=5", ("EXIST", ">=", 5, None, "", False)),
        ("CONS=每年", ("CONS", "=", None, None, "年", True)),
        ("EXIST=3-8日", ("EXIST", "between", 3, 8, "日", False)),
        ("CONS=三季度", ("CONS", "=", 3, None, "季度", False)),
        ("CONS=2天", ("CONS", "=", 2, None, "日", False)),
        ("CONS>1", ("CONS", ">", 1, None, "", False)),
        ("EXIST>0", ("EXIST", ">", 0, None, "", False)),
    ],
)
def test_official_count_expression_is_parsed_into_typed_contract(source, expected):
    result = parse_temporal_quantifier(source)

    assert (
        result.mode,
        result.comparator,
        result.threshold,
        result.maximum,
        result.unit,
        result.every,
    ) == expected
    assert result.source == source
    assert result.trading_sequence is True


@pytest.mark.parametrize(
    "source,code",
    [
        ("COUNT=3日", "TEMPORAL_MODE_UNSUPPORTED"),
        ("CONS=0日", "TEMPORAL_CONSECUTIVE_THRESHOLD_INVALID"),
        ("EXIST=8-3日", "TEMPORAL_RANGE_INVALID"),
        ("CONS=每", "TEMPORAL_EVERY_UNIT_REQUIRED"),
        ("EXIST>每日", "TEMPORAL_EVERY_COMPARATOR_INVALID"),
        ("CONS=1.5周", "TEMPORAL_FRACTIONAL_UNIT_UNSUPPORTED"),
    ],
)
def test_invalid_temporal_contract_has_stable_diagnostic(source, code):
    with pytest.raises(TemporalParseError) as excinfo:
        parse_temporal_quantifier(source)

    assert excinfo.value.code == code


def test_temporal_contract_is_deterministic_and_sql_free():
    first = parse_temporal_quantifier("CONS=3日")
    second = parse_temporal_quantifier("CONS=3日")

    assert first.node_id == second.node_id
    assert "SELECT" not in first.canonical_json().upper()
    assert first.to_dict()["semantics"] == "trading_sequence"


def test_not_every_contract_is_preserved_for_official_negative_semantics():
    result = parse_temporal_quantifier("CONS!=每日")

    assert result.every is True
    assert result.comparator == "!="


def test_exact_fractional_year_is_normalized_to_calendar_months():
    result = parse_temporal_quantifier("CONS=0.5年")

    assert result.threshold == 6
    assert result.unit == "月"


def test_non_integral_fractional_calendar_conversion_is_rejected():
    with pytest.raises(TemporalParseError) as excinfo:
        parse_temporal_quantifier("CONS=0.1年")

    assert excinfo.value.code == "TEMPORAL_FRACTIONAL_UNIT_UNSUPPORTED"


def test_reference_oracle_distinguishes_consecutive_run_from_total_matches():
    matches = [True, False, True, False, True]

    assert evaluate_temporal_matches(matches, parse_temporal_quantifier("EXIST>=3")) is True
    assert evaluate_temporal_matches(matches, parse_temporal_quantifier("CONS=3日")) is False


@pytest.mark.parametrize(
    "source,matches,expected",
    [
        ("CONS=3日", [False, True, True, True, False], True),
        ("CONS>3日", [True, True, True], False),
        ("EXIST=2-3日", [True, False, True], True),
        ("EXIST=每日", [True, True], True),
        ("EXIST=每日", [], False),
        ("CONS!=每日", [True, False], True),
        ("CONS!=每日", [], False),
    ],
)
def test_reference_oracle_covers_bounds_every_and_empty_windows(source, matches, expected):
    assert evaluate_temporal_matches(matches, parse_temporal_quantifier(source)) is expected


def test_calendar_bucket_oracle_inserts_missing_periods_as_false():
    buckets = [(2024, True), (2026, True)]

    assert evaluate_calendar_bucket_matches(
        buckets, parse_temporal_quantifier("CONS=每年")
    ) is False
    assert evaluate_calendar_bucket_matches(
        buckets, parse_temporal_quantifier("CONS=2年")
    ) is False
    assert evaluate_calendar_bucket_matches(
        buckets, parse_temporal_quantifier("EXIST>=2年")
    ) is True


def test_calendar_bucket_oracle_coalesces_multiple_rows_in_one_bucket():
    buckets = [(2024, False), (2024, True), (2025, True)]

    assert evaluate_calendar_bucket_matches(
        buckets, parse_temporal_quantifier("CONS=2年")
    ) is True

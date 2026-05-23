import json
import os
import subprocess
import sys

from findsl.compiler import Compiler
from findsl.demo import _error_payload
from findsl.diagnostics import diagnose_exception
from findsl.errors import ParseError


def test_diagnose_unknown_indicator_offers_configured_repair_hint():
    try:
        Compiler().compile('filter(indicator("clos") > 10)')
    except Exception as exc:  # noqa: BLE001 - asserting diagnostic behavior for compiler errors.
        diagnostics = diagnose_exception(exc)

    assert diagnostics[0].code == "UNKNOWN_INDICATOR"
    assert any('indicator("close")' in hint for hint in diagnostics[0].suggestions)


def test_diagnose_parse_error_points_to_missing_parenthesis():
    diagnostics = diagnose_exception(ParseError("Expected ), got EOF at 42"))

    assert diagnostics[0].code == "PARSE_ERROR"
    assert any("missing closing parenthesis" in hint for hint in diagnostics[0].suggestions)


def test_demo_error_payload_includes_structured_diagnostics():
    try:
        Compiler().compile('filter(CONS(indicator("close"), 3))')
    except Exception as exc:  # noqa: BLE001 - asserting diagnostic payload shape.
        payload = _error_payload(exc)

    assert payload["type"]
    assert payload["diagnostics"]
    assert payload["diagnostics"][0]["code"] == "SEMANTIC_ERROR"
    assert payload["diagnostics"][0]["suggestions"]


def test_diagnose_invalid_rank_percent_offers_bound_hint():
    try:
        Compiler().compile('rank(indicator("close"), desc, percent=120)')
    except Exception as exc:  # noqa: BLE001 - asserting diagnostic behavior for compiler errors.
        diagnostics = diagnose_exception(exc)

    assert diagnostics[0].code == "SEMANTIC_ERROR"
    assert any("0 < N <= 100" in hint for hint in diagnostics[0].suggestions)


def test_diagnose_invalid_date_between_offers_iso_date_hint():
    try:
        Compiler().compile('filter(date_between("2026-01-04", "2026-01-02"))')
    except Exception as exc:  # noqa: BLE001 - asserting diagnostic behavior for compiler errors.
        diagnostics = diagnose_exception(exc)

    assert diagnostics[0].code == "SEMANTIC_ERROR"
    assert any("YYYY-MM-DD" in hint for hint in diagnostics[0].suggestions)


def test_diagnose_invalid_date_format_offers_iso_date_hint():
    try:
        Compiler().compile('filter(date_between("2026/01/01", "2026-01-02"))')
    except Exception as exc:  # noqa: BLE001 - asserting diagnostic behavior for compiler errors.
        diagnostics = diagnose_exception(exc)

    assert diagnostics[0].code == "SEMANTIC_ERROR"
    assert any("YYYY-MM-DD" in hint for hint in diagnostics[0].suggestions)


def test_diagnose_rank_bottom_order_mismatch_offers_direction_hint():
    try:
        Compiler().compile('rank(indicator("close"), desc, bottom=2)')
    except Exception as exc:  # noqa: BLE001 - asserting diagnostic behavior for compiler errors.
        diagnostics = diagnose_exception(exc)

    assert diagnostics[0].code == "SEMANTIC_ERROR"
    assert any("rank(..., asc, bottom=N)" in hint for hint in diagnostics[0].suggestions)


def test_diagnose_invalid_number_literal_is_lexical_not_generic():
    try:
        Compiler().compile('filter(indicator("close") > 1.2.3)')
    except Exception as exc:  # noqa: BLE001 - asserting diagnostic behavior for compiler errors.
        diagnostics = diagnose_exception(exc)

    assert diagnostics[0].code == "LEX_ERROR"
    assert any("numeric literals" in hint for hint in diagnostics[0].suggestions)


def test_diagnose_bare_identifier_suggests_indicator_wrapper():
    try:
        Compiler().compile("close > 10")
    except Exception as exc:  # noqa: BLE001 - asserting diagnostic behavior for compiler errors.
        diagnostics = diagnose_exception(exc)

    assert diagnostics[0].code == "SEMANTIC_ERROR"
    assert any('indicator("close")' in hint for hint in diagnostics[0].suggestions)


def test_diagnose_filter_single_equal_bare_identifier_suggests_indicator_wrapper():
    try:
        Compiler().compile("filter(close=10)")
    except Exception as exc:  # noqa: BLE001 - asserting diagnostic behavior for compiler errors.
        diagnostics = diagnose_exception(exc)

    assert diagnostics[0].code == "SEMANTIC_ERROR"
    assert any('filter(indicator("close") = 10)' in hint for hint in diagnostics[0].suggestions)


def test_diagnose_filter_numeric_condition_offers_boolean_hint():
    try:
        Compiler().compile('filter(indicator("close"))')
    except Exception as exc:  # noqa: BLE001 - asserting diagnostic behavior for compiler errors.
        diagnostics = diagnose_exception(exc)

    assert diagnostics[0].code == "SEMANTIC_ERROR"
    assert any("filter() expects a boolean condition" in hint for hint in diagnostics[0].suggestions)


def test_diagnose_invalid_then_stage_offers_pipeline_hint():
    try:
        Compiler().compile('then(filter(indicator("close") > 10), indicator("volume"))')
    except Exception as exc:  # noqa: BLE001 - asserting diagnostic behavior for compiler errors.
        diagnostics = diagnose_exception(exc)

    assert diagnostics[0].code == "SEMANTIC_ERROR"
    assert any("then(filter(...), rank(...))" in hint for hint in diagnostics[0].suggestions)


def test_diagnose_non_integer_window_offers_integer_window_hint():
    try:
        Compiler().compile('filter(MA(indicator("close"), 2.5) > 10)')
    except Exception as exc:  # noqa: BLE001 - asserting diagnostic behavior for compiler errors.
        diagnostics = diagnose_exception(exc)

    assert diagnostics[0].code == "SEMANTIC_ERROR"
    assert any("positive integer window" in hint for hint in diagnostics[0].suggestions)


def test_diagnose_top_level_numeric_expression_offers_filter_hint():
    try:
        Compiler().compile('indicator("close")')
    except Exception as exc:  # noqa: BLE001 - asserting diagnostic behavior for compiler errors.
        diagnostics = diagnose_exception(exc)

    assert diagnostics[0].code == "SEMANTIC_ERROR"
    assert any("filter(indicator(\"close\") > 10)" in hint for hint in diagnostics[0].suggestions)


def test_diagnose_invalid_market_argument_offers_market_code_hint():
    try:
        Compiler().compile("filter(market(1))")
    except Exception as exc:  # noqa: BLE001 - asserting diagnostic behavior for compiler errors.
        diagnostics = diagnose_exception(exc)

    assert diagnostics[0].code == "SEMANTIC_ERROR"
    assert any('market("A")' in hint for hint in diagnostics[0].suggestions)


def test_diagnose_invalid_indicator_argument_offers_indicator_hint():
    try:
        Compiler().compile("filter(indicator(123) > 10)")
    except Exception as exc:  # noqa: BLE001 - asserting diagnostic behavior for compiler errors.
        diagnostics = diagnose_exception(exc)

    assert diagnostics[0].code == "SEMANTIC_ERROR"
    assert any('indicator("close")' in hint for hint in diagnostics[0].suggestions)


def test_diagnose_literal_division_by_zero_offers_denominator_hint():
    try:
        Compiler().compile('filter((indicator("close") / 0) > 1)')
    except Exception as exc:  # noqa: BLE001 - asserting diagnostic behavior for compiler errors.
        diagnostics = diagnose_exception(exc)

    assert diagnostics[0].code == "SEMANTIC_ERROR"
    assert any("non-zero denominator" in hint for hint in diagnostics[0].suggestions)


def test_cli_diagnose_returns_json_repair_hints_for_invalid_dsl():
    env = os.environ.copy()
    env["PYTHONPATH"] = "src" + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "findsl.cli",
            "diagnose",
            'filter(indicator("clos") > 10)',
            "--json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert not payload["ok"]
    assert payload["diagnostics"][0]["code"] == "UNKNOWN_INDICATOR"
    assert any('indicator("close")' in hint for hint in payload["diagnostics"][0]["suggestions"])

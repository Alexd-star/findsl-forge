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

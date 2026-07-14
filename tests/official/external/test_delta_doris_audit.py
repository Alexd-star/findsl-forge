import importlib.util
from pathlib import Path

import pytest


def _load_script():
    root = Path(__file__).resolve().parents[3]
    path = root / "scripts" / "audit_funnel_delta_doris.py"
    spec = importlib.util.spec_from_file_location("audit_funnel_delta_doris", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_select_delta_rows_uses_backend_success_transition():
    module = _load_script()
    previous = {
        "rows": [
            {"excel_row": 2, "new_backend_success": True},
            {"excel_row": 3, "new_backend_success": False},
        ]
    }
    current = {
        "rows": [
            {"excel_row": 2, "new_backend_success": True},
            {"excel_row": 3, "new_backend_success": True},
            {"excel_row": 4, "new_backend_success": False},
        ]
    }

    assert [item["excel_row"] for item in module.select_delta_rows(previous, current)] == [3]


def test_canonicalize_result_order_wraps_unordered_set_query():
    module = _load_script()

    sql, contract = module.canonicalize_result_order("SELECT a, b FROM t")

    assert contract == "canonical_full_row_order"
    assert "ORDER BY 1, 2" in sql
    assert "audit_rows" in sql


def test_canonicalize_result_order_preserves_generated_order():
    module = _load_script()
    source = "SELECT a, b FROM t ORDER BY a"

    assert module.canonicalize_result_order(source) == (source, "generated_order")


def test_canonicalize_result_order_rejects_unordered_limit():
    module = _load_script()

    with pytest.raises(ValueError, match="unordered LIMIT"):
        module.canonicalize_result_order("SELECT a FROM t LIMIT 2")

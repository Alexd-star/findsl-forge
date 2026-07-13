import importlib.util
from pathlib import Path


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

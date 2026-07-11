import json
import sys

from findsl.cli import main


DSL = "indicator('', '', '成交量', '今日', '', '', '') > 100"


def test_official_slot_physical_cli_outputs_selected_resource(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["findsl", "official-slot-physical", DSL, "--json"])
    main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["selected_resource"] == "official_basic"
    assert payload["plan"]["kind"] == "PhysicalFilter"


def test_official_slot_backend_cli_outputs_validated_sql(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["findsl", "official-slot-backend", DSL, "--json"])
    main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["validation_passed"] is True
    assert "hsj_stock_hq_basic" in payload["sql"]

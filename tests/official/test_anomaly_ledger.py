import json
from pathlib import Path

import pytest

from findsl.official.anomalies import (
    OfficialAnomalyLedgerError,
    OfficialDslAnomalyLedger,
)
from findsl.official_slot import OfficialSlotError, parse_official_slot_with_diagnostics


LEDGER = Path("configs/official/official_dsl_anomaly_ledger.json")


def test_official_anomaly_ledger_freezes_all_seven_source_repairs():
    ledger = OfficialDslAnomalyLedger.load(LEDGER)

    assert ledger.source_sha256 == "b5603a9bf9db60a76abe46ec6360c4ab09e26e5c10fac3c9dbccd92615963623"
    assert [item.excel_row for item in ledger.anomalies] == [2122, 2194, 2466, 3785, 5328, 5521, 5753]
    for item in ledger.anomalies:
        with pytest.raises(OfficialSlotError):
            parse_official_slot_with_diagnostics(item.original_dsl, mode="strict", frontend="antlr")
        recovered = parse_official_slot_with_diagnostics(item.original_dsl, mode="recovery", frontend="antlr")
        assert recovered.normalized_source == item.normalized_dsl
        assert [(repair.code, repair.position) for repair in recovered.repairs] == [
            (item.repair_code, item.repair_position)
        ]


def test_official_anomaly_ledger_rejects_tampered_source_hash(tmp_path):
    raw = json.loads(LEDGER.read_text(encoding="utf-8"))
    raw["anomalies"][0]["original_dsl"] += " "
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(OfficialAnomalyLedgerError, match="hash mismatch"):
        OfficialDslAnomalyLedger.load(path)

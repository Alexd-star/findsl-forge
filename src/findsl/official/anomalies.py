from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Tuple


class OfficialAnomalyLedgerError(ValueError):
    pass


@dataclass(frozen=True)
class OfficialDslAnomaly:
    excel_row: int
    original_dsl: str
    normalized_dsl: str
    repair_code: str
    repair_position: int
    original_sha256: str
    normalized_sha256: str
    disposition: str


@dataclass(frozen=True)
class OfficialDslAnomalyLedger:
    schema_version: int
    ledger_id: str
    source_workbook: str
    source_sha256: str
    evidence_policy: str
    anomalies: Tuple[OfficialDslAnomaly, ...]

    @classmethod
    def load(cls, path: Path) -> "OfficialDslAnomalyLedger":
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OfficialAnomalyLedgerError(f"cannot load anomaly ledger: {exc}") from exc
        return cls.from_mapping(raw)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "OfficialDslAnomalyLedger":
        expected = {
            "schema_version",
            "ledger_id",
            "source_workbook",
            "source_sha256",
            "evidence_policy",
            "anomalies",
        }
        if not isinstance(raw, Mapping) or set(raw) != expected:
            raise OfficialAnomalyLedgerError("invalid anomaly ledger fields")
        if raw["schema_version"] != 1:
            raise OfficialAnomalyLedgerError("unsupported anomaly ledger schema_version")
        anomalies = tuple(_anomaly(item) for item in raw["anomalies"])
        if len(anomalies) != 7:
            raise OfficialAnomalyLedgerError("official anomaly ledger must contain exactly 7 rows")
        rows = [item.excel_row for item in anomalies]
        if rows != sorted(rows) or len(set(rows)) != len(rows):
            raise OfficialAnomalyLedgerError("anomaly rows must be unique and sorted")
        return cls(
            1,
            str(raw["ledger_id"]),
            str(raw["source_workbook"]),
            _sha256_value(raw["source_sha256"], "source_sha256"),
            str(raw["evidence_policy"]),
            anomalies,
        )


def _anomaly(raw: Mapping[str, Any]) -> OfficialDslAnomaly:
    expected = {
        "excel_row",
        "original_dsl",
        "normalized_dsl",
        "repair_code",
        "repair_position",
        "original_sha256",
        "normalized_sha256",
        "disposition",
    }
    if not isinstance(raw, Mapping) or set(raw) != expected:
        raise OfficialAnomalyLedgerError("invalid anomaly row fields")
    original = str(raw["original_dsl"])
    normalized = str(raw["normalized_dsl"])
    original_hash = _sha256_value(raw["original_sha256"], "original_sha256")
    normalized_hash = _sha256_value(raw["normalized_sha256"], "normalized_sha256")
    if _sha256(original) != original_hash:
        raise OfficialAnomalyLedgerError(f"row {raw['excel_row']}: original DSL hash mismatch")
    if _sha256(normalized) != normalized_hash:
        raise OfficialAnomalyLedgerError(f"row {raw['excel_row']}: normalized DSL hash mismatch")
    if original == normalized:
        raise OfficialAnomalyLedgerError(f"row {raw['excel_row']}: repair does not change source")
    return OfficialDslAnomaly(
        int(raw["excel_row"]),
        original,
        normalized,
        str(raw["repair_code"]),
        int(raw["repair_position"]),
        original_hash,
        normalized_hash,
        str(raw["disposition"]),
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_value(value: Any, name: str) -> str:
    normalized = str(value).lower()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        raise OfficialAnomalyLedgerError(f"{name} must be a lowercase SHA-256 digest")
    return normalized

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple


class RepairCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class RepairCandidate:
    repair_code: str
    original_dsl: str
    candidate_dsl: str
    repair_position: int
    original_sha256: str
    candidate_sha256: str
    source_row: int
    confidence: str = "exact_ledger_match"
    requires_confirmation: bool = True
    auto_execute: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OfficialRepairCatalog:
    def __init__(self, candidates: Tuple[RepairCandidate, ...]) -> None:
        by_hash: Dict[str, RepairCandidate] = {}
        for candidate in candidates:
            observed_original = _sha256(candidate.original_dsl)
            observed_candidate = _sha256(candidate.candidate_dsl)
            if observed_original != candidate.original_sha256:
                raise RepairCatalogError(
                    f"repair source hash mismatch at row {candidate.source_row}"
                )
            if observed_candidate != candidate.candidate_sha256:
                raise RepairCatalogError(
                    f"repair candidate hash mismatch at row {candidate.source_row}"
                )
            if candidate.original_sha256 in by_hash:
                raise RepairCatalogError("duplicate repair source hash")
            by_hash[candidate.original_sha256] = candidate
        self._by_hash: Mapping[str, RepairCandidate] = MappingProxyType(by_hash)

    def suggest(self, dsl: str) -> Optional[RepairCandidate]:
        source = str(dsl or "")
        candidate = self._by_hash.get(_sha256(source))
        if candidate is None or candidate.original_dsl != source:
            return None
        return candidate

    @classmethod
    def load(cls, path: Path) -> "OfficialRepairCatalog":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            raise RepairCatalogError("invalid official repair ledger")
        anomalies = raw.get("anomalies")
        if not isinstance(anomalies, list):
            raise RepairCatalogError("official repair ledger anomalies must be an array")
        candidates = tuple(
            RepairCandidate(
                repair_code=str(item["repair_code"]),
                original_dsl=str(item["original_dsl"]),
                candidate_dsl=str(item["normalized_dsl"]),
                repair_position=int(item["repair_position"]),
                original_sha256=str(item["original_sha256"]),
                candidate_sha256=str(item["normalized_sha256"]),
                source_row=int(item["excel_row"]),
            )
            for item in anomalies
        )
        return cls(candidates)


@lru_cache(maxsize=1)
def default_repair_catalog() -> OfficialRepairCatalog:
    root = Path(__file__).resolve().parents[3]
    return OfficialRepairCatalog.load(
        root / "configs" / "official" / "official_dsl_anomaly_ledger.json"
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

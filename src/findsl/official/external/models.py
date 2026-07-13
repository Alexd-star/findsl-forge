from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Tuple


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SECURITY_CODE = re.compile(r"[A-Za-z0-9._-]{1,32}\Z")


def normalize_catalog_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    return re.sub(r"\s+", "", text)


def _iso_date(value: Optional[str], *, label: str) -> Optional[str]:
    if value in {None, ""}:
        return None
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise ValueError(f"{label} must use YYYY-MM-DD") from exc


@dataclass(frozen=True)
class CatalogSnapshot:
    snapshot_id: str
    source: str
    source_url: str
    retrieved_at: str
    as_of_date: str
    content_sha256: str
    license_note: str
    scope_memberships: Tuple["ScopeMembership", ...] = ()
    industry_memberships: Tuple["IndustryMembership", ...] = ()
    instrument_rules: Tuple["InstrumentRule", ...] = ()

    def __post_init__(self) -> None:
        if not self.snapshot_id.strip() or not self.source.strip() or not self.source_url.strip():
            raise ValueError("snapshot identity, source, and source_url are required")
        try:
            datetime.fromisoformat(self.retrieved_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("retrieved_at must be ISO-8601") from exc
        object.__setattr__(self, "as_of_date", _iso_date(self.as_of_date, label="as_of_date"))
        if not _SHA256.fullmatch(self.content_sha256):
            raise ValueError("content_sha256 must be a lowercase SHA-256 digest")
        if not (
            self.scope_memberships or self.industry_memberships or self.instrument_rules
        ):
            raise ValueError("an external snapshot cannot be empty")


@dataclass(frozen=True)
class ScopeMembership:
    scope_type: str
    scope_code: str
    scope_name: str
    aliases: Tuple[str, ...]
    mktcode: int
    tgtcode: str
    effective_from: Optional[str]
    effective_to: Optional[str]
    weight: Optional[float]
    match_method: str = "source_exact"

    def __post_init__(self) -> None:
        if not self.scope_type.strip() or not self.scope_code.strip() or not self.scope_name.strip():
            raise ValueError("scope type, code, and name are required")
        if not _SECURITY_CODE.fullmatch(self.tgtcode):
            raise ValueError(f"invalid security code: {self.tgtcode}")
        start = _iso_date(self.effective_from, label="effective_from")
        end = _iso_date(self.effective_to, label="effective_to")
        if start and end and start > end:
            raise ValueError("effective_from cannot be after effective_to")
        object.__setattr__(self, "effective_from", start)
        object.__setattr__(self, "effective_to", end)
        object.__setattr__(
            self,
            "aliases",
            tuple(dict.fromkeys(alias.strip() for alias in self.aliases if alias.strip())),
        )


@dataclass(frozen=True)
class IndustryMembership:
    classification_system: str
    industry_level: str
    industry_code: str
    industry_name: str
    mktcode: int
    tgtcode: str
    effective_from: Optional[str]
    effective_to: Optional[str]

    def __post_init__(self) -> None:
        required = (
            self.classification_system,
            self.industry_level,
            self.industry_code,
            self.industry_name,
        )
        if not all(str(value).strip() for value in required):
            raise ValueError("industry system, level, code, and name are required")
        if not _SECURITY_CODE.fullmatch(self.tgtcode):
            raise ValueError(f"invalid security code: {self.tgtcode}")
        start = _iso_date(self.effective_from, label="effective_from")
        end = _iso_date(self.effective_to, label="effective_to")
        if start and end and start > end:
            raise ValueError("effective_from cannot be after effective_to")
        object.__setattr__(self, "effective_from", start)
        object.__setattr__(self, "effective_to", end)


@dataclass(frozen=True)
class InstrumentRule:
    mktcode: int
    tgtcode: str
    instrument_type: str
    t0_eligible: bool
    effective_from: Optional[str]
    effective_to: Optional[str]
    rule_source: str

    def __post_init__(self) -> None:
        if not _SECURITY_CODE.fullmatch(self.tgtcode):
            raise ValueError(f"invalid security code: {self.tgtcode}")
        if not self.instrument_type.strip() or not self.rule_source.strip():
            raise ValueError("instrument_type and rule_source are required")
        start = _iso_date(self.effective_from, label="effective_from")
        end = _iso_date(self.effective_to, label="effective_to")
        if start and end and start > end:
            raise ValueError("effective_from cannot be after effective_to")
        object.__setattr__(self, "effective_from", start)
        object.__setattr__(self, "effective_to", end)

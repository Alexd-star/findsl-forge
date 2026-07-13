from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Dict, Tuple

from .models import CatalogSnapshot, IndustryMembership, ScopeMembership
from .providers.eastmoney import security_market_code
from .providers.sina import SinaSectorProvider


@dataclass(frozen=True)
class SinaSyncResult:
    snapshot: CatalogSnapshot
    discovered_sectors: int
    successful_sectors: int
    failed_sectors: Tuple[Dict[str, str], ...]

    def to_dict(self):
        return {
            "snapshot_id": self.snapshot.snapshot_id,
            "source": self.snapshot.source,
            "as_of_date": self.snapshot.as_of_date,
            "scope_memberships": len(self.snapshot.scope_memberships),
            "industry_memberships": len(self.snapshot.industry_memberships),
            "discovered_sectors": self.discovered_sectors,
            "successful_sectors": self.successful_sectors,
            "failed_sectors": list(self.failed_sectors),
        }


def build_sina_sector_snapshot(
    *, provider: SinaSectorProvider, as_of_date: str = None
) -> SinaSyncResult:
    sectors = tuple(
        sector
        for sector_type in ("concept", "region", "industry")
        for sector in provider.list_sectors(sector_type)
    )
    snapshot_date = as_of_date or date.today().isoformat()
    scope_rows = []
    industry_rows = []
    failures = []
    successful = 0
    for sector in sectors:
        try:
            members = provider.list_constituents(sector)
        except Exception as exc:
            failures.append(
                {
                    "sector_type": sector.sector_type,
                    "sector_code": sector.code,
                    "sector_name": sector.name,
                    "error": str(exc),
                }
            )
            continue
        successful += 1
        aliases = _sector_aliases(sector.sector_type, sector.name)
        for member in members:
            market = security_market_code(member.code)
            scope_rows.append(
                ScopeMembership(
                    sector.sector_type,
                    f"SINA:{sector.code}",
                    sector.name,
                    aliases,
                    market,
                    member.code,
                    snapshot_date,
                    None,
                    None,
                    "sina_sector_exact",
                )
            )
            if sector.sector_type == "industry":
                industry_rows.append(
                    IndustryMembership(
                        "Sina Finance industry",
                        "provider",
                        sector.code,
                        sector.name,
                        market,
                        member.code,
                        snapshot_date,
                        None,
                    )
                )
    if not scope_rows:
        raise ValueError("Sina synchronization produced no scope memberships")
    content = {
        "scope_memberships": [_canonical_row(item) for item in scope_rows],
        "industry_memberships": [_canonical_row(item) for item in industry_rows],
    }
    digest = hashlib.sha256(
        json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    snapshot = CatalogSnapshot(
        f"sina-sector-{snapshot_date}-{digest[:12]}",
        provider.source,
        provider.source_url,
        datetime.now(timezone.utc).isoformat(),
        snapshot_date,
        digest,
        provider.license_note,
        scope_memberships=tuple(scope_rows),
        industry_memberships=tuple(industry_rows),
    )
    return SinaSyncResult(snapshot, len(sectors), successful, tuple(failures))


def _sector_aliases(sector_type: str, name: str) -> Tuple[str, ...]:
    if sector_type != "region":
        return ()
    aliases = []
    for suffix in ("维吾尔自治区", "壮族自治区", "回族自治区", "自治区", "省", "市"):
        if name.endswith(suffix):
            aliases.append(name[: -len(suffix)])
            break
    return tuple(aliases)


def _canonical_row(item):
    payload = dict(item.__dict__)
    if isinstance(payload.get("aliases"), tuple):
        payload["aliases"] = list(payload["aliases"])
    return payload

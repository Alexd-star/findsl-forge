from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone

from .models import CatalogSnapshot, IndustryMembership


_INDUSTRY_CODE = re.compile(r"^([A-Z]\d{2,4})(.*)$")
_MARKETS = {"sz": 0, "sh": 1, "bj": 103}


def build_baostock_industry_snapshot(provider, *, as_of_date: str = None):
    source_rows = provider.fetch()
    memberships = {}
    classification_systems = set()
    for row in source_rows:
        code_parts = str(row.code).strip().lower().split(".", 1)
        if len(code_parts) != 2 or code_parts[0] not in _MARKETS:
            continue
        security_code = code_parts[1]
        industry = str(row.industry).strip()
        classification = str(row.classification_system).strip()
        match = _INDUSTRY_CODE.fullmatch(industry)
        if not match or not classification:
            continue
        industry_code, industry_name = match.groups()
        industry_name = industry_name.strip() or industry_code
        classification_systems.add(classification)
        membership = IndustryMembership(
            classification,
            "industry",
            industry_code,
            industry_name,
            _MARKETS[code_parts[0]],
            security_code,
            str(row.update_date).strip() or as_of_date or date.today().isoformat(),
            None,
        )
        memberships[(membership.mktcode, membership.tgtcode)] = membership
    if not memberships:
        raise ValueError("BaoStock synchronization produced no classified securities")
    if len(classification_systems) != 1:
        raise ValueError("BaoStock industry snapshot must use one classification system")
    rows = tuple(memberships[key] for key in sorted(memberships))
    canonical = [dict(item.__dict__) for item in rows]
    digest = hashlib.sha256(
        json.dumps(
            canonical,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    snapshot_date = as_of_date or max(item.effective_from for item in rows)
    snapshot = CatalogSnapshot(
        f"baostock-industry-{snapshot_date}-{digest[:12]}",
        provider.source,
        provider.source_url,
        datetime.now(timezone.utc).isoformat(),
        snapshot_date,
        digest,
        provider.license_note,
        industry_memberships=rows,
    )
    return snapshot, next(iter(classification_systems))

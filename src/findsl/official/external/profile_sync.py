from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Iterable

from .models import CatalogSnapshot, ScopeMembership
from .providers.eastmoney import SecurityProfile, security_market_code


def build_security_profile_snapshot(
    profiles: Iterable[SecurityProfile], *, as_of_date: str = None
) -> CatalogSnapshot:
    snapshot_date = as_of_date or date.today().isoformat()
    memberships = {}
    for profile in profiles:
        market = security_market_code(profile.code)
        if market is None:
            continue
        _add_membership(
            memberships,
            "security",
            f"SEC:{market}:{profile.code}",
            profile.name,
            (profile.code,),
            market,
            profile.code,
            snapshot_date,
        )
        region = _trim_suffix(profile.region, "板块")
        if region:
            _add_membership(
                memberships,
                "region",
                _scope_code("EMR", region),
                region,
                (profile.region,),
                market,
                profile.code,
                snapshot_date,
            )
        if profile.industry and profile.industry != "-":
            _add_membership(
                memberships,
                "industry",
                _scope_code("EMI", profile.industry),
                profile.industry,
                (),
                market,
                profile.code,
                snapshot_date,
            )
        for concept in profile.concepts:
            _add_membership(
                memberships,
                "concept",
                _scope_code("EMC", concept),
                concept,
                (),
                market,
                profile.code,
                snapshot_date,
            )
    rows = tuple(memberships[key] for key in sorted(memberships))
    if not rows:
        raise ValueError("security profile synchronization produced no memberships")
    content = [dict(item.__dict__, aliases=list(item.aliases)) for item in rows]
    digest = hashlib.sha256(
        json.dumps(
            content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    return CatalogSnapshot(
        f"eastmoney-security-profile-{snapshot_date}-{digest[:12]}",
        "eastmoney-security-profile",
        "https://quote.eastmoney.com/center/gridlist.html",
        datetime.now(timezone.utc).isoformat(),
        snapshot_date,
        digest,
        "Eastmoney public security profile fields; retain attribution and snapshot date",
        scope_memberships=rows,
    )


def build_security_identity_snapshot(
    identities, *, as_of_date: str = None
) -> CatalogSnapshot:
    snapshot_date = as_of_date or date.today().isoformat()
    rows = []
    for code, name in identities:
        normalized_code = str(code).strip().zfill(6)
        market = security_market_code(normalized_code)
        normalized_name = str(name).strip()
        if market is None or not normalized_name:
            continue
        rows.append(
            ScopeMembership(
                "security",
                f"SEC:{market}:{normalized_code}",
                normalized_name,
                (normalized_code,),
                market,
                normalized_code,
                snapshot_date,
                None,
                None,
                "public_security_identity_exact",
            )
        )
    rows = tuple(sorted(rows, key=lambda item: (item.mktcode, item.tgtcode)))
    if not rows:
        raise ValueError("security identity synchronization produced no memberships")
    content = [dict(item.__dict__, aliases=list(item.aliases)) for item in rows]
    digest = hashlib.sha256(
        json.dumps(
            content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    return CatalogSnapshot(
        f"akshare-security-identity-{snapshot_date}-{digest[:12]}",
        "akshare-security-identity",
        "https://github.com/akfamily/akshare",
        datetime.now(timezone.utc).isoformat(),
        snapshot_date,
        digest,
        "AKShare public A-share code/name list; retain upstream attribution",
        scope_memberships=rows,
    )


def _add_membership(
    target,
    scope_type,
    scope_code,
    scope_name,
    aliases,
    market,
    code,
    snapshot_date,
):
    key = (scope_code, market, code)
    target[key] = ScopeMembership(
        scope_type,
        scope_code,
        scope_name,
        tuple(aliases),
        market,
        code,
        snapshot_date,
        None,
        None,
        "eastmoney_profile_exact",
    )


def _scope_code(prefix: str, name: str) -> str:
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _trim_suffix(value: str, suffix: str) -> str:
    text = str(value or "").strip()
    return text[: -len(suffix)] if text.endswith(suffix) else text

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from typing import Iterable, Mapping, Optional, Tuple

from .matching import canonical_scope_name
from .models import CatalogSnapshot, ScopeMembership
from .providers.eastmoney import security_market_code
from .providers.indexes import IndexDefinition


@dataclass(frozen=True)
class IndexSyncResult:
    snapshot: CatalogSnapshot
    matched: Tuple[dict, ...]
    unresolved: Tuple[str, ...]
    failed: Tuple[dict, ...]

    def to_dict(self):
        return {
            "snapshot_id": self.snapshot.snapshot_id,
            "source": self.snapshot.source,
            "scope_memberships": len(self.snapshot.scope_memberships),
            "matched": list(self.matched),
            "unresolved": list(self.unresolved),
            "failed": list(self.failed),
        }


def build_index_snapshot(
    targets: Iterable[str],
    *,
    provider,
    aliases: Mapping[str, str] = None,
    as_of_date: str = None,
) -> Optional[IndexSyncResult]:
    definitions = provider.list_indices()
    matched = []
    unresolved = []
    for target in dict.fromkeys(str(item).strip() for item in targets if str(item).strip()):
        match = _match_index(target, definitions, aliases or {})
        if match is None:
            unresolved.append(target)
        else:
            matched.append((target, match))
    rows = []
    successful = []
    failed = []
    by_code = {}
    for target, index in matched:
        by_code.setdefault(index.code, (index, []))[1].append(target)
    for index, target_aliases in by_code.values():
        try:
            constituents = provider.list_constituents(index)
        except Exception as exc:
            failed.append({"code": index.code, "name": index.name, "error": str(exc)})
            continue
        for constituent in constituents:
            market = security_market_code(constituent.code)
            if market is None:
                continue
            rows.append(
                ScopeMembership(
                    "index",
                    index.code,
                    index.name,
                    tuple(dict.fromkeys((*target_aliases, index.full_name))),
                    market,
                    constituent.code,
                    constituent.effective_date or as_of_date or date.today().isoformat(),
                    None,
                    constituent.weight,
                    "official_index_exact",
                )
            )
        successful.extend(
            {
                "target": target,
                "index_code": index.code,
                "index_name": index.name,
            }
            for target in target_aliases
        )
    if not rows:
        return None
    content = [dict(item.__dict__, aliases=list(item.aliases)) for item in rows]
    digest = hashlib.sha256(
        json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    snapshot_date = as_of_date or date.today().isoformat()
    snapshot = CatalogSnapshot(
        f"{provider.source}-{snapshot_date}-{digest[:12]}",
        provider.source,
        provider.source_url,
        datetime.now(timezone.utc).isoformat(),
        snapshot_date,
        digest,
        provider.license_note,
        scope_memberships=tuple(rows),
    )
    failed_names = {item["name"] for item in failed}
    failed_targets = [
        target for target, index in matched if index.name in failed_names
    ]
    return IndexSyncResult(
        snapshot,
        tuple(successful),
        tuple(dict.fromkeys((*unresolved, *failed_targets))),
        tuple(failed),
    )


def _match_index(
    target: str,
    definitions: Tuple[IndexDefinition, ...],
    aliases: Mapping[str, str],
) -> Optional[IndexDefinition]:
    canonical = canonical_scope_name(target)
    alias_used = canonical in aliases
    desired = aliases.get(canonical, target)
    desired_canonical = canonical_scope_name(desired)
    desired_code = str(desired).strip().upper()
    if re.fullmatch(r"[A-Z0-9]{6}", desired_code):
        code_matches = [
            item for item in definitions if item.code.upper() == desired_code
        ]
        return code_matches[0] if len(code_matches) == 1 else None
    exact_source = [
        item
        for item in definitions
        if str(target).strip().casefold()
        in {item.name.strip().casefold(), item.full_name.strip().casefold()}
    ]
    if len(exact_source) == 1:
        return exact_source[0]
    if not alias_used and "指数" not in str(target):
        return None
    exact = [
        item
        for item in definitions
        if desired_canonical
        in {canonical_scope_name(item.name), canonical_scope_name(item.full_name)}
    ]
    if len(exact) == 1:
        return exact[0]
    # A high string-similarity score is not sufficient to turn a generic board
    # name into an index.  Fuzzy matching is reserved for explicitly index-like
    # targets; all other non-exact mappings must be curated in index_aliases.
    scored = sorted(
        (
            max(
                SequenceMatcher(None, desired_canonical, canonical_scope_name(item.name)).ratio(),
                SequenceMatcher(None, desired_canonical, canonical_scope_name(item.full_name)).ratio(),
            ),
            item.code,
            item,
        )
        for item in definitions
    )
    if not scored:
        return None
    best_score, _, best = scored[-1]
    second = scored[-2][0] if len(scored) > 1 else 0.0
    if best_score >= 0.94 and best_score - second >= 0.08:
        return best
    return None

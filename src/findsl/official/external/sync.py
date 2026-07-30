from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Dict, Iterable, Mapping, Tuple

from .matching import ScopeMatch, canonical_scope_name, match_scope_target
from .models import CatalogSnapshot, IndustryMembership, ScopeMembership
from .providers.eastmoney import (
    EastmoneyBoardProvider,
    security_market_code,
)


@dataclass(frozen=True)
class ExternalSyncResult:
    snapshot: CatalogSnapshot
    matched: Tuple[ScopeMatch, ...]
    unresolved: Tuple[str, ...]
    failed_boards: Tuple[Dict[str, str], ...]
    discovered_boards: int = 0
    attempted_boards: int = 0

    def to_dict(self):
        return {
            "snapshot_id": self.snapshot.snapshot_id,
            "source": self.snapshot.source,
            "as_of_date": self.snapshot.as_of_date,
            "scope_memberships": len(self.snapshot.scope_memberships),
            "industry_memberships": len(self.snapshot.industry_memberships),
            "matched": [
                {
                    "target": item.target,
                    "board_type": item.board.board_type,
                    "board_code": item.board.code,
                    "board_name": item.board.name,
                    "method": item.method,
                    "score": item.score,
                }
                for item in self.matched
            ],
            "unresolved": list(self.unresolved),
            "failed_boards": list(self.failed_boards),
            "discovered_boards": self.discovered_boards,
            "attempted_boards": self.attempted_boards,
            "successful_boards": len(
                {
                    (item.board.board_type, item.board.code)
                    for item in self.matched
                }
            ),
        }


def build_eastmoney_snapshot(
    targets: Iterable[str],
    *,
    provider: EastmoneyBoardProvider,
    aliases: Mapping[str, str] = None,
    as_of_date: str = None,
) -> ExternalSyncResult:
    target_list = tuple(dict.fromkeys(str(item).strip() for item in targets if str(item).strip()))
    if not target_list:
        raise ValueError("at least one external scope target is required")
    board_sets = {
        "concept": provider.list_boards("concept"),
        "industry": provider.list_boards("industry"),
    }
    boards = tuple((*board_sets["concept"], *board_sets["industry"]))
    matches = []
    unresolved = []
    for target in target_list:
        match = _match_with_type_hint(target, board_sets, boards, aliases or {})
        if match is None:
            unresolved.append(target)
        else:
            matches.append(match)

    return _build_snapshot_from_matches(
        matches,
        unresolved,
        provider=provider,
        as_of_date=as_of_date,
        discovered_boards=len(boards),
    )


def build_full_eastmoney_snapshot(
    *,
    provider: EastmoneyBoardProvider,
    as_of_date: str = None,
) -> ExternalSyncResult:
    boards = tuple(
        (*provider.list_boards("concept"), *provider.list_boards("industry"))
    )
    matches = tuple(
        ScopeMatch(board.name, board, "source_full", 1.0) for board in boards
    )
    return _build_snapshot_from_matches(
        matches,
        (),
        provider=provider,
        as_of_date=as_of_date,
        discovered_boards=len(boards),
    )


def _build_snapshot_from_matches(
    matches,
    unresolved,
    *,
    provider,
    as_of_date,
    discovered_boards,
):
    scope_rows = []
    industry_rows = []
    failed = []
    by_board: Dict[Tuple[str, str], list[ScopeMatch]] = {}
    for match in matches:
        by_board.setdefault((match.board.board_type, match.board.code), []).append(match)
    for board_matches in by_board.values():
        board = board_matches[0].board
        try:
            constituents = provider.list_constituents(board)
        except Exception as exc:
            failed.append(
                {
                    "board_type": board.board_type,
                    "board_code": board.code,
                    "board_name": board.name,
                    "error": str(exc),
                }
            )
            continue
        target_aliases = tuple(item.target for item in board_matches)
        method = "+".join(sorted({item.method for item in board_matches}))
        for constituent in constituents:
            market = security_market_code(constituent.code)
            if market is None:
                continue
            scope_rows.append(
                ScopeMembership(
                    board.board_type,
                    board.code,
                    board.name,
                    target_aliases,
                    market,
                    constituent.code,
                    as_of_date or date.today().isoformat(),
                    None,
                    None,
                    method,
                )
            )
            if board.board_type == "industry":
                industry_rows.append(
                    IndustryMembership(
                        "Eastmoney industry board",
                        "provider",
                        board.code,
                        board.name,
                        market,
                        constituent.code,
                        as_of_date or date.today().isoformat(),
                        None,
                    )
                )
    if not scope_rows:
        raise ValueError("external synchronization produced no scope memberships")
    snapshot_date = as_of_date or date.today().isoformat()
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
        snapshot_id=f"eastmoney-{snapshot_date}-{digest[:12]}",
        source=provider.source,
        source_url=provider.source_url,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        as_of_date=snapshot_date,
        content_sha256=digest,
        license_note=provider.license_note,
        scope_memberships=tuple(scope_rows),
        industry_memberships=tuple(industry_rows),
    )
    successful_keys = {
        (item.scope_type, item.scope_code) for item in snapshot.scope_memberships
    }
    successful_matches = tuple(
        item for item in matches if (item.board.board_type, item.board.code) in successful_keys
    )
    failed_targets = tuple(
        item.target
        for item in matches
        if (item.board.board_type, item.board.code) not in successful_keys
    )
    return ExternalSyncResult(
        snapshot,
        successful_matches,
        tuple(dict.fromkeys((*unresolved, *failed_targets))),
        tuple(failed),
        discovered_boards=discovered_boards,
        attempted_boards=len(by_board),
    )


def _match_with_type_hint(target, board_sets, boards, aliases) -> ScopeMatch:
    normalized = canonical_scope_name(target)
    exact_source = [
        board for board in boards if board.name.casefold() == str(target).strip().casefold()
    ]
    if len(exact_source) == 1:
        return ScopeMatch(target, exact_source[0], "source_exact", 1.0)
    aliased = aliases.get(normalized)
    if aliased:
        return match_scope_target(target, boards, aliases=aliases)
    if "行业" in target or target.endswith("类"):
        hinted = match_scope_target(target, board_sets["industry"], aliases=aliases)
        if hinted:
            return hinted
    if "概念" in target:
        hinted = match_scope_target(target, board_sets["concept"], aliases=aliases)
        if hinted:
            return hinted
    return match_scope_target(target, boards, aliases=aliases)


def _canonical_row(item):
    payload = dict(item.__dict__)
    if isinstance(payload.get("aliases"), tuple):
        payload["aliases"] = list(payload["aliases"])
    return payload

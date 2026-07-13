from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Mapping, Optional

from .models import normalize_catalog_name
from .providers.eastmoney import BoardDefinition


_SUFFIXES = (
    "概念板块",
    "行业板块",
    "概念",
    "行业",
    "板块",
    "指数",
    "公司",
    "企业",
    "类",
)


def canonical_scope_name(value: str) -> str:
    normalized = normalize_catalog_name(value)
    changed = True
    while changed:
        changed = False
        for suffix in _SUFFIXES:
            folded = normalize_catalog_name(suffix)
            if normalized.endswith(folded) and len(normalized) > len(folded):
                normalized = normalized[: -len(folded)]
                changed = True
                break
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", normalized)


@dataclass(frozen=True)
class ScopeMatch:
    target: str
    board: BoardDefinition
    method: str
    score: float


def match_scope_target(
    target: str,
    boards: Iterable[BoardDefinition],
    *,
    aliases: Mapping[str, str] = None,
    fuzzy_threshold: float = 0.9,
    minimum_margin: float = 0.08,
) -> Optional[ScopeMatch]:
    board_list = tuple(boards)
    if not board_list:
        return None
    normalized = canonical_scope_name(target)
    alias_target = (aliases or {}).get(normalized)
    if alias_target:
        normalized = canonical_scope_name(alias_target)
    exact = [board for board in board_list if canonical_scope_name(board.name) == normalized]
    if len(exact) == 1:
        return ScopeMatch(target, exact[0], "alias_exact" if alias_target else "canonical_exact", 1.0)
    scored = sorted(
        [
            (
            SequenceMatcher(None, normalized, canonical_scope_name(board.name)).ratio(),
            board,
            )
            for board in board_list
        ],
        key=lambda item: (item[0], item[1].code),
    )
    best_score, best = scored[-1]
    second_score = scored[-2][0] if len(scored) > 1 else 0.0
    if best_score >= fuzzy_threshold and best_score - second_score >= minimum_margin:
        return ScopeMatch(target, best, "fuzzy_unique", round(best_score, 6))
    return None

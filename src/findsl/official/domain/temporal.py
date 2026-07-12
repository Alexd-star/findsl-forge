from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from ..ir.base import CanonicalIr


class TemporalParseError(ValueError):
    def __init__(self, code: str, message: str, source: str):
        super().__init__(message)
        self.code = code
        self.source = source


@dataclass(frozen=True)
class TemporalQuantifier(CanonicalIr):
    mode: str
    comparator: str
    threshold: Optional[int]
    maximum: Optional[int]
    unit: str
    every: bool
    source: str
    trading_sequence: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "TemporalQuantifier",
            "mode": self.mode,
            "comparator": self.comparator,
            "threshold": self.threshold,
            "maximum": self.maximum,
            "unit": self.unit,
            "every": self.every,
            "source": self.source,
            "semantics": "trading_sequence" if self.trading_sequence else "calendar_sequence",
        }


_COUNT_RE = re.compile(
    r"^(?P<mode>CONS|EXIST)\s*"
    r"(?P<comparator>>=|<=|!=|=|>|<)?\s*"
    r"(?P<value>每|\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百]+)?\s*"
    r"(?P<value_unit>年|季度|月|周|日|天|分钟)?\s*"
    r"(?:[-~至到]\s*(?P<maximum>\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百]+)\s*"
    r"(?P<maximum_unit>年|季度|月|周|日|天|分钟)?)?\s*$",
    re.IGNORECASE,
)


def parse_temporal_quantifier(source: str) -> TemporalQuantifier:
    text = str(source or "").strip()
    if not re.match(r"^(CONS|EXIST)\b", text, flags=re.IGNORECASE):
        raise TemporalParseError(
            "TEMPORAL_MODE_UNSUPPORTED",
            f"count_exp must start with CONS or EXIST: {source}",
            text,
        )
    match = _COUNT_RE.fullmatch(text)
    if match is None:
        raise TemporalParseError(
            "TEMPORAL_SYNTAX_INVALID",
            f"invalid count_exp syntax: {source}",
            text,
        )

    mode = match.group("mode").upper()
    comparator = match.group("comparator") or ">"
    raw_value = match.group("value") or ""
    unit = _canonical_unit(match.group("value_unit") or match.group("maximum_unit") or "")

    if raw_value == "每":
        if not unit:
            raise TemporalParseError(
                "TEMPORAL_EVERY_UNIT_REQUIRED",
                "the every form requires a year/quarter/month/week/day unit",
                text,
            )
        if comparator not in {"=", "!="}:
            raise TemporalParseError(
                "TEMPORAL_EVERY_COMPARATOR_INVALID",
                "the every form only supports equality semantics",
                text,
            )
        if match.group("maximum"):
            raise TemporalParseError(
                "TEMPORAL_RANGE_INVALID",
                "the every form cannot declare a numeric range",
                text,
            )
        return TemporalQuantifier(mode, comparator, None, None, unit, True, text)

    if raw_value:
        threshold = parse_count_token(raw_value, text)
    else:
        threshold = 1 if mode == "CONS" else 0

    raw_maximum = match.group("maximum")
    maximum = parse_count_token(raw_maximum, text) if raw_maximum else None
    if mode == "CONS" and threshold <= 0:
        raise TemporalParseError(
            "TEMPORAL_CONSECUTIVE_THRESHOLD_INVALID",
            "CONS requires a positive run-length threshold",
            text,
        )
    if threshold < 0:
        raise TemporalParseError(
            "TEMPORAL_THRESHOLD_INVALID",
            "temporal threshold cannot be negative",
            text,
        )
    if maximum is not None:
        if comparator not in {"=", ">"}:
            raise TemporalParseError(
                "TEMPORAL_RANGE_COMPARATOR_INVALID",
                "a temporal range cannot be combined with an explicit comparator",
                text,
            )
        if maximum < threshold:
            raise TemporalParseError(
                "TEMPORAL_RANGE_INVALID",
                "temporal range maximum must not be lower than its minimum",
                text,
            )
        comparator = "between"

    return TemporalQuantifier(mode, comparator, threshold, maximum, unit, False, text)


def evaluate_temporal_matches(
    matches: Iterable[bool],
    quantifier: TemporalQuantifier,
) -> bool:
    values = tuple(bool(value) for value in matches)
    if quantifier.every:
        if not values:
            return False
        all_match = all(values)
        return all_match if quantifier.comparator == "=" else not all_match

    if quantifier.mode == "EXIST":
        metric = sum(values)
    else:
        metric = 0
        current = 0
        for matched in values:
            current = current + 1 if matched else 0
            metric = max(metric, current)

    if quantifier.maximum is not None or quantifier.comparator == "between":
        return quantifier.threshold <= metric <= quantifier.maximum
    comparator = quantifier.comparator
    if quantifier.mode == "CONS" and comparator == "=":
        comparator = ">="
    threshold = quantifier.threshold
    return {
        "<": metric < threshold,
        "<=": metric <= threshold,
        "=": metric == threshold,
        "!=": metric != threshold,
        ">": metric > threshold,
        ">=": metric >= threshold,
    }[comparator]


def evaluate_calendar_bucket_matches(
    bucket_matches: Iterable[tuple[int, bool]],
    quantifier: TemporalQuantifier,
) -> bool:
    coalesced: Dict[int, bool] = {}
    for ordinal, matched in bucket_matches:
        ordinal = int(ordinal)
        coalesced[ordinal] = coalesced.get(ordinal, False) or bool(matched)
    if not coalesced:
        return evaluate_temporal_matches((), quantifier)
    first, last = min(coalesced), max(coalesced)
    dense = tuple(coalesced.get(ordinal, False) for ordinal in range(first, last + 1))
    return evaluate_temporal_matches(dense, quantifier)


def _canonical_unit(unit: str) -> str:
    return "日" if unit == "天" else unit


def parse_count_token(value: str, source: str = "") -> int:
    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        number = float(value)
        if not number.is_integer():
            raise TemporalParseError(
                "TEMPORAL_FRACTIONAL_UNIT_UNSUPPORTED",
                "fractional temporal counts require an explicit business conversion policy",
                source,
            )
        return int(number)
    return _parse_chinese_integer(value, source or value)


def _parse_chinese_integer(value: str, source: str) -> int:
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if all(char in digits for char in value):
        return int("".join(str(digits[char]) for char in value))
    total = 0
    current = 0
    for char in value:
        if char in digits:
            current = digits[char]
        elif char == "十":
            total += (current or 1) * 10
            current = 0
        elif char == "百":
            total += (current or 1) * 100
            current = 0
        else:
            raise TemporalParseError(
                "TEMPORAL_COUNT_INVALID",
                f"unsupported Chinese count: {value}",
                source,
            )
    return total + current

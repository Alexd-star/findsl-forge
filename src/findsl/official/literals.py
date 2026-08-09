from __future__ import annotations

import re
from typing import Optional

from .ast import OfficialLiteral, OfficialRangeLiteral


def parse_range_text(value: str) -> Optional[OfficialRangeLiteral]:
    match = re.fullmatch(
        r"\s*([\[(])\s*(?P<lower>.+?)\s*,\s*(?P<upper>.+?)\s*([\])])\s*",
        value,
    )
    if not match:
        return None
    return OfficialRangeLiteral(
        lower=_range_part_literal(match.group("lower")),
        upper=_range_part_literal(match.group("upper")),
        lower_inclusive=match.group(1) == "[",
        upper_inclusive=match.group(4) == "]",
    )


def is_numeric_percent_literal(value: str) -> bool:
    return bool(re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)%", str(value)))


def _range_part_literal(value: str) -> OfficialLiteral:
    text = value.strip()
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?%", text):
        return OfficialLiteral(text)
    if re.fullmatch(r"[+-]?\d+", text):
        return OfficialLiteral(int(text))
    if re.fullmatch(r"[+-]?\d+\.\d+", text):
        return OfficialLiteral(float(text))
    return OfficialLiteral(text)

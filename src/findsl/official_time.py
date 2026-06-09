from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, List, Optional, Sequence


@dataclass(frozen=True)
class DateNormalization:
    constraints: List[str]
    warnings: List[str]


@dataclass(frozen=True)
class _DateInterval:
    start: date
    end: date


CURRENT_DAY_ALIASES = {"今天", "今日", "当前", "目前", "当日", "当天", "本日", "现在", "最新"}
PREVIOUS_TRADING_DAY_ALIASES = {"昨天", "昨日", "上个交易日", "前一个交易日"}
TWO_TRADING_DAYS_AGO_ALIASES = {"前天"}
CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def normalize_official_date(
    value: str,
    *,
    anchor_date: str = "2026-04-14",
    trading_dates: Optional[Sequence[str]] = None,
    field: str = "base.bizdate",
) -> DateNormalization:
    text = str(value or "").strip()
    if not text:
        return DateNormalization([], [])

    anchor = _parse_iso_date(anchor_date)
    calendar = _sorted_trading_dates(trading_dates)

    normalized = _normalize_interval(text, anchor, calendar)
    if normalized:
        interval, warnings = normalized
        interval, clip_warnings = _clip_future_interval(text, interval, anchor)
        warnings = warnings + clip_warnings
        if interval is None:
            return DateNormalization(["1=0"], warnings)
        return DateNormalization([_interval_constraint(field, interval)], warnings)

    return DateNormalization(["1=1"], [f"date slot requires runtime normalization: {text}"])


def _normalize_interval(text: str, anchor: date, calendar: List[date]) -> Optional[tuple[_DateInterval, List[str]]]:
    exact = _normalize_exact_date(text, anchor)
    if exact:
        exact_date = _parse_iso_date(exact)
        return _DateInterval(exact_date, exact_date), []

    if text in CURRENT_DAY_ALIASES:
        return _DateInterval(anchor, anchor), []
    if text in PREVIOUS_TRADING_DAY_ALIASES:
        shifted = _shift_trading_or_calendar(anchor, -1, calendar)
        return _DateInterval(shifted, shifted), []
    if text in TWO_TRADING_DAYS_AGO_ALIASES:
        shifted = _shift_trading_or_calendar(anchor, -2, calendar)
        return _DateInterval(shifted, shifted), []

    recent_ordinal = _parse_recent_ordinal(text)
    if recent_ordinal:
        amount, unit = recent_ordinal
        if unit == "日":
            target = _shift_trading_or_calendar(anchor, -(amount - 1), calendar)
            return _DateInterval(target, target), []

    composite = _parse_composite_relative(text)
    if composite:
        base_text, direction, amount, unit = composite
        base = _normalize_interval(base_text, anchor, calendar)
        if not base:
            return None
        base_interval, base_warnings = base
        interval, warnings = _apply_composite_interval(text, base_interval, direction, amount, unit, calendar, anchor)
        return interval, base_warnings + warnings

    year_range = _normalize_year_range_text(text)
    if year_range:
        start_year, end_year = year_range
        return _DateInterval(date(start_year, 1, 1), date(end_year, 12, 31)), []

    year = _normalize_year_text(text)
    if year is not None:
        return _DateInterval(date(year, 1, 1), date(year, 12, 31)), []

    if text in {"今年", "本年", "本年度", "今年以来", "年初至今"}:
        return _DateInterval(date(anchor.year, 1, 1), anchor), []
    if text in {"去年", "上一年"}:
        year = anchor.year - 1
        return _DateInterval(date(year, 1, 1), date(year, 12, 31)), []
    if text == "前年":
        year = anchor.year - 2
        return _DateInterval(date(year, 1, 1), date(year, 12, 31)), []
    if text in {"本月", "这个月"}:
        return _DateInterval(date(anchor.year, anchor.month, 1), anchor), []
    if text in {"上月", "上个月"}:
        start = _add_months(date(anchor.year, anchor.month, 1), -1)
        end = date(anchor.year, anchor.month, 1) - timedelta(days=1)
        return _DateInterval(start, end), []
    if text == "本周":
        start = anchor - timedelta(days=anchor.weekday())
        return _DateInterval(start, anchor), []
    if text == "上周":
        this_monday = anchor - timedelta(days=anchor.weekday())
        start = this_monday - timedelta(days=7)
        end = this_monday - timedelta(days=1)
        return _DateInterval(start, end), []

    recent = _parse_recent_window(text)
    if recent:
        amount, unit = recent
        start, end = _window_start_end(anchor, amount, unit, calendar)
        return _DateInterval(start, end), []

    return None


def _normalize_exact_date(text: str, anchor: date) -> str:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    match = re.fullmatch(r"(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})[日号]?", text)
    if match:
        return date(int(match.group("year")), int(match.group("month")), int(match.group("day"))).isoformat()
    match = re.fullmatch(r"(?P<month>\d{1,2})月(?P<day>\d{1,2})[日号]?", text)
    if match:
        return date(anchor.year, int(match.group("month")), int(match.group("day"))).isoformat()
    return ""


def _normalize_year_text(text: str) -> Optional[int]:
    match = re.fullmatch(r"(\d{4})年", text)
    if match:
        return int(match.group(1))
    match = re.fullmatch(r"(\d{2})年", text)
    if match:
        return _century_year(int(match.group(1)))
    match = re.fullmatch(r"([零〇一二两三四五六七八九]{2,4})年", text)
    if not match:
        return None
    digits = "".join(str(CHINESE_DIGITS[ch]) for ch in match.group(1))
    if len(digits) == 4:
        return int(digits)
    if len(digits) == 2:
        return _century_year(int(digits))
    return None


def _normalize_year_range_text(text: str) -> Optional[tuple[int, int]]:
    match = re.fullmatch(
        r"(?P<start>\d{2,4}|[零〇一二两三四五六七八九]{2,4})年(?:-|到|至|~|～|—|－)(?P<end>\d{2,4}|[零〇一二两三四五六七八九]{2,4})年",
        text,
    )
    if not match:
        return None
    start = _normalize_year_text(f"{match.group('start')}年")
    end = _normalize_year_text(f"{match.group('end')}年")
    if start is None or end is None:
        return None
    return start, end


def _parse_recent_window(text: str) -> Optional[tuple[int, str]]:
    match = re.fullmatch(r"(?:近|最近|这)(?P<num>\d+|[零〇一二两三四五六七八九十百个]+)(?P<unit>日|天|个交易日|周|月|个月|年)", text)
    if not match:
        match = re.fullmatch(r"(?P<num>\d+|[零〇一二两三四五六七八九十百个]+)(?P<unit>日|天|个交易日|周|月|个月|年)内", text)
    if not match:
        return None
    amount = _parse_count(match.group("num"))
    if amount <= 0:
        return None
    unit = match.group("unit")
    if unit in {"天", "个交易日"}:
        unit = "日"
    if unit == "个月":
        unit = "月"
    return amount, unit


def _parse_recent_ordinal(text: str) -> Optional[tuple[int, str]]:
    match = re.fullmatch(
        r"最近的(?:第)?(?P<num>\d+|[零〇一二两三四五六七八九十百个]+)(?P<unit>个交易日|日|天)",
        text,
    )
    if not match:
        return None
    amount = _parse_count(match.group("num"))
    if amount <= 0:
        return None
    return amount, _normalize_unit(match.group("unit"))


def _parse_composite_relative(text: str) -> Optional[tuple[str, str, int, str]]:
    match = re.fullmatch(
        r"(?P<base>.+)的(?P<direction>前|后|第)(?P<num>\d+|[零〇一二两三四五六七八九十百个]+)(?P<unit>个交易日|日|天|周|个月|月|年)",
        text,
    )
    if not match:
        return None
    amount = _parse_count(match.group("num"))
    if amount <= 0:
        return None
    return match.group("base"), match.group("direction"), amount, _normalize_unit(match.group("unit"))


def _normalize_unit(unit: str) -> str:
    if unit in {"天", "个交易日"}:
        return "日"
    if unit == "个月":
        return "月"
    return unit


def _apply_composite_interval(
    text: str,
    base: _DateInterval,
    direction: str,
    amount: int,
    unit: str,
    calendar: List[date],
    anchor: date,
) -> tuple[_DateInterval, List[str]]:
    if direction == "前":
        return _interval_before(base, amount, unit, calendar), []
    if direction == "后":
        return _interval_after(text, base, amount, unit, calendar, anchor)
    return _interval_ordinal(text, base, amount, unit, calendar, anchor)


def _interval_before(base: _DateInterval, amount: int, unit: str, calendar: List[date]) -> _DateInterval:
    if unit == "日":
        if calendar:
            end_index = _trading_index_before(base.start, calendar)
            if end_index is not None:
                start_index = max(0, end_index - amount + 1)
                return _DateInterval(calendar[start_index], calendar[end_index])
        return _DateInterval(base.start - timedelta(days=amount), base.start - timedelta(days=1))
    if unit == "周":
        return _DateInterval(base.start - timedelta(days=amount * 7), base.start - timedelta(days=1))
    if unit == "月":
        return _DateInterval(_add_months(base.start, -amount), base.start - timedelta(days=1))
    if unit == "年":
        return _DateInterval(_add_years(base.start, -amount), base.start - timedelta(days=1))
    return base


def _interval_after(
    text: str,
    base: _DateInterval,
    amount: int,
    unit: str,
    calendar: List[date],
    anchor: date,
) -> tuple[_DateInterval, List[str]]:
    warnings: List[str] = []
    if unit == "日":
        if calendar:
            start_index = _trading_index_after(base.end, calendar)
            if start_index is None:
                return _DateInterval(base.end + timedelta(days=1), base.end + timedelta(days=amount)), warnings
            end_index = start_index + amount - 1
            if end_index >= len(calendar):
                end_index = len(calendar) - 1
                warnings.append(_future_clip_warning(text, anchor))
            return _DateInterval(calendar[start_index], calendar[end_index]), warnings
        return _DateInterval(base.end + timedelta(days=1), base.end + timedelta(days=amount)), warnings
    if unit == "周":
        return _DateInterval(base.end + timedelta(days=1), base.end + timedelta(days=amount * 7)), warnings
    if unit == "月":
        return _DateInterval(base.end + timedelta(days=1), _add_months(base.end, amount)), warnings
    if unit == "年":
        return _DateInterval(base.end + timedelta(days=1), _add_years(base.end, amount)), warnings
    return base, warnings


def _interval_ordinal(
    text: str,
    base: _DateInterval,
    amount: int,
    unit: str,
    calendar: List[date],
    anchor: date,
) -> tuple[_DateInterval, List[str]]:
    warnings: List[str] = []
    if unit == "日":
        if calendar:
            start_index = _trading_index_at_or_after(base.start, calendar)
            if start_index is not None:
                target_index = start_index + amount - 1
                if target_index >= len(calendar):
                    target_index = len(calendar) - 1
                    warnings.append(_future_clip_warning(text, anchor))
                target = calendar[target_index]
                return _DateInterval(target, target), warnings
        target = base.start + timedelta(days=amount - 1)
        return _DateInterval(target, target), warnings
    if unit == "周":
        start = base.start + timedelta(days=(amount - 1) * 7)
        return _DateInterval(start, start + timedelta(days=6)), warnings
    if unit == "月":
        start = _add_months(date(base.start.year, base.start.month, 1), amount - 1)
        end = _add_months(start, 1) - timedelta(days=1)
        return _DateInterval(start, end), warnings
    if unit == "年":
        year = base.start.year + amount - 1
        return _DateInterval(date(year, 1, 1), date(year, 12, 31)), warnings
    return base, warnings


def _clip_future_interval(text: str, interval: _DateInterval, anchor: date) -> tuple[Optional[_DateInterval], List[str]]:
    if interval.start > anchor:
        return None, [
            f"date slot '{text}' starts after official anchor date {anchor.isoformat()}; no official rows can satisfy it"
        ]
    if interval.end > anchor:
        return _DateInterval(interval.start, anchor), [_future_clip_warning(text, anchor)]
    return interval, []


def _future_clip_warning(text: str, anchor: date) -> str:
    return f"date slot '{text}' extends beyond official anchor date {anchor.isoformat()}; clipped to available official data"


def _trading_index_before(target: date, calendar: List[date]) -> Optional[int]:
    for index in range(len(calendar) - 1, -1, -1):
        if calendar[index] < target:
            return index
    return None


def _trading_index_after(target: date, calendar: List[date]) -> Optional[int]:
    for index, item in enumerate(calendar):
        if item > target:
            return index
    return None


def _trading_index_at_or_after(target: date, calendar: List[date]) -> Optional[int]:
    for index, item in enumerate(calendar):
        if item >= target:
            return index
    return None


def _window_start_end(anchor: date, amount: int, unit: str, trading_dates: List[date]) -> tuple[date, date]:
    if unit == "日":
        if trading_dates:
            return _shift_trading_or_calendar(anchor, -(amount - 1), trading_dates), anchor
        return anchor - timedelta(days=amount - 1), anchor
    if unit == "周":
        return anchor - timedelta(days=amount * 7 - 1), anchor
    if unit == "月":
        return _add_months(anchor, -amount) + timedelta(days=1), anchor
    if unit == "年":
        return date(anchor.year - amount + 1, 1, 1), anchor
    return anchor, anchor


def _shift_trading_or_calendar(anchor: date, offset: int, trading_dates: List[date]) -> date:
    if not trading_dates:
        return anchor + timedelta(days=offset)
    if anchor in trading_dates:
        index = trading_dates.index(anchor)
    else:
        earlier = [item for item in trading_dates if item <= anchor]
        index = len(earlier) - 1
    target_index = max(0, min(len(trading_dates) - 1, index + offset))
    return trading_dates[target_index]


def _sorted_trading_dates(values: Optional[Iterable[str]]) -> List[date]:
    if not values:
        return []
    return sorted({_parse_iso_date(item) for item in values})


def _parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _parse_count(value: str) -> int:
    text = value.replace("个", "")
    if text.isdigit():
        return int(text)
    if text in CHINESE_DIGITS:
        return CHINESE_DIGITS[text]
    if text == "十":
        return 10
    if "十" in text:
        left, _, right = text.partition("十")
        tens = CHINESE_DIGITS[left] if left else 1
        ones = CHINESE_DIGITS[right] if right else 0
        return tens * 10 + ones
    if "百" in text:
        left, _, right = text.partition("百")
        hundreds = CHINESE_DIGITS[left] if left else 1
        return hundreds * 100 + (_parse_count(right) if right else 0)
    return 0


def _century_year(value: int) -> int:
    return 2000 + value if value <= 30 else 1900 + value


def _add_months(base: date, months: int) -> date:
    month_index = base.month - 1 + months
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base.day, _month_last_day(year, month))
    return date(year, month, day)


def _add_years(base: date, years: int) -> date:
    target_year = base.year + years
    day = min(base.day, _month_last_day(target_year, base.month))
    return date(target_year, base.month, day)


def _month_last_day(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - timedelta(days=1)).day


def _interval_constraint(field: str, interval: _DateInterval) -> str:
    if interval.start == interval.end:
        return f"{field} = '{interval.start.isoformat()}'"
    return _between(field, interval.start, interval.end)


def _between(field: str, start: date, end: date) -> str:
    return f"{field} BETWEEN '{start.isoformat()}' AND '{end.isoformat()}'"

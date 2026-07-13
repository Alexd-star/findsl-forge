from __future__ import annotations

import re
from calendar import monthrange
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

from ..registry import IndicatorDefinition, OfficialIndicatorRegistry
from ..typed_ast import TypedNode
from ..types import BOOLEAN, NUMERIC, STRING, TIME
from .expressions import DataRequirement, DateConstraint, EventSpec, IndicatorRef, MarketScope, UniverseSpec
from .temporal import TemporalParseError, TemporalQuantifier, parse_temporal_quantifier
from .temporal import parse_count_token
from .market import MarketParseError, parse_market_expression
from .scope import ScopeParseError, parse_scope_expression


class DomainBindingError(ValueError):
    def __init__(self, code: str, message: str, *, function: str, slot: str, value: str):
        super().__init__(message)
        self.code = code
        self.function = function
        self.slot = slot
        self.value = value


@dataclass(frozen=True)
class BoundFunction:
    function_name: str
    expression: object
    indicators: Tuple[IndicatorRef, ...]
    market_scope: MarketScope
    market_expression: object
    scope_expression: object
    date_constraint: DateConstraint
    requirement: DataRequirement
    aggregate: Optional[str]
    temporal: Optional[TemporalQuantifier]

    def to_dict(self):
        return {
            "function_name": self.function_name,
            "expression": self.expression.to_dict(),
            "indicators": [item.to_dict() for item in self.indicators],
            "market_scope": self.market_scope.to_dict(),
            "market_expression": self.market_expression.to_dict() if self.market_expression else None,
            "scope_expression": self.scope_expression.to_dict() if self.scope_expression else None,
            "date_constraint": self.date_constraint.to_dict(),
            "requirement": self.requirement.to_dict(),
            "aggregate": self.aggregate,
            "temporal": self.temporal.to_dict() if self.temporal else None,
        }


_TYPE_MAP = {"numeric": NUMERIC, "boolean": BOOLEAN, "string": STRING, "time": TIME}
_EVENT_FUNCTIONS = {"cross_above", "cross_down", "close_together", "reset", "golden_cross"}
_DEFAULT_PRICE_SLOTS = {
    "cross_above": "indicator_name_1",
    "cross_down": "indicator_name_1",
    "close_together": "indicator_name_1",
    "reset": "indicator_name_1",
    "record_high": "indicator_name",
    "record_low": "indicator_name",
    "position": "indicator_name",
}
_MARKETS = {"沪": "SH", "深": "SZ", "北": "BJ", "港": "HK", "美": "US", "A股": "A", "B股": "B"}


def bind_function(typed: TypedNode, registry: OfficialIndicatorRegistry) -> BoundFunction:
    if typed.binding is None:
        raise DomainBindingError("DOMAIN_NOT_FUNCTION", "typed node has no function binding", function="", slot="", value="")
    name = typed.binding.signature.name
    slots = normalize_function_slots(name, typed.binding.slots)
    indicator_slots = [slot for slot in typed.binding.signature.slots if slot.startswith("indicator_name")]
    is_universe = (
        name == "indicator"
        and indicator_slots == ["indicator_name"]
        and not str(slots.get("indicator_name", "")).strip()
    )
    indicators = (
        ()
        if is_universe
        else tuple(_bind_indicator(name, slot, slots.get(slot, ""), registry) for slot in indicator_slots)
    )
    if not indicators and not is_universe:
        raise DomainBindingError("DOMAIN_CAPABILITY_UNSUPPORTED", f"{name} has no bindable indicator slot", function=name, slot="indicator_name", value="")
    market_value = slots.get("market", "")
    try:
        market_expression = parse_market_expression(market_value)
    except MarketParseError as exc:
        raise DomainBindingError(
            exc.code,
            str(exc),
            function=name,
            slot="market",
            value=market_value,
        ) from exc
    market = _bind_market(name, market_value)
    scope_value = slots.get("filter_scope", slots.get("keywords", ""))
    try:
        scope_expression = parse_scope_expression(scope_value)
    except ScopeParseError as exc:
        raise DomainBindingError(
            exc.code,
            str(exc),
            function=name,
            slot="filter_scope" if "filter_scope" in slots else "keywords",
            value=scope_value,
        ) from exc
    date = parse_date_constraint(slots.get("date", slots.get("period", "")))
    aggregate = slots.get("agg_func", "").strip().upper() or None
    if aggregate and aggregate not in {"AVG", "SUM", "MAX", "MIN", "GROWTH", "GROWTH_RISE", "GROWTH_FALL"}:
        raise DomainBindingError("DOMAIN_INVALID_ENUM", f"unsupported aggregate {aggregate}", function=name, slot="agg_func", value=aggregate)
    if name == "rank":
        direction = slots.get("direction", "").lower()
        if direction not in {"asc", "desc"}:
            raise DomainBindingError("DOMAIN_INVALID_ENUM", f"unsupported rank direction {direction}", function=name, slot="direction", value=direction)
    count_expression = slots.get("count_exp", "").strip()
    try:
        temporal = parse_temporal_quantifier(count_expression) if count_expression else None
    except TemporalParseError as exc:
        raise DomainBindingError(exc.code, str(exc), function=name, slot="count_exp", value=count_expression) from exc
    domains = frozenset({"quote"}) if is_universe else frozenset(item.domain for item in indicators)
    capabilities = (
        frozenset({"scan"})
        if is_universe
        else frozenset(capability for definition in (_definition(item, registry) for item in indicators) for capability in definition.capabilities)
    )
    requirement = DataRequirement(domains, capabilities)
    expression = (
        UniverseSpec()
        if is_universe
        else EventSpec(name, indicators[0], indicators[1])
        if name in _EVENT_FUNCTIONS
        else indicators[0]
    )
    return BoundFunction(
        name,
        expression,
        indicators,
        market,
        market_expression,
        scope_expression,
        date,
        requirement,
        aggregate,
        temporal,
    )


def normalize_function_slots(name: str, slots: Mapping[str, str]) -> Mapping[str, str]:
    """Apply only defaults that are explicit in the official slot contract."""
    normalized = dict(slots)
    default_slot = _DEFAULT_PRICE_SLOTS.get(name)
    if default_slot and not str(normalized.get(default_slot, "")).strip():
        normalized[default_slot] = "最新价"
    return normalized


def _definition(indicator: IndicatorRef, registry: OfficialIndicatorRegistry) -> IndicatorDefinition:
    return registry.resolve(indicator.indicator_id)


def _bind_indicator(function: str, slot: str, value: str, registry: OfficialIndicatorRegistry) -> IndicatorRef:
    if not value:
        raise DomainBindingError("DOMAIN_CAPABILITY_UNSUPPORTED", "empty indicator slot cannot be bound", function=function, slot=slot, value=value)
    try:
        definition = registry.resolve(value)
    except KeyError as exc:
        raise DomainBindingError("DOMAIN_UNKNOWN_INDICATOR", f"unknown indicator {value}", function=function, slot=slot, value=value) from exc
    if definition.availability == "missing":
        raise DomainBindingError("DOMAIN_DATA_UNAVAILABLE", f"indicator data is unavailable: {value}", function=function, slot=slot, value=value)
    return IndicatorRef(definition.canonical_name, _TYPE_MAP[definition.value_type], definition.unit, definition.domain, definition.availability)


def _bind_market(function: str, value: str) -> MarketScope:
    if not value.strip():
        return MarketScope(("ALL",))
    parts = [part.strip() for part in re.split(r"[|&^,，]", value) if part.strip()]
    return MarketScope(tuple(dict.fromkeys(_MARKETS.get(part, part.upper()) for part in parts)))


def parse_date_constraint(value: str) -> DateConstraint:
    value = value.strip()
    if not value:
        return DateConstraint("unspecified")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return DateConstraint("exact", value, value)
    if value in {"今日", "今天", "当天", "当前", "目前", "当日", "本日", "现在", "最新"}:
        return DateConstraint("relative", anchor="today")
    relative_sessions = {
        "昨天": 1,
        "昨日": 1,
        "前一个交易日": 1,
        "前一交易日": 1,
        "前天": 2,
    }
    if value in relative_sessions:
        return DateConstraint(
            "relative_session",
            anchor="latest",
            amount=relative_sessions[value],
            unit="session",
            trading_day_based=True,
        )
    if value in {"近半年", "最近半年", "过去半年", "这半年"}:
        return DateConstraint(
            "recent_calendar",
            anchor="latest",
            amount=6,
            unit="month",
            trading_day_based=False,
        )
    number = r"\d+|[零〇一二两三四五六七八九十百]+"
    year_token = r"\d{2,4}|[零〇一二两三四五六七八九]{2,4}"
    dynamic_periods = {
        "本周": ("week", 0),
        "本月": ("month", 0),
        "这个月": ("month", 0),
        "本季度": ("quarter", 0),
        "这个季度": ("quarter", 0),
        "今年": ("year", 0),
        "本年": ("year", 0),
        "本年度": ("year", 0),
        "今年以来": ("year", 0),
        "年初至今": ("year", 0),
        "上周": ("week", -1),
        "上月": ("month", -1),
        "上个月": ("month", -1),
        "去年": ("year", -1),
        "上一年": ("year", -1),
        "前年": ("year", -2),
    }
    if value in dynamic_periods:
        unit, offset = dynamic_periods[value]
        return DateConstraint(
            "dynamic_period",
            anchor="latest",
            unit=unit,
            trading_day_based=False,
            offset=offset,
        )
    ordinal_year = re.fullmatch(
        rf"(?P<base>.+)的第(?P<count>{number})年",
        value,
    )
    if ordinal_year:
        base = parse_date_constraint(ordinal_year.group("base"))
        count = parse_count_token(ordinal_year.group("count"), value)
        if base.kind == "calendar_range" and base.start:
            year_value = int(base.start[:4]) + count - 1
            return DateConstraint(
                "calendar_range",
                f"{year_value:04d}-01-01",
                f"{year_value:04d}-12-31",
                unit="year",
                trading_day_based=False,
            )
    following_years = re.fullmatch(
        rf"(?P<base>.+)的后(?P<count>{number})年",
        value,
    )
    if following_years:
        base = parse_date_constraint(following_years.group("base"))
        count = parse_count_token(following_years.group("count"), value)
        if base.kind == "calendar_range" and base.end:
            start_year = int(base.end[:4]) + 1
            end_year = start_year + count - 1
            return DateConstraint(
                "calendar_range",
                f"{start_year:04d}-01-01",
                f"{end_year:04d}-12-31",
                amount=count,
                unit="year",
                trading_day_based=False,
            )
    shifted_month = re.fullmatch(
        rf"(?P<base>.+)的前(?P<count>{number})月",
        value,
    )
    if shifted_month:
        base = parse_date_constraint(shifted_month.group("base"))
        count = parse_count_token(shifted_month.group("count"), value)
        if base.kind == "anchor_calendar" and base.unit == "month":
            return DateConstraint(
                "anchor_calendar",
                anchor="latest",
                unit="month",
                trading_day_based=False,
                offset=base.offset - count,
                month=base.month,
            )
    previous_sessions = re.fullmatch(
        rf"(?P<base>.+)的前(?P<count>{number})(?:个交易日|日|天)",
        value,
    )
    if previous_sessions:
        base = parse_date_constraint(previous_sessions.group("base"))
        count = parse_count_token(previous_sessions.group("count"), value)
        if base.kind == "relative_session" and base.amount:
            return DateConstraint(
                "session_slice",
                anchor="latest",
                amount=count,
                unit="session",
                offset=base.amount + 1,
            )
        if base.kind == "recent_sessions" and base.amount:
            return DateConstraint(
                "session_slice",
                anchor="latest",
                amount=count,
                unit="session",
                offset=base.amount,
            )
        if base.kind == "dynamic_period" and base.unit:
            return DateConstraint(
                "before_period_sessions",
                anchor="latest",
                amount=count,
                unit=base.unit,
                trading_day_based=True,
                offset=base.offset,
            )
        if base.kind == "relative" and base.anchor == "today":
            return DateConstraint(
                "session_slice",
                anchor="latest",
                amount=count,
                unit="session",
                trading_day_based=True,
                offset=1,
            )
        if base.kind == "anchor_calendar" and base.day is not None:
            return DateConstraint(
                "before_anchor_sessions",
                anchor="latest",
                amount=count,
                unit="session",
                trading_day_based=True,
                offset=base.offset,
                month=base.month,
                day=base.day,
            )
    following_sessions = re.fullmatch(
        rf"(?P<base>.+)的后(?P<count>{number})(?:个交易日|日|天)",
        value,
    )
    if following_sessions:
        base = parse_date_constraint(following_sessions.group("base"))
        count = parse_count_token(following_sessions.group("count"), value)
        if base.kind == "exact" and base.start:
            return DateConstraint(
                "after_date_sessions",
                start=base.start,
                anchor="explicit",
                amount=count,
                unit="session",
                trading_day_based=True,
            )
        if base.kind == "anchor_calendar" and base.day is not None:
            return DateConstraint(
                "after_anchor_sessions",
                anchor="latest",
                amount=count,
                unit="session",
                trading_day_based=True,
                offset=base.offset,
                month=base.month,
                day=base.day,
            )
    ordinal_session = re.fullmatch(
        rf"(?P<base>.+)的第(?P<count>{number})(?:个交易日|日|天)",
        value,
    )
    if ordinal_session:
        base = parse_date_constraint(ordinal_session.group("base"))
        count = parse_count_token(ordinal_session.group("count"), value)
        if base.kind == "relative_session" and base.amount:
            target_offset = base.amount - count + 1
            if target_offset >= 0:
                return (
                    DateConstraint("relative", anchor="today")
                    if target_offset == 0
                    else DateConstraint(
                        "relative_session",
                        anchor="latest",
                        amount=target_offset,
                        unit="session",
                    )
                )
    full_date = re.fullmatch(
        rf"(?P<year>{year_token})年(?P<month>{number})月(?P<day>{number})(?:日|号)",
        value,
    )
    if full_date:
        year_value = _calendar_year(full_date.group("year"), value)
        month_value = parse_count_token(full_date.group("month"), value)
        day_value = parse_count_token(full_date.group("day"), value)
        try:
            normalized = f"{year_value:04d}-{month_value:02d}-{day_value:02d}"
            if day_value > monthrange(year_value, month_value)[1]:
                raise ValueError
        except (IndexError, ValueError) as exc:
            raise DomainBindingError(
                "DOMAIN_DATE_INVALID",
                f"invalid calendar date {value}",
                function="",
                slot="date",
                value=value,
            ) from exc
        return DateConstraint("exact", normalized, normalized)
    anchor_date = re.fullmatch(
        rf"(?:(?P<month>{number})月)?(?P<day>{number})(?:日|号)",
        value,
    )
    if anchor_date:
        month_value = (
            parse_count_token(anchor_date.group("month"), value)
            if anchor_date.group("month")
            else None
        )
        day_value = parse_count_token(anchor_date.group("day"), value)
        if (month_value is not None and not 1 <= month_value <= 12) or not 1 <= day_value <= 31:
            raise DomainBindingError(
                "DOMAIN_DATE_INVALID",
                f"invalid anchor-relative calendar date {value}",
                function="",
                slot="date",
                value=value,
            )
        return DateConstraint(
            "anchor_calendar",
            anchor="latest",
            unit="day",
            trading_day_based=False,
            month=month_value,
            day=day_value,
        )
    anchor_month = re.fullmatch(rf"(?P<month>{number})月", value)
    if anchor_month:
        month_value = parse_count_token(anchor_month.group("month"), value)
        if not 1 <= month_value <= 12:
            raise DomainBindingError(
                "DOMAIN_DATE_INVALID",
                f"invalid anchor-relative calendar month {value}",
                function="",
                slot="date",
                value=value,
            )
        return DateConstraint(
            "anchor_calendar",
            anchor="latest",
            unit="month",
            trading_day_based=False,
            month=month_value,
        )
    month = re.fullmatch(
        rf"(?P<year>{year_token})年(?P<month>{number})月",
        value,
    )
    if month:
        year_value = _calendar_year(month.group("year"), value)
        month_value = parse_count_token(month.group("month"), value)
        try:
            last_day = monthrange(year_value, month_value)[1]
        except (IndexError, ValueError) as exc:
            raise DomainBindingError(
                "DOMAIN_DATE_INVALID",
                f"invalid calendar month {value}",
                function="",
                slot="date",
                value=value,
            ) from exc
        return DateConstraint(
            "calendar_range",
            f"{year_value:04d}-{month_value:02d}-01",
            f"{year_value:04d}-{month_value:02d}-{last_day:02d}",
            unit="month",
            trading_day_based=False,
        )
    recent_sessions = re.fullmatch(
        rf"(?:最近|近|过去|这)(?P<count>{number})(?:个)?(?:交易)?(?:日|天)(?:内|以内|之内)?",
        value,
    ) or re.fullmatch(
        rf"(?P<count>{number})(?:个)?(?:交易)?(?:日|天)(?:内|以内|之内)?",
        value,
    )
    if recent_sessions:
        amount = parse_count_token(recent_sessions.group("count"), value)
        return DateConstraint("recent_sessions", anchor="latest", amount=amount, unit="session")
    year = re.fullmatch(rf"(?P<year>{year_token})年", value)
    if year:
        token = year.group("year")
        number_value = _calendar_year(token, value)
        if 1990 <= number_value <= 2100:
            return DateConstraint(
                "calendar_range",
                f"{number_value:04d}-01-01",
                f"{number_value:04d}-12-31",
                amount=None,
                unit="year",
                trading_day_based=False,
            )
    recent_calendar = re.fullmatch(
        rf"(?:最近|近|过去|这)(?P<count>{number})(?:个)?(?P<unit>年|月|周)(?:内|以内|之内|至今)?",
        value,
    ) or re.fullmatch(
        rf"(?P<count>{number})(?:个)?(?P<unit>年|月|周)(?:内|以内|之内)?",
        value,
    )
    if recent_calendar:
        amount = parse_count_token(recent_calendar.group("count"), value)
        unit = {"年": "year", "月": "month", "周": "week"}[recent_calendar.group("unit")]
        return DateConstraint("recent_calendar", anchor="latest", amount=amount, unit=unit, trading_day_based=False)
    return DateConstraint("expression", anchor=value)


def _calendar_year(token: str, source: str) -> int:
    number_value = parse_count_token(token, source)
    if len(token) == 2:
        number_value = 2000 + number_value if number_value <= 26 else 1900 + number_value
    if not 1990 <= number_value <= 2100:
        raise DomainBindingError(
            "DOMAIN_DATE_INVALID",
            f"calendar year is outside the supported range: {source}",
            function="",
            slot="date",
            value=source,
        )
    return number_value

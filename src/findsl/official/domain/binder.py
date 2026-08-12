from __future__ import annotations

import re
from calendar import monthrange
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple, TYPE_CHECKING

from ..registry import IndicatorDefinition, OfficialIndicatorRegistry
from ..typed_ast import TypedNode
from ..types import BOOLEAN, NUMERIC, STRING, TIME
from .expressions import DataRequirement, DateConstraint, EventSpec, IndicatorRef, MarketScope, UniverseSpec
from .temporal import TemporalParseError, TemporalQuantifier, parse_temporal_quantifier
from .temporal import parse_count_token
from .market import MarketParseError, parse_market_expression
from .scope import ScopeParseError, parse_scope_expression
from .target import EntityTargetSpec, TargetParseError
from ..target_catalog import EntityTargetCatalog, default_entity_target_catalog

if TYPE_CHECKING:
    from ..external.data_domains import DataDomainCatalog


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
    entity_target: EntityTargetSpec

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
            "entity_target": self.entity_target.to_dict(),
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
EMPTY_RANK_POLICY_INDICATOR = "稳定证券顺序"
_DYNAMIC_MOVING_AVERAGE = re.compile(r"^(\d{1,4})日均(量)?线$")


def bind_function(
    typed: TypedNode,
    registry: OfficialIndicatorRegistry,
    *,
    entity_targets: Optional[EntityTargetCatalog] = None,
    data_domains: Optional["DataDomainCatalog"] = None,
    profile_id: str = "competition-v1",
) -> BoundFunction:
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
    is_empty_rank = (
        name == "rank"
        and indicator_slots == ["indicator_name"]
        and str(slots.get("indicator_name", "")).strip()
        in {"", EMPTY_RANK_POLICY_INDICATOR}
    )
    indicators = (
        ()
        if is_universe
        else (
            IndicatorRef(
                EMPTY_RANK_POLICY_INDICATOR,
                NUMERIC,
                "ordinal",
                "security_reference",
                "derived",
            ),
        )
        if is_empty_rank
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
    try:
        entity_target = (entity_targets or default_entity_target_catalog()).bind(
            slots.get("select_type", ""),
            data_domains=data_domains,
            profile_id=profile_id,
        )
    except TargetParseError as exc:
        raise DomainBindingError(
            exc.code,
            str(exc),
            function=name,
            slot="select_type",
            value=str(slots.get("select_type", "")),
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
    domains = (
        frozenset({"quote"})
        if is_universe
        else frozenset(item.domain for item in indicators)
    )
    capabilities = (
        frozenset({"scan"})
        if is_universe
        else frozenset({"scan", "stable_order"})
        if is_empty_rank
        else frozenset(
            capability
            for indicator in indicators
            for capability in _indicator_capabilities(indicator, registry)
        )
    )
    requirement = DataRequirement(
        domains,
        capabilities,
        entity_target.required_data_domains,
    )
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
        entity_target,
    )


def normalize_function_slots(name: str, slots: Mapping[str, str]) -> Mapping[str, str]:
    """Apply only defaults that are explicit in the official slot contract."""
    normalized = dict(slots)
    default_slot = _DEFAULT_PRICE_SLOTS.get(name)
    if default_slot and not str(normalized.get(default_slot, "")).strip():
        normalized[default_slot] = "最新价"
    if name == "rank" and not str(normalized.get("indicator_name", "")).strip():
        normalized["indicator_name"] = EMPTY_RANK_POLICY_INDICATOR
    return normalized


def _definition(indicator: IndicatorRef, registry: OfficialIndicatorRegistry) -> IndicatorDefinition:
    return registry.resolve(indicator.indicator_id)


def _indicator_capabilities(
    indicator: IndicatorRef,
    registry: OfficialIndicatorRegistry,
):
    if _DYNAMIC_MOVING_AVERAGE.fullmatch(indicator.indicator_id):
        return ("scan", "prefix_average", "window")
    return _definition(indicator, registry).capabilities


def _bind_indicator(function: str, slot: str, value: str, registry: OfficialIndicatorRegistry) -> IndicatorRef:
    if not value:
        raise DomainBindingError("DOMAIN_CAPABILITY_UNSUPPORTED", "empty indicator slot cannot be bound", function=function, slot=slot, value=value)
    dynamic = _DYNAMIC_MOVING_AVERAGE.fullmatch(str(value).strip())
    if dynamic and 1 <= int(dynamic.group(1)) <= 1000:
        return IndicatorRef(
            str(value).strip(),
            NUMERIC,
            "shares" if dynamic.group(2) else "currency",
            "quote",
            "derived",
        )
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
    number = r"\d+|[零〇一二两三四五六七八九十百]+"
    year_token = r"\d{2,4}|[零〇一二两三四五六七八九]{2,4}"
    if not value:
        return DateConstraint("unspecified")
    aliases = {
        "截至今天": "今天",
        "上一个月": "上个月",
        "上年": "去年",
        "当季": "本季度",
        "今年一整年": "今年",
        "半年": "近半年",
        "最近在3月份": "3月",
    }
    value = aliases.get(value, value)
    if value == "上周五最后一个交易日":
        value = "上周最后一个交易日"
    workday_window = re.fullmatch(rf"(?:最近|近|过去)?(?P<count>{number})个?工作日", value)
    if workday_window:
        value = f"近{workday_window.group('count')}交易日"
    weekday_close = re.fullmatch(
        r"(?P<weekday>(?:本周|上周|上上周|星期|周)[一二三四五六日天])收盘",
        value,
    )
    if weekday_close:
        value = weekday_close.group("weekday")
    prior_year_compact = re.fullmatch(r"去年(?P<month>\d{1,2})(?P<day>\d{2})(?:行情)?", value)
    if prior_year_compact:
        month_value = int(prior_year_compact.group("month"))
        day_value = int(prior_year_compact.group("day"))
        if not 1 <= month_value <= 12 or not 1 <= day_value <= 31:
            raise DomainBindingError(
                "DOMAIN_DATE_INVALID",
                f"invalid prior-year anchor date: {value}",
                function="",
                slot="date",
                value=value,
            )
        return DateConstraint(
            "anchor_calendar",
            anchor="latest",
            unit="day",
            trading_day_based=False,
            offset=-12,
            month=month_value,
            day=day_value,
        )
    for suffix in ("的当日", "的当天"):
        if value.endswith(suffix):
            return parse_date_constraint(value[: -len(suffix)])
    iso_date = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
    if iso_date:
        return _exact_date(
            int(iso_date.group(1)),
            int(iso_date.group(2)),
            int(iso_date.group(3)),
            value,
        )
    slash_date = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", value)
    if slash_date:
        return _exact_date(
            int(slash_date.group(1)),
            int(slash_date.group(2)),
            int(slash_date.group(3)),
            value,
        )
    compact_date = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", value)
    if compact_date:
        return _exact_date(
            int(compact_date.group(1)),
            int(compact_date.group(2)),
            int(compact_date.group(3)),
            value,
        )
    dotted_date = re.fullmatch(r"(\d{4})\.(\d{1,2})\.(\d{1,2})(?:号|日)?", value)
    if dotted_date:
        return _exact_date(
            int(dotted_date.group(1)),
            int(dotted_date.group(2)),
            int(dotted_date.group(3)),
            value,
        )
    compact_range = re.fullmatch(
        r"(\d{4})(\d{2})(\d{2})\s*[-至到]\s*(\d{4})(\d{2})(\d{2})",
        value,
    )
    if compact_range:
        start = _exact_date(
            int(compact_range.group(1)),
            int(compact_range.group(2)),
            int(compact_range.group(3)),
            value,
        )
        end = _exact_date(
            int(compact_range.group(4)),
            int(compact_range.group(5)),
            int(compact_range.group(6)),
            value,
        )
        return _calendar_bounds(start.start, end.end, value)
    full_date_range = re.fullmatch(
        r"(?P<start>\d{4}年\d{1,2}月\d{1,2}(?:日|号))\s*[-至到]\s*"
        r"(?P<end>\d{4}年\d{1,2}月\d{1,2}(?:日|号))",
        value,
    )
    if full_date_range:
        start = parse_date_constraint(full_date_range.group("start"))
        end = parse_date_constraint(full_date_range.group("end"))
        return _calendar_bounds(start.start, end.end, value)
    explicit_since = re.fullmatch(r"(?P<start>.+?)(?:至今|到现在|以来|开始)$", value)
    if explicit_since:
        start_text = explicit_since.group("start").removeprefix("从")
        if start_text in {"年初", "今年年初", "今年开年"}:
            return DateConstraint(
                "dynamic_period",
                anchor="latest",
                unit="year",
                trading_day_based=False,
            )
        if start_text in {"月初", "本月初"}:
            return DateConstraint(
                "dynamic_period",
                anchor="latest",
                unit="month",
                trading_day_based=False,
            )
        if start_text in {"上月", "上个月"}:
            return DateConstraint(
                "period_since",
                anchor="latest",
                unit="month",
                offset=-1,
                trading_day_based=False,
            )
        current_year_month = re.fullmatch(
            rf"今年(?P<month>{number})月(?:份)?", start_text
        )
        if current_year_month:
            month_value = parse_count_token(current_year_month.group("month"), value)
            if not 1 <= month_value <= 12:
                raise DomainBindingError(
                    "DOMAIN_DATE_INVALID",
                    f"invalid current-year month: {value}",
                    function="",
                    slot="date",
                    value=value,
                )
            return DateConstraint(
                "anchor_since",
                anchor="latest",
                unit="day",
                month=month_value,
                day=1,
                trading_day_based=False,
            )
        start = parse_date_constraint(start_text)
        if start.kind in {"exact", "calendar_range"} and start.start:
            return DateConstraint(
                "calendar_since",
                start=start.start,
                anchor="latest",
                unit="day",
                trading_day_based=False,
            )
        if start.kind == "anchor_calendar" and start.month is not None:
            return DateConstraint(
                "anchor_since",
                anchor="latest",
                unit="day",
                offset=start.offset,
                month=start.month,
                day=start.day or 1,
                trading_day_based=False,
            )
        if start.kind == "relative_session" and start.amount:
            return DateConstraint(
                "session_slice",
                anchor="latest",
                amount=start.amount + 1,
                unit="session",
                trading_day_based=True,
            )
    containing_month = re.fullmatch(r"(?P<base>.+)的当月", value)
    if containing_month:
        base = parse_date_constraint(containing_month.group("base"))
        if base.kind == "exact" and base.start:
            year_value, month_value = map(int, base.start.split("-")[:2])
            return DateConstraint(
                "calendar_range",
                f"{year_value:04d}-{month_value:02d}-01",
                f"{year_value:04d}-{month_value:02d}-{monthrange(year_value, month_value)[1]:02d}",
                unit="month",
                trading_day_based=False,
            )
        if base.kind == "anchor_calendar" and base.month is not None:
            return DateConstraint(
                "anchor_calendar",
                anchor="latest",
                unit="month",
                trading_day_based=False,
                offset=base.offset,
                month=base.month,
            )
    month_day_range = re.fullmatch(
        rf"(?P<start_month>{number})月(?P<start_day>{number})(?:日|号)?\s*"
        rf"[-至到]\s*(?P<end_month>{number})月(?P<end_day>{number})(?:日|号)?",
        value,
    )
    if month_day_range:
        return _month_day_range(
            parse_count_token(month_day_range.group("start_month"), value),
            parse_count_token(month_day_range.group("start_day"), value),
            parse_count_token(month_day_range.group("end_month"), value),
            parse_count_token(month_day_range.group("end_day"), value),
            value,
        )
    current_month_day_range = re.fullmatch(
        rf"本月(?P<start_day>{number})(?:日|号)?\s*[-至到]\s*"
        rf"(?P<end_day>{number})(?:日|号)?",
        value,
    )
    if current_month_day_range:
        return _month_day_range(
            None,
            parse_count_token(current_month_day_range.group("start_day"), value),
            None,
            parse_count_token(current_month_day_range.group("end_day"), value),
            value,
        )
    current_month_day = re.fullmatch(
        rf"本月(?P<day>{number})(?:日|号)",
        value,
    )
    if current_month_day:
        day_value = parse_count_token(current_month_day.group("day"), value)
        if not 1 <= day_value <= 31:
            raise DomainBindingError(
                "DOMAIN_DATE_INVALID",
                f"invalid current-month day: {value}",
                function="",
                slot="date",
                value=value,
            )
        return DateConstraint(
            "anchor_calendar",
            anchor="latest",
            unit="day",
            trading_day_based=False,
            day=day_value,
        )
    current_day_range = re.fullmatch(
        rf"(?P<start_day>{number})(?:日|号)\s*[-至到]\s*"
        rf"(?P<end_day>{number})(?:日|号)",
        value,
    )
    if current_day_range:
        return _month_day_range(
            None,
            parse_count_token(current_day_range.group("start_day"), value),
            None,
            parse_count_token(current_day_range.group("end_day"), value),
            value,
        )
    if value in {
        "今日",
        "今天",
        "当天",
        "当前",
        "目前",
        "当日",
        "本日",
        "现在",
        "最新",
        "截止今天",
        "今天收盘",
        "今日收盘时",
        "今天截止收盘",
        "今日开盘",
        "最近一个交易日收盘",
    }:
        return DateConstraint("relative", anchor="today")
    relative_sessions = {
        "昨天": 1,
        "昨日": 1,
        "上个交易日": 1,
        "前一个交易日": 1,
        "前一交易日": 1,
        "上一交易日": 1,
        "昨天收盘": 1,
        "上一天": 1,
        "前天": 2,
        "大前天": 3,
    }
    if value in relative_sessions:
        return DateConstraint(
            "relative_session",
            anchor="latest",
            amount=relative_sessions[value],
            unit="session",
            trading_day_based=True,
        )
    if value in {"历史", "历史上"}:
        return DateConstraint(
            "all_history",
            anchor="history",
            trading_day_based=False,
        )
    if value == "前天后":
        return DateConstraint(
            "session_slice",
            anchor="latest",
            amount=2,
            unit="session",
            trading_day_based=True,
        )
    calendar_ago = re.fullmatch(
        rf"(?P<count>{number})(?:个)?(?P<unit>年|周)前",
        value,
    )
    if calendar_ago:
        return DateConstraint(
            "shifted_calendar_session",
            anchor="latest",
            amount=1,
            unit={"年": "year", "周": "week"}[calendar_ago.group("unit")],
            trading_day_based=True,
            offset=-parse_count_token(calendar_ago.group("count"), value),
        )
    days_ago = re.fullmatch(
        r"(?P<count>\d+|[零〇一二两三四五六七八九十百]+)(?:个交易日|交易日|日|天)前",
        value,
    )
    if days_ago:
        return DateConstraint(
            "relative_session",
            anchor="latest",
            amount=parse_count_token(days_ago.group("count"), value),
            unit="session",
            trading_day_based=True,
        )
    if value in {"近半年", "最近半年", "过去半年", "这半年", "半年内"}:
        return DateConstraint(
            "recent_calendar",
            anchor="latest",
            amount=6,
            unit="month",
            trading_day_based=False,
        )
    if value in {"半个月", "近半个月", "最近半个月", "过去半个月"}:
        return DateConstraint(
            "recent_calendar",
            anchor="latest",
            amount=15,
            unit="day",
            trading_day_based=False,
        )
    dynamic_periods = {
        "本周": ("week", 0),
        "这周": ("week", 0),
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
        "上季度": ("quarter", -1),
        "当季": ("quarter", 0),
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
    period_end = re.fullmatch(
        r"(?P<period>本周|上周|上上周|本月|上月|上个月|本季度|上季度|今年|去年)最后一个交易日",
        value,
    )
    if period_end:
        base = parse_date_constraint(period_end.group("period"))
        if base.kind == "dynamic_period" and base.unit:
            return DateConstraint(
                "period_end_session",
                anchor="latest",
                amount=1,
                unit=base.unit,
                trading_day_based=True,
                offset=base.offset,
            )
    rolling_periods = re.fullmatch(
        rf"连续(?P<count>{number})(?:个)?(?P<unit>年|季度|月)",
        value,
    )
    if rolling_periods:
        return DateConstraint(
            "rolling_periods",
            anchor="latest",
            amount=parse_count_token(rolling_periods.group("count"), value),
            unit={"年": "year", "季度": "quarter", "月": "month"}[
                rolling_periods.group("unit")
            ],
            trading_day_based=False,
        )
    if value in {"一年里", "一年中"}:
        return DateConstraint(
            "recent_calendar",
            anchor="latest",
            amount=1,
            unit="year",
            trading_day_based=False,
        )
    explicit_quarter_range = re.fullmatch(
        rf"(?P<start_year>{year_token})年?(?:第)?"
        rf"(?P<start_quarter>{number})个?季度\s*[-至到]\s*"
        rf"(?P<end_year>{year_token})年?(?:第)?"
        rf"(?P<end_quarter>{number})个?季度",
        value,
    )
    if explicit_quarter_range:
        start_year = _calendar_year(explicit_quarter_range.group("start_year"), value)
        end_year = _calendar_year(explicit_quarter_range.group("end_year"), value)
        start_quarter = parse_count_token(
            explicit_quarter_range.group("start_quarter"), value
        )
        end_quarter = parse_count_token(
            explicit_quarter_range.group("end_quarter"), value
        )
        if not 1 <= start_quarter <= 4 or not 1 <= end_quarter <= 4:
            raise DomainBindingError(
                "DOMAIN_DATE_INVALID",
                f"invalid quarter range: {value}",
                function="",
                slot="date",
                value=value,
            )
        start_month = (start_quarter - 1) * 3 + 1
        end_month = (end_quarter - 1) * 3 + 3
        return _calendar_bounds(
            f"{start_year:04d}-{start_month:02d}-01",
            f"{end_year:04d}-{end_month:02d}-{monthrange(end_year, end_month)[1]:02d}",
            value,
        )
    explicit_quarter = re.fullmatch(
        rf"(?P<year>{year_token})年(?:第)?(?P<quarter>{number})个?季度",
        value,
    )
    if explicit_quarter:
        year_value = _calendar_year(explicit_quarter.group("year"), value)
        quarter_value = parse_count_token(explicit_quarter.group("quarter"), value)
        if not 1 <= quarter_value <= 4:
            raise DomainBindingError(
                "DOMAIN_DATE_INVALID",
                f"invalid quarter: {value}",
                function="",
                slot="date",
                value=value,
            )
        start_month = (quarter_value - 1) * 3 + 1
        end_month = start_month + 2
        return DateConstraint(
            "calendar_range",
            f"{year_value:04d}-{start_month:02d}-01",
            f"{year_value:04d}-{end_month:02d}-{monthrange(year_value, end_month)[1]:02d}",
            unit="quarter",
            trading_day_based=False,
        )
    q_quarter = re.fullmatch(r"(?:(?P<year>\d{4})年?)?Q(?P<quarter>[1-4])", value, re.IGNORECASE)
    if q_quarter:
        quarter_value = int(q_quarter.group("quarter"))
        start_month = (quarter_value - 1) * 3 + 1
        if q_quarter.group("year"):
            year_value = int(q_quarter.group("year"))
            end_month = start_month + 2
            return DateConstraint(
                "calendar_range",
                f"{year_value:04d}-{start_month:02d}-01",
                f"{year_value:04d}-{end_month:02d}-{monthrange(year_value, end_month)[1]:02d}",
                unit="quarter",
                trading_day_based=False,
            )
        return DateConstraint(
            "year_month_range",
            anchor="latest",
            unit="month",
            trading_day_based=False,
            month=start_month,
            end_month=start_month + 2,
        )
    half_year = re.fullmatch(
        r"(?:(?P<year>\d{2,4})年|今年)?(?P<half>上半年|下半年)", value
    )
    if half_year:
        start_month, end_month = (1, 6) if half_year.group("half") == "上半年" else (7, 12)
        if half_year.group("year"):
            year_value = _calendar_year(half_year.group("year"), value)
            return DateConstraint(
                "calendar_range",
                f"{year_value:04d}-{start_month:02d}-01",
                f"{year_value:04d}-{end_month:02d}-{monthrange(year_value, end_month)[1]:02d}",
                unit="month",
                trading_day_based=False,
            )
        return DateConstraint(
            "year_month_range",
            anchor="latest",
            unit="month",
            trading_day_based=False,
            month=start_month,
            end_month=end_month,
        )
    quarter = re.fullmatch(
        r"(?:今年)?(?P<quarter>[一二三四1-4])季度", value
    )
    if quarter:
        quarter_value = parse_count_token(quarter.group("quarter"), value)
        start_month = (quarter_value - 1) * 3 + 1
        return DateConstraint(
            "year_month_range",
            anchor="latest",
            unit="month",
            trading_day_based=False,
            month=start_month,
            end_month=start_month + 2,
        )
    relative_year_quarter = re.fullmatch(
        r"(?P<year>去年|前年)(?:第)?(?P<quarter>[一二三四1-4])季度",
        value,
    )
    if relative_year_quarter:
        quarter_value = parse_count_token(relative_year_quarter.group("quarter"), value)
        start_month = (quarter_value - 1) * 3 + 1
        return DateConstraint(
            "year_month_range",
            anchor="latest",
            unit="month",
            trading_day_based=False,
            offset=-1 if relative_year_quarter.group("year") == "去年" else -2,
            month=start_month,
            end_month=start_month + 2,
        )
    adjacent_quarters = re.fullmatch(
        r"(?P<start>[一二三1-3])(?P<end>[二三四2-4])季度",
        value,
    )
    if adjacent_quarters:
        start_quarter = parse_count_token(adjacent_quarters.group("start"), value)
        end_quarter = parse_count_token(adjacent_quarters.group("end"), value)
        if end_quarter == start_quarter + 1:
            return DateConstraint(
                "year_month_range",
                anchor="latest",
                unit="month",
                trading_day_based=False,
                month=(start_quarter - 1) * 3 + 1,
                end_month=(end_quarter - 1) * 3 + 3,
            )
    month_range = re.fullmatch(r"(?P<start>\d{1,2})\s*[-至到]\s*(?P<end>\d{1,2})月", value)
    if month_range:
        start_month = int(month_range.group("start"))
        end_month = int(month_range.group("end"))
        if not 1 <= start_month <= end_month <= 12:
            raise DomainBindingError(
                "DOMAIN_DATE_INVALID",
                f"invalid current-year month range: {value}",
                function="",
                slot="date",
                value=value,
            )
        return DateConstraint(
            "year_month_range",
            anchor="latest",
            unit="month",
            trading_day_based=False,
            month=start_month,
            end_month=end_month,
        )
    explicit_month_range = re.fullmatch(
        rf"(?P<start>{number})月\s*[-至到]\s*(?P<end>{number})月",
        value,
    )
    if explicit_month_range:
        start_month = parse_count_token(explicit_month_range.group("start"), value)
        end_month = parse_count_token(explicit_month_range.group("end"), value)
        if not 1 <= start_month <= end_month <= 12:
            raise DomainBindingError(
                "DOMAIN_DATE_INVALID",
                f"invalid current-year month range: {value}",
                function="",
                slot="date",
                value=value,
            )
        return DateConstraint(
            "year_month_range",
            anchor="latest",
            unit="month",
            trading_day_based=False,
            month=start_month,
            end_month=end_month,
        )
    adjacent_months = re.fullmatch(
        rf"(?P<start>{number})月(?P<end>{number})月",
        value,
    )
    if adjacent_months:
        start_month = parse_count_token(adjacent_months.group("start"), value)
        end_month = parse_count_token(adjacent_months.group("end"), value)
        if end_month == start_month + 1 and end_month <= 12:
            return DateConstraint(
                "year_month_range",
                anchor="latest",
                unit="month",
                trading_day_based=False,
                month=start_month,
                end_month=end_month,
            )
    weekday_range = re.fullmatch(
        r"(?P<period>本周|上周|上上周)(?P<start>[一二三四五六日天])(?:到|至)(?:(?P<end_period>本周|上周|上上周)|周)?(?P<end>[一二三四五六日天])",
        value,
    )
    if weekday_range:
        period = weekday_range.group("period")
        end_period = weekday_range.group("end_period")
        if end_period and end_period != period:
            raise DomainBindingError(
                "DOMAIN_DATE_INVALID",
                f"weekday range crosses incompatible weeks: {value}",
                function="",
                slot="date",
                value=value,
            )
        weekdays = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}
        start_weekday = weekdays[weekday_range.group("start")]
        end_weekday = weekdays[weekday_range.group("end")]
        if start_weekday > end_weekday:
            raise DomainBindingError(
                "DOMAIN_DATE_INVALID",
                f"weekday range starts after it ends: {value}",
                function="",
                slot="date",
                value=value,
            )
        return DateConstraint(
            "dynamic_weekday_range",
            anchor="latest",
            unit="week",
            trading_day_based=False,
            offset={"本周": 0, "上周": -1, "上上周": -2}[period],
            weekday_start=start_weekday,
            weekday_end=end_weekday,
        )
    weekday = re.fullmatch(
        r"(?:(?P<period>本周|上周|上上周|星期|周))(?P<weekday>[一二三四五六日天])",
        value,
    )
    if weekday:
        weekday_value = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}[weekday.group("weekday")]
        period = weekday.group("period")
        return DateConstraint(
            "dynamic_weekday_range",
            anchor="latest",
            unit="week",
            trading_day_based=False,
            offset={"上上周": -2, "上周": -1}.get(period, 0),
            weekday_start=weekday_value,
            weekday_end=weekday_value,
        )
    weekday_range_short = re.fullmatch(
        r"周(?P<start>[一二三四五六日天])(?:到|至)周(?P<end>[一二三四五六日天])",
        value,
    )
    if weekday_range_short:
        weekdays = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}
        start_weekday = weekdays[weekday_range_short.group("start")]
        end_weekday = weekdays[weekday_range_short.group("end")]
        if start_weekday > end_weekday:
            raise DomainBindingError(
                "DOMAIN_DATE_INVALID",
                f"weekday range starts after it ends: {value}",
                function="",
                slot="date",
                value=value,
            )
        return DateConstraint(
            "dynamic_weekday_range",
            anchor="latest",
            unit="week",
            trading_day_based=False,
            weekday_start=start_weekday,
            weekday_end=end_weekday,
        )
    adjacent_weekdays = re.fullmatch(
        r"周(?P<start>[一二三四五六日天])周?(?P<end>[一二三四五六日天])",
        value,
    )
    if adjacent_weekdays:
        weekdays = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}
        start_weekday = weekdays[adjacent_weekdays.group("start")]
        end_weekday = weekdays[adjacent_weekdays.group("end")]
        if start_weekday <= end_weekday:
            return DateConstraint(
                "dynamic_weekday_range",
                anchor="latest",
                unit="week",
                trading_day_based=False,
                weekday_start=start_weekday,
                weekday_end=end_weekday,
            )
    latest_ordinal_session = re.fullmatch(
        rf"最近的第(?P<count>{number})(?:个交易日|交易日|日|天)",
        value,
    )
    if latest_ordinal_session:
        count = parse_count_token(latest_ordinal_session.group("count"), value)
        if count < 1:
            raise DomainBindingError(
                "DOMAIN_DATE_INVALID",
                f"latest ordinal session must start from one: {value}",
                function="",
                slot="date",
                value=value,
            )
        if count == 1:
            return DateConstraint("relative", anchor="today")
        return DateConstraint(
            "relative_session",
            anchor="latest",
            amount=count - 1,
            unit="session",
            trading_day_based=True,
        )
    continuous_recent_sessions = re.fullmatch(
        rf"最近连续(?P<count>{number})(?:个)?交易日", value
    )
    if continuous_recent_sessions:
        return DateConstraint(
            "recent_sessions",
            anchor="latest",
            amount=parse_count_token(continuous_recent_sessions.group("count"), value),
            unit="session",
        )
    consecutive_sessions = re.fullmatch(
        rf"连续(?P<count>{number})(?:个)?(?:交易)?(?:日|天)", value
    )
    if consecutive_sessions:
        return DateConstraint(
            "recent_sessions",
            anchor="latest",
            amount=parse_count_token(consecutive_sessions.group("count"), value),
            unit="session",
        )
    previous_session_slice = re.fullmatch(
        rf"前(?P<count>{number})(?:个交易日|交易日|日|天)", value
    )
    if previous_session_slice:
        return DateConstraint(
            "session_slice",
            anchor="latest",
            amount=parse_count_token(previous_session_slice.group("count"), value),
            unit="session",
            offset=1,
        )
    previous_calendar = re.fullmatch(
        rf"前(?P<count>{number})(?:个)?(?P<unit>周|月|年)", value
    )
    if previous_calendar:
        return DateConstraint(
            "recent_calendar",
            anchor="latest",
            amount=parse_count_token(previous_calendar.group("count"), value),
            unit={"周": "week", "月": "month", "年": "year"}[
                previous_calendar.group("unit")
            ],
            trading_day_based=False,
        )
    before_current_period = re.fullmatch(
        rf"本(?P<period>周|月|季度|年)之前的前(?P<count>{number})(?:个交易日|交易日|日|天)",
        value,
    )
    if before_current_period:
        return DateConstraint(
            "before_period_sessions",
            anchor="latest",
            amount=parse_count_token(before_current_period.group("count"), value),
            unit={"周": "week", "月": "month", "季度": "quarter", "年": "year"}[
                before_current_period.group("period")
            ],
            trading_day_based=True,
        )
    period_start_sessions = re.fullmatch(
        rf"(?P<base>本周|上周|上上周|本月|上月|上个月|本季度|上季度|今年|去年)开始(?P<count>{number})(?:个交易日|交易日|日|天)",
        value,
    )
    if period_start_sessions:
        base = parse_date_constraint(period_start_sessions.group("base"))
        if base.kind == "dynamic_period" and base.unit:
            return DateConstraint(
                "from_period_sessions",
                anchor="latest",
                amount=parse_count_token(period_start_sessions.group("count"), value),
                unit=base.unit,
                trading_day_based=True,
                offset=base.offset,
            )
    anchor_start_sessions = re.fullmatch(
        rf"(?P<base>.+)开始(?P<count>{number})(?:个交易日|交易日|日|天)",
        value,
    )
    if anchor_start_sessions:
        base = parse_date_constraint(anchor_start_sessions.group("base"))
        count = parse_count_token(anchor_start_sessions.group("count"), value)
        if base.kind == "exact" and base.start:
            return DateConstraint(
                "from_date_sessions",
                start=base.start,
                anchor="explicit",
                amount=count,
                unit="session",
                trading_day_based=True,
            )
        if base.kind == "anchor_calendar" and base.day is not None:
            return DateConstraint(
                "from_anchor_sessions",
                anchor="latest",
                amount=count,
                unit="session",
                trading_day_based=True,
                offset=base.offset,
                month=base.month,
                day=base.day,
            )
        if base.kind == "dynamic_weekday_range" and base.weekday_start == base.weekday_end:
            return DateConstraint(
                "from_weekday_sessions",
                anchor="latest",
                amount=count,
                unit="session",
                trading_day_based=True,
                offset=base.offset,
                weekday_start=base.weekday_start,
                weekday_end=base.weekday_end,
            )
    period_start_point = {
        "今年年初": ("year", 0),
        "去年年初": ("year", -1),
        "本月月初": ("month", 0),
        "上月月初": ("month", -1),
    }.get(value)
    if period_start_point:
        return DateConstraint(
            "from_period_sessions",
            anchor="latest",
            amount=1,
            unit=period_start_point[0],
            trading_day_based=True,
            offset=period_start_point[1],
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
        rf"(?P<base>.+?)(?:的)?后(?P<count>{number})年",
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
        if base.kind == "exact" and base.start:
            return DateConstraint(
                "before_date_sessions",
                start=base.start,
                anchor="explicit",
                amount=count,
                unit="session",
                trading_day_based=True,
            )
    following_sessions = re.fullmatch(
        rf"(?P<base>.+?)(?:的)?后(?P<count>{number})(?:个交易日|日|天)",
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
        if base.kind == "relative_session" and base.amount:
            return DateConstraint(
                "session_slice",
                anchor="latest",
                amount=min(count, base.amount),
                unit="session",
                trading_day_based=True,
                offset=max(base.amount - count, 0),
            )
        if (
            base.kind == "dynamic_weekday_range"
            and base.weekday_start is not None
            and base.weekday_start == base.weekday_end
        ):
            return DateConstraint(
                "after_weekday_sessions",
                anchor="latest",
                amount=count,
                unit="session",
                trading_day_based=True,
                offset=base.offset,
                weekday_start=base.weekday_start,
                weekday_end=base.weekday_end,
            )
    following_months = re.fullmatch(
        rf"(?P<base>.+?)(?:的)?后(?P<count>{number})(?:个)?月",
        value,
    )
    if following_months:
        base = parse_date_constraint(following_months.group("base"))
        count = parse_count_token(following_months.group("count"), value)
        if base.kind == "calendar_range" and base.start and base.unit == "month":
            year_value, month_value = map(int, base.start.split("-")[:2])
            start_ordinal = year_value * 12 + month_value
            start_year, start_month_zero = divmod(start_ordinal, 12)
            start_month = start_month_zero + 1
            end_ordinal = start_ordinal + count - 1
            end_year, end_month_zero = divmod(end_ordinal, 12)
            end_month = end_month_zero + 1
            return DateConstraint(
                "calendar_range",
                f"{start_year:04d}-{start_month:02d}-01",
                f"{end_year:04d}-{end_month:02d}-{monthrange(end_year, end_month)[1]:02d}",
                amount=count,
                unit="month",
                trading_day_based=False,
            )
        if base.kind == "anchor_calendar" and base.unit == "month" and base.month:
            start_month = base.month + 1
            end_month = base.month + count
            if end_month <= 12:
                return DateConstraint(
                    "year_month_range",
                    anchor="latest",
                    unit="month",
                    trading_day_based=False,
                    offset=base.offset,
                    month=start_month,
                    end_month=end_month,
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
        if count >= 2 and base.kind == "exact" and base.start:
            return DateConstraint(
                "after_date_sessions",
                start=base.start,
                anchor="explicit",
                amount=1,
                unit="session",
                trading_day_based=True,
            )
        if count >= 2 and base.kind == "anchor_calendar" and base.day is not None:
            return DateConstraint(
                "after_anchor_sessions",
                anchor="latest",
                amount=1,
                unit="session",
                trading_day_based=True,
                offset=base.offset,
                month=base.month,
                day=base.day,
            )
        if (
            count >= 2
            and base.kind == "dynamic_weekday_range"
            and base.weekday_start is not None
            and base.weekday_start == base.weekday_end
        ):
            return DateConstraint(
                "after_weekday_sessions",
                anchor="latest",
                amount=1,
                unit="session",
                trading_day_based=True,
                offset=base.offset,
                weekday_start=base.weekday_start,
                weekday_end=base.weekday_end,
            )
    full_date = re.fullmatch(
        rf"(?P<year>{year_token})年(?P<month>{number})月(?P<day>{number})(?:日|号)",
        value,
    )
    if full_date:
        year_value = _calendar_year(full_date.group("year"), value)
        month_value = parse_count_token(full_date.group("month"), value)
        day_value = parse_count_token(full_date.group("day"), value)
        return _exact_date(year_value, month_value, day_value, value)
    prior_year_month_start = re.fullmatch(
        rf"去年(?P<month>{number})月初",
        value,
    )
    if prior_year_month_start:
        month_value = parse_count_token(prior_year_month_start.group("month"), value)
        if not 1 <= month_value <= 12:
            raise DomainBindingError(
                "DOMAIN_DATE_INVALID",
                f"invalid prior-year month start: {value}",
                function="",
                slot="date",
                value=value,
            )
        return DateConstraint(
            "from_anchor_sessions",
            anchor="latest",
            amount=1,
            unit="session",
            trading_day_based=True,
            offset=-12,
            month=month_value,
            day=1,
        )
    hyphen_anchor_date = re.fullmatch(
        r"(?P<month>\d{1,2})-(?P<day>\d{1,2})(?:日|号)?",
        value,
    )
    if hyphen_anchor_date:
        return parse_date_constraint(
            f"{hyphen_anchor_date.group('month')}月{hyphen_anchor_date.group('day')}日"
        )
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
    current_year_month = re.fullmatch(rf"今年(?P<month>{number})月", value)
    if current_year_month:
        month_value = parse_count_token(current_year_month.group("month"), value)
        if not 1 <= month_value <= 12:
            raise DomainBindingError(
                "DOMAIN_DATE_INVALID",
                f"invalid current-year month: {value}",
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
    year_range = re.fullmatch(
        rf"(?P<start>{year_token})年\s*[-至到]\s*(?P<end>{year_token})年",
        value,
    )
    if year_range:
        start_year = _calendar_year(year_range.group("start"), value)
        end_year = _calendar_year(year_range.group("end"), value)
        if start_year > end_year:
            raise DomainBindingError(
                "DOMAIN_DATE_INVALID",
                f"calendar range starts after it ends: {value}",
                function="",
                slot="date",
                value=value,
            )
        return DateConstraint(
            "calendar_range",
            f"{start_year:04d}-01-01",
            f"{end_year:04d}-12-31",
            unit="year",
            trading_day_based=False,
        )
    year_range_without_first_suffix = re.fullmatch(
        rf"(?P<start>{year_token})\s*[-至到]\s*(?P<end>{year_token})年",
        value,
    )
    if year_range_without_first_suffix:
        start_year = _calendar_year(year_range_without_first_suffix.group("start"), value)
        end_year = _calendar_year(year_range_without_first_suffix.group("end"), value)
        if start_year > end_year:
            raise DomainBindingError(
                "DOMAIN_DATE_INVALID",
                f"calendar range starts after it ends: {value}",
                function="",
                slot="date",
                value=value,
            )
        return DateConstraint(
            "calendar_range",
            f"{start_year:04d}-01-01",
            f"{end_year:04d}-12-31",
            unit="year",
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
    recent_quarters = re.fullmatch(
        rf"(?:最近|近|过去)(?P<count>{number})(?:个)?季度", value
    )
    if recent_quarters:
        return DateConstraint(
            "recent_calendar",
            anchor="latest",
            amount=parse_count_token(recent_quarters.group("count"), value) * 3,
            unit="month",
            trading_day_based=False,
        )
    year_current = re.fullmatch(rf"(?P<year>{year_token})年的当年", value)
    if year_current:
        return parse_date_constraint(f"{year_current.group('year')}年")
    month_alias = re.fullmatch(rf"(?P<month>{number})月份", value)
    if month_alias:
        return parse_date_constraint(f"{month_alias.group('month')}月")
    month_day_dotted = re.fullmatch(
        r"(?P<month>\d{1,2})\.(?P<day>\d{1,2})(?:号|日)?", value
    )
    if month_day_dotted:
        return parse_date_constraint(
            f"{month_day_dotted.group('month')}月{month_day_dotted.group('day')}日"
        )
    return DateConstraint("expression", anchor=value)


def _exact_date(year_value: int, month_value: int, day_value: int, source: str):
    try:
        normalized = f"{year_value:04d}-{month_value:02d}-{day_value:02d}"
        if day_value > monthrange(year_value, month_value)[1]:
            raise ValueError
    except (IndexError, ValueError) as exc:
        raise DomainBindingError(
            "DOMAIN_DATE_INVALID",
            f"invalid calendar date {source}",
            function="",
            slot="date",
            value=source,
        ) from exc
    return DateConstraint("exact", normalized, normalized)


def _calendar_bounds(start: Optional[str], end: Optional[str], source: str) -> DateConstraint:
    if not start or not end or start > end:
        raise DomainBindingError(
            "DOMAIN_DATE_INVALID",
            f"calendar range has invalid bounds: {source}",
            function="",
            slot="date",
            value=source,
        )
    return DateConstraint(
        "calendar_range",
        start,
        end,
        unit="day",
        trading_day_based=False,
    )


def _month_day_range(
    start_month: Optional[int],
    start_day: int,
    end_month: Optional[int],
    end_day: int,
    source: str,
) -> DateConstraint:
    if (
        (start_month is not None and not 1 <= start_month <= 12)
        or (end_month is not None and not 1 <= end_month <= 12)
        or not 1 <= start_day <= 31
        or not 1 <= end_day <= 31
        or (
            start_month is not None
            and end_month is not None
            and (start_month, start_day) > (end_month, end_day)
        )
        or (
            start_month is None
            and end_month is None
            and start_day > end_day
        )
    ):
        raise DomainBindingError(
            "DOMAIN_DATE_INVALID",
            f"month-day range has invalid bounds: {source}",
            function="",
            slot="date",
            value=source,
        )
    return DateConstraint(
        "month_day_range",
        anchor="latest",
        unit="day",
        trading_day_based=False,
        month=start_month,
        day=start_day,
        end_month=end_month,
        end_day=end_day,
    )


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

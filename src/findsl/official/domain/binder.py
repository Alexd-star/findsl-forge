from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from ..registry import IndicatorDefinition, OfficialIndicatorRegistry
from ..typed_ast import TypedNode
from ..types import BOOLEAN, NUMERIC, STRING, TIME, OfficialType
from .expressions import DataRequirement, DateConstraint, EventSpec, IndicatorRef, MarketScope
from .temporal import TemporalParseError, TemporalQuantifier, parse_temporal_quantifier
from .temporal import parse_count_token


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
            "date_constraint": self.date_constraint.to_dict(),
            "requirement": self.requirement.to_dict(),
            "aggregate": self.aggregate,
            "temporal": self.temporal.to_dict() if self.temporal else None,
        }


_TYPE_MAP = {"numeric": NUMERIC, "boolean": BOOLEAN, "string": STRING, "time": TIME}
_EVENT_FUNCTIONS = {"cross_above", "cross_down", "close_together", "reset", "golden_cross"}
_MARKETS = {"沪": "SH", "深": "SZ", "北": "BJ", "港": "HK", "美": "US", "A股": "A", "B股": "B"}


def bind_function(typed: TypedNode, registry: OfficialIndicatorRegistry) -> BoundFunction:
    if typed.binding is None:
        raise DomainBindingError("DOMAIN_NOT_FUNCTION", "typed node has no function binding", function="", slot="", value="")
    name = typed.binding.signature.name
    slots = typed.binding.slots
    indicator_slots = [slot for slot in typed.binding.signature.slots if slot.startswith("indicator_name")]
    indicators = tuple(_bind_indicator(name, slot, slots.get(slot, ""), registry) for slot in indicator_slots)
    if not indicators:
        raise DomainBindingError("DOMAIN_CAPABILITY_UNSUPPORTED", f"{name} has no bindable indicator slot", function=name, slot="indicator_name", value="")
    market = _bind_market(name, slots.get("market", ""))
    date = _bind_date(name, slots.get("date", slots.get("period", "")))
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
    domains = frozenset(item.domain for item in indicators)
    capabilities = frozenset(capability for definition in (_definition(item, registry) for item in indicators) for capability in definition.capabilities)
    requirement = DataRequirement(domains, capabilities)
    expression = EventSpec(name, indicators[0], indicators[1]) if name in _EVENT_FUNCTIONS else indicators[0]
    return BoundFunction(name, expression, indicators, market, date, requirement, aggregate, temporal)


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


def _bind_date(function: str, value: str) -> DateConstraint:
    value = value.strip()
    if not value:
        return DateConstraint("unspecified")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return DateConstraint("exact", value, value)
    if value in {"今日", "今天", "当前", "最新"}:
        return DateConstraint("relative", anchor="today")
    number = r"\d+|[零〇一二两三四五六七八九十百]+"
    recent_sessions = re.fullmatch(
        rf"(?:最近|近|过去|这)(?P<count>{number})(?:个)?(?:交易)?(?:日|天)",
        value,
    ) or re.fullmatch(
        rf"(?P<count>{number})(?:个)?(?:交易)?(?:日|天)(?:内|以内)",
        value,
    )
    if recent_sessions:
        amount = parse_count_token(recent_sessions.group("count"), value)
        return DateConstraint("recent_sessions", anchor="latest", amount=amount, unit="session")
    recent_calendar = re.fullmatch(
        rf"(?:最近|近|过去)(?P<count>{number})(?:个)?(?P<unit>年|月)(?:内|以内)?",
        value,
    ) or re.fullmatch(
        rf"(?P<count>{number})(?:个)?(?P<unit>年|月)(?:内|以内)",
        value,
    )
    if recent_calendar:
        amount = parse_count_token(recent_calendar.group("count"), value)
        unit = {"年": "year", "月": "month"}[recent_calendar.group("unit")]
        return DateConstraint("recent_calendar", anchor="latest", amount=amount, unit=unit, trading_day_based=False)
    year = re.fullmatch(r"(?P<year>\d{4}|[零〇一二两三四五六七八九]{2,4})年", value)
    if year:
        token = year.group("year")
        number_value = parse_count_token(token, value)
        if len(token) == 2:
            number_value = 2000 + number_value if number_value <= 26 else 1900 + number_value
        if 1990 <= number_value <= 2100:
            return DateConstraint(
                "calendar_range",
                f"{number_value:04d}-01-01",
                f"{number_value:04d}-12-31",
                amount=None,
                unit="year",
                trading_day_based=False,
            )
    return DateConstraint("expression", anchor=value)

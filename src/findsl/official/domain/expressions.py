from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional, Tuple

from ..ir.base import CanonicalIr
from ..types import OfficialType


@dataclass(frozen=True)
class IndicatorRef(CanonicalIr):
    indicator_id: str
    value_type: OfficialType
    unit: str
    domain: str
    availability: str

    @property
    def type(self) -> OfficialType:
        return self.value_type

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "IndicatorRef", "indicator_id": self.indicator_id, "type": self.value_type.to_dict(), "unit": self.unit, "domain": self.domain, "availability": self.availability}


@dataclass(frozen=True)
class MarketScope(CanonicalIr):
    markets: Tuple[str, ...]

    def to_dict(self):
        return {"kind": "MarketScope", "markets": list(self.markets)}


@dataclass(frozen=True)
class DateConstraint(CanonicalIr):
    kind: str
    start: Optional[str] = None
    end: Optional[str] = None
    anchor: Optional[str] = None
    trading_day_based: bool = True

    def to_dict(self):
        return {"kind": "DateConstraint", "constraint_kind": self.kind, "start": self.start, "end": self.end, "anchor": self.anchor, "trading_day_based": self.trading_day_based}


@dataclass(frozen=True)
class AggregateSpec(CanonicalIr):
    function: str
    expression: Any
    window: Optional[str] = None

    def to_dict(self):
        return {"kind": "AggregateSpec", "function": self.function, "expression": self.expression.to_dict(), "window": self.window}


@dataclass(frozen=True)
class EventSpec(CanonicalIr):
    kind: str
    left: Any
    right: Any
    tolerance: Optional[float] = None

    def to_dict(self):
        return {"kind": "EventSpec", "event_kind": self.kind, "left": self.left.to_dict(), "right": self.right.to_dict(), "tolerance": self.tolerance}


@dataclass(frozen=True)
class ConsecutiveSpec(CanonicalIr):
    predicate: Any
    comparator: str
    threshold: Optional[int]
    maximum: Optional[int]
    unit: str
    every: bool
    source: str
    trading_sequence: bool = True

    def to_dict(self):
        return {"kind": "ConsecutiveSpec", "predicate": self.predicate.to_dict(), "comparator": self.comparator, "threshold": self.threshold, "maximum": self.maximum, "unit": self.unit, "every": self.every, "source": self.source, "semantics": "trading_sequence" if self.trading_sequence else "calendar_sequence"}


@dataclass(frozen=True)
class ExistSpec(CanonicalIr):
    predicate: Any
    comparator: str
    threshold: Optional[int]
    maximum: Optional[int]
    unit: str
    every: bool
    source: str
    trading_sequence: bool = True

    def to_dict(self):
        return {"kind": "ExistSpec", "predicate": self.predicate.to_dict(), "comparator": self.comparator, "threshold": self.threshold, "maximum": self.maximum, "unit": self.unit, "every": self.every, "source": self.source, "semantics": "trading_sequence" if self.trading_sequence else "calendar_sequence"}


@dataclass(frozen=True)
class RankSpec(CanonicalIr):
    expression: Any
    direction: str
    bound: Any
    partition: Tuple[str, ...]

    def to_dict(self):
        return {"kind": "RankSpec", "expression": self.expression.to_dict(), "direction": self.direction, "bound": self.bound.to_dict(), "partition": list(self.partition)}


@dataclass(frozen=True)
class DataRequirement(CanonicalIr):
    domains: FrozenSet[str]
    capabilities: FrozenSet[str]

    def to_dict(self):
        return {"kind": "DataRequirement", "domains": sorted(self.domains), "capabilities": sorted(self.capabilities)}

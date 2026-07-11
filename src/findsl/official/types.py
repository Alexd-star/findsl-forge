from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class TypeKind(str, Enum):
    BOOLEAN = "boolean"
    NUMERIC = "numeric"
    STRING = "string"
    TIME = "time"
    UNKNOWN = "unknown"
    RANGE = "range"


class OfficialTypeError(ValueError):
    code = "OFFICIAL_TYPE_ERROR"


@dataclass(frozen=True)
class OfficialType:
    kind: TypeKind

    @property
    def legacy_name(self) -> str:
        return self.kind.value

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind.value}


@dataclass(frozen=True)
class RangeType(OfficialType):
    element_type: OfficialType

    def __init__(self, element_type: OfficialType):
        object.__setattr__(self, "kind", TypeKind.RANGE)
        object.__setattr__(self, "element_type", element_type)

    @property
    def legacy_name(self) -> str:
        return f"range[{self.element_type.legacy_name}]"

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "range", "element_type": self.element_type.to_dict()}


BOOLEAN = OfficialType(TypeKind.BOOLEAN)
NUMERIC = OfficialType(TypeKind.NUMERIC)
STRING = OfficialType(TypeKind.STRING)
TIME = OfficialType(TypeKind.TIME)
UNKNOWN = OfficialType(TypeKind.UNKNOWN)


def arithmetic_result(left: OfficialType, right: OfficialType) -> OfficialType:
    if UNKNOWN in {left, right}:
        if all(item in {NUMERIC, UNKNOWN} for item in (left, right)):
            return UNKNOWN
    if left is NUMERIC and right is NUMERIC:
        return NUMERIC
    raise OfficialTypeError(f"Arithmetic requires numeric operands, got {left.legacy_name} and {right.legacy_name}")


def require_boolean(left: OfficialType, right: OfficialType) -> OfficialType:
    if all(item in {BOOLEAN, UNKNOWN} for item in (left, right)):
        return BOOLEAN
    raise OfficialTypeError(f"Logical operation requires boolean operands, got {left.legacy_name} and {right.legacy_name}")


def require_ordered(left: OfficialType, right: OfficialType) -> OfficialType:
    if UNKNOWN in {left, right}:
        return BOOLEAN
    if left is right and left in {NUMERIC, TIME}:
        return BOOLEAN
    raise OfficialTypeError(f"Ordered comparison requires matching numeric or time operands, got {left.legacy_name} and {right.legacy_name}")


def require_equality(left: OfficialType, right: OfficialType) -> OfficialType:
    if UNKNOWN in {left, right} or left is right:
        return BOOLEAN
    raise OfficialTypeError(f"Equality comparison requires compatible operands, got {left.legacy_name} and {right.legacy_name}")


def require_approximate(left: OfficialType, right: OfficialType) -> OfficialType:
    if UNKNOWN in {left, right}:
        return BOOLEAN
    if left is right and left in {NUMERIC, STRING}:
        return BOOLEAN
    raise OfficialTypeError(f"Approximate comparison requires numeric or string operands, got {left.legacy_name} and {right.legacy_name}")

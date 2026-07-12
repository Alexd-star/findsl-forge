from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Tuple

from .catalog import PhysicalCatalog, default_physical_catalog


class PhysicalExpressionError(ValueError):
    pass


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_TYPES = {"boolean", "numeric", "string", "time"}
_ARITHMETIC = {"add", "subtract", "multiply", "divide", "safe_divide"}
_COMPARISONS = {"equal", "not_equal", "greater", "greater_equal", "less", "less_equal"}
_LOGICAL = {"and", "or"}


@dataclass(frozen=True)
class PhysicalExpressionNode:
    op: str
    type: str
    args: Tuple["PhysicalExpressionNode", ...] = ()
    column: str = ""
    value: Any = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"op": self.op, "type": self.type}
        if self.op == "column":
            payload["column"] = self.column
        elif self.op == "literal":
            payload["value"] = self.value
        else:
            payload["args"] = [item.to_dict() for item in self.args]
        return payload

    @property
    def required_columns(self) -> Tuple[Tuple[str, str], ...]:
        columns: Dict[str, str] = {}
        _collect_columns(self, columns)
        return tuple(sorted(columns.items()))


@dataclass(frozen=True)
class PhysicalExpressionDefinition:
    indicator_id: str
    resource_id: str
    value_type: str
    nullable: bool
    expression: PhysicalExpressionNode

    @property
    def required_columns(self) -> Tuple[Tuple[str, str], ...]:
        return self.expression.required_columns

    def to_dict(self) -> Dict[str, Any]:
        return {
            "indicator_id": self.indicator_id,
            "resource_id": self.resource_id,
            "value_type": self.value_type,
            "nullable": self.nullable,
            "expression": self.expression.to_dict(),
        }


class PhysicalExpressionRegistry:
    def __init__(self, definitions: Tuple[PhysicalExpressionDefinition, ...]):
        index: Dict[str, PhysicalExpressionDefinition] = {}
        for definition in definitions:
            key = definition.indicator_id.casefold()
            if key in index:
                raise PhysicalExpressionError(
                    f"duplicate physical expression: {definition.indicator_id}"
                )
            index[key] = definition
        self._definitions = MappingProxyType(index)
        canonical = [index[key].to_dict() for key in sorted(index)]
        payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self._fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @property
    def definitions(self) -> Tuple[PhysicalExpressionDefinition, ...]:
        return tuple(self._definitions.values())

    @property
    def fingerprint(self) -> str:
        return self._fingerprint

    def resolve(self, indicator_id: str) -> PhysicalExpressionDefinition:
        return self._definitions[indicator_id.casefold()]

    @classmethod
    def from_dict(cls, raw: Dict[str, Any], catalog: PhysicalCatalog) -> "PhysicalExpressionRegistry":
        if set(raw) != {"schema_version", "definitions"} or raw.get("schema_version") != 1:
            raise PhysicalExpressionError("physical expression root requires schema_version=1 and definitions")
        definitions = []
        for item in raw["definitions"]:
            if set(item) != {"indicator_id", "resource_id", "value_type", "nullable", "expression"}:
                raise PhysicalExpressionError("invalid physical expression definition fields")
            resource_id = str(item["resource_id"])
            try:
                catalog.resource(resource_id)
            except KeyError as exc:
                raise PhysicalExpressionError(f"unknown physical resource: {resource_id}") from exc
            value_type = _type_name(item["value_type"])
            expression = _parse_expression(item["expression"])
            if expression.type != value_type:
                raise PhysicalExpressionError(
                    f"expression root type {expression.type} does not match {value_type}"
                )
            definitions.append(
                PhysicalExpressionDefinition(
                    str(item["indicator_id"]),
                    resource_id,
                    value_type,
                    bool(item["nullable"]),
                    expression,
                )
            )
        return cls(tuple(definitions))

    @classmethod
    def load(cls, path: Path, catalog: PhysicalCatalog) -> "PhysicalExpressionRegistry":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")), catalog)


def default_physical_expressions(
    catalog: PhysicalCatalog = None,
) -> PhysicalExpressionRegistry:
    catalog = catalog or default_physical_catalog()
    root = Path(__file__).resolve().parents[4]
    return PhysicalExpressionRegistry.load(
        root / "configs" / "official" / "physical_expressions.json",
        catalog,
    )


def _parse_expression(raw: Dict[str, Any]) -> PhysicalExpressionNode:
    if not isinstance(raw, dict) or "op" not in raw:
        raise PhysicalExpressionError("physical expression node requires op")
    op = str(raw["op"])
    if op == "column":
        if set(raw) != {"op", "column", "type"}:
            raise PhysicalExpressionError("invalid column expression fields")
        column = str(raw["column"])
        if not _IDENTIFIER.fullmatch(column):
            raise PhysicalExpressionError(f"invalid physical column: {column}")
        return PhysicalExpressionNode(op, _type_name(raw["type"]), column=column)
    if op == "literal":
        if set(raw) != {"op", "value", "type"}:
            raise PhysicalExpressionError("invalid literal expression fields")
        value_type = _type_name(raw["type"])
        _validate_literal(raw["value"], value_type)
        return PhysicalExpressionNode(op, value_type, value=raw["value"])
    if op in _ARITHMETIC | _COMPARISONS | _LOGICAL:
        if set(raw) != {"op", "left", "right"}:
            raise PhysicalExpressionError(f"invalid {op} expression fields")
        left = _parse_expression(raw["left"])
        right = _parse_expression(raw["right"])
        if op in _ARITHMETIC:
            if left.type != "numeric" or right.type != "numeric":
                raise PhysicalExpressionError(f"{op} requires numeric operands")
            result_type = "numeric"
        elif op in _LOGICAL:
            if left.type != "boolean" or right.type != "boolean":
                raise PhysicalExpressionError(f"{op} requires boolean operands")
            result_type = "boolean"
        else:
            if left.type != right.type:
                raise PhysicalExpressionError(f"{op} requires compatible operands")
            if op not in {"equal", "not_equal"} and left.type not in {"numeric", "time"}:
                raise PhysicalExpressionError(f"{op} requires ordered operands")
            result_type = "boolean"
        return PhysicalExpressionNode(op, result_type, (left, right))
    if op == "negate":
        if set(raw) != {"op", "arg"}:
            raise PhysicalExpressionError("invalid negate expression fields")
        arg = _parse_expression(raw["arg"])
        if arg.type != "numeric":
            raise PhysicalExpressionError("negate requires numeric operand")
        return PhysicalExpressionNode(op, "numeric", (arg,))
    if op == "coalesce":
        if set(raw) != {"op", "args"} or not isinstance(raw["args"], list) or len(raw["args"]) < 2:
            raise PhysicalExpressionError("coalesce requires at least two args")
        args = tuple(_parse_expression(item) for item in raw["args"])
        if len({item.type for item in args}) != 1:
            raise PhysicalExpressionError("coalesce requires compatible operands")
        return PhysicalExpressionNode(op, args[0].type, args)
    raise PhysicalExpressionError(f"unsupported expression operator: {op}")


def _type_name(value: Any) -> str:
    name = str(value)
    if name not in _TYPES:
        raise PhysicalExpressionError(f"unsupported physical expression type: {name}")
    return name


def _validate_literal(value: Any, value_type: str) -> None:
    valid = {
        "boolean": isinstance(value, bool),
        "numeric": isinstance(value, (int, float)) and not isinstance(value, bool),
        "string": isinstance(value, str),
        "time": isinstance(value, str),
    }[value_type]
    if not valid:
        raise PhysicalExpressionError(f"literal value does not match type {value_type}")


def _collect_columns(node: PhysicalExpressionNode, columns: Dict[str, str]) -> None:
    if node.op == "column":
        existing = columns.get(node.column)
        if existing is not None and existing != node.type:
            raise PhysicalExpressionError(f"column {node.column} has conflicting types")
        columns[node.column] = node.type
    for child in node.args:
        _collect_columns(child, columns)

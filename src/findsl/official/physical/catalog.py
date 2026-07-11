from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Dict, Optional, Tuple


class PhysicalCatalogError(ValueError):
    pass


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


@dataclass(frozen=True)
class PhysicalResource:
    resource_id: str
    database: str
    table: str
    logical_entity: str
    partition_key: str
    distribution_key: str
    capabilities: Tuple[str, ...]
    priority: int

    @property
    def qualified_table(self) -> str:
        return f"{self.database}.{self.table}"


@dataclass(frozen=True)
class PhysicalField:
    indicator_id: str
    resource_id: str
    column: str
    value_type: str
    scale: Optional[float]
    nullable: bool


class PhysicalCatalog:
    def __init__(self, resources: Tuple[PhysicalResource, ...], fields: Tuple[PhysicalField, ...]):
        resource_index = {item.resource_id: item for item in resources}
        if len(resource_index) != len(resources):
            raise PhysicalCatalogError("duplicate physical resource ID")
        field_index: Dict[str, PhysicalField] = {}
        for field in fields:
            if field.resource_id not in resource_index:
                raise PhysicalCatalogError(f"unknown resource for {field.indicator_id}: {field.resource_id}")
            folded = field.indicator_id.casefold()
            if folded in field_index:
                raise PhysicalCatalogError(f"duplicate physical indicator: {field.indicator_id}")
            field_index[folded] = field
        self._resources = MappingProxyType(resource_index)
        self._fields = MappingProxyType(field_index)

    def resource(self, resource_id: str) -> PhysicalResource:
        return self._resources[resource_id]

    def indicator(self, indicator_id: str) -> PhysicalField:
        return self._fields[indicator_id.casefold()]

    @property
    def resources(self):
        return tuple(self._resources.values())

    @property
    def fields(self):
        return tuple(self._fields.values())

    @classmethod
    def load(cls, path: Path) -> "PhysicalCatalog":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if set(raw) != {"resources", "fields"}:
            raise PhysicalCatalogError("physical catalog root must contain only resources and fields")
        resources = tuple(_resource(item) for item in raw["resources"])
        fields = tuple(_field(item) for item in raw["fields"])
        return cls(resources, fields)


def _validate_identifier(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(str(value)):
        raise PhysicalCatalogError(f"invalid {label}: {value}")
    return str(value)


def _resource(item) -> PhysicalResource:
    expected = {"resource_id", "database", "table", "logical_entity", "partition_key", "distribution_key", "capabilities", "priority"}
    if set(item) != expected:
        raise PhysicalCatalogError("invalid physical resource fields")
    return PhysicalResource(
        _validate_identifier(item["resource_id"], "resource_id"),
        _validate_identifier(item["database"], "database"),
        _validate_identifier(item["table"], "table"),
        str(item["logical_entity"]),
        _validate_identifier(item["partition_key"], "partition_key"),
        _validate_identifier(item["distribution_key"], "distribution_key"),
        tuple(sorted(set(item["capabilities"]))),
        int(item["priority"]),
    )


def _field(item) -> PhysicalField:
    expected = {"indicator_id", "resource_id", "column", "value_type", "scale", "nullable"}
    if set(item) != expected:
        raise PhysicalCatalogError("invalid physical field fields")
    return PhysicalField(
        str(item["indicator_id"]),
        _validate_identifier(item["resource_id"], "resource_id"),
        _validate_identifier(item["column"], "column"),
        str(item["value_type"]),
        None if item["scale"] is None else float(item["scale"]),
        bool(item["nullable"]),
    )


@lru_cache(maxsize=1)
def default_physical_catalog() -> PhysicalCatalog:
    root = Path(__file__).resolve().parents[4]
    return PhysicalCatalog.load(root / "configs" / "official" / "physical_catalog.json")

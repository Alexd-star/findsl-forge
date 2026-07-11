from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple


class RegistryValidationError(ValueError):
    pass


_ALLOWED_FIELDS = {
    "canonical_name", "aliases", "value_type", "domain", "logical_field", "unit",
    "scale", "nullable", "availability", "capabilities", "physical_hint",
}
_VALUE_TYPES = {"numeric", "boolean", "string", "time"}
_AVAILABILITY = {"official_provided", "derived", "missing"}


@dataclass(frozen=True)
class IndicatorDefinition:
    canonical_name: str
    aliases: Tuple[str, ...]
    value_type: str
    domain: str
    logical_field: str
    unit: str
    scale: Optional[float]
    nullable: bool
    availability: str
    capabilities: Tuple[str, ...]
    physical_hint: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "canonical_name": self.canonical_name,
            "aliases": list(self.aliases),
            "value_type": self.value_type,
            "domain": self.domain,
            "logical_field": self.logical_field,
            "unit": self.unit,
            "scale": self.scale,
            "nullable": self.nullable,
            "availability": self.availability,
            "capabilities": list(self.capabilities),
            "physical_hint": self.physical_hint,
        }


class OfficialIndicatorRegistry:
    def __init__(self, definitions: Tuple[IndicatorDefinition, ...]):
        index: Dict[str, IndicatorDefinition] = {}
        for definition in definitions:
            for name in (definition.canonical_name, *definition.aliases):
                folded = name.casefold()
                if folded in index:
                    raise RegistryValidationError(f"duplicate indicator name or alias: {name}")
                index[folded] = definition
        self._definitions = definitions
        self._index: Mapping[str, IndicatorDefinition] = MappingProxyType(index)

    def __len__(self) -> int:
        return len(self._definitions)

    @property
    def definitions(self) -> Tuple[IndicatorDefinition, ...]:
        return self._definitions

    def resolve(self, name: str) -> IndicatorDefinition:
        try:
            return self._index[str(name).casefold()]
        except KeyError as exc:
            raise KeyError(f"unknown official indicator: {name}") from exc

    @classmethod
    def load(cls, path: Path) -> "OfficialIndicatorRegistry":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise RegistryValidationError("official indicator registry must be a JSON array")
        definitions = tuple(_validate_definition(item, index) for index, item in enumerate(raw))
        return cls(definitions)


def _validate_definition(item: Any, index: int) -> IndicatorDefinition:
    if not isinstance(item, dict):
        raise RegistryValidationError(f"indicator entry {index} must be an object")
    unknown = set(item) - _ALLOWED_FIELDS
    if unknown:
        raise RegistryValidationError(f"indicator entry {index} has unknown fields: {sorted(unknown)}")
    required = _ALLOWED_FIELDS - {"physical_hint"}
    missing = required - set(item)
    if missing:
        raise RegistryValidationError(f"indicator entry {index} misses fields: {sorted(missing)}")
    if item["value_type"] not in _VALUE_TYPES:
        raise RegistryValidationError(f"invalid value_type: {item['value_type']}")
    if item["availability"] not in _AVAILABILITY:
        raise RegistryValidationError(f"invalid availability: {item['availability']}")
    if item["availability"] == "missing" and item.get("physical_hint"):
        raise RegistryValidationError("missing indicator cannot declare physical_hint")
    if item["value_type"] in {"boolean", "string", "time"} and item["scale"] not in {None, 1, 1.0}:
        raise RegistryValidationError("non-numeric indicator cannot declare numeric scaling")
    aliases = item["aliases"]
    capabilities = item["capabilities"]
    if not isinstance(aliases, list) or not all(isinstance(value, str) for value in aliases):
        raise RegistryValidationError("aliases must be a string array")
    if not isinstance(capabilities, list) or not all(isinstance(value, str) for value in capabilities):
        raise RegistryValidationError("capabilities must be a string array")
    return IndicatorDefinition(
        canonical_name=str(item["canonical_name"]), aliases=tuple(aliases),
        value_type=str(item["value_type"]), domain=str(item["domain"]),
        logical_field=str(item["logical_field"]), unit=str(item["unit"]),
        scale=None if item["scale"] is None else float(item["scale"]),
        nullable=bool(item["nullable"]), availability=str(item["availability"]),
        capabilities=tuple(sorted(set(capabilities))), physical_hint=item.get("physical_hint"),
    )


@lru_cache(maxsize=1)
def default_official_registry() -> OfficialIndicatorRegistry:
    root = Path(__file__).resolve().parents[3]
    return OfficialIndicatorRegistry.load(root / "configs" / "official" / "indicators.json")

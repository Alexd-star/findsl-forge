from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

from .domain.target import EntityTargetSpec, parse_target_expression
from .external.data_domains import DataDomainCatalog


class EntityTargetCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class EntityTargetDefinition:
    token: str
    target_id: str
    logical_entity: str
    execution_mode: str
    required_data_domains: Tuple[str, ...]
    result_keys: Tuple[str, ...]


class EntityTargetCatalog:
    def __init__(
        self,
        default_target: EntityTargetDefinition,
        definitions: Tuple[EntityTargetDefinition, ...],
    ):
        by_token = {item.token: item for item in definitions}
        if len(by_token) != len(definitions):
            raise EntityTargetCatalogError("duplicate select_type token")
        if default_target.token:
            raise EntityTargetCatalogError("default target token must be empty")
        self.default_target = default_target
        self._definitions: Mapping[str, EntityTargetDefinition] = MappingProxyType(
            by_token
        )

    @property
    def definitions(self) -> Tuple[EntityTargetDefinition, ...]:
        return tuple(self._definitions.values())

    def bind(
        self,
        source: str,
        *,
        data_domains: Optional[DataDomainCatalog],
        profile_id: str,
    ) -> EntityTargetSpec:
        text = str(source or "").strip()
        expression = parse_target_expression(text, self._definitions)
        selected = (
            (self.default_target,)
            if expression is None
            else tuple(self._definitions[token] for token in expression.atoms)
        )
        required_domains = frozenset(
            domain_id for item in selected for domain_id in item.required_data_domains
        )
        statuses = (
            tuple(
                (
                    domain_id,
                    data_domains.resolve(domain_id).for_profile(profile_id).status,
                )
                for domain_id in sorted(required_domains)
            )
            if data_domains is not None
            else ()
        )
        return EntityTargetSpec(
            text,
            expression,
            tuple(dict.fromkeys(item.target_id for item in selected)),
            tuple(dict.fromkeys(item.logical_entity for item in selected)),
            tuple(dict.fromkeys(item.execution_mode for item in selected)),
            required_domains,
            statuses,
            tuple(dict.fromkeys(key for item in selected for key in item.result_keys)),
        )

    @classmethod
    def load(cls, path: Path) -> "EntityTargetCatalog":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if set(raw) != {"schema_version", "default_target", "targets"}:
            raise EntityTargetCatalogError("invalid entity target catalog root")
        if raw["schema_version"] != 1:
            raise EntityTargetCatalogError("unsupported entity target catalog version")
        return cls(
            _definition(raw["default_target"]),
            tuple(_definition(item) for item in raw["targets"]),
        )


def _definition(item) -> EntityTargetDefinition:
    expected = {
        "token",
        "target_id",
        "logical_entity",
        "execution_mode",
        "required_data_domains",
        "result_keys",
    }
    if not isinstance(item, dict) or set(item) != expected:
        raise EntityTargetCatalogError("invalid entity target definition")
    values = {
        key: str(item[key]).strip()
        for key in ("target_id", "logical_entity", "execution_mode")
    }
    if not all(values.values()):
        raise EntityTargetCatalogError("entity target identifiers cannot be empty")
    domains = tuple(dict.fromkeys(str(value).strip() for value in item["required_data_domains"]))
    keys = tuple(dict.fromkeys(str(value).strip() for value in item["result_keys"]))
    if not domains or not keys or any(not value for value in (*domains, *keys)):
        raise EntityTargetCatalogError("entity target domains and result keys cannot be empty")
    return EntityTargetDefinition(
        str(item["token"]).strip(),
        values["target_id"],
        values["logical_entity"],
        values["execution_mode"],
        domains,
        keys,
    )


@lru_cache(maxsize=1)
def default_entity_target_catalog() -> EntityTargetCatalog:
    root = Path(__file__).resolve().parents[3]
    return EntityTargetCatalog.load(root / "configs" / "official" / "entity_targets.json")

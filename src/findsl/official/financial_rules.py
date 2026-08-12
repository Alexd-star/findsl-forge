from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple


class FinancialRuleCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class FinancialRule:
    rule_id: str
    category: str
    source_role: str
    config_pointer: str
    applies_to: Tuple[str, ...]
    preconditions: Tuple[str, ...]
    semantic_invariant: str
    fallback_code: str
    fallback_behavior: str
    version: str

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["applies_to"] = list(self.applies_to)
        payload["preconditions"] = list(self.preconditions)
        return payload


@dataclass(frozen=True)
class FinancialRuleCatalog:
    schema_version: int
    catalog_id: str
    rules: Tuple[FinancialRule, ...]

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        available_roles: Mapping[str, Path] | None = None,
    ) -> "FinancialRuleCatalog":
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FinancialRuleCatalogError(f"cannot load financial rule catalog: {exc}") from exc
        if not isinstance(raw, dict) or set(raw) != {"schema_version", "catalog_id", "rules"}:
            raise FinancialRuleCatalogError("invalid financial rule catalog root")
        if raw["schema_version"] != 1 or not str(raw["catalog_id"]).strip():
            raise FinancialRuleCatalogError("invalid financial rule catalog identity")
        rules = tuple(_rule(item, index) for index, item in enumerate(raw["rules"]))
        identifiers = [item.rule_id for item in rules]
        if not rules or len(identifiers) != len(set(identifiers)):
            raise FinancialRuleCatalogError("financial rule IDs must be non-empty and unique")
        if available_roles is not None:
            missing = sorted({item.source_role for item in rules} - set(available_roles))
            if missing:
                raise FinancialRuleCatalogError(
                    f"financial rules reference unavailable compiler roles: {missing}"
                )
        return cls(1, str(raw["catalog_id"]), rules)

    def select(self, features: Mapping[str, Any]) -> Tuple[FinancialRule, ...]:
        tokens = {
            str(item)
            for key in (
                "function_families",
                "indicator_ids",
                "date_kinds",
                "scope_kinds",
                "aggregate_functions",
                "temporal_modes",
            )
            for item in features.get(key, ())
        }
        tokens.update(
            key for key, value in features.items() if isinstance(value, bool) and value
        )
        return tuple(
            rule
            for rule in self.rules
            if "all" in rule.applies_to or tokens.intersection(rule.applies_to)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "catalog_id": self.catalog_id,
            "rules": [item.to_dict() for item in self.rules],
        }


def _rule(raw: Any, index: int) -> FinancialRule:
    expected = {
        "rule_id",
        "category",
        "source_role",
        "config_pointer",
        "applies_to",
        "preconditions",
        "semantic_invariant",
        "fallback_code",
        "fallback_behavior",
        "version",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise FinancialRuleCatalogError(f"invalid financial rule fields at index {index}")
    scalar_fields = expected - {"applies_to", "preconditions"}
    if any(not str(raw[key]).strip() for key in scalar_fields):
        raise FinancialRuleCatalogError(f"financial rule scalar field is empty at index {index}")
    applies_to = tuple(str(item).strip() for item in raw["applies_to"] if str(item).strip())
    preconditions = tuple(
        str(item).strip() for item in raw["preconditions"] if str(item).strip()
    )
    if not applies_to or not preconditions:
        raise FinancialRuleCatalogError(
            f"financial rule applies_to and preconditions are required at index {index}"
        )
    return FinancialRule(
        rule_id=str(raw["rule_id"]),
        category=str(raw["category"]),
        source_role=str(raw["source_role"]),
        config_pointer=str(raw["config_pointer"]),
        applies_to=applies_to,
        preconditions=preconditions,
        semantic_invariant=str(raw["semantic_invariant"]),
        fallback_code=str(raw["fallback_code"]),
        fallback_behavior=str(raw["fallback_behavior"]),
        version=str(raw["version"]),
    )

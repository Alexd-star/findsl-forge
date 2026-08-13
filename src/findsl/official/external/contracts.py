from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Dict, Mapping, Tuple


class DomainTableContractError(ValueError):
    pass


@dataclass(frozen=True)
class DomainTableVariant:
    variant_id: str
    required_columns: Tuple[str, ...]
    any_of_columns: Tuple[str, ...]
    temporal_columns: Tuple[str, ...]
    description: str

    def evaluate(self, columns: Tuple[str, ...]) -> Mapping[str, object]:
        observed = set(columns)
        missing_required = sorted(set(self.required_columns) - observed)
        has_any = not self.any_of_columns or bool(
            observed.intersection(self.any_of_columns)
        )
        missing_temporal = sorted(set(self.temporal_columns) - observed)
        passed = not missing_required and has_any and not missing_temporal
        return MappingProxyType(
            {
                "variant_id": self.variant_id,
                "passed": passed,
                "missing_required_columns": missing_required,
                "missing_temporal_columns": missing_temporal,
                "any_of_columns_satisfied": has_any,
            }
        )


class DomainTableContractCatalog:
    def __init__(
        self, definitions: Mapping[str, Tuple[DomainTableVariant, ...]]
    ) -> None:
        self._definitions = MappingProxyType(dict(definitions))

    def resolve(self, domain_id: str) -> Tuple[DomainTableVariant, ...]:
        return self._definitions.get(str(domain_id).strip(), ())

    def audit(
        self, domain_id: str, columns: Tuple[str, ...]
    ) -> Mapping[str, object]:
        variants = self.resolve(domain_id)
        if not variants:
            return MappingProxyType(
                {
                    "status": "NO_CONTRACT",
                    "passed": True,
                    "domain_id": domain_id,
                    "matched_variant": None,
                    "variants": [],
                }
            )
        evaluations = [dict(item.evaluate(columns)) for item in variants]
        matched = next(
            (item["variant_id"] for item in evaluations if item["passed"]), None
        )
        return MappingProxyType(
            {
                "status": "PASS" if matched else "REJECTED",
                "passed": matched is not None,
                "domain_id": domain_id,
                "matched_variant": matched,
                "variants": evaluations,
            }
        )

    @classmethod
    def load(cls, path: Path) -> "DomainTableContractCatalog":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or set(raw) != {"schema_version", "domains"}:
            raise DomainTableContractError("invalid domain table contract root")
        if raw["schema_version"] != 1 or not isinstance(raw["domains"], list):
            raise DomainTableContractError("unsupported domain table contract version")
        definitions: Dict[str, Tuple[DomainTableVariant, ...]] = {}
        for domain in raw["domains"]:
            if not isinstance(domain, dict) or set(domain) != {
                "domain_id",
                "variants",
            }:
                raise DomainTableContractError("invalid domain table contract entry")
            domain_id = str(domain["domain_id"]).strip()
            if not domain_id or domain_id in definitions:
                raise DomainTableContractError(
                    f"duplicate or empty domain contract: {domain_id}"
                )
            variants = tuple(_parse_variant(item) for item in domain["variants"])
            if not variants or len({item.variant_id for item in variants}) != len(
                variants
            ):
                raise DomainTableContractError(
                    f"domain contract variants are empty or duplicated: {domain_id}"
                )
            definitions[domain_id] = variants
        return cls(definitions)


def _parse_variant(raw) -> DomainTableVariant:
    expected = {
        "variant_id",
        "required_columns",
        "any_of_columns",
        "temporal_columns",
        "description",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise DomainTableContractError("invalid domain table variant")
    arrays = {}
    for key in ("required_columns", "any_of_columns", "temporal_columns"):
        if not isinstance(raw[key], list):
            raise DomainTableContractError(f"{key} must be an array")
        values = tuple(str(item).strip() for item in raw[key])
        if any(not item for item in values) or len(set(values)) != len(values):
            raise DomainTableContractError(f"{key} contains empty or duplicate values")
        arrays[key] = values
    if not set(arrays["temporal_columns"]).issubset(arrays["required_columns"]):
        raise DomainTableContractError(
            "temporal columns must also be required columns"
        )
    return DomainTableVariant(
        variant_id=str(raw["variant_id"]).strip(),
        required_columns=arrays["required_columns"],
        any_of_columns=arrays["any_of_columns"],
        temporal_columns=arrays["temporal_columns"],
        description=str(raw["description"]).strip(),
    )


@lru_cache(maxsize=1)
def default_domain_table_contracts() -> DomainTableContractCatalog:
    root = Path(__file__).resolve().parents[4]
    return DomainTableContractCatalog.load(
        root / "configs" / "official" / "domain_table_contracts.json"
    )

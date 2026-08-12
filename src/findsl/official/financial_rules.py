from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple


class FinancialRuleCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class FinancialRuleRelease:
    release_id: str
    status: str
    effective_from: str
    effective_to: Optional[str]
    approved_by: str
    change_ticket: str
    previous_catalog_id: Optional[str]
    rollback_catalog_id: Optional[str]
    retired_rule_ids: Tuple[str, ...]

    def active_on(self, as_of_date: str) -> bool:
        return bool(
            self.status == "active"
            and self.effective_from <= as_of_date
            and (self.effective_to is None or as_of_date <= self.effective_to)
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["retired_rule_ids"] = list(self.retired_rule_ids)
        return payload


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
    release: FinancialRuleRelease
    rules: Tuple[FinancialRule, ...]
    fingerprint: str

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        available_roles: Mapping[str, Path] | None = None,
        require_active: bool = True,
        as_of_date: str | None = None,
    ) -> "FinancialRuleCatalog":
        try:
            payload = Path(path).read_bytes()
            raw = json.loads(payload.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FinancialRuleCatalogError(f"cannot load financial rule catalog: {exc}") from exc
        expected = {"schema_version", "catalog_id", "release", "rules"}
        if not isinstance(raw, dict) or set(raw) != expected:
            raise FinancialRuleCatalogError("invalid financial rule catalog root")
        if raw["schema_version"] != 2 or not str(raw["catalog_id"]).strip():
            raise FinancialRuleCatalogError("invalid financial rule catalog identity")
        release = _release(raw["release"])
        effective_date = _iso_date(as_of_date or date.today().isoformat(), "as_of_date")
        if require_active and not release.active_on(effective_date):
            raise FinancialRuleCatalogError(
                "financial rule release is not active on "
                f"{effective_date}: {release.release_id}/{release.status}"
            )
        rules = tuple(_rule(item, index) for index, item in enumerate(raw["rules"]))
        identifiers = [item.rule_id for item in rules]
        if not rules or len(identifiers) != len(set(identifiers)):
            raise FinancialRuleCatalogError("financial rule IDs must be non-empty and unique")
        if set(identifiers).intersection(release.retired_rule_ids):
            raise FinancialRuleCatalogError("active and retired financial rule IDs overlap")
        if available_roles is not None:
            missing = sorted({item.source_role for item in rules} - set(available_roles))
            if missing:
                raise FinancialRuleCatalogError(
                    f"financial rules reference unavailable compiler roles: {missing}"
                )
        return cls(
            2,
            str(raw["catalog_id"]),
            release,
            rules,
            hashlib.sha256(payload).hexdigest(),
        )

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
            "release": self.release.to_dict(),
            "fingerprint": self.fingerprint,
            "rules": [item.to_dict() for item in self.rules],
        }


def validate_rule_release_transition(
    baseline: FinancialRuleCatalog,
    candidate: FinancialRuleCatalog,
) -> Dict[str, Any]:
    errors = []
    if candidate.catalog_id == baseline.catalog_id:
        errors.append("candidate catalog_id must differ from baseline")
    if candidate.release.release_id == baseline.release.release_id:
        errors.append("candidate release_id must differ from baseline")
    if candidate.release.previous_catalog_id != baseline.catalog_id:
        errors.append("candidate previous_catalog_id must reference the baseline catalog")
    if candidate.release.rollback_catalog_id != baseline.catalog_id:
        errors.append("candidate rollback_catalog_id must reference the baseline catalog")
    if candidate.release.status not in {"draft", "shadow", "active"}:
        errors.append("candidate status must be draft, shadow or active")

    baseline_rules = {item.rule_id: item for item in baseline.rules}
    candidate_rules = {item.rule_id: item for item in candidate.rules}
    removed = tuple(sorted(set(baseline_rules) - set(candidate_rules)))
    undocumented = tuple(
        rule_id
        for rule_id in removed
        if rule_id not in candidate.release.retired_rule_ids
    )
    if undocumented:
        errors.append("removed rules must be declared in retired_rule_ids: " + ", ".join(undocumented))
    for rule_id in sorted(set(baseline_rules).intersection(candidate_rules)):
        if _version_key(candidate_rules[rule_id].version) < _version_key(
            baseline_rules[rule_id].version
        ):
            errors.append(f"rule version cannot decrease: {rule_id}")

    changed = tuple(
        sorted(
            rule_id
            for rule_id in set(baseline_rules).intersection(candidate_rules)
            if baseline_rules[rule_id] != candidate_rules[rule_id]
        )
    )
    added = tuple(sorted(set(candidate_rules) - set(baseline_rules)))
    return {
        "schema_version": 1,
        "baseline_catalog_id": baseline.catalog_id,
        "baseline_fingerprint": baseline.fingerprint,
        "candidate_catalog_id": candidate.catalog_id,
        "candidate_fingerprint": candidate.fingerprint,
        "candidate_release": candidate.release.to_dict(),
        "added_rule_ids": list(added),
        "changed_rule_ids": list(changed),
        "removed_rule_ids": list(removed),
        "errors": errors,
        "passed": not errors,
    }


def _release(raw: Any) -> FinancialRuleRelease:
    expected = {
        "release_id",
        "status",
        "effective_from",
        "effective_to",
        "approved_by",
        "change_ticket",
        "previous_catalog_id",
        "rollback_catalog_id",
        "retired_rule_ids",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise FinancialRuleCatalogError("invalid financial rule release fields")
    status = str(raw["status"])
    if status not in {"draft", "shadow", "active", "retired"}:
        raise FinancialRuleCatalogError("invalid financial rule release status")
    scalar = ("release_id", "approved_by", "change_ticket")
    if any(not str(raw[key]).strip() for key in scalar):
        raise FinancialRuleCatalogError("financial rule release identity is incomplete")
    effective_from = _iso_date(raw["effective_from"], "effective_from")
    effective_to = (
        None
        if raw["effective_to"] is None
        else _iso_date(raw["effective_to"], "effective_to")
    )
    if effective_to is not None and effective_from > effective_to:
        raise FinancialRuleCatalogError("financial rule release date range is invalid")
    retired = tuple(str(item).strip() for item in raw["retired_rule_ids"])
    if any(not item for item in retired) or len(retired) != len(set(retired)):
        raise FinancialRuleCatalogError("retired_rule_ids must be unique non-empty IDs")
    return FinancialRuleRelease(
        release_id=str(raw["release_id"]),
        status=status,
        effective_from=effective_from,
        effective_to=effective_to,
        approved_by=str(raw["approved_by"]),
        change_ticket=str(raw["change_ticket"]),
        previous_catalog_id=_optional_non_empty(raw["previous_catalog_id"]),
        rollback_catalog_id=_optional_non_empty(raw["rollback_catalog_id"]),
        retired_rule_ids=retired,
    )


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


def _iso_date(value: Any, label: str) -> str:
    text = str(value).strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise FinancialRuleCatalogError(f"{label} must use YYYY-MM-DD") from exc


def _optional_non_empty(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        raise FinancialRuleCatalogError("optional release identifiers cannot be empty")
    return text


def _version_key(value: str) -> Tuple[int, ...]:
    try:
        return tuple(int(item) for item in str(value).split("."))
    except ValueError as exc:
        raise FinancialRuleCatalogError(f"rule version must be numeric: {value}") from exc

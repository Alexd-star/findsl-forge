from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Dict, Optional, Tuple

from .models import normalize_catalog_name


class ScopeSemanticPolicyError(ValueError):
    pass


_RESOLUTION_KINDS = {"exact_scope", "security_name_regex", "set_operation"}
_SEMANTIC_BASES = {
    "official_rule",
    "provider_taxonomy",
    "business_policy",
    "controlled_typo_correction",
}
_CONFIDENCE_LEVELS = {"high", "medium", "low"}
_RISK_LEVELS = {"low", "medium", "high"}
_REVIEW_STATUSES = {"approved", "draft", "rejected"}
_SET_OPERATIONS = {"intersection", "union"}


@dataclass(frozen=True)
class ScopePolicyComponent:
    source_snapshot_id: str
    scope_code: str
    minimum_member_count: int = 1


@dataclass(frozen=True)
class ScopeSemanticPolicy:
    policy_id: str
    aliases: Tuple[str, ...]
    resolution_kind: str
    scope_name: str
    minimum_member_count: int
    maximum_member_count: Optional[int]
    semantic_basis: str
    confidence: str
    risk_level: str
    review_status: str
    effective_from: str
    rationale: str
    rationale_urls: Tuple[str, ...]
    data_boundary: str
    source_snapshot_id: str = ""
    target_scope_code: str = ""
    selector_pattern: str = ""
    operation: str = ""
    components: Tuple[ScopePolicyComponent, ...] = ()

    @property
    def scope_code(self) -> str:
        if self.resolution_kind == "exact_scope":
            return self.target_scope_code
        canonical = {
            "policy_id": self.policy_id,
            "resolution_kind": self.resolution_kind,
            "source_snapshot_id": self.source_snapshot_id,
            "selector_pattern": self.selector_pattern,
            "operation": self.operation,
            "components": [component.__dict__ for component in self.components],
        }
        digest = hashlib.sha256(
            json.dumps(
                canonical,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return f"POLICY:{digest[:16]}"

    def to_audit_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "policy_id": self.policy_id,
            "aliases": list(self.aliases),
            "resolution_kind": self.resolution_kind,
            "scope_name": self.scope_name,
            "scope_code": self.scope_code,
            "minimum_member_count": self.minimum_member_count,
            "maximum_member_count": self.maximum_member_count,
            "semantic_basis": self.semantic_basis,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "review_status": self.review_status,
            "effective_from": self.effective_from,
            "rationale": self.rationale,
            "rationale_urls": list(self.rationale_urls),
            "data_boundary": self.data_boundary,
        }
        if self.resolution_kind == "exact_scope":
            payload["target"] = {
                "source_snapshot_id": self.source_snapshot_id,
                "scope_code": self.target_scope_code,
            }
        elif self.resolution_kind == "security_name_regex":
            payload["source_snapshot_id"] = self.source_snapshot_id
            payload["selector"] = {
                "field": "scope_name",
                "operator": "regex",
                "value": self.selector_pattern,
            }
        else:
            payload["operation"] = self.operation
            payload["components"] = [component.__dict__ for component in self.components]
        return payload


class ScopeSemanticPolicyCatalog:
    def __init__(
        self,
        policies: Tuple[ScopeSemanticPolicy, ...],
        *,
        policy_set_id: str,
        profile: str,
        allowed_risk_levels: Tuple[str, ...],
    ):
        if not policy_set_id.strip() or not profile.strip():
            raise ScopeSemanticPolicyError("policy set id and profile are required")
        invalid_risks = set(allowed_risk_levels) - _RISK_LEVELS
        if invalid_risks or not allowed_risk_levels:
            raise ScopeSemanticPolicyError("invalid allowed risk levels")
        by_alias: Dict[str, ScopeSemanticPolicy] = {}
        by_id: Dict[str, ScopeSemanticPolicy] = {}
        for policy in policies:
            if policy.review_status != "approved":
                raise ScopeSemanticPolicyError(
                    f"active policy is not approved: {policy.policy_id}"
                )
            if policy.risk_level not in allowed_risk_levels:
                raise ScopeSemanticPolicyError(
                    f"active profile rejects policy risk: {policy.policy_id}"
                )
            if policy.policy_id in by_id:
                raise ScopeSemanticPolicyError(
                    f"duplicate semantic policy id: {policy.policy_id}"
                )
            by_id[policy.policy_id] = policy
            for alias in policy.aliases:
                normalized = normalize_catalog_name(alias)
                existing = by_alias.get(normalized)
                if existing is not None and existing.policy_id != policy.policy_id:
                    raise ScopeSemanticPolicyError(
                        f"conflicting semantic policy alias: {alias}"
                    )
                by_alias[normalized] = policy
        self.policy_set_id = policy_set_id
        self.profile = profile
        self.allowed_risk_levels = allowed_risk_levels
        self.policies = policies
        self._by_alias = MappingProxyType(by_alias)

    def resolve(self, alias: str) -> ScopeSemanticPolicy:
        source = str(alias).strip()
        try:
            return self._by_alias[normalize_catalog_name(source)]
        except KeyError as exc:
            raise KeyError(source) from exc

    @classmethod
    def from_dict(cls, raw) -> "ScopeSemanticPolicyCatalog":
        required = {
            "schema_version",
            "policy_set_id",
            "profile",
            "allowed_risk_levels",
            "entries",
        }
        if set(raw) != required:
            raise ScopeSemanticPolicyError("invalid semantic policy root")
        if raw["schema_version"] != 1:
            raise ScopeSemanticPolicyError("unsupported semantic policy version")
        policies = tuple(_policy_from_dict(entry) for entry in raw["entries"])
        return cls(
            policies,
            policy_set_id=str(raw["policy_set_id"]),
            profile=str(raw["profile"]),
            allowed_risk_levels=tuple(str(item) for item in raw["allowed_risk_levels"]),
        )

    @classmethod
    def load(cls, path: Path) -> "ScopeSemanticPolicyCatalog":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _policy_from_dict(raw) -> ScopeSemanticPolicy:
    common = {
        "policy_id",
        "aliases",
        "resolution_kind",
        "scope_name",
        "minimum_member_count",
        "maximum_member_count",
        "semantic_basis",
        "confidence",
        "risk_level",
        "review_status",
        "effective_from",
        "rationale",
        "rationale_urls",
        "data_boundary",
    }
    kind = str(raw.get("resolution_kind", ""))
    specific = {
        "exact_scope": {"target"},
        "security_name_regex": {"source_snapshot_id", "selector"},
        "set_operation": {"operation", "components"},
    }.get(kind)
    if specific is None or set(raw) != common | specific:
        raise ScopeSemanticPolicyError("invalid semantic policy entry")

    aliases = tuple(str(item).strip() for item in raw["aliases"])
    normalized_aliases = {normalize_catalog_name(item) for item in aliases if item}
    if not aliases or not all(aliases) or len(normalized_aliases) != len(aliases):
        raise ScopeSemanticPolicyError("policy aliases must be non-empty and unique")
    minimum = int(raw["minimum_member_count"])
    maximum_raw = raw["maximum_member_count"]
    maximum = None if maximum_raw is None else int(maximum_raw)
    if minimum < 1 or (maximum is not None and maximum < minimum):
        raise ScopeSemanticPolicyError("invalid policy member count bounds")

    semantic_basis = str(raw["semantic_basis"])
    confidence = str(raw["confidence"])
    risk_level = str(raw["risk_level"])
    review_status = str(raw["review_status"])
    if semantic_basis not in _SEMANTIC_BASES:
        raise ScopeSemanticPolicyError("invalid semantic policy basis")
    if confidence not in _CONFIDENCE_LEVELS:
        raise ScopeSemanticPolicyError("invalid semantic policy confidence")
    if risk_level not in _RISK_LEVELS:
        raise ScopeSemanticPolicyError("invalid semantic policy risk")
    if review_status not in _REVIEW_STATUSES:
        raise ScopeSemanticPolicyError("invalid semantic policy review status")
    effective_from = str(raw["effective_from"])
    try:
        date.fromisoformat(effective_from)
    except ValueError as exc:
        raise ScopeSemanticPolicyError("policy effective_from must use YYYY-MM-DD") from exc
    rationale_urls = tuple(str(item).strip() for item in raw["rationale_urls"])
    if not rationale_urls or any(
        not (item.startswith("https://") or item.startswith("urn:"))
        for item in rationale_urls
    ):
        raise ScopeSemanticPolicyError("policy rationale URLs must be HTTPS or URN")
    text_fields = {
        "policy_id": raw["policy_id"],
        "scope_name": raw["scope_name"],
        "rationale": raw["rationale"],
        "data_boundary": raw["data_boundary"],
    }
    if any(not str(value).strip() for value in text_fields.values()):
        raise ScopeSemanticPolicyError("semantic policy text fields are required")

    source_snapshot_id = ""
    target_scope_code = ""
    selector_pattern = ""
    operation = ""
    components: Tuple[ScopePolicyComponent, ...] = ()
    if kind == "exact_scope":
        target = raw["target"]
        if set(target) != {"source_snapshot_id", "scope_code"}:
            raise ScopeSemanticPolicyError("invalid exact scope target")
        source_snapshot_id = str(target["source_snapshot_id"]).strip()
        target_scope_code = str(target["scope_code"]).strip()
        if not source_snapshot_id or not target_scope_code:
            raise ScopeSemanticPolicyError("exact scope target is required")
    elif kind == "security_name_regex":
        selector = raw["selector"]
        if set(selector) != {"field", "operator", "value"} or (
            selector["field"] != "scope_name" or selector["operator"] != "regex"
        ):
            raise ScopeSemanticPolicyError("unsupported security selector")
        source_snapshot_id = str(raw["source_snapshot_id"]).strip()
        selector_pattern = str(selector["value"]).strip()
        if not source_snapshot_id or not selector_pattern:
            raise ScopeSemanticPolicyError("security selector source and pattern are required")
        try:
            re.compile(selector_pattern)
        except re.error as exc:
            raise ScopeSemanticPolicyError("invalid security selector regex") from exc
    else:
        operation = str(raw["operation"])
        if operation not in _SET_OPERATIONS:
            raise ScopeSemanticPolicyError("unsupported semantic set operation")
        components = tuple(_component_from_dict(item) for item in raw["components"])
        if len(components) < 2:
            raise ScopeSemanticPolicyError("semantic set operation requires two components")

    return ScopeSemanticPolicy(
        policy_id=str(raw["policy_id"]),
        aliases=aliases,
        resolution_kind=kind,
        scope_name=str(raw["scope_name"]),
        minimum_member_count=minimum,
        maximum_member_count=maximum,
        semantic_basis=semantic_basis,
        confidence=confidence,
        risk_level=risk_level,
        review_status=review_status,
        effective_from=effective_from,
        rationale=str(raw["rationale"]),
        rationale_urls=rationale_urls,
        data_boundary=str(raw["data_boundary"]),
        source_snapshot_id=source_snapshot_id,
        target_scope_code=target_scope_code,
        selector_pattern=selector_pattern,
        operation=operation,
        components=components,
    )


def _component_from_dict(raw) -> ScopePolicyComponent:
    required = {"source_snapshot_id", "scope_code", "minimum_member_count"}
    if set(raw) != required:
        raise ScopeSemanticPolicyError("invalid semantic policy component")
    minimum = int(raw["minimum_member_count"])
    if minimum < 1:
        raise ScopeSemanticPolicyError("component minimum member count must be positive")
    source_snapshot_id = str(raw["source_snapshot_id"]).strip()
    scope_code = str(raw["scope_code"]).strip()
    if not source_snapshot_id or not scope_code:
        raise ScopeSemanticPolicyError("semantic policy component source is required")
    return ScopePolicyComponent(source_snapshot_id, scope_code, minimum)

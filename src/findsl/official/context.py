from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Mapping, Tuple

from .external.policy import ScopeSemanticPolicyCatalog
from .external.runtime import (
    BenchmarkPolicyCatalog,
    ExternalDataPolicy,
    ExternalIndexQuoteCatalog,
    ExternalScopeRuntimeCatalog,
)
from .physical.approximation import NumericApproximationPolicy
from .physical.catalog import PhysicalCatalog
from .physical.expressions import PhysicalExpressionRegistry
from .physical.patterns import PhysicalPatternConfig
from .physical.runtime import PhysicalRuntimeCatalogs
from .physical.scopes import SecurityScopeCatalog
from .physical.statistics import PhysicalStatisticsSnapshot
from .physical.strategies import PhysicalStrategyRegistry
from .policy import SemanticPolicySet
from .registry import OfficialIndicatorRegistry
from .signatures import OfficialFunctionCatalog


class CompileContextError(ValueError):
    pass


@dataclass(frozen=True)
class CatalogFile:
    role: str
    relative_path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class CatalogSnapshot:
    repo_root: Path
    manifest_path: Path
    profile_id: str
    policy_id: str
    files: Tuple[CatalogFile, ...]
    fingerprint: str

    @classmethod
    def capture(
        cls,
        repo_root: Path,
        manifest_path: Path | None = None,
    ) -> "CatalogSnapshot":
        root = Path(repo_root).resolve()
        manifest = Path(manifest_path or root / "configs/official/compiler_manifest.json").resolve()
        raw = json.loads(manifest.read_text(encoding="utf-8"))
        expected = {"schema_version", "profile_id", "policy_id", "entries"}
        if not isinstance(raw, dict) or set(raw) != expected or raw["schema_version"] != 1:
            raise CompileContextError("invalid compiler manifest root")
        profile_id = _non_empty(raw["profile_id"], "profile_id")
        policy_id = _non_empty(raw["policy_id"], "policy_id")
        files = []
        roles = set()
        paths = set()
        for index, item in enumerate(raw["entries"]):
            if not isinstance(item, dict) or set(item) != {"role", "path"}:
                raise CompileContextError(f"invalid compiler manifest entry {index}")
            role = _non_empty(item["role"], f"entries[{index}].role")
            relative = _non_empty(item["path"], f"entries[{index}].path").replace("\\", "/")
            if role in roles or relative in paths:
                raise CompileContextError(f"duplicate compiler manifest role or path: {role}/{relative}")
            absolute = (root / relative).resolve()
            if root not in absolute.parents or not absolute.is_file():
                raise CompileContextError(f"compiler config is missing or outside repository: {relative}")
            payload = absolute.read_bytes()
            files.append(
                CatalogFile(
                    role,
                    relative,
                    hashlib.sha256(payload).hexdigest(),
                    len(payload),
                )
            )
            roles.add(role)
            paths.add(relative)
        required_roles = {
            "indicator_registry",
            "function_catalog",
            "semantic_policies",
            "physical_catalog",
            "physical_expressions",
            "physical_statistics",
            "physical_strategies",
            "security_scopes",
            "external_scope_runtime",
            "scope_semantic_policies",
            "external_data_policy",
            "external_index_quotes",
            "benchmark_policy",
            "approximation_policy",
            "technical_patterns",
        }
        missing = required_roles - roles
        if missing:
            raise CompileContextError(f"compiler manifest misses roles: {sorted(missing)}")
        canonical = {
            "profile_id": profile_id,
            "policy_id": policy_id,
            "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "files": [item.__dict__ for item in sorted(files, key=lambda value: value.role)],
        }
        encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return cls(
            root,
            manifest,
            profile_id,
            policy_id,
            tuple(sorted(files, key=lambda value: value.role)),
            hashlib.sha256(encoded).hexdigest(),
        )

    @property
    def paths(self) -> Mapping[str, Path]:
        return MappingProxyType(
            {item.role: self.repo_root / item.relative_path for item in self.files}
        )

    def assert_current(self) -> None:
        current = CatalogSnapshot.capture(self.repo_root, self.manifest_path)
        if current.fingerprint != self.fingerprint:
            raise CompileContextError(
                "compiler catalog changed during the lifetime of the compile context"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "policy_id": self.policy_id,
            "fingerprint": self.fingerprint,
            "files": [item.__dict__ for item in self.files],
        }


@dataclass(frozen=True)
class CompileContext:
    snapshot: CatalogSnapshot
    registry: OfficialIndicatorRegistry
    function_catalog: OfficialFunctionCatalog
    physical_catalog: PhysicalCatalog
    physical_expressions: PhysicalExpressionRegistry
    physical_statistics: PhysicalStatisticsSnapshot
    physical_strategies: PhysicalStrategyRegistry
    physical_runtime: PhysicalRuntimeCatalogs

    @classmethod
    def load(
        cls,
        repo_root: Path | None = None,
        manifest_path: Path | None = None,
    ) -> "CompileContext":
        root = Path(repo_root or Path(__file__).resolve().parents[3]).resolve()
        snapshot = CatalogSnapshot.capture(root, manifest_path)
        paths = snapshot.paths
        registry = OfficialIndicatorRegistry.load(paths["indicator_registry"])
        function_catalog = OfficialFunctionCatalog.load(paths["function_catalog"])
        catalog = PhysicalCatalog.load(paths["physical_catalog"])
        expressions = PhysicalExpressionRegistry.load(paths["physical_expressions"], catalog)
        statistics = PhysicalStatisticsSnapshot.load(paths["physical_statistics"], catalog)
        strategies = PhysicalStrategyRegistry.load(paths["physical_strategies"], catalog)
        policies = ScopeSemanticPolicyCatalog.load(paths["scope_semantic_policies"])
        runtime_raw = json.loads(paths["external_scope_runtime"].read_text(encoding="utf-8"))
        if set(runtime_raw) != {"schema_version", "membership_resource_id", "entries"}:
            raise CompileContextError("invalid external scope runtime catalog")
        external_scopes = ExternalScopeRuntimeCatalog(
            runtime_raw["entries"],
            membership_resource_id=str(runtime_raw["membership_resource_id"]),
            semantic_policies=policies,
        )
        runtime = PhysicalRuntimeCatalogs(
            semantic_policy=SemanticPolicySet.load(paths["semantic_policies"]),
            function_catalog=function_catalog,
            security_scopes=SecurityScopeCatalog.load(paths["security_scopes"]),
            external_scopes=external_scopes,
            external_data_policy=ExternalDataPolicy.load(paths["external_data_policy"]),
            external_index_quotes=ExternalIndexQuoteCatalog.load(paths["external_index_quotes"]),
            benchmark_policy=BenchmarkPolicyCatalog.load(paths["benchmark_policy"]),
            approximation_policy=NumericApproximationPolicy.load(paths["approximation_policy"]),
            technical_patterns=PhysicalPatternConfig.load(paths["technical_patterns"]),
        )
        if runtime.semantic_policy.policy_id != snapshot.policy_id:
            raise CompileContextError(
                "semantic policy ID does not match compiler manifest policy_id"
            )
        snapshot.assert_current()
        return cls(
            snapshot,
            registry,
            function_catalog,
            catalog,
            expressions,
            statistics,
            strategies,
            runtime,
        )

    @property
    def context_id(self) -> str:
        return self.snapshot.fingerprint

    def assert_current(self) -> None:
        self.snapshot.assert_current()

    def versioned_plan_id(self, physical_node_id: str, options: Mapping[str, Any]) -> str:
        payload = json.dumps(
            {
                "physical_node_id": physical_node_id,
                "context_id": self.context_id,
                "options": dict(options),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context_id": self.context_id,
            "catalog_snapshot": self.snapshot.to_dict(),
        }


@lru_cache(maxsize=1)
def default_compile_context() -> CompileContext:
    return CompileContext.load()


def _non_empty(value: Any, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise CompileContextError(f"{label} cannot be empty")
    return text

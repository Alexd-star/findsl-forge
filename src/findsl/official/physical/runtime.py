from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator, Optional

from ..policy import SemanticPolicySet
from ..signatures import OfficialFunctionCatalog
from ..external.runtime import (
    BenchmarkPolicyCatalog,
    ExternalDataPolicy,
    ExternalIndexQuoteCatalog,
    ExternalScopeRuntimeCatalog,
    default_benchmark_policy_catalog,
    default_external_data_policy,
    default_external_index_quote_catalog,
    default_external_scope_catalog,
)
from .approximation import NumericApproximationPolicy, default_numeric_approximation_policy
from .patterns import PhysicalPatternConfig, default_physical_pattern_config
from .scopes import SecurityScopeCatalog, default_security_scope_catalog


@dataclass(frozen=True)
class PhysicalRuntimeCatalogs:
    semantic_policy: SemanticPolicySet
    function_catalog: OfficialFunctionCatalog
    security_scopes: SecurityScopeCatalog
    external_scopes: ExternalScopeRuntimeCatalog
    external_data_policy: ExternalDataPolicy
    external_index_quotes: ExternalIndexQuoteCatalog
    benchmark_policy: BenchmarkPolicyCatalog
    approximation_policy: NumericApproximationPolicy
    technical_patterns: PhysicalPatternConfig


_ACTIVE_RUNTIME: ContextVar[Optional[PhysicalRuntimeCatalogs]] = ContextVar(
    "findsl_official_physical_runtime",
    default=None,
)


@contextmanager
def use_physical_runtime(runtime: PhysicalRuntimeCatalogs) -> Iterator[None]:
    token = _ACTIVE_RUNTIME.set(runtime)
    try:
        yield
    finally:
        _ACTIVE_RUNTIME.reset(token)


def current_security_scope_catalog() -> SecurityScopeCatalog:
    runtime = _ACTIVE_RUNTIME.get()
    return runtime.security_scopes if runtime else default_security_scope_catalog()


def current_semantic_policy() -> Optional[SemanticPolicySet]:
    runtime = _ACTIVE_RUNTIME.get()
    return runtime.semantic_policy if runtime else None


def current_function_catalog() -> Optional[OfficialFunctionCatalog]:
    runtime = _ACTIVE_RUNTIME.get()
    return runtime.function_catalog if runtime else None


def current_external_scope_catalog() -> ExternalScopeRuntimeCatalog:
    runtime = _ACTIVE_RUNTIME.get()
    return runtime.external_scopes if runtime else default_external_scope_catalog()


def current_external_data_policy() -> ExternalDataPolicy:
    runtime = _ACTIVE_RUNTIME.get()
    return runtime.external_data_policy if runtime else default_external_data_policy()


def current_external_index_quote_catalog() -> ExternalIndexQuoteCatalog:
    runtime = _ACTIVE_RUNTIME.get()
    return runtime.external_index_quotes if runtime else default_external_index_quote_catalog()


def current_benchmark_policy_catalog() -> BenchmarkPolicyCatalog:
    runtime = _ACTIVE_RUNTIME.get()
    return runtime.benchmark_policy if runtime else default_benchmark_policy_catalog()


def current_numeric_approximation_policy() -> NumericApproximationPolicy:
    runtime = _ACTIVE_RUNTIME.get()
    return runtime.approximation_policy if runtime else default_numeric_approximation_policy()


def current_physical_pattern_config() -> PhysicalPatternConfig:
    runtime = _ACTIVE_RUNTIME.get()
    return runtime.technical_patterns if runtime else default_physical_pattern_config()

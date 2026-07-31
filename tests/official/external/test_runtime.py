import pytest

from findsl.official.external.runtime import (
    BenchmarkPolicyCatalog,
    ExternalDataPolicy,
    ExternalScopeRuntimeCatalog,
    ExternalScopeRuntimeError,
    default_external_scope_catalog,
)


def _entry(scope_type, scope_code, scope_name, alias, source):
    return {
        "scope_type": scope_type,
        "scope_code": scope_code,
        "scope_name": scope_name,
        "alias": alias,
        "normalized_alias": alias.casefold(),
        "source": source,
        "as_of_date": "2026-07-13",
        "snapshot_id": f"{source}-snapshot",
    }


def test_runtime_resolution_prefers_semantic_type_and_source():
    catalog = ExternalScopeRuntimeCatalog(
        (
            _entry("industry", "BK1", "银行", "银行", "eastmoney"),
            _entry("index", "932133", "银行行业", "银行", "csindex"),
            _entry("index", "000300", "沪深300", "沪深300指数", "csindex"),
        ),
        membership_resource_id="external_scope_membership",
    )

    assert catalog.resolve("银行").option.scope_code == "BK1"
    assert catalog.resolve("沪深300指数").option.scope_code == "000300"


def test_external_data_policy_requires_versioned_industry_and_rule_sources():
    policy = ExternalDataPolicy.from_dict(
        {
            "schema_version": 1,
            "industry": {
                "resource_id": "external_industry_membership",
                "snapshot_id": "industry-snapshot",
                "source": "provider",
                "as_of_date": "2026-07-13",
                "classification_system": "provider industry",
                "industry_level": "provider",
            },
            "instrument_rule": {
                "resource_id": "external_instrument_rule",
                "snapshot_id": "rule-snapshot",
                "source": "exchange",
                "as_of_date": "2026-07-13",
            },
        }
    )

    assert policy.industry.classification_system == "provider industry"
    assert policy.instrument_rule.snapshot_id == "rule-snapshot"

    with pytest.raises(ExternalScopeRuntimeError):
        ExternalDataPolicy.from_dict({"schema_version": 1})


def test_benchmark_policy_requires_one_explicit_context_match():
    catalog = BenchmarkPolicyCatalog.from_dict(
        {
            "schema_version": 1,
            "resource_id": "external_index_quote",
            "entries": [
                {
                    "alias": "大盘",
                    "normalized_alias": "大盘",
                    "market": "",
                    "index_code": "000300",
                    "index_name": "沪深300",
                    "policy_id": "a-share-v1",
                    "source": "business-policy",
                    "effective_from": "2005-04-08",
                    "rationale_url": "https://example.test/benchmark",
                },
                {
                    "alias": "大盘",
                    "normalized_alias": "大盘",
                    "market": "沪",
                    "index_code": "000001",
                    "index_name": "上证指数",
                    "policy_id": "sse-v1",
                    "source": "business-policy",
                    "effective_from": "1991-07-15",
                    "rationale_url": "https://example.test/benchmark",
                },
            ],
        }
    )

    assert catalog.resolve("大盘").index_code == "000300"
    assert catalog.resolve("大盘", "沪").index_code == "000001"
    with pytest.raises(KeyError):
        catalog.resolve("未知基准")


def test_default_runtime_resolves_versioned_scope_policy_casefold_and_provenance():
    catalog = default_external_scope_catalog()

    upper = catalog.resolve("S板")
    lower = catalog.resolve("s板")

    assert upper.option.scope_code == lower.option.scope_code
    assert upper.option.snapshot_id.startswith("curated-scope-alias-2026-08-01-")
    assert upper.policy is not None
    assert upper.policy.policy_id == "exchange-s-board-name-rule-v1"

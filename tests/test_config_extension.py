from findsl import Compiler
from findsl.registry import Registry, default_registry


def test_new_indicator_compiles_from_registry_metadata_only():
    base = default_registry()
    registry = Registry(
        indicators={
            **base.indicators,
            "alpha_score": {
                "type": "numeric",
                "table": "daily_quote",
                "column": "alpha_score",
                "adjustment": "none",
                "supports_prefix_sum": False,
            },
        },
        tables=base.tables,
        functions=base.functions,
    )

    result = Compiler(registry=registry).compile('filter(indicator("alpha_score") > 0)')

    assert "alpha_score > 0" in result.sql
    assert any(step["rule"] == "DORIS_SQL_VALIDATION" for step in result.explain)


def test_indicator_lookup_is_case_insensitive_after_exact_match():
    registry = default_registry()

    assert registry.indicator("Close") == registry.indicator("close")
    assert registry.indicator("MAIN_NET_INFLOW") == registry.indicator("main_net_inflow")

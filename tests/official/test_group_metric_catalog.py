from pathlib import Path

import pytest

from findsl.official.group_metric_catalog import (
    GroupMetricCatalogError,
    GroupMetricPolicyCatalog,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_group_metric_catalog_is_machine_readable_and_conservative() -> None:
    catalog = GroupMetricPolicyCatalog.load(
        REPO_ROOT / "configs/official/group_metric_policies.json"
    )

    volume = catalog.metric("成交量", ("industry", "concept"))
    assert volume.default_aggregation == "sum"
    assert volume.null_policy == "ignore"
    assert catalog.combined_target(("board",)).scope_types == (
        "concept",
        "industry",
    )


def test_group_metric_catalog_does_not_invent_price_or_turnover_policies() -> None:
    catalog = GroupMetricPolicyCatalog.load(
        REPO_ROOT / "configs/official/group_metric_policies.json"
    )

    for indicator in ("收盘价", "最新价", "换手率"):
        with pytest.raises(GroupMetricCatalogError):
            catalog.metric(indicator, ("industry",))


def test_group_return_policy_is_explicitly_float_cap_weighted() -> None:
    catalog = GroupMetricPolicyCatalog.load(
        REPO_ROOT / "configs/official/group_metric_policies.json"
    )

    policy = catalog.metric("涨跌幅", ("industry",))
    assert policy.default_aggregation == "float_market_cap_weighted_return"

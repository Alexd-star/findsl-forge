from decimal import Decimal
from pathlib import Path

from findsl.official.adjustment import (
    AdjustmentPolicy,
    adjusted_price,
    load_adjustment_fixture,
    render_adjustment_fixture_sql,
)


def test_nontrivial_adjustment_policy_is_configured_and_deterministic():
    policy = AdjustmentPolicy.load(Path("configs/official/adjustment_validation_policy.json"))
    fixture = load_adjustment_fixture(Path("data/official_correctness/adjustment_policy_fixture.json"))

    actual = {
        item["case_id"]: adjusted_price(
            policy,
            asset_class=item["asset_class"],
            raw_price=Decimal(item["raw_price"]),
            multiplier=Decimal(item["multiplier"]),
            additive=Decimal(item["additive"]),
        )
        for item in fixture
    }
    assert actual["STOCK-FORWARD-01"] == Decimal("11.500000")
    assert actual["STOCK-FORWARD-02"] == Decimal("16.000000")
    assert actual["INDEX-UNCHANGED-01"] == Decimal("10.000000")
    assert "raw_price*multiplier+additive" in render_adjustment_fixture_sql(policy, fixture)

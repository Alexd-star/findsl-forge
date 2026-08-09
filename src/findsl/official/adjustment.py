from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Tuple


class AdjustmentPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class AdjustmentPolicy:
    policy_id: str
    stock_mode: str
    index_mode: str

    @classmethod
    def load(cls, path: Path) -> "AdjustmentPolicy":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        expected = {"schema_version", "policy_id", "stock_mode", "index_mode", "formula"}
        if set(raw) != expected or raw["schema_version"] != 1:
            raise AdjustmentPolicyError("invalid adjustment validation policy")
        if raw["stock_mode"] != "forward_adjusted":
            raise AdjustmentPolicyError("validation policy must exercise forward-adjusted stock prices")
        if raw["index_mode"] != "unadjusted":
            raise AdjustmentPolicyError("index price policy must remain unadjusted")
        formula = raw["formula"]
        if formula != "raw_price * multiplier + additive":
            raise AdjustmentPolicyError("unsupported forward-adjustment formula")
        return cls(str(raw["policy_id"]), str(raw["stock_mode"]), str(raw["index_mode"]))


def adjusted_price(
    policy: AdjustmentPolicy,
    *,
    asset_class: str,
    raw_price: Decimal,
    multiplier: Decimal,
    additive: Decimal,
) -> Decimal:
    if asset_class == "stock":
        return raw_price * multiplier + additive
    if asset_class == "index":
        return raw_price
    raise AdjustmentPolicyError(f"unsupported asset_class: {asset_class}")


def load_adjustment_fixture(path: Path) -> Tuple[Mapping[str, Any], ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise AdjustmentPolicyError("adjustment fixture must be a non-empty array")
    return tuple(raw)


def render_adjustment_fixture_sql(
    policy: AdjustmentPolicy, fixture: Tuple[Mapping[str, Any], ...]
) -> str:
    rows = []
    for item in fixture:
        rows.append(
            "SELECT "
            f"'{_literal(item['case_id'])}' AS case_id,"
            f"'{_literal(item['asset_class'])}' AS asset_class,"
            f"CAST({item['raw_price']} AS DECIMAL(18,6)) AS raw_price,"
            f"CAST({item['multiplier']} AS DECIMAL(18,6)) AS multiplier,"
            f"CAST({item['additive']} AS DECIMAL(18,6)) AS additive"
        )
    fixture_sql = " UNION ALL ".join(rows)
    return (
        f"WITH fixture AS ({fixture_sql}) "
        "SELECT case_id,CASE WHEN asset_class='stock' THEN raw_price*multiplier+additive "
        "WHEN asset_class='index' THEN raw_price ELSE NULL END AS adjusted_price "
        f"FROM fixture ORDER BY case_id /* policy:{policy.policy_id} */"
    )


def _literal(value: Any) -> str:
    return str(value).replace("'", "''")

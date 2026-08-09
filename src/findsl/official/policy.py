from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Tuple


class CompileMode(str, Enum):
    STRICT = "strict"
    RECOVERY = "recovery"

    @classmethod
    def parse(cls, value: str) -> "CompileMode":
        try:
            return cls(str(value).lower())
        except ValueError as exc:
            raise ValueError(f"Unsupported official compile mode: {value}") from exc


class SemanticPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class RankingPolicy:
    method: str
    tie_breakers: Tuple[str, ...]
    metric_null_order: str
    rationale: str


@dataclass(frozen=True)
class PriceAdjustmentPolicy:
    stock_mode: str
    index_mode: str
    missing_factor_behavior: str
    rationale: str


@dataclass(frozen=True)
class SemanticPolicySet:
    policy_id: str
    profile: str
    ranking: RankingPolicy
    price_adjustment: PriceAdjustmentPolicy
    nulls: Mapping[str, str]
    time: Mapping[str, str]
    provisional_items: Tuple[str, ...]

    @classmethod
    def load(cls, path: Path) -> "SemanticPolicySet":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "SemanticPolicySet":
        expected = {
            "schema_version",
            "policy_id",
            "profile",
            "ranking",
            "price_adjustment",
            "nulls",
            "time",
            "provisional_items",
        }
        if set(raw) != expected or raw.get("schema_version") != 1:
            raise SemanticPolicyError("invalid semantic policy root")
        ranking = raw["ranking"]
        if set(ranking) != {"method", "tie_breakers", "metric_null_order", "rationale"}:
            raise SemanticPolicyError("invalid ranking policy")
        if ranking["method"] not in {"row_number", "rank", "dense_rank"}:
            raise SemanticPolicyError("unsupported ranking method")
        if ranking["metric_null_order"] not in {"engine_default", "first", "last", "exclude"}:
            raise SemanticPolicyError("unsupported ranking NULL order")
        ties = tuple(str(item) for item in ranking["tie_breakers"])
        if not ties or len(set(ties)) != len(ties):
            raise SemanticPolicyError("ranking tie breakers must be unique and non-empty")
        adjustment = raw["price_adjustment"]
        if set(adjustment) != {
            "stock_mode",
            "index_mode",
            "missing_factor_behavior",
            "rationale",
        }:
            raise SemanticPolicyError("invalid price adjustment policy")
        if adjustment["index_mode"] != "unadjusted":
            raise SemanticPolicyError("index price policy must remain unadjusted")
        for section in ("nulls", "time"):
            if not isinstance(raw[section], dict) or not raw[section]:
                raise SemanticPolicyError(f"{section} policy cannot be empty")
        provisional = tuple(str(item) for item in raw["provisional_items"])
        return cls(
            policy_id=str(raw["policy_id"]),
            profile=str(raw["profile"]),
            ranking=RankingPolicy(
                str(ranking["method"]),
                ties,
                str(ranking["metric_null_order"]),
                str(ranking["rationale"]),
            ),
            price_adjustment=PriceAdjustmentPolicy(
                str(adjustment["stock_mode"]),
                str(adjustment["index_mode"]),
                str(adjustment["missing_factor_behavior"]),
                str(adjustment["rationale"]),
            ),
            nulls=dict(raw["nulls"]),
            time=dict(raw["time"]),
            provisional_items=provisional,
        )

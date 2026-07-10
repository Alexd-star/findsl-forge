from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping, Tuple


ResultKind = Literal["dynamic", "numeric", "boolean", "string"]


@dataclass(frozen=True)
class FunctionSignature:
    name: str
    slots: Tuple[str, ...]
    result_kind: ResultKind

    @property
    def arity(self) -> int:
        return len(self.slots)


_SIGNATURES = (
    FunctionSignature(
        name="indicator",
        slots=(
            "market",
            "filter_scope",
            "indicator_name",
            "date",
            "select_type",
            "agg_func",
            "count_exp",
        ),
        result_kind="dynamic",
    ),
    FunctionSignature(
        name="rank",
        slots=(
            "market",
            "filter_scope",
            "indicator_name",
            "direction",
            "date",
            "select_type",
            "agg_func",
            "count_exp",
        ),
        result_kind="numeric",
    ),
    FunctionSignature(
        name="belong_industry",
        slots=("market", "filter_scope", "indicator_name", "date", "agg_func"),
        result_kind="dynamic",
    ),
    FunctionSignature(
        name="queryData",
        slots=("market", "keywords", "indicator_name", "date", "agg_func"),
        result_kind="dynamic",
    ),
    FunctionSignature(
        name="cross_above",
        slots=(
            "market",
            "filter_scope",
            "indicator_name_1",
            "indicator_name_2",
            "date",
            "select_type",
            "count_exp",
        ),
        result_kind="boolean",
    ),
    FunctionSignature(
        name="cross_down",
        slots=(
            "market",
            "filter_scope",
            "indicator_name_1",
            "indicator_name_2",
            "date",
            "select_type",
            "count_exp",
        ),
        result_kind="boolean",
    ),
    FunctionSignature(
        name="close_together",
        slots=(
            "market",
            "filter_scope",
            "indicator_name_1",
            "indicator_name_2",
            "date",
            "select_type",
            "count_exp",
        ),
        result_kind="boolean",
    ),
    FunctionSignature(
        name="reset",
        slots=(
            "market",
            "filter_scope",
            "indicator_name_1",
            "indicator_name_2",
            "date",
            "select_type",
            "count_exp",
        ),
        result_kind="boolean",
    ),
    FunctionSignature(
        name="golden_cross",
        slots=(
            "market",
            "filter_scope",
            "indicator_name_1",
            "indicator_name_2",
            "date",
            "select_type",
            "count_exp",
        ),
        result_kind="boolean",
    ),
    FunctionSignature(
        name="record_high",
        slots=(
            "market",
            "filter_scope",
            "indicator_name",
            "period",
            "date",
            "select_type",
            "agg_func",
            "count_exp",
        ),
        result_kind="boolean",
    ),
    FunctionSignature(
        name="record_low",
        slots=(
            "market",
            "filter_scope",
            "indicator_name",
            "period",
            "date",
            "select_type",
            "agg_func",
            "count_exp",
        ),
        result_kind="boolean",
    ),
    FunctionSignature(
        name="position",
        slots=(
            "market",
            "filter_scope",
            "indicator_name",
            "period",
            "date",
            "select_type",
            "agg_func",
            "count_exp",
        ),
        result_kind="string",
    ),
)


OFFICIAL_FUNCTION_SIGNATURES: Mapping[str, FunctionSignature] = MappingProxyType(
    {signature.name: signature for signature in _SIGNATURES}
)

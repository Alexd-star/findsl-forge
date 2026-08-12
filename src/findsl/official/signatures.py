from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Literal, Mapping, Optional, Tuple

from .template_language import FunctionTemplateError, validate_expression_template


ResultKind = Literal["dynamic", "numeric", "boolean", "string"]


@dataclass(frozen=True)
class FunctionSignature:
    name: str
    slots: Tuple[str, ...]
    result_kind: ResultKind
    argument_mode: str = "slot_literals"
    arg_types: Tuple[str, ...] = ()
    expression_template: Optional[Mapping[str, Any]] = None
    version: str = "builtin"

    @property
    def arity(self) -> int:
        return len(self.arg_types) if self.argument_mode == "expressions" else len(self.slots)


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


class FunctionCatalogError(ValueError):
    pass


class OfficialFunctionCatalog:
    def __init__(self, configured: Tuple[Tuple[FunctionSignature, Tuple[str, ...]], ...] = ()):
        index: Dict[str, FunctionSignature] = {}
        for signature in _SIGNATURES:
            index[signature.name.casefold()] = signature
        for signature, aliases in configured:
            for name in (signature.name, *aliases):
                key = name.casefold()
                if key in index:
                    raise FunctionCatalogError(f"duplicate function name or alias: {name}")
                index[key] = signature
        self._index = MappingProxyType(index)
        self._configured = tuple(signature for signature, _ in configured)

    def resolve(self, name: str) -> Optional[FunctionSignature]:
        return self._index.get(str(name).casefold())

    @property
    def configured(self) -> Tuple[FunctionSignature, ...]:
        return self._configured

    @classmethod
    def load(cls, path: Path) -> "OfficialFunctionCatalog":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if set(raw) != {"schema_version", "functions"} or raw.get("schema_version") != 1:
            raise FunctionCatalogError("invalid official function catalog root")
        configured = tuple(_configured_function(item, index) for index, item in enumerate(raw["functions"]))
        return cls(configured)


def _configured_function(raw, index):
    expected = {
        "name", "aliases", "argument_mode", "arg_types", "result_kind",
        "expression_template", "version",
    }
    if not isinstance(raw, dict) or set(raw) != expected:
        raise FunctionCatalogError(f"invalid configured function fields at index {index}")
    name = str(raw["name"])
    aliases = tuple(str(item) for item in raw["aliases"])
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or any(
        not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", alias) for alias in aliases
    ):
        raise FunctionCatalogError(f"invalid configured function identifier: {name}")
    arg_types = tuple(str(item) for item in raw["arg_types"])
    if raw["argument_mode"] != "expressions" or not 1 <= len(arg_types) <= 8:
        raise FunctionCatalogError(f"unsupported configured function argument mode: {name}")
    if any(item not in {"numeric", "boolean", "string"} for item in arg_types):
        raise FunctionCatalogError(f"unsupported configured function argument type: {name}")
    result_kind = str(raw["result_kind"])
    if result_kind not in {"numeric", "boolean", "string"}:
        raise FunctionCatalogError(f"unsupported configured function result kind: {name}")
    try:
        expression_template = validate_expression_template(
            raw["expression_template"],
            arg_types=arg_types,
            result_kind=result_kind,
        )
    except FunctionTemplateError as exc:
        raise FunctionCatalogError(f"invalid function template {name}: {exc}") from exc
    signature = FunctionSignature(
        name=name,
        slots=(),
        result_kind=result_kind,
        argument_mode="expressions",
        arg_types=arg_types,
        expression_template=expression_template,
        version=str(raw["version"]),
    )
    return signature, aliases


DEFAULT_OFFICIAL_FUNCTION_CATALOG = OfficialFunctionCatalog()
OFFICIAL_FUNCTION_SIGNATURES: Mapping[str, FunctionSignature] = MappingProxyType(
    {signature.name: signature for signature in _SIGNATURES}
)

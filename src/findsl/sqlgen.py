from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .ast_nodes import BinaryOp, Comparison, FunctionCall, Identifier, Literal, Node
from .errors import SemanticError
from .explain import ExplainStep
from .registry import Registry


@dataclass
class SqlPlan:
    sql: str
    trace: List[str] = field(default_factory=list)
    explain: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Feature:
    alias: str
    expression: str
    joins: List[str] = field(default_factory=list)


class SqlGenerator:
    def __init__(self, registry: Registry, enable_prefix_sum: bool = True):
        self.registry = registry
        self.enable_prefix_sum = enable_prefix_sum
        self.required_tables: Set[str] = set()
        self.trace: List[str] = []
        self.explain: List[ExplainStep] = []
        self._feature_counter = 0
        self._current_source: Optional[str] = None
        self._numeric_features: List[Feature] = []
        self._rolling_features: List[Feature] = []

    def generate(self, node: Node) -> SqlPlan:
        self.required_tables = self._collect_tables(node)
        self.trace = []
        self.explain = []
        self._feature_counter = 0
        sql = self._relation_sql(node)
        return SqlPlan(sql=_format_sql(sql), trace=list(self.trace), explain=[step.to_dict() for step in self.explain])

    def _collect_tables(self, node: Node) -> Set[str]:
        tables: Set[str] = set()

        def visit(current: Node) -> None:
            if isinstance(current, FunctionCall):
                if current.name.upper() == "INDICATOR":
                    indicator_name = self._symbol_arg(current.args[0], "indicator")
                    tables.add(self.registry.indicator(indicator_name)["table"])
                elif current.name.upper() == "MARKET":
                    tables.add("stock_universe")
                for arg in current.args:
                    visit(arg)
                for named in current.named_args or []:
                    visit(named.value)
                return
            if isinstance(current, (BinaryOp, Comparison)):
                visit(current.left)
                visit(current.right)

        visit(node)
        tables.add("daily_quote")
        return tables

    def _relation_sql(self, node: Node) -> str:
        if isinstance(node, FunctionCall) and node.name.lower() == "then":
            return self._then_sql(node)
        if isinstance(node, FunctionCall) and node.name.lower() == "filter":
            return self._filter_sql(node.args[0])
        if isinstance(node, FunctionCall) and node.name.lower() == "rank":
            return self._rank_sql(node, base_relation=None)
        return self._filter_sql(node)

    def _then_sql(self, node: FunctionCall) -> str:
        self.trace.append("rewrite then() into staged CTE pipeline")
        self._explain(
            "THEN_PIPELINE",
            "applied",
            "Rewrite then() into staged CTE pipeline",
            stage_count=len(node.args),
        )
        ctes = []
        current_name = None
        for idx, stage in enumerate(node.args, 1):
            cte_name = f"stage{idx}"
            if isinstance(stage, FunctionCall) and stage.name.lower() == "filter":
                ctes.append(f"{cte_name} AS ({self._filter_sql(stage.args[0], source=current_name)})")
            elif isinstance(stage, FunctionCall) and stage.name.lower() == "rank":
                ctes.append(f"{cte_name} AS ({self._rank_sql(stage, base_relation=current_name)})")
            else:
                raise SemanticError("then() stages currently support filter() and rank()")
            current_name = cte_name
        return "WITH " + ", ".join(ctes) + f" SELECT * FROM {current_name}"

    def _filter_sql(self, condition_node: Node, source: str = None) -> str:
        old_source = self._current_source
        old_numeric = self._numeric_features
        old_rolling = self._rolling_features
        self._current_source = source
        self._numeric_features = []
        self._rolling_features = []
        try:
            condition = self._bool_sql(condition_node)
            from_clause = self._from_clause(source)
            pushdown_kind = self._date_pushdown_kind(condition_node)
            base_predicates = self._base_date_pushdown_predicates(condition_node, pushdown_kind)
            base_where = f" WHERE {' AND '.join(base_predicates)}" if base_predicates else ""
            if base_predicates:
                if pushdown_kind == "upper_bound":
                    self.trace.append("push safe date upper bound into base scan for window context")
                    self._explain(
                        "DATE_RANGE_WINDOW_PRUNING",
                        "applied",
                        "Push safe date upper bound into base scan without truncating window history",
                        predicate_count=len(base_predicates),
                        source=source or "physical_base",
                    )
                elif pushdown_kind == "prefix_full_range":
                    self.trace.append("push full date range into prefix-sum base scan")
                    self._explain(
                        "DATE_RANGE_PREFIX_PRUNING",
                        "applied",
                        "Push full date range into prefix-sum base scan because prefix lookup preserves history",
                        predicate_count=len(base_predicates),
                        source=source or "physical_base",
                    )
                else:
                    self.trace.append("push safe date range predicate into base scan")
                    self._explain(
                        "DATE_RANGE_BASE_PRUNING",
                        "applied",
                        "Push safe date range predicate into base scan",
                        predicate_count=len(base_predicates),
                        source=source or "physical_base",
                    )
            layer_sql = f"SELECT {self._project_columns()} FROM {from_clause}{base_where}"
            layer_name = "base_features"

            if self._numeric_features:
                self.trace.append("materialize numeric window features before filtering")
                self._explain(
                    "FEATURE_LAYER",
                    "applied",
                    "Materialize numeric features before filtering",
                    feature_count=len(self._numeric_features),
                )
                for idx, feature in enumerate(self._numeric_features, 1):
                    layer_sql = self._feature_layer_sql(layer_sql, layer_name, [feature])
                    layer_name = f"numeric_features_{idx}"
            if self._rolling_features:
                self.trace.append("materialize rolling boolean features after numeric features")
                self._explain(
                    "FEATURE_LAYER",
                    "applied",
                    "Materialize rolling boolean features after numeric features",
                    feature_count=len(self._rolling_features),
                )
                for idx, feature in enumerate(self._rolling_features, 1):
                    layer_sql = self._feature_layer_sql(layer_sql, layer_name, [feature])
                    layer_name = f"rolling_features_{idx}"

            self.trace.append("rewrite filter predicate into outer WHERE over materialized features")
            self._explain(
                "FILTER_OUTER_WHERE",
                "applied",
                "Rewrite filter predicate into outer WHERE over materialized features",
                condition=condition,
            )
            return f"SELECT * FROM ({layer_sql}) {layer_name} WHERE {condition}"
        finally:
            self._current_source = old_source
            self._numeric_features = old_numeric
            self._rolling_features = old_rolling

    def _feature_layer_sql(self, inner_sql: str, inner_alias: str, features: List[Feature]) -> str:
        feature_sql = ", ".join(
            f"{feature.expression.format(source=inner_alias)} AS {feature.alias}" for feature in features
        )
        joins = " ".join(
            join.format(source=inner_alias) for feature in features for join in feature.joins
        )
        join_sql = f" {joins}" if joins else ""
        return f"SELECT {inner_alias}.*, {feature_sql} FROM ({inner_sql}) {inner_alias}{join_sql}"

    def _date_pushdown_kind(self, node: Node) -> str:
        if self._requires_window_history(node):
            return "upper_bound"
        if self._contains_prefix_sum_window(node):
            return "prefix_full_range"
        return "full_range"

    def _base_date_pushdown_predicates(self, node: Node, pushdown_kind: str) -> List[str]:
        if pushdown_kind == "upper_bound":
            return self._collect_and_date_upper_bound_predicates(node)
        return self._collect_and_date_predicates(node)

    def _requires_window_history(self, node: Node) -> bool:
        if isinstance(node, FunctionCall):
            name = node.name.upper()
            if name in {"MA", "MAX", "MIN", "CONS", "EXIST"}:
                return True
            if name == "SUM" and not self._sum_can_use_prefix_lookup(node):
                return True
            return any(self._requires_window_history(arg) for arg in node.args) or any(
                self._requires_window_history(named.value) for named in node.named_args or []
            )
        if isinstance(node, (BinaryOp, Comparison)):
            return self._requires_window_history(node.left) or self._requires_window_history(node.right)
        return False

    def _contains_prefix_sum_window(self, node: Node) -> bool:
        if isinstance(node, FunctionCall):
            if node.name.upper() == "SUM" and self._sum_can_use_prefix_lookup(node):
                return True
            return any(self._contains_prefix_sum_window(arg) for arg in node.args) or any(
                self._contains_prefix_sum_window(named.value) for named in node.named_args or []
            )
        if isinstance(node, (BinaryOp, Comparison)):
            return self._contains_prefix_sum_window(node.left) or self._contains_prefix_sum_window(node.right)
        return False

    def _sum_can_use_prefix_lookup(self, node: FunctionCall) -> bool:
        if not self.enable_prefix_sum or self._current_source:
            return False
        if len(node.args) < 2:
            return False
        indicator_call = node.args[0]
        if not isinstance(indicator_call, FunctionCall) or indicator_call.name.upper() != "INDICATOR":
            return False
        indicator_name = self._symbol_arg(indicator_call.args[0], "indicator")
        return bool(self.registry.indicator(indicator_name).get("supports_prefix_sum"))

    def _collect_and_date_predicates(self, node: Node) -> List[str]:
        if isinstance(node, FunctionCall) and node.name.upper() == "DATE_BETWEEN":
            return [self._date_between_predicate(node)]
        if isinstance(node, BinaryOp) and node.op == "&":
            return self._collect_and_date_predicates(node.left) + self._collect_and_date_predicates(node.right)
        return []

    def _collect_and_date_upper_bound_predicates(self, node: Node) -> List[str]:
        if isinstance(node, FunctionCall) and node.name.upper() == "DATE_BETWEEN":
            return [self._date_between_upper_bound_predicate(node)]
        if isinstance(node, BinaryOp) and node.op == "&":
            return (
                self._collect_and_date_upper_bound_predicates(node.left)
                + self._collect_and_date_upper_bound_predicates(node.right)
            )
        return []

    def _rank_sql(self, node: FunctionCall, base_relation: str = None) -> str:
        old_source = self._current_source
        old_numeric = self._numeric_features
        old_rolling = self._rolling_features
        self._current_source = base_relation
        self._numeric_features = []
        self._rolling_features = []
        try:
            expr_sql = self._numeric_sql(node.args[0])
            rank_source = self._rank_source_sql(base_relation)
            order_node = node.args[1]
            if not isinstance(order_node, Identifier) or order_node.name.lower() not in {"asc", "desc"}:
                raise SemanticError("rank() second argument must be asc or desc")
            order = order_node.name.upper()
            limit = self._rank_limit(node)
            rank_source = self._rank_count_source_sql(self._rank_source_sql(base_relation), limit)
            self.trace.append("rewrite rank() into ROW_NUMBER window")
            self._explain(
                "RANK_ROW_NUMBER",
                "applied",
                "Rewrite rank() into ROW_NUMBER window",
                source=base_relation or "base_relation",
                limit_kind=limit["kind"] or "none",
                limit_value=limit["value"],
            )
            non_null_guard = self._rank_non_null_guard(expr_sql, limit)
            where = self._rank_where(limit)
            return (
                "SELECT * FROM ("
                f"SELECT base.*, ROW_NUMBER() OVER (PARTITION BY trade_date ORDER BY {expr_sql} {order}, ts_code ASC) AS rank_no"
                f" FROM {rank_source}{non_null_guard}"
                f") ranked{where}"
            )
        finally:
            self._current_source = old_source
            self._numeric_features = old_numeric
            self._rolling_features = old_rolling

    def _rank_count_source_sql(self, rank_source: str, limit: Dict[str, Any]) -> str:
        if limit["kind"] != "percent":
            return rank_source
        return f"(SELECT base.*, COUNT(*) OVER (PARTITION BY trade_date) AS __partition_count FROM {rank_source}) base"

    def _rank_non_null_guard(self, expr_sql: str, limit: Dict[str, Any]) -> str:
        if not limit["kind"]:
            return ""
        self.trace.append("exclude null rank expressions before applying rank cutoff")
        self._explain(
            "RANK_NULL_GUARD",
            "applied",
            "Exclude null rank expressions before applying rank cutoff",
            limit_kind=limit["kind"],
        )
        return f" WHERE {expr_sql} IS NOT NULL"

    def _rank_source_sql(self, base_relation: str = None) -> str:
        source = self._from_clause(base_relation)
        if not self._numeric_features:
            if base_relation is not None:
                self.trace.append("project staged relation columns before re-ranking")
                self._explain(
                    "RELATION_PROJECTION",
                    "applied",
                    "Project staged relation columns before re-ranking",
                    source=base_relation,
                )
                return f"(SELECT {self._stage_relation_projection_columns()} FROM {source}) AS base"
            if base_relation is None and len(self._ordered_tables()) > 1:
                self.trace.append("project joined relation columns before ranking")
                self._explain(
                    "RELATION_PROJECTION",
                    "applied",
                    "Project joined relation columns before ranking",
                    table_count=len(self._ordered_tables()),
                )
                return f"(SELECT {self._project_columns()} FROM {source}) AS base"
            return source
        self.trace.append("materialize rank numeric features before ranking")
        self._explain(
            "FEATURE_LAYER",
            "applied",
            "Materialize rank numeric features before ranking",
            feature_count=len(self._numeric_features),
        )
        projection = (
            self._stage_relation_projection_columns()
            if base_relation is not None
            else self._project_columns()
        )
        layer_sql = f"SELECT {projection} FROM {source}"
        layer_name = "rank_base_features"
        for idx, feature in enumerate(self._numeric_features, 1):
            layer_sql = self._feature_layer_sql(layer_sql, layer_name, [feature])
            layer_name = f"rank_numeric_features_{idx}"
        return f"({layer_sql}) AS base"

    def _rank_limit(self, node: FunctionCall) -> Dict[str, Any]:
        for named in node.named_args or []:
            arg_name = named.name.lower()
            if arg_name == "top" and isinstance(named.value, Literal):
                return {"kind": "top", "value": int(named.value.value)}
            if arg_name == "bottom" and isinstance(named.value, Literal):
                return {"kind": "bottom", "value": int(named.value.value)}
            if arg_name == "percent" and isinstance(named.value, Literal):
                return {"kind": "percent", "value": float(named.value.value)}
        return {"kind": None, "value": None}

    def _rank_where(self, limit: Dict[str, Any]) -> str:
        if limit["kind"] in {"top", "bottom"}:
            return f" WHERE rank_no <= {int(limit['value'])}"
        if limit["kind"] == "percent":
            value = _format_number(float(limit["value"]))
            threshold = f"CAST(((__partition_count * {value}) + 99.999999) / 100.0 AS INTEGER)"
            return f" WHERE rank_no <= {threshold}"
        return ""

    def _from_clause(self, source: str = None) -> str:
        if source:
            return f"{source} AS base"
        return self._base_from_clause()

    def _base_from_clause(self) -> str:
        ordered = self._ordered_tables()
        base_meta = self.registry.table(ordered[0])
        base = f"{base_meta['physical']} AS base"
        joins = []
        for table_name in ordered[1:]:
            meta = self.registry.table(table_name)
            alias = meta.get("alias", table_name)
            joins.append(f" LEFT JOIN {meta['physical']} AS {alias} USING (ts_code, trade_date)")
        return base + "".join(joins)

    def _ordered_tables(self) -> List[str]:
        ordered = sorted(self.required_tables)
        if "daily_quote" in ordered:
            ordered.remove("daily_quote")
            ordered.insert(0, "daily_quote")
        return ordered or ["daily_quote"]

    def _project_columns(self) -> str:
        if self._current_source:
            return "base.*"
        columns = ["base.*"]
        for table_name in self._ordered_tables()[1:]:
            alias = self.registry.table(table_name).get("alias", table_name)
            if table_name == "stock_universe":
                columns.append(f"{alias}.market AS market")
            for indicator_name, meta in self.registry.indicators.items():
                if meta["table"] == table_name:
                    columns.append(f"{alias}.{meta['column']} AS {meta['column']}")
        return ", ".join(dict.fromkeys(columns))

    def _stage_relation_projection_columns(self) -> str:
        columns = ["base.ts_code AS ts_code", "base.trade_date AS trade_date"]
        for table_name in self._ordered_tables():
            if table_name == "stock_universe":
                columns.append("base.market AS market")
                continue
            for indicator_name, meta in self.registry.indicators.items():
                if meta["table"] == table_name:
                    column = meta["column"]
                    columns.append(f"base.{column} AS {column}")
        return ", ".join(dict.fromkeys(columns))

    def _bool_sql(self, node: Node) -> str:
        if isinstance(node, Comparison):
            return f"{self._numeric_sql(node.left)} {_sql_comparison_operator(node.op)} {self._numeric_sql(node.right)}"
        if isinstance(node, BinaryOp) and node.op in {"&", "|"}:
            op = "AND" if node.op == "&" else "OR"
            return f"({self._bool_sql(node.left)} {op} {self._bool_sql(node.right)})"
        if isinstance(node, FunctionCall):
            name = node.name.upper()
            if name == "MARKET":
                return self._market_sql(node)
            if name == "DATE_BETWEEN":
                return self._date_between_sql(node)
            if name == "CONS":
                cond = self._bool_sql(node.args[0])
                window = self._window_value(node.args[1])
                alias = self._register_rolling_feature(
                    "CONS",
                    "SUM(CASE WHEN "
                    + cond
                    + " THEN 1 ELSE 0 END) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN "
                    + f"{window - 1} PRECEDING AND CURRENT ROW)",
                )
                return f"{alias} = {window}"
            if name == "EXIST":
                cond = self._bool_sql(node.args[0])
                window = self._window_value(node.args[1])
                alias = self._register_rolling_feature(
                    "EXIST",
                    "MAX(CASE WHEN "
                    + cond
                    + " THEN 1 ELSE 0 END) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN "
                    + f"{window - 1} PRECEDING AND CURRENT ROW)",
                )
                return f"{alias} = 1"
        raise SemanticError(f"Expected boolean expression, got {node!r}")

    def _numeric_sql(self, node: Node) -> str:
        if isinstance(node, Literal):
            if isinstance(node.value, str):
                return _sql_string_literal(node.value)
            return str(node.value)
        if isinstance(node, Identifier):
            return node.name
        if isinstance(node, BinaryOp) and node.op in {"+", "-", "*", "/"}:
            return f"({self._numeric_sql(node.left)} {node.op} {self._numeric_sql(node.right)})"
        if isinstance(node, FunctionCall):
            name = node.name.upper()
            if name == "INDICATOR":
                return self._indicator_sql(node)
            if name in {"MA", "SUM", "MAX", "MIN"}:
                return self._register_numeric_window(node)
        raise SemanticError(f"Expected numeric expression, got {node!r}")

    def _indicator_sql(self, node: FunctionCall) -> str:
        indicator_name = self._symbol_arg(node.args[0], "indicator")
        meta = self.registry.indicator(indicator_name)
        self.required_tables.add(meta["table"])
        if self._current_source:
            return meta["column"]
        return meta["column"]

    def _market_sql(self, node: FunctionCall) -> str:
        market_name = self._symbol_arg(node.args[0], "market")
        self.required_tables.add("stock_universe")
        market_literal = _sql_string_literal(market_name)
        if self._current_source:
            return f"market = {market_literal}"
        return f"market = {market_literal}"

    def _date_between_sql(self, node: FunctionCall) -> str:
        predicate = self._date_between_predicate(node)
        start = self._date_arg(node.args[0], "date_between")
        end = self._date_arg(node.args[1], "date_between")
        self.trace.append("rewrite date_between() into trade_date range predicate")
        self._explain(
            "DATE_RANGE_PUSHDOWN",
            "applied",
            "Rewrite date_between() into trade_date range predicate",
            start_date=start,
            end_date=end,
        )
        return predicate

    def _date_between_predicate(self, node: FunctionCall) -> str:
        start = self._date_arg(node.args[0], "date_between")
        end = self._date_arg(node.args[1], "date_between")
        return f"(trade_date >= {_sql_string_literal(start)} AND trade_date <= {_sql_string_literal(end)})"

    def _date_between_upper_bound_predicate(self, node: FunctionCall) -> str:
        end = self._date_arg(node.args[1], "date_between")
        return f"trade_date <= {_sql_string_literal(end)}"

    def _symbol_arg(self, node: Node, function_name: str) -> str:
        if isinstance(node, Literal) and isinstance(node.value, str):
            return node.value
        if isinstance(node, Identifier):
            return node.name
        raise SemanticError(f"{function_name}() requires a string or identifier argument")

    def _date_arg(self, node: Node, function_name: str) -> str:
        if isinstance(node, Literal) and isinstance(node.value, str):
            return node.value
        raise SemanticError(f"{function_name}() requires ISO date string arguments")

    def _register_numeric_window(self, node: FunctionCall) -> str:
        name = node.name.upper()
        if name == "SUM":
            prefix_alias = self._try_register_prefix_sum(node)
            if prefix_alias:
                return prefix_alias
        expr = self._numeric_sql(node.args[0])
        window = self._window_value(node.args[1])
        sql_name = {"MA": "AVG", "SUM": "SUM", "MAX": "MAX", "MIN": "MIN"}[name]
        alias = self._next_alias("__win")
        self.trace.append(f"rewrite {name}() into {sql_name} window feature {alias}")
        self._explain(
            "WINDOW_FEATURE",
            "applied",
            f"Rewrite {name}() into {sql_name} window feature",
            alias=alias,
            function=name,
            sql_function=sql_name,
            window=window,
        )
        expression = (
            f"{sql_name}({expr}) OVER (PARTITION BY ts_code ORDER BY trade_date "
            f"ROWS BETWEEN {window - 1} PRECEDING AND CURRENT ROW)"
        )
        self._numeric_features.append(Feature(alias=alias, expression=expression))
        return alias

    def _try_register_prefix_sum(self, node: FunctionCall) -> Optional[str]:
        if not self.enable_prefix_sum:
            self._explain(
                "PREFIX_SUM",
                "skipped",
                "Prefix-sum optimizer is disabled",
                reason="disabled",
            )
            return None
        if self._current_source:
            self._explain(
                "PREFIX_SUM",
                "skipped",
                "Prefix-sum optimizer currently applies only to base relations",
                reason="staged_relation",
                source=self._current_source,
            )
            return None
        indicator_call = node.args[0]
        if not isinstance(indicator_call, FunctionCall) or indicator_call.name.upper() != "INDICATOR":
            self._explain(
                "PREFIX_SUM",
                "skipped",
                "Prefix-sum optimizer requires SUM(indicator(...), window)",
                reason="non_indicator_expression",
            )
            return None
        indicator_name = self._symbol_arg(indicator_call.args[0], "indicator")
        meta = self.registry.indicator(indicator_name)
        if not meta.get("supports_prefix_sum"):
            self._explain(
                "PREFIX_SUM",
                "skipped",
                "Indicator does not declare prefix-sum support",
                reason="unsupported_indicator",
                indicator=indicator_name,
            )
            return None

        window = self._window_value(node.args[1])
        prefix_table = self.registry.table(meta["prefix_table"])
        prefix_physical = prefix_table["physical"]
        prefix_column = meta["prefix_column"]
        row_column = prefix_table.get("row_column", "row_no")
        alias = self._next_alias("__psum")
        feature_no = self._feature_counter
        curr = f"__pref_curr_{feature_no}"
        prev = f"__pref_prev_{feature_no}"
        self.trace.append(f"rewrite SUM() on {indicator_name} into prefix-sum feature {alias}")
        self._explain(
            "PREFIX_SUM",
            "applied",
            "Rewrite rolling SUM into prefix table subtraction",
            alias=alias,
            indicator=indicator_name,
            window=window,
            prefix_table=prefix_physical,
            prefix_column=prefix_column,
        )
        joins = [
            (
                f"LEFT JOIN {prefix_physical} AS {curr} "
                f"ON {curr}.ts_code = {{source}}.ts_code AND {curr}.trade_date = {{source}}.trade_date"
            ),
            (
                f"LEFT JOIN {prefix_physical} AS {prev} "
                f"ON {prev}.ts_code = {curr}.ts_code AND {prev}.{row_column} = {curr}.{row_column} - {window}"
            ),
        ]
        expression = f"({curr}.{prefix_column} - COALESCE({prev}.{prefix_column}, 0))"
        self._numeric_features.append(Feature(alias=alias, expression=expression, joins=joins))
        return alias

    def _register_rolling_feature(self, feature_name: str, expression: str) -> str:
        alias = self._next_alias("__roll")
        self.trace.append(f"rewrite {feature_name}() into rolling window feature {alias}")
        self._explain(
            "ROLLING_BOOLEAN",
            "applied",
            f"Rewrite {feature_name}() into rolling boolean window feature",
            alias=alias,
            function=feature_name,
        )
        self._rolling_features.append(Feature(alias=alias, expression=expression))
        return alias

    def _explain(self, rule: str, status: str, message: str, **evidence: Any) -> None:
        self.explain.append(ExplainStep(rule=rule, status=status, message=message, evidence=evidence))

    def _next_alias(self, prefix: str) -> str:
        self._feature_counter += 1
        return f"{prefix}_{self._feature_counter}"

    def _window_value(self, node: Node) -> int:
        if not isinstance(node, Literal) or not isinstance(node.value, int):
            raise SemanticError("Window argument must be an integer literal")
        if node.value <= 0:
            raise SemanticError("Window argument must be positive")
        return node.value


def _format_sql(sql: str) -> str:
    return " ".join(sql.split())


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.12f}".rstrip("0").rstrip(".")


def _sql_comparison_operator(op: str) -> str:
    return {"=": "=", "==": "=", "!=": "<>"}.get(op, op)


def _sql_string_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"

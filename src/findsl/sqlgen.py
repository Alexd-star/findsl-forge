from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

from .ast_nodes import BinaryOp, Comparison, FunctionCall, Identifier, Literal, Node
from .errors import SemanticError
from .registry import Registry


@dataclass
class SqlPlan:
    sql: str
    trace: List[str] = field(default_factory=list)


@dataclass
class Feature:
    alias: str
    expression: str


class SqlGenerator:
    def __init__(self, registry: Registry):
        self.registry = registry
        self.required_tables: Set[str] = set()
        self.trace: List[str] = []
        self._feature_counter = 0
        self._current_source: Optional[str] = None
        self._numeric_features: List[Feature] = []
        self._rolling_features: List[Feature] = []

    def generate(self, node: Node) -> SqlPlan:
        self.required_tables = self._collect_tables(node)
        self.trace = []
        self._feature_counter = 0
        sql = self._relation_sql(node)
        return SqlPlan(sql=_format_sql(sql), trace=list(self.trace))

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
        if not tables:
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
            layer_sql = f"SELECT {self._project_columns()} FROM {from_clause}"
            layer_name = "base_features"

            if self._numeric_features:
                self.trace.append("materialize numeric window features before filtering")
                layer_sql = self._feature_layer_sql(layer_sql, layer_name, self._numeric_features, "numeric_features")
                layer_name = "numeric_features"
            if self._rolling_features:
                self.trace.append("materialize rolling boolean features after numeric features")
                layer_sql = self._feature_layer_sql(layer_sql, layer_name, self._rolling_features, "rolling_features")
                layer_name = "rolling_features"

            self.trace.append("rewrite filter predicate into outer WHERE over materialized features")
            return f"SELECT * FROM ({layer_sql}) {layer_name} WHERE {condition}"
        finally:
            self._current_source = old_source
            self._numeric_features = old_numeric
            self._rolling_features = old_rolling

    def _feature_layer_sql(self, inner_sql: str, inner_alias: str, features: List[Feature], output_alias: str) -> str:
        feature_sql = ", ".join(f"{feature.expression} AS {feature.alias}" for feature in features)
        return f"SELECT {inner_alias}.*, {feature_sql} FROM ({inner_sql}) {inner_alias}"

    def _rank_sql(self, node: FunctionCall, base_relation: str = None) -> str:
        self.trace.append("rewrite rank() into ROW_NUMBER window")
        old_source = self._current_source
        self._current_source = base_relation
        try:
            expr_sql = self._numeric_sql(node.args[0])
        finally:
            self._current_source = old_source
        order_node = node.args[1]
        if not isinstance(order_node, Identifier) or order_node.name.lower() not in {"asc", "desc"}:
            raise SemanticError("rank() second argument must be asc or desc")
        order = order_node.name.upper()
        limit = self._rank_limit(node)
        source = self._from_clause(base_relation)
        where = f" WHERE rank_no <= {limit}" if limit is not None else ""
        return (
            "SELECT * FROM ("
            f"SELECT base.*, ROW_NUMBER() OVER (PARTITION BY trade_date ORDER BY {expr_sql} {order}) AS rank_no "
            f"FROM {source}"
            f") ranked{where}"
        )

    def _rank_limit(self, node: FunctionCall):
        for named in node.named_args or []:
            if named.name == "top" and isinstance(named.value, Literal):
                return int(named.value.value)
            if named.name == "bottom" and isinstance(named.value, Literal):
                return int(named.value.value)
        return None

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
            joins.append(f" JOIN {meta['physical']} AS {alias} USING (ts_code, trade_date)")
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

    def _table_alias(self, table_name: str) -> str:
        if self._current_source:
            return "base"
        ordered = self._ordered_tables()
        if table_name == ordered[0]:
            return "base"
        return self.registry.table(table_name).get("alias", table_name)

    def _bool_sql(self, node: Node) -> str:
        if isinstance(node, Comparison):
            return f"{self._numeric_sql(node.left)} {node.op} {self._numeric_sql(node.right)}"
        if isinstance(node, BinaryOp) and node.op in {"&", "|"}:
            op = "AND" if node.op == "&" else "OR"
            return f"({self._bool_sql(node.left)} {op} {self._bool_sql(node.right)})"
        if isinstance(node, FunctionCall):
            name = node.name.upper()
            if name == "MARKET":
                return self._market_sql(node)
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
                return f"'{node.value}'"
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
            return f"{self._table_alias(meta['table'])}.{meta['column']}"
        return meta["column"]

    def _market_sql(self, node: FunctionCall) -> str:
        market_name = self._symbol_arg(node.args[0], "market")
        self.required_tables.add("stock_universe")
        if self._current_source:
            return f"{self._table_alias('stock_universe')}.market = '{market_name}'"
        return f"market = '{market_name}'"

    def _symbol_arg(self, node: Node, function_name: str) -> str:
        if isinstance(node, Literal) and isinstance(node.value, str):
            return node.value
        if isinstance(node, Identifier):
            return node.name
        raise SemanticError(f"{function_name}() requires a string or identifier argument")

    def _register_numeric_window(self, node: FunctionCall) -> str:
        name = node.name.upper()
        expr = self._numeric_sql(node.args[0])
        window = self._window_value(node.args[1])
        sql_name = {"MA": "AVG", "SUM": "SUM", "MAX": "MAX", "MIN": "MIN"}[name]
        alias = self._next_alias("__win")
        self.trace.append(f"rewrite {name}() into {sql_name} window feature {alias}")
        expression = (
            f"{sql_name}({expr}) OVER (PARTITION BY ts_code ORDER BY trade_date "
            f"ROWS BETWEEN {window - 1} PRECEDING AND CURRENT ROW)"
        )
        self._numeric_features.append(Feature(alias=alias, expression=expression))
        return alias

    def _register_rolling_feature(self, feature_name: str, expression: str) -> str:
        alias = self._next_alias("__roll")
        self.trace.append(f"rewrite {feature_name}() into rolling window feature {alias}")
        self._rolling_features.append(Feature(alias=alias, expression=expression))
        return alias

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

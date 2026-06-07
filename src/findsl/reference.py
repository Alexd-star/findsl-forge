from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ast_nodes import BinaryOp, Comparison, FunctionCall, Identifier, Literal, Node
from .errors import SemanticError
from .parser import parse
from .registry import Registry, default_registry


@dataclass(frozen=True)
class ReferenceResult:
    rows: Any

    def keys(self):
        return list(zip(self.rows["ts_code"].tolist(), self.rows["trade_date"].astype(str).tolist()))


class PandasReferenceEvaluator:
    """Slow but trustworthy DSL evaluator for semantic regression tests."""

    def __init__(self, data_dir: Path, registry: Registry = None):
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover - depends on runtime environment.
            raise RuntimeError("PandasReferenceEvaluator requires pandas") from exc
        self.pd = pd
        self.registry = registry or default_registry()
        self.data = self._load_data(data_dir)

    def evaluate(self, dsl: str) -> ReferenceResult:
        ast = parse(dsl)
        rows = self._relation(ast, self.data.copy())
        return ReferenceResult(rows=rows.sort_values(["trade_date", "ts_code"]).reset_index(drop=True))

    def _load_data(self, data_dir: Path):
        pd = self.pd
        daily = pd.read_csv(data_dir / "daily_quote.csv", parse_dates=["trade_date"])
        money = pd.read_csv(data_dir / "money_flow.csv", parse_dates=["trade_date"])
        universe = pd.read_csv(data_dir / "stock_universe.csv", parse_dates=["trade_date"])
        rows = daily.merge(money, on=["ts_code", "trade_date"], how="left")
        rows = rows.merge(universe, on=["ts_code", "trade_date"], how="left")
        return rows.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)

    def _relation(self, node: Node, rows):
        if isinstance(node, FunctionCall) and node.name.lower() == "then":
            current = rows
            for stage in node.args:
                current = self._relation(stage, current)
            return current
        if isinstance(node, FunctionCall) and node.name.lower() == "filter":
            mask = self._bool(node.args[0], rows)
            return rows[self._filter_mask(mask)].copy()
        if isinstance(node, FunctionCall) and node.name.lower() == "rank":
            return self._rank(node, rows)
        mask = self._bool(node, rows)
        return rows[self._filter_mask(mask)].copy()

    def _rank(self, node: FunctionCall, rows):
        expr = self._numeric(node.args[0], rows)
        order_node = node.args[1]
        if not isinstance(order_node, Identifier) or order_node.name.lower() not in {"asc", "desc"}:
            raise SemanticError("rank() second argument must be asc or desc")
        ascending = order_node.name.lower() == "asc"
        ranked = rows.copy()
        ranked["__rank_expr"] = expr
        ranked["rank_no"] = ranked.groupby("trade_date")["__rank_expr"].rank(
            method="first", ascending=ascending
        )
        limit = None
        percent = None
        for named in node.named_args or []:
            arg_name = named.name.lower()
            if arg_name in {"top", "bottom"} and isinstance(named.value, Literal):
                limit = int(named.value.value)
            if arg_name == "percent" and isinstance(named.value, Literal):
                percent = float(named.value.value)
        if limit is not None:
            ranked = ranked[ranked["rank_no"] <= limit]
        if percent is not None:
            ranked = ranked[ranked["__rank_expr"].notna()].copy()
            ranked["__partition_count"] = ranked.groupby("trade_date")["ts_code"].transform("count")
            threshold = ((ranked["__partition_count"] * percent) / 100.0).apply(math.ceil)
            ranked = ranked[ranked["rank_no"] <= threshold]
        drop_columns = [column for column in ["__rank_expr", "__partition_count"] if column in ranked.columns]
        return ranked.drop(columns=drop_columns)

    def _bool(self, node: Node, rows):
        if isinstance(node, Comparison):
            left = self._numeric(node.left, rows)
            right = self._numeric(node.right, rows)
            if node.op == ">":
                return self._compare(left, right, lambda l, r: l > r)
            if node.op == ">=":
                return self._compare(left, right, lambda l, r: l >= r)
            if node.op == "<":
                return self._compare(left, right, lambda l, r: l < r)
            if node.op == "<=":
                return self._compare(left, right, lambda l, r: l <= r)
            if node.op in {"=", "=="}:
                return self._compare(left, right, lambda l, r: l == r)
            if node.op == "!=":
                return self._compare(left, right, lambda l, r: l != r)
            raise SemanticError(f"Unsupported comparison operator {node.op}")
        if isinstance(node, BinaryOp) and node.op in {"&", "^", "|"}:
            left = self._bool(node.left, rows)
            right = self._bool(node.right, rows)
            if node.op == "&":
                return left & right
            if node.op == "^":
                return left.fillna(False) ^ right.fillna(False)
            return left | right
        if isinstance(node, FunctionCall):
            name = node.name.upper()
            if name == "MARKET":
                return rows["market"] == self._symbol_arg(node.args[0], "market").upper()
            if name == "DATE_BETWEEN":
                start = self.pd.Timestamp(self._symbol_arg(node.args[0], "date_between"))
                end = self.pd.Timestamp(self._symbol_arg(node.args[1], "date_between"))
                return (rows["trade_date"] >= start) & (rows["trade_date"] <= end)
            if name == "CONS":
                cond = self._filter_mask(self._bool(node.args[0], rows)).astype(int)
                window = self._window_value(node.args[1])
                return self._rolling(cond, rows, window, "sum") == window
            if name == "EXIST":
                cond = self._filter_mask(self._bool(node.args[0], rows)).astype(int)
                window = self._window_value(node.args[1])
                return self._rolling(cond, rows, window, "max") == 1
        raise SemanticError(f"Expected boolean expression, got {node!r}")

    def _compare(self, left, right, op):
        result = op(left, right)
        if not hasattr(result, "where"):
            return result if not (self.pd.isna(left) or self.pd.isna(right)) else self.pd.NA
        valid = self.pd.Series(True, index=result.index)
        for operand in (left, right):
            if hasattr(operand, "isna"):
                valid &= ~operand.isna()
            elif self.pd.isna(operand):
                valid &= False
        return result.where(valid)

    def _filter_mask(self, mask):
        return mask.where(mask.notna(), False).astype(bool)

    def _numeric(self, node: Node, rows):
        if isinstance(node, Literal):
            return node.value
        if isinstance(node, Identifier):
            if node.name in rows.columns:
                return rows[node.name]
            return node.name
        if isinstance(node, BinaryOp) and node.op in {"+", "-", "*", "/"}:
            left = self._numeric(node.left, rows)
            right = self._numeric(node.right, rows)
            if node.op == "+":
                return left + right
            if node.op == "-":
                return left - right
            if node.op == "*":
                return left * right
            return left / right
        if isinstance(node, FunctionCall):
            name = node.name.upper()
            if name == "INDICATOR":
                indicator_name = self._symbol_arg(node.args[0], "indicator")
                column = str(self.registry.indicator(indicator_name)["column"])
                if column not in rows.columns:
                    raise SemanticError(f"Unknown indicator column in sample data: {column}")
                return rows[column]
            if name in {"MA", "SUM", "MAX", "MIN"}:
                series = self._numeric(node.args[0], rows)
                window = self._window_value(node.args[1])
                agg = {"MA": "mean", "SUM": "sum", "MAX": "max", "MIN": "min"}[name]
                return self._rolling(series, rows, window, agg)
            if name == "RET":
                series = self._numeric(node.args[0], rows)
                window = self._window_value(node.args[1])
                previous = self._lag(series, rows, window)
                previous = previous.mask(previous == 0)
                return (series / previous) - 1
        raise SemanticError(f"Expected numeric expression, got {node!r}")

    def _lag(self, series, rows, window: int):
        work = rows[["ts_code", "trade_date"]].copy()
        work["__value"] = series
        work["__original_index"] = rows.index
        work = work.sort_values(["ts_code", "trade_date"])
        work["__lagged"] = work.groupby("ts_code")["__value"].shift(window)
        return work.sort_values("__original_index")["__lagged"].set_axis(rows.index)

    def _rolling(self, series, rows, window: int, agg: str):
        pd = self.pd
        work = rows[["ts_code", "trade_date"]].copy()
        work["__value"] = series
        work["__original_index"] = rows.index
        work = work.sort_values(["ts_code", "trade_date"])
        rolled = (
            work.groupby("ts_code")["__value"]
            .rolling(window=window, min_periods=1)
            .agg(agg)
            .reset_index(level=0, drop=True)
        )
        work["__rolled"] = rolled
        return work.sort_values("__original_index")["__rolled"].set_axis(rows.index)

    def _symbol_arg(self, node: Node, function_name: str) -> str:
        if isinstance(node, Literal) and isinstance(node.value, str):
            return node.value
        if isinstance(node, Identifier):
            return node.name
        raise SemanticError(f"{function_name}() requires a string or identifier argument")

    def _window_value(self, node: Node) -> int:
        if not isinstance(node, Literal) or not isinstance(node.value, int):
            raise SemanticError("Window argument must be an integer literal")
        if node.value <= 0:
            raise SemanticError("Window argument must be positive")
        return node.value

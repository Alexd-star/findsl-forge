from __future__ import annotations

import csv
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .official import CompileMode, SourceRepair
from .official_time import normalize_official_date


class OfficialSlotError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    position: int


class OfficialNode:
    def to_dict(self) -> Dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class OfficialParseResult:
    source: str
    normalized_source: str
    ast: OfficialNode
    repairs: Tuple[SourceRepair, ...]


@dataclass(frozen=True)
class _MappedSource:
    text: str
    positions: Tuple[int, ...]

    @classmethod
    def from_source(cls, source: str) -> "_MappedSource":
        return cls(source, tuple(range(len(source))))

    def replace(
        self,
        start: int,
        end: int,
        replacement: str = "",
        replacement_positions: Sequence[int] = (),
    ) -> "_MappedSource":
        if len(replacement) != len(replacement_positions):
            raise ValueError("replacement text and source positions must have equal lengths")
        return _MappedSource(
            self.text[:start] + replacement + self.text[end:],
            self.positions[:start] + tuple(replacement_positions) + self.positions[end:],
        )


@dataclass(frozen=True)
class OfficialLiteral(OfficialNode):
    value: Any

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "Literal", "value": self.value}


@dataclass(frozen=True)
class OfficialIdentifier(OfficialNode):
    name: str

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "Identifier", "name": self.name}


@dataclass(frozen=True)
class OfficialFunctionCall(OfficialNode):
    name: str
    args: List[OfficialNode]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "FunctionCall",
            "name": self.name,
            "args": [arg.to_dict() for arg in self.args],
        }


@dataclass(frozen=True)
class OfficialBinaryOp(OfficialNode):
    op: str
    left: OfficialNode
    right: OfficialNode

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "BinaryOp",
            "op": self.op,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
        }


@dataclass(frozen=True)
class OfficialComparison(OfficialNode):
    op: str
    left: OfficialNode
    right: OfficialNode

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "Comparison",
            "op": self.op,
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
        }


@dataclass(frozen=True)
class OfficialLimit(OfficialNode):
    expr: OfficialNode
    lower: int
    upper: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "Limit",
            "lower": self.lower,
            "upper": self.upper,
            "expr": self.expr.to_dict(),
        }


@dataclass(frozen=True)
class OfficialRangeLiteral(OfficialNode):
    lower: OfficialNode
    upper: OfficialNode
    lower_inclusive: bool
    upper_inclusive: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "RangeLiteral",
            "lower": self.lower.to_dict(),
            "upper": self.upper.to_dict(),
            "lower_inclusive": self.lower_inclusive,
            "upper_inclusive": self.upper_inclusive,
        }


@dataclass(frozen=True)
class IndicatorMeta:
    table: str
    column: Optional[str] = None
    kind: str = "numeric"
    expression: Optional[str] = None
    true_condition: Optional[str] = None
    false_condition: Optional[str] = None


@dataclass
class SqlExpr:
    sql: str
    kind: str
    tables: List[str]
    constraints: List[str]
    date_localized: bool = False


@dataclass(frozen=True)
class CountExpRule:
    mode: str
    operator: str
    count: Optional[int]
    unit: str = ""
    every: bool = False
    max_count: Optional[int] = None


@dataclass(frozen=True)
class CountExpSpec:
    count_exp: str
    market: str
    filter_scope: str
    date: str
    select_type: str
    agg_func: str = ""


@dataclass(frozen=True)
class OfficialCompileResult:
    source: str
    ast: Dict[str, Any]
    sql: str
    requires_tables: List[str]
    warnings: List[str]
    normalized_source: str = ""
    repairs: Tuple[SourceRepair, ...] = ()
    strict_success: bool = True
    degraded: bool = False
    fallback_predicates: Tuple[str, ...] = ()


class _CompilationWarnings(list):
    def __init__(self) -> None:
        super().__init__()
        self.fallback_predicates: set[str] = set()

    def mark_fallback(self, predicate: Optional[str]) -> None:
        if predicate:
            self.fallback_predicates.add(predicate)


def _mark_fallback(warnings: List[str], predicate: Optional[str]) -> None:
    if isinstance(warnings, _CompilationWarnings):
        warnings.mark_fallback(predicate)


OPERATORS = {">=", "<=", "!=", "~=", ">", "<", "=", "+", "-", "*", "/", "(", ")", "[", "]", ","}
KEYWORDS = {"and", "or", "then", "between", "limit", "true", "false"}
AGGREGATE_FUNCTIONS = {"MAX", "MIN", "AVG", "SUM"}
GROWTH_FUNCTIONS = {"GROWTH_RISE", "GROWTH_FALL"}


DEFAULT_TECHNICAL_PATTERN_CONFIG: Dict[str, Any] = {
    "close_together": {"relative_threshold": 0.03},
    "reset": {"near_line_threshold": 0.02, "below_line_tolerance": 0.005},
}


def _load_technical_pattern_config() -> Dict[str, Any]:
    config = json.loads(json.dumps(DEFAULT_TECHNICAL_PATTERN_CONFIG))
    path = Path(__file__).resolve().parents[2] / "configs" / "official_technical_patterns.json"
    if not path.exists():
        return config
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return config
    for section in DEFAULT_TECHNICAL_PATTERN_CONFIG:
        user_values = loaded.get(section, {})
        if isinstance(user_values, dict):
            config[section].update(user_values)
    return config


MARKET_CODE_MAP = {
    "深": 0,
    "深主板": 0,
    "沪": 1,
    "沪主板": 1,
    "京": 103,
}


MARKET_FLAG_MAP = {
    "科创板": "code.kcbFlag = TRUE",
    "创业板": "code.gemFlag = TRUE",
    "沪深": "code.hsFlag = TRUE",
    "沪深京": "code.hsjFlag = TRUE",
}


def _scale_expr(sql: str, scale: float = 10000.0) -> str:
    return f"({sql} / {scale:.1f})"


def _price_expr(column: str) -> str:
    return _scale_expr(f"base.{column}")


def _rate_expr(column: str, alias: str = "base") -> str:
    return _scale_expr(f"{alias}.{column}")


INDICATORS: Dict[str, IndicatorMeta] = {
    "最新价": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_price_expr("lastPx")),
    "现价": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_price_expr("lastPx")),
    "开盘价": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_price_expr("openPx")),
    "最高价": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_price_expr("highPx")),
    "最低价": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_price_expr("lowPx")),
    "收盘价": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_price_expr("closePx")),
    "昨收价": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_price_expr("preClosePx")),
    "成交量": IndicatorMeta("hsj_stock_hq_basic", "volume"),
    "成交额": IndicatorMeta("hsj_stock_hq_basic", "turnover"),
    "换手率": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_rate_expr("turnRatio")),
    "实际换手率": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_rate_expr("trueTurnRatio")),
    "量比": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_rate_expr("quantRatio")),
    "外盘": IndicatorMeta("hsj_stock_hq_basic", "outerVol"),
    "内盘": IndicatorMeta("hsj_stock_hq_basic", "innerVol"),
    "委买": IndicatorMeta("hsj_stock_hq_basic", "commissionBuy"),
    "委卖": IndicatorMeta("hsj_stock_hq_basic", "commissionSale"),
    "委比": IndicatorMeta(
        "hsj_stock_hq_basic",
        kind="numeric",
        expression="((base.commissionBuy - base.commissionSale) * 100.0 / NULLIF(base.commissionBuy + base.commissionSale, 0))",
    ),
    "委差": IndicatorMeta(
        "hsj_stock_hq_basic",
        kind="numeric",
        expression="(base.commissionBuy - base.commissionSale)",
    ),
    "挂单量": IndicatorMeta("hsj_stock_hq_basic", "numOfOrders"),
    "振幅": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_rate_expr("amplitude")),
    "总股本": IndicatorMeta("hsj_stock_hq_basic", "totalShare"),
    "流通股本": IndicatorMeta("hsj_stock_hq_basic", "listedShare"),
    "自由流通股股本": IndicatorMeta("hsj_stock_hq_basic", "freeShare"),
    "自由流通股本": IndicatorMeta("hsj_stock_hq_basic", "freeShare"),
    "每手股数": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression="100"),
    "总市值": IndicatorMeta(
        "hsj_stock_hq_basic",
        kind="numeric",
        expression="((base.lastPx / 10000.0) * base.totalShare)",
    ),
    "流通市值": IndicatorMeta(
        "hsj_stock_hq_basic",
        kind="numeric",
        expression="((base.lastPx / 10000.0) * base.listedShare)",
    ),
    "每股净资产": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_price_expr("bVPS")),
    "市净率": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_rate_expr("pBR")),
    "动态市盈率": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_rate_expr("dynPE")),
    "静态市盈率": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_rate_expr("staticPE")),
    "市盈率": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_rate_expr("pETTM")),
    "TTM市盈率": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_rate_expr("pETTM")),
    "成交均价": IndicatorMeta(
        "hsj_stock_hq_basic",
        kind="numeric",
        expression="((base.turnover / NULLIF(base.volume, 0)) / 100.0)",
    ),
    "涨跌幅": IndicatorMeta(
        "hsj_stock_hq_basic",
        kind="numeric",
        expression="((base.lastPx - base.preClosePx) * 100.0 / NULLIF(base.preClosePx, 0))",
    ),
    "涨幅": IndicatorMeta(
        "hsj_stock_hq_basic",
        kind="numeric",
        expression="((base.lastPx - base.preClosePx) * 100.0 / NULLIF(base.preClosePx, 0))",
    ),
    "跌幅": IndicatorMeta(
        "hsj_stock_hq_basic",
        kind="numeric",
        expression="((base.preClosePx - base.lastPx) * 100.0 / NULLIF(base.preClosePx, 0))",
    ),
    "涨停": IndicatorMeta(
        "hsj_stock_hq_basic",
        kind="boolean",
        true_condition="base.limitFlag = 1",
        false_condition="base.limitFlag != 1",
    ),
    "跌停": IndicatorMeta(
        "hsj_stock_hq_basic",
        kind="boolean",
        true_condition="base.limitFlag = -1",
        false_condition="base.limitFlag != -1",
    ),
    "首板涨停": IndicatorMeta(
        "hsj_stock_hq_basic",
        kind="boolean",
        true_condition="base.limitFlag = 1 AND COALESCE(base.upSerialLb, 0) = 1",
        false_condition="NOT (base.limitFlag = 1 AND COALESCE(base.upSerialLb, 0) = 1)",
    ),
    "涨停天数": IndicatorMeta("hsj_stock_hq_basic", "upCount"),
    "跌停天数": IndicatorMeta("hsj_stock_hq_basic", "downCount"),
    "连续涨停天数": IndicatorMeta("hsj_stock_hq_basic", "upSerialLb"),
    "连板天数": IndicatorMeta("hsj_stock_hq_basic", "upSerialLb"),
    "涨停次数": IndicatorMeta("hsj_stock_hq_basic", "upCount"),
    "跌停次数": IndicatorMeta("hsj_stock_hq_basic", "downCount"),
    "涨跌停类型": IndicatorMeta("hsj_stock_hq_basic", "limitType"),
    "涨停形态": IndicatorMeta("hsj_stock_hq_basic", "limitShape"),
    "涨停时间": IndicatorMeta("hsj_stock_hq_basic", "firstLimitUpTime", kind="time"),
    "首次涨停时间": IndicatorMeta("hsj_stock_hq_basic", "firstLimitUpTime", kind="time"),
    "最后涨停时间": IndicatorMeta("hsj_stock_hq_basic", "lastLimitUpTime", kind="time"),
    "最后一次涨停时间": IndicatorMeta("hsj_stock_hq_basic", "lastLimitUpTime", kind="time"),
    "跌停时间": IndicatorMeta("hsj_stock_hq_basic", "firstLimitDownTime", kind="time"),
    "首次跌停时间": IndicatorMeta("hsj_stock_hq_basic", "firstLimitDownTime", kind="time"),
    "最后跌停时间": IndicatorMeta("hsj_stock_hq_basic", "lastLimitDownTime", kind="time"),
    "最后一次跌停时间": IndicatorMeta("hsj_stock_hq_basic", "lastLimitDownTime", kind="time"),
    "涨停成交额": IndicatorMeta("hsj_stock_hq_basic", "upTradeAmt"),
    "跌停成交额": IndicatorMeta("hsj_stock_hq_basic", "downTradeAmt"),
    "最高涨停封单量": IndicatorMeta("hsj_stock_hq_basic", "maxUpSealVol"),
    "最高跌停封单量": IndicatorMeta("hsj_stock_hq_basic", "maxDownSealVol"),
    "涨停价": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_price_expr("upSealPx")),
    "涨停封单价": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_price_expr("upSealPx")),
    "涨停封单量": IndicatorMeta("hsj_stock_hq_basic", "upSealVol"),
    "跌停价": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_price_expr("downSealPx")),
    "跌停封单价": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_price_expr("downSealPx")),
    "跌停封单量": IndicatorMeta("hsj_stock_hq_basic", "downSealVol"),
    "最后一次炸板时间": IndicatorMeta("hsj_stock_hq_basic", "lastFUpTime", kind="time"),
    "最后一次跌停打开时间": IndicatorMeta("hsj_stock_hq_basic", "lastFDownTime", kind="time"),
    "涨停炸板": IndicatorMeta(
        "hsj_stock_hq_ext",
        kind="boolean",
        true_condition="(COALESCE(ext.lmtUpNum, 0) > 0 OR COALESCE(ext.boardBreaks, 0) > 0)",
    ),
    "炸板": IndicatorMeta(
        "hsj_stock_hq_ext",
        kind="boolean",
        true_condition="(COALESCE(ext.lmtUpNum, 0) > 0 OR COALESCE(ext.boardBreaks, 0) > 0)",
    ),
    "涨停未封板": IndicatorMeta(
        "hsj_stock_hq_ext",
        kind="boolean",
        true_condition="((COALESCE(ext.lmtUpNum, 0) > 0 OR COALESCE(ext.boardBreaks, 0) > 0) AND base.limitFlag != 1)",
    ),
    "压力位": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_price_expr("pressure")),
    "支持位": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_price_expr("support")),
    "支撑位": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_price_expr("support")),
    "上影线": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_price_expr("upperShadow")),
    "下影线": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_price_expr("lowerShadow")),
    "3分钟涨速": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("riseSpd3m", "ext")),
    "三分钟涨速": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("riseSpd3m", "ext")),
    "5分钟涨速": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("riseSpd5m", "ext")),
    "五分钟涨速": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("riseSpd5m", "ext")),
    "10分钟涨速": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("riseSpd10m", "ext")),
    "十分钟涨速": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("riseSpd10m", "ext")),
    "集合竞价金额": IndicatorMeta("hsj_stock_hq_ext", "callAucAmt"),
    "集合竞价涨幅": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("callAucRisePct", "ext")),
    "集合竞价涨跌幅": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("callAucRisePct", "ext")),
    "集合竞价卖方未匹配量": IndicatorMeta("hsj_stock_hq_ext", "callAucAsk2Vol"),
    "卖方未匹配量": IndicatorMeta("hsj_stock_hq_ext", "callAucAsk2Vol"),
    "集合竞价买方未匹配量": IndicatorMeta("hsj_stock_hq_ext", "callAucBid2Vol"),
    "买方未匹配量": IndicatorMeta("hsj_stock_hq_ext", "callAucBid2Vol"),
    "集合竞价匹配量": IndicatorMeta("hsj_stock_hq_ext", "callAucMatchVol"),
    "集合竞价匹配价": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("callAucMatchPx", "ext")),
    "主力分歧度": IndicatorMeta("hsj_stock_hq_ext", "MPResExt"),
    "主力成本": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("MPCost", "ext")),
    "主力净流入": IndicatorMeta("hsj_stock_hq_ext", "ZJLXMainNetTur"),
    "资金净流入": IndicatorMeta("hsj_stock_hq_ext", "ZJLXMainNetTur"),
    "主力净流出": IndicatorMeta(
        "hsj_stock_hq_ext",
        kind="numeric",
        expression="(-ext.ZJLXMainNetTur)",
    ),
    "今日主力增仓占比": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("ZJLXMainIncPer", "ext")),
    "小单买入": IndicatorMeta("hsj_stock_hq_ext", "smBuyTur"),
    "小单卖出": IndicatorMeta("hsj_stock_hq_ext", "smSellTur"),
    "大单买入": IndicatorMeta("hsj_stock_hq_ext", "bigBuyTur"),
    "大单买入金额": IndicatorMeta("hsj_stock_hq_ext", "bigBuyTur"),
    "大单卖出": IndicatorMeta("hsj_stock_hq_ext", "bigSellTur"),
    "大单卖出金额": IndicatorMeta("hsj_stock_hq_ext", "bigSellTur"),
    "中单买入": IndicatorMeta("hsj_stock_hq_ext", "midBuyTur"),
    "中单卖出": IndicatorMeta("hsj_stock_hq_ext", "midSellTur"),
    "超大单买入": IndicatorMeta("hsj_stock_hq_ext", "supBuyTur"),
    "超大单卖出": IndicatorMeta("hsj_stock_hq_ext", "supSellTur"),
    "主力买入金额": IndicatorMeta("hsj_stock_hq_ext", "ZJLXMainBuyTur"),
    "主力卖出金额": IndicatorMeta("hsj_stock_hq_ext", "ZJLXMainSellTur"),
    "主力成交量": IndicatorMeta("hsj_stock_hq_ext", "ZJLXMainCnt"),
    "主力成交量占比": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("ZJLXMainTradeVolPer", "ext")),
    "超大单净流入": IndicatorMeta("hsj_stock_hq_ext", "ZJLXSupNetTur"),
    "大单净流入": IndicatorMeta("hsj_stock_hq_ext", "ZJLXBigNetTur"),
    "中单净流入": IndicatorMeta("hsj_stock_hq_ext", "ZJLXMidNetTur"),
    "小单净流入": IndicatorMeta("hsj_stock_hq_ext", "ZJLXSmNetTur"),
    "主力主动买入数量": IndicatorMeta("hsj_stock_hq_ext", "ZJLXMainActBuyCnt"),
    "主力主动买入占比": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("ZJLXMainActBuyCntPer", "ext")),
    "主力主动卖出数量": IndicatorMeta("hsj_stock_hq_ext", "ZJLXMainActSellCnt"),
    "主力主动卖出占比": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("ZJLXMainActSellCntPer", "ext")),
    "散户买入": IndicatorMeta("hsj_stock_hq_ext", "ZJLXRetailBuyCnt"),
    "散户卖出": IndicatorMeta("hsj_stock_hq_ext", "ZJLXRetailSellCnt"),
    "主力买入手数": IndicatorMeta("hsj_stock_hq_ext", "ZJLXMainBuyCnt"),
    "主力买入占比": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("ZJLXMainBuyCntPer", "ext")),
    "主力卖出手数": IndicatorMeta("hsj_stock_hq_ext", "ZJLXMainSellCnt"),
    "主力卖出占比": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("ZJLXMainSellCntPer", "ext")),
    "散户买入占比": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("ZJLXRetailBuyCntPer", "ext")),
    "散户卖出占比": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("ZJLXRetailSellCntPer", "ext")),
    "主力净占比": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("ZJLXMainNetCntTurPer", "ext")),
    "散户净流入": IndicatorMeta("hsj_stock_hq_ext", "ZJLXMidAndSmNetTur"),
    "主力连续净流入天数": IndicatorMeta("hsj_stock_hq_ext", "ZJLXMainNetTurInDays"),
    "主力连续净流出天数": IndicatorMeta("hsj_stock_hq_ext", "ZJLXMainNetTurOutDays"),
    "主力连续净流入金额": IndicatorMeta("hsj_stock_hq_ext", "ZJLXMainNetTurInSeries"),
    "主力连续净流出金额": IndicatorMeta("hsj_stock_hq_ext", "ZJLXMainNetTurOutSeries"),
    "大单动向": IndicatorMeta("hsj_stock_hq_ext", "ZJLXDDX"),
    "涨跌动因": IndicatorMeta("hsj_stock_hq_ext", "ZJLXDDY"),
    "大单差分": IndicatorMeta("hsj_stock_hq_ext", "ZJLXDDZ"),
    "筹码形态": IndicatorMeta("hsj_stock_hq_ext", "formFlag"),
    "最大回撤": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("maxRetreat", "ext")),
    "历史最大回撤": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("maxRetreat", "ext")),
    "历史最大跌幅": IndicatorMeta("hsj_stock_hq_ext", kind="numeric", expression=_rate_expr("maxRetreat", "ext")),
    "MA角度": IndicatorMeta("hsj_stock_hq_ext", "maAngle"),
    "创N日新高": IndicatorMeta("hsj_stock_hq_ext", "pxMkTopDays"),
    "创N日新低": IndicatorMeta("hsj_stock_hq_ext", "pxMkBotDays"),
    "连涨天数": IndicatorMeta("hsj_stock_hq_ext", "pxMkIncDays"),
    "连跌天数": IndicatorMeta("hsj_stock_hq_ext", "pxMkDescDays"),
    "资金净流入创N日新高": IndicatorMeta("hsj_stock_hq_ext", "mainTurMkTopDays"),
    "涨停开板次数": IndicatorMeta("hsj_stock_hq_ext", "lmtUpNum"),
    "破板次数": IndicatorMeta("hsj_stock_hq_ext", "boardBreaks"),
    "跌停破板次数": IndicatorMeta("hsj_stock_hq_ext", "downBoardBreaks"),
    "3日均线": IndicatorMeta("hsj_stock_hq_basic_technical", "ma3"),
    "三日均线": IndicatorMeta("hsj_stock_hq_basic_technical", "ma3"),
    "5日均线": IndicatorMeta("hsj_stock_hq_basic_technical", "ma5"),
    "一周均线": IndicatorMeta("hsj_stock_hq_basic_technical", "ma5"),
    "10日均线": IndicatorMeta("hsj_stock_hq_basic_technical", "ma10"),
    "20日均线": IndicatorMeta("hsj_stock_hq_basic_technical", "ma20"),
    "一个月均线": IndicatorMeta("hsj_stock_hq_basic_technical", "ma20"),
    "30日均线": IndicatorMeta("hsj_stock_hq_basic_technical", "ma30"),
    "60日均线": IndicatorMeta("hsj_stock_hq_basic_technical", "ma60"),
    "一个季度均线": IndicatorMeta("hsj_stock_hq_basic_technical", "ma60"),
    "120日均线": IndicatorMeta("hsj_stock_hq_basic_technical", "ma120"),
    "半年均线": IndicatorMeta("hsj_stock_hq_basic_technical", "ma120"),
    "200日均线": IndicatorMeta("hsj_stock_hq_basic_technical", "ma200"),
    "250日均线": IndicatorMeta("hsj_stock_hq_basic_technical", "ma250"),
    "一年均线": IndicatorMeta("hsj_stock_hq_basic_technical", "ma250"),
    "年均线": IndicatorMeta("hsj_stock_hq_basic_technical", "ma250"),
    "5日均量线": IndicatorMeta("hsj_stock_hq_basic_technical", "volume_avg_5"),
    "一周均量线": IndicatorMeta("hsj_stock_hq_basic_technical", "volume_avg_5"),
    "10日均量线": IndicatorMeta("hsj_stock_hq_basic_technical", "volume_avg_10"),
    "20日均量线": IndicatorMeta("hsj_stock_hq_basic_technical", "volume_avg_20"),
    "一个月均量线": IndicatorMeta("hsj_stock_hq_basic_technical", "volume_avg_20"),
    "30日均量线": IndicatorMeta("hsj_stock_hq_basic_technical", "volume_avg_30"),
    "60日均量线": IndicatorMeta("hsj_stock_hq_basic_technical", "volume_avg_60"),
    "一个季度均量线": IndicatorMeta("hsj_stock_hq_basic_technical", "volume_avg_60"),
    "阳线": IndicatorMeta(
        "hsj_stock_hq_basic_technical",
        kind="boolean",
        true_condition="tech.yang_line = TRUE",
        false_condition="tech.yang_line != TRUE",
    ),
    "阴线": IndicatorMeta(
        "hsj_stock_hq_basic_technical",
        kind="boolean",
        true_condition="tech.yin_line = TRUE",
        false_condition="tech.yin_line != TRUE",
    ),
    "十字星": IndicatorMeta(
        "hsj_stock_hq_basic_technical",
        kind="boolean",
        true_condition="tech.doji = TRUE",
        false_condition="tech.doji != TRUE",
    ),
    "放量": IndicatorMeta(
        "hsj_stock_hq_basic_technical",
        kind="boolean",
        true_condition="tech.volume_breakout = TRUE",
        false_condition="tech.volume_breakout != TRUE",
    ),
    "均线多头排列": IndicatorMeta(
        "hsj_stock_hq_basic_technical",
        kind="boolean",
        true_condition="tech.ma_bullish = TRUE",
        false_condition="tech.ma_bullish != TRUE",
    ),
    "均线空头排列": IndicatorMeta(
        "hsj_stock_hq_basic_technical",
        kind="boolean",
        true_condition="tech.ma_bearish = TRUE",
        false_condition="tech.ma_bearish != TRUE",
    ),
    "上涨趋势": IndicatorMeta(
        "hsj_stock_hq_basic_technical",
        kind="boolean",
        true_condition="tech.uptrend = TRUE",
        false_condition="tech.uptrend != TRUE",
    ),
    "ST股票标识": IndicatorMeta("hsj_stock_code_info", "stFlag", kind="boolean"),
    "ST标识": IndicatorMeta("hsj_stock_code_info", "stFlag", kind="boolean"),
    "A股港股同时上市标识": IndicatorMeta("hsj_stock_code_info", "ahFlag", kind="boolean"),
    "陆股通标识": IndicatorMeta("hsj_stock_code_info", "hkConnFlag", kind="boolean"),
    "港股通标识": IndicatorMeta("hsj_stock_code_info", "hkConnFlag", kind="boolean"),
    "沪股通标识": IndicatorMeta("hsj_stock_code_info", "shConnFlag", kind="boolean"),
    "沪港通标识": IndicatorMeta("hsj_stock_code_info", "shConnFlag", kind="boolean"),
    "深股通标识": IndicatorMeta("hsj_stock_code_info", "szConnFlag", kind="boolean"),
    "深港通标识": IndicatorMeta("hsj_stock_code_info", "szConnFlag", kind="boolean"),
    "科创板标识": IndicatorMeta("hsj_stock_code_info", "kcbFlag", kind="boolean"),
    "创业板标识": IndicatorMeta("hsj_stock_code_info", "gemFlag", kind="boolean"),
    "B股标识": IndicatorMeta("hsj_stock_code_info", "bShareFlag", kind="boolean"),
    "是否T+0": IndicatorMeta("hsj_stock_hq_basic", kind="boolean", true_condition="FALSE"),
    "股票名称": IndicatorMeta("hsj_stock_code_info", "name", kind="string"),
    "证券代码": IndicatorMeta("hsj_stock_code_info", "tztcode", kind="string"),
    "股票代码": IndicatorMeta("hsj_stock_code_info", "tgtcode", kind="string"),
    "所属行业": IndicatorMeta("hsj_stock_code_info", "hyBlkRefName", kind="string"),
}


def _resolve_indicator_meta(indicator_name: str) -> Optional[IndicatorMeta]:
    meta = INDICATORS.get(indicator_name)
    if meta:
        return meta
    return _dynamic_prefix_indicator_meta(indicator_name)


def _dynamic_prefix_indicator_meta(indicator_name: str) -> Optional[IndicatorMeta]:
    match = re.fullmatch(
        r"(?P<count>\d+|[零〇一二两三四五六七八九十百两]+)(?:日|天)均(?P<volume>量)?线",
        str(indicator_name or "").strip(),
    )
    if not match:
        return None
    window = _parse_small_count(match.group("count"))
    if window <= 0:
        return None
    if match.group("volume"):
        expression = _dynamic_prefix_average_expr(
            window,
            prefix_column="volume_prefix",
            count_column="volume_count_prefix",
            scale_divisor=None,
        )
    else:
        expression = _dynamic_prefix_average_expr(
            window,
            prefix_column="close_prefix",
            count_column="close_count_prefix",
            scale_divisor=10000.0,
        )
    return IndicatorMeta("hsj_stock_hq_basic_prefix", kind="numeric", expression=expression)


def _dynamic_prefix_average_expr(
    window: int,
    *,
    prefix_column: str,
    count_column: str,
    scale_divisor: Optional[float],
) -> str:
    average_sql = (
        f"(SELECT ((p.{prefix_column} - COALESCE(p_prev.{prefix_column}, 0)) * 1.0 "
        f"/ NULLIF(p.{count_column} - COALESCE(p_prev.{count_column}, 0), 0))\n"
        " FROM newzl.hsj_stock_hq_basic_prefix AS p\n"
        " LEFT JOIN newzl.hsj_stock_hq_basic_prefix AS p_prev "
        "ON p_prev.mktcode = p.mktcode "
        "AND p_prev.tgtcode = p.tgtcode "
        f"AND p_prev.row_no = p.row_no - {window}\n"
        " WHERE p.mktcode = base.mktcode "
        "AND p.tgtcode = base.tgtcode "
        "AND p.bizdate = base.bizdate)"
    )
    if scale_divisor is None:
        return average_sql
    return f"({average_sql} / {scale_divisor:.1f})"


def _normalize_official_slot_source(source: str) -> Tuple[str, Tuple[SourceRepair, ...]]:
    mapped = _MappedSource.from_source(str(source or ""))
    repairs: List[SourceRepair] = []

    leading = re.match(r"^\s*(and|or|then)\b\s+", mapped.text, flags=re.IGNORECASE)
    if leading:
        repairs.append(
            SourceRepair(
                code="LEADING_BOOLEAN_OPERATOR",
                message=f"removed leading {leading.group(1).lower()} operator",
                position=mapped.positions[leading.start(1)],
            )
        )
        mapped = mapped.replace(0, leading.end())

    for quote in ("'", '"'):
        if mapped.text.count(quote) % 2 == 0:
            continue
        stripped = mapped.text.strip()
        match: Optional[re.Match[str]] = None
        if stripped.startswith(quote):
            match = re.match(
                rf"^\s*(?P<quote>{re.escape(quote)})\s*(?=[A-Za-z_])",
                mapped.text,
            )
        elif stripped.endswith(quote):
            match = re.search(
                rf"\s*(?P<quote>{re.escape(quote)})\s*$",
                mapped.text,
            )
        if match is None:
            continue
        repairs.append(
            SourceRepair(
                code="DANGLING_EDGE_QUOTE",
                message="removed dangling quote at the source boundary",
                position=mapped.positions[match.start("quote")],
            )
        )
        mapped = mapped.replace(match.start(), match.end())

    orphan_pattern = re.compile(r"(,\s*)([^,'\"\(\)\[\]\s]+)''(?=\s*,)")
    orphan_matches = list(orphan_pattern.finditer(mapped.text))
    for match in orphan_matches:
        repairs.append(
            SourceRepair(
                code="ORPHAN_LITERAL_QUOTED",
                message="quoted an orphan slot literal before an empty string",
                position=mapped.positions[match.start(2)],
            )
        )
    for match in reversed(orphan_matches):
        literal_start = match.start(2)
        literal_end = match.end(2)
        literal = mapped.text[literal_start:literal_end]
        replacement = f"'{literal}'"
        replacement_positions = (
            mapped.positions[literal_start],
            *mapped.positions[literal_start:literal_end],
            mapped.positions[literal_end],
        )
        mapped = mapped.replace(
            literal_start,
            literal_end + 2,
            replacement,
            replacement_positions,
        )

    _, removed_positions = _strip_unmatched_closing_parens_with_positions(mapped.text)
    for position in removed_positions:
        repairs.append(
            SourceRepair(
                code="UNMATCHED_CLOSING_PAREN",
                message="removed an unmatched closing parenthesis",
                position=mapped.positions[position],
            )
        )
    for position in reversed(removed_positions):
        mapped = mapped.replace(position, position + 1)
    return mapped.text.strip(), tuple(repairs)


def _sanitize_official_slot_source(source: str) -> str:
    normalized, _ = _normalize_official_slot_source(source)
    return normalized


def _strip_unmatched_closing_parens_with_positions(text: str) -> Tuple[str, List[int]]:
    depth = 0
    remove_positions = set()
    quote: Optional[str] = None
    escaped = False
    for index, ch in enumerate(text):
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in {"'", '"'}:
            quote = ch
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                remove_positions.add(index)
            else:
                depth -= 1
    if not remove_positions:
        return text, []
    ordered = sorted(remove_positions)
    return "".join(ch for index, ch in enumerate(text) if index not in remove_positions), ordered


def lex_official_slot(source: str) -> List[Token]:
    tokens: List[Token] = []
    i = 0
    while i < len(source):
        ch = source[i]
        if ch.isspace():
            i += 1
            continue
        if ch in {"'", '"'}:
            quote = ch
            start = i
            i += 1
            chars: List[str] = []
            while i < len(source):
                if source[i] == "\\":
                    if i + 1 >= len(source):
                        raise OfficialSlotError("OFFICIAL_LEX_ERROR", f"Unfinished escape at {i}")
                    chars.append(source[i + 1])
                    i += 2
                    continue
                if source[i] == quote:
                    tokens.append(Token("STRING", "".join(chars), start))
                    i += 1
                    break
                chars.append(source[i])
                i += 1
            else:
                raise OfficialSlotError("OFFICIAL_LEX_ERROR", f"Unclosed string starting at {start}")
            continue
        if ch.isdigit():
            start = i
            while i < len(source) and source[i].isdigit():
                i += 1
            if i < len(source) and source[i] == ".":
                i += 1
                while i < len(source) and source[i].isdigit():
                    i += 1
            if i < len(source) and source[i] == "%":
                i += 1
                tokens.append(Token("PERCENT", source[start:i], start))
            else:
                tokens.append(Token("NUMBER", source[start:i], start))
            continue
        if ch.isalpha() or ch == "_":
            start = i
            while i < len(source) and (source[i].isalnum() or source[i] == "_"):
                i += 1
            value = source[start:i]
            lower = value.lower()
            if lower in KEYWORDS:
                tokens.append(Token(lower.upper(), value, start))
            else:
                tokens.append(Token("IDENT", value, start))
            continue
        two = source[i : i + 2]
        if two in OPERATORS:
            tokens.append(Token(two, two, i))
            i += 2
            continue
        if ch in OPERATORS:
            tokens.append(Token(ch, ch, i))
            i += 1
            continue
        raise OfficialSlotError("OFFICIAL_LEX_ERROR", f"Unexpected character {ch!r} at {i}")
    tokens.append(Token("EOF", "", len(source)))
    return tokens


class OfficialSlotParser:
    def __init__(self, source: str, normalized_source: Optional[str] = None):
        self.source = source
        self.normalized_source = (
            _sanitize_official_slot_source(source)
            if normalized_source is None
            else normalized_source
        )
        self.tokens = lex_official_slot(self.normalized_source)
        self.index = 0

    def parse(self) -> OfficialNode:
        node = self._parse_limit()
        self._expect("EOF")
        return node

    def _peek(self) -> Token:
        return self.tokens[self.index]

    def _advance(self) -> Token:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def _match(self, *kinds: str) -> Optional[Token]:
        if self._peek().kind in kinds:
            return self._advance()
        return None

    def _expect(self, kind: str) -> Token:
        token = self._peek()
        if token.kind != kind:
            raise OfficialSlotError(
                "OFFICIAL_PARSE_ERROR", f"Expected {kind}, got {token.kind} at {token.position}"
            )
        return self._advance()

    def _parse_limit(self) -> OfficialNode:
        node = self._parse_then()
        if self._match("LIMIT"):
            lower = self._parse_int_literal()
            self._expect(",")
            upper = self._parse_int_literal()
            return OfficialLimit(node, lower, upper)
        return node

    def _parse_int_literal(self) -> int:
        sign = -1 if self._match("-") else 1
        if sign == 1:
            self._match("+")
        return sign * int(self._expect("NUMBER").value)

    def _parse_then(self) -> OfficialNode:
        node = self._parse_or()
        while self._match("THEN"):
            right = self._parse_or()
            node = OfficialBinaryOp("then", node, right)
        return node

    def _parse_or(self) -> OfficialNode:
        node = self._parse_and()
        while self._match("OR"):
            right = self._parse_and()
            node = OfficialBinaryOp("or", node, right)
        return node

    def _parse_and(self) -> OfficialNode:
        node = self._parse_comparison()
        while self._match("AND"):
            right = self._parse_comparison()
            node = OfficialBinaryOp("and", node, right)
        return node

    def _parse_comparison(self) -> OfficialNode:
        node = self._parse_additive()
        if self._match("BETWEEN"):
            right = self._parse_range_literal() or self._parse_additive()
            return OfficialComparison("between", node, right)
        token = self._match(">=", "<=", "!=", "~=", "=", ">", "<")
        if token:
            right = self._parse_additive()
            return OfficialComparison(token.kind, node, right)
        return node

    def _parse_additive(self) -> OfficialNode:
        node = self._parse_multiplicative()
        while True:
            token = self._match("+", "-")
            if not token:
                return node
            right = self._parse_multiplicative()
            node = OfficialBinaryOp(token.kind, node, right)

    def _parse_multiplicative(self) -> OfficialNode:
        node = self._parse_primary()
        while True:
            token = self._match("*", "/")
            if not token:
                return node
            right = self._parse_primary()
            node = OfficialBinaryOp(token.kind, node, right)

    def _parse_primary(self) -> OfficialNode:
        token = self._peek()
        if self._match("("):
            node = self._parse_then()
            self._expect(")")
            return node
        if token.kind == "STRING":
            self._advance()
            return OfficialLiteral(token.value)
        if token.kind == "PERCENT":
            self._advance()
            return OfficialLiteral(token.value)
        if token.kind == "NUMBER":
            self._advance()
            return OfficialLiteral(float(token.value) if "." in token.value else int(token.value))
        if token.kind == "TRUE":
            self._advance()
            return OfficialLiteral(True)
        if token.kind == "FALSE":
            self._advance()
            return OfficialLiteral(False)
        if token.kind in {"+", "-"} and self.tokens[self.index + 1].kind in {"NUMBER", "PERCENT"}:
            sign = -1 if self._advance().kind == "-" else 1
            next_token = self._advance()
            if next_token.kind == "PERCENT":
                prefix = "-" if sign < 0 else ""
                return OfficialLiteral(prefix + next_token.value)
            number: Any = float(next_token.value) if "." in next_token.value else int(next_token.value)
            return OfficialLiteral(sign * number)
        if token.kind == "IDENT":
            ident = self._advance().value
            if self._match("("):
                return self._parse_call(ident)
            return OfficialIdentifier(ident)
        raise OfficialSlotError("OFFICIAL_PARSE_ERROR", f"Unexpected token {token.kind} at {token.position}")

    def _parse_range_literal(self) -> Optional[OfficialRangeLiteral]:
        open_token = self._peek()
        if open_token.kind not in {"[", "("}:
            if open_token.kind == "STRING":
                parsed = _parse_range_text(open_token.value)
                if parsed:
                    self._advance()
                    return parsed
            return None
        self._advance()
        lower = self._parse_additive()
        self._expect(",")
        upper = self._parse_additive()
        close_token = self._peek()
        if close_token.kind not in {"]", ")"}:
            raise OfficialSlotError(
                "OFFICIAL_PARSE_ERROR",
                f"Expected range closing bracket, got {close_token.kind} at {close_token.position}",
            )
        self._advance()
        return OfficialRangeLiteral(
            lower=lower,
            upper=upper,
            lower_inclusive=open_token.kind == "[",
            upper_inclusive=close_token.kind == "]",
        )

    def _parse_call(self, name: str) -> OfficialFunctionCall:
        args: List[OfficialNode] = []
        if self._match(")"):
            return OfficialFunctionCall(name, args)
        while True:
            args.append(self._parse_then())
            if self._match(","):
                continue
            self._expect(")")
            return OfficialFunctionCall(name, args)


def parse_official_slot_with_diagnostics(
    source: str,
    mode: str = CompileMode.RECOVERY.value,
) -> OfficialParseResult:
    compile_mode = CompileMode.parse(mode)
    if compile_mode is CompileMode.STRICT:
        normalized_source = str(source or "")
        repairs: Tuple[SourceRepair, ...] = ()
    else:
        normalized_source, repairs = _normalize_official_slot_source(source)
    ast = OfficialSlotParser(source, normalized_source=normalized_source).parse()
    return OfficialParseResult(
        source=source,
        normalized_source=normalized_source,
        ast=ast,
        repairs=repairs,
    )


def parse_official_slot(source: str, mode: str = CompileMode.RECOVERY.value) -> OfficialNode:
    return parse_official_slot_with_diagnostics(source, mode=mode).ast


class OfficialSlotCompiler:
    def __init__(
        self,
        anchor_date: str = "2026-04-14",
        trading_dates: Optional[Sequence[str]] = None,
        mode: str = CompileMode.RECOVERY.value,
    ):
        self.anchor_date = anchor_date
        self.trading_dates = list(trading_dates or [])
        self.mode = CompileMode.parse(mode)
        self.technical_pattern_config = _load_technical_pattern_config()

    def compile(self, source: str) -> OfficialCompileResult:
        parsed = self._parse_for_compile(source)
        ast = parsed.ast
        from .official.semantics import OfficialSemanticAnalyzer

        OfficialSemanticAnalyzer(_resolve_indicator_meta).validate(ast)
        warnings = _CompilationWarnings()
        sql, tables = self._compile_query(ast, warnings)
        fallback_predicates = tuple(sorted(warnings.fallback_predicates))
        degraded = bool(parsed.repairs or warnings or fallback_predicates)
        if self.mode is CompileMode.STRICT and degraded:
            reasons: List[str] = []
            if parsed.repairs:
                reasons.append(f"source repairs={len(parsed.repairs)}")
            if warnings:
                reasons.append(f"warnings={len(warnings)}")
            if fallback_predicates:
                reasons.append(f"fallbacks={','.join(fallback_predicates)}")
            raise OfficialSlotError(
                "OFFICIAL_DEGRADED_SEMANTICS",
                "Strict official compilation rejected degraded semantics: " + ", ".join(reasons),
            )
        return OfficialCompileResult(
            source=source,
            normalized_source=parsed.normalized_source,
            ast=ast.to_dict(),
            sql=sql,
            requires_tables=tables,
            warnings=list(warnings),
            repairs=parsed.repairs,
            strict_success=not degraded,
            degraded=degraded,
            fallback_predicates=fallback_predicates,
        )

    def _parse_for_compile(self, source: str) -> OfficialParseResult:
        if self.mode is CompileMode.RECOVERY:
            return parse_official_slot_with_diagnostics(source, mode=self.mode.value)
        try:
            return parse_official_slot_with_diagnostics(source, mode=self.mode.value)
        except OfficialSlotError as strict_error:
            try:
                recovered = parse_official_slot_with_diagnostics(
                    source,
                    mode=CompileMode.RECOVERY.value,
                )
            except OfficialSlotError:
                raise strict_error
            if recovered.repairs:
                repair_codes = ", ".join(repair.code for repair in recovered.repairs)
                semantic_detail = ""
                try:
                    from .official.semantics import OfficialSemanticAnalyzer

                    OfficialSemanticAnalyzer(_resolve_indicator_meta).validate(recovered.ast)
                except OfficialSlotError as semantic_error:
                    semantic_detail = (
                        f"; recovered semantic error={semantic_error.code}: {semantic_error}"
                    )
                raise OfficialSlotError(
                    "OFFICIAL_DEGRADED_SEMANTICS",
                    f"Strict official compilation rejected source repairs: {repair_codes}{semantic_detail}",
                ) from strict_error
            raise strict_error

    def _compile_query(self, node: OfficialNode, warnings: List[str]) -> Tuple[str, List[str]]:
        if isinstance(node, OfficialLimit):
            inner_sql, tables = self._compile_query(node.expr, warnings)
            if node.upper >= 0:
                return f"{inner_sql}\nLIMIT {node.upper}", tables
            return inner_sql, tables
        if isinstance(node, OfficialBinaryOp) and node.op == "then":
            stages = self._flatten_then_chain(node)
            if len(stages) > 2:
                return self._compile_then_chain(stages, warnings)
            return self._compile_then(node, warnings)
        if isinstance(node, OfficialBinaryOp) and node.op == "or" and self._contains_then(node):
            return self._compile_or_union_query(node, warnings)
        if self._is_rank_filter_comparison(node):
            return self._compile_rank_query(node, None, warnings)
        condition = self._condition_sql(node, warnings)
        tables = self._ordered_tables(condition.tables)
        where = self._where_clause(condition)
        return self._select_sql(tables, where), tables

    def _compile_or_union_query(self, node: OfficialNode, warnings: List[str]) -> Tuple[str, List[str]]:
        branches = self._flatten_boolean_chain(node, "or")
        branch_sql: List[str] = []
        all_tables: List[str] = []
        for branch in branches:
            sql, tables = self._compile_query(branch, warnings)
            branch_sql.append(sql)
            all_tables.extend(tables)
        return "\nUNION\n".join(branch_sql), self._ordered_tables(all_tables)

    def _compile_then(self, node: OfficialBinaryOp, warnings: List[str]) -> Tuple[str, List[str]]:
        left = self._condition_sql(node.left, warnings)
        if self._is_rank_filter_comparison(node.right) and not (
            isinstance(node.right, OfficialComparison) and node.right.op == "between"
        ):
            return self._compile_rank_query(node.right, left, warnings)
        return self._compile_then_condition_stage(left, node.right, warnings)

    def _compile_then_condition_stage(
        self,
        prefilter: SqlExpr,
        right: OfficialNode,
        warnings: List[str],
    ) -> Tuple[str, List[str]]:
        stage_0_tables = self._ordered_tables(prefilter.tables + ["hsj_stock_code_info"])
        right_condition = self._then_condition_sql(right, "stage_0", warnings)
        stage_1_tables = self._ordered_tables(right_condition.tables + ["hsj_stock_code_info"])
        all_tables = self._ordered_tables(stage_0_tables + stage_1_tables)
        sql = (
            "WITH stage_0 AS (\n"
            f"{self._select_sql(stage_0_tables, self._where_clause(prefilter))}\n"
            "),\n"
            "stage_1 AS (\n"
            "  SELECT base.mktcode, base.tgtcode, base.bizdate, code.name\n"
            "  FROM stage_0 AS prev\n"
            "  INNER JOIN newzl.hsj_stock_hq_basic AS base "
            "ON base.mktcode = prev.mktcode "
            "AND base.tgtcode = prev.tgtcode "
            "AND base.bizdate = prev.bizdate\n"
            f"{self._joins(stage_1_tables)}"
            f"  WHERE {self._where_clause(right_condition)}\n"
            ")\n"
            "SELECT * FROM stage_1"
        )
        return sql, all_tables

    def _flatten_then_chain(self, node: OfficialNode) -> List[OfficialNode]:
        if isinstance(node, OfficialBinaryOp) and node.op == "then":
            return self._flatten_then_chain(node.left) + self._flatten_then_chain(node.right)
        return [node]

    def _flatten_boolean_chain(self, node: OfficialNode, op: str) -> List[OfficialNode]:
        if isinstance(node, OfficialBinaryOp) and node.op == op:
            return self._flatten_boolean_chain(node.left, op) + self._flatten_boolean_chain(node.right, op)
        return [node]

    def _contains_then(self, node: OfficialNode) -> bool:
        if isinstance(node, OfficialBinaryOp):
            if node.op == "then":
                return True
            return self._contains_then(node.left) or self._contains_then(node.right)
        if isinstance(node, OfficialComparison):
            return self._contains_then(node.left) or self._contains_then(node.right)
        if isinstance(node, OfficialLimit):
            return self._contains_then(node.expr)
        if isinstance(node, OfficialFunctionCall):
            return any(self._contains_then(arg) for arg in node.args)
        if isinstance(node, OfficialRangeLiteral):
            return self._contains_then(node.lower) or self._contains_then(node.upper)
        return False

    def _compile_then_chain(self, stages: Sequence[OfficialNode], warnings: List[str]) -> Tuple[str, List[str]]:
        if len(stages) < 2:
            raise OfficialSlotError("OFFICIAL_RANK_SHAPE_ERROR", "then pipeline requires a prefilter and rank stage")
        prefilter = self._condition_sql(stages[0], warnings)
        all_tables = self._ordered_tables(prefilter.tables + ["hsj_stock_code_info"])
        ctes = [
            (
                "stage_0 AS (\n"
                f"{self._select_sql(all_tables, self._where_clause(prefilter))}\n"
                ")"
            )
        ]
        previous = "stage_0"
        for stage_index, stage in enumerate(stages[1:], 1):
            if not self._is_rank_filter_comparison(stage):
                condition = self._then_condition_sql(stage, previous, warnings)
                stage_tables = self._ordered_tables(condition.tables + ["hsj_stock_code_info"])
                all_tables = self._ordered_tables(all_tables + stage_tables)
                ctes.append(
                    (
                        f"stage_{stage_index} AS (\n"
                        "  SELECT base.mktcode, base.tgtcode, base.bizdate, code.name\n"
                        f"  FROM {previous} AS prev\n"
                        "  INNER JOIN newzl.hsj_stock_hq_basic AS base "
                        "ON base.mktcode = prev.mktcode "
                        "AND base.tgtcode = prev.tgtcode "
                        "AND base.bizdate = prev.bizdate\n"
                        f"{self._joins(stage_tables)}"
                        f"  WHERE {self._where_clause(condition)}\n"
                        ")"
                    )
                )
                previous = f"stage_{stage_index}"
                continue
            assert isinstance(stage, OfficialComparison)
            rank_call = stage.left
            assert isinstance(rank_call, OfficialFunctionCall)
            if self._rank_count_exp(rank_call):
                raise OfficialSlotError(
                    "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                    "chained then rank(..., count_exp) needs a materialized temporal rank feature table",
                )
            if stage.op not in {"<=", "=", "<", ">", ">=", "!="}:
                raise OfficialSlotError("OFFICIAL_RANK_OPERATOR_ERROR", f"Unsupported rank comparison: {stage.op}")
            rank_expr = self._rank_expr(rank_call, warnings)
            stage_tables = self._ordered_tables(rank_expr.tables + ["hsj_stock_code_info"])
            all_tables = self._ordered_tables(all_tables + stage_tables)
            where = " AND ".join(_dedupe(rank_expr.constraints)) or "1=1"
            joins = self._joins(stage_tables)
            limit_value = self._literal_sql(stage.right)
            rank_limit = f"ranked_{stage_index}.rank_no {self._sql_operator(stage.op)} {limit_value}"
            ctes.append(
                (
                    f"stage_{stage_index} AS (\n"
                    f"  SELECT ranked_{stage_index}.mktcode, ranked_{stage_index}.tgtcode, "
                    f"ranked_{stage_index}.bizdate, ranked_{stage_index}.name\n"
                    "  FROM (\n"
                    f"    SELECT prev.mktcode, prev.tgtcode, prev.bizdate, prev.name,\n"
                    f"           ROW_NUMBER() OVER (PARTITION BY prev.bizdate ORDER BY {rank_expr.sql} "
                    f"{self._rank_order(rank_call)}, prev.tgtcode ASC) AS rank_no\n"
                    f"    FROM {previous} AS prev\n"
                    "    INNER JOIN newzl.hsj_stock_hq_basic AS base "
                    "ON base.mktcode = prev.mktcode "
                    "AND base.tgtcode = prev.tgtcode "
                    "AND base.bizdate = prev.bizdate\n"
                    f"{joins}"
                    f"    WHERE {where}\n"
                    f"  ) AS ranked_{stage_index}\n"
                    f"  WHERE {rank_limit}\n"
                    ")"
                )
            )
            previous = f"stage_{stage_index}"
        sql = "WITH " + ",\n".join(ctes) + f"\nSELECT * FROM {previous}"
        return sql, all_tables

    def _compile_rank_query(
        self, node: OfficialNode, prefilter: Optional[SqlExpr], warnings: List[str]
    ) -> Tuple[str, List[str]]:
        if not isinstance(node, OfficialComparison) or not isinstance(node.left, OfficialFunctionCall):
            raise OfficialSlotError("OFFICIAL_RANK_SHAPE_ERROR", "then right side must be rank(...) comparison")
        rank_call = node.left
        if rank_call.name != "rank":
            raise OfficialSlotError("OFFICIAL_RANK_SHAPE_ERROR", "then right side must start with rank(...)")
        if self._rank_count_exp(rank_call):
            condition = self._rank_count_condition_sql(node, prefilter, warnings)
            tables = self._ordered_tables(condition.tables)
            where = self._where_clause(condition)
            return self._select_sql(tables, where), tables
        rank_expr = self._rank_expr(rank_call, warnings)
        if node.op not in {"<=", "=", "<", ">", ">=", "!=", "between"}:
            raise OfficialSlotError("OFFICIAL_RANK_OPERATOR_ERROR", f"Unsupported rank comparison: {node.op}")
        tables = self._ordered_tables(rank_expr.tables + (prefilter.tables if prefilter else []))
        constraints = rank_expr.constraints + (prefilter.constraints if prefilter else [])
        where_parts = []
        if prefilter:
            where_parts.append(prefilter.sql)
        where_parts.extend(constraints)
        where = " AND ".join(_dedupe(where_parts)) or "1=1"
        joins = self._joins(tables)
        sql = (
            "SELECT * FROM (\n"
            "  SELECT base.mktcode, base.tgtcode, base.bizdate, code.name,\n"
            f"         ROW_NUMBER() OVER (PARTITION BY base.bizdate ORDER BY {rank_expr.sql} {self._rank_order(rank_call)}, base.tgtcode ASC) AS rank_no,\n"
            "         COUNT(*) OVER (PARTITION BY base.bizdate) AS partition_count\n"
            "  FROM newzl.hsj_stock_hq_basic AS base\n"
            f"{joins}"
            f"  WHERE {where}\n"
            ") AS ranked\n"
            f"WHERE {self._rank_no_predicate(node, 'ranked.rank_no', 'ranked.partition_count')}"
        )
        return sql, tables

    def _then_condition_sql(self, node: OfficialNode, rank_scope: str, warnings: List[str]) -> SqlExpr:
        if isinstance(node, OfficialBinaryOp) and node.op in {"and", "or"}:
            left = self._then_condition_sql(node.left, rank_scope, warnings)
            right = self._then_condition_sql(node.right, rank_scope, warnings)
            if node.op == "or":
                return SqlExpr(
                    sql=f"({self._condition_with_constraints(left)} OR {self._condition_with_constraints(right)})",
                    kind="boolean",
                    tables=left.tables + right.tables,
                    constraints=[],
                )
            return SqlExpr(
                sql=f"({left.sql} AND {right.sql})",
                kind="boolean",
                tables=left.tables + right.tables,
                constraints=left.constraints + right.constraints,
            )
        if self._is_rank_comparison(node):
            return self._then_rank_condition_sql(node, rank_scope, warnings)
        return self._condition_sql(node, warnings)

    def _then_rank_condition_sql(
        self,
        node: OfficialNode,
        rank_scope: str,
        warnings: List[str],
    ) -> SqlExpr:
        if not isinstance(node, OfficialComparison) or not isinstance(node.left, OfficialFunctionCall):
            raise OfficialSlotError("OFFICIAL_RANK_SHAPE_ERROR", "then rank stage must be rank(...) comparison")
        rank_call = node.left
        if self._rank_count_exp(rank_call):
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                "then rank(..., count_exp) inside composite conditions needs a materialized temporal rank feature table",
            )
        rank_expr = self._rank_expr(rank_call, warnings)
        rank_sql = _rank_alias_sql(rank_expr.sql)
        constraints = [_rank_alias_sql(item) for item in rank_expr.constraints]
        where = " AND ".join(_dedupe(constraints)) or "1=1"
        tables = self._ordered_tables(rank_expr.tables)
        joins = self._joins_for_aliases(tables, "rb", "rcode", "rext")
        predicate = self._rank_no_predicate(node, "ranked.rank_no")
        sql = (
            "EXISTS (\n"
            "  SELECT 1 FROM (\n"
            "    SELECT rb.mktcode, rb.tgtcode, rb.bizdate,\n"
            f"           ROW_NUMBER() OVER (PARTITION BY rb.bizdate ORDER BY {rank_sql} {self._rank_order(rank_call)}, rb.tgtcode ASC) AS rank_no\n"
            f"    FROM {rank_scope} AS prev_rank\n"
            "    INNER JOIN newzl.hsj_stock_hq_basic AS rb "
            "ON rb.mktcode = prev_rank.mktcode "
            "AND rb.tgtcode = prev_rank.tgtcode "
            "AND rb.bizdate = prev_rank.bizdate\n"
            f"{joins}"
            f"    WHERE {where}\n"
            "  ) AS ranked\n"
            "  WHERE ranked.mktcode = base.mktcode\n"
            "    AND ranked.tgtcode = base.tgtcode\n"
            "    AND ranked.bizdate = base.bizdate\n"
            f"    AND {predicate}\n"
            ")"
        )
        return SqlExpr(sql=sql, kind="boolean", tables=["hsj_stock_hq_basic"], constraints=[])

    def _rank_no_predicate(
        self,
        node: OfficialComparison,
        rank_no_sql: str,
        partition_count_sql: str = "",
    ) -> str:
        if node.op == "between":
            if not isinstance(node.right, OfficialRangeLiteral):
                right = self._expr_sql(node.right, [])
                return f"{rank_no_sql} BETWEEN {right.sql}"
            lower = self._rank_bound_sql(node.right.lower, partition_count_sql)
            upper = self._rank_bound_sql(node.right.upper, partition_count_sql)
            lower_op = ">=" if node.right.lower_inclusive else ">"
            upper_op = "<=" if node.right.upper_inclusive else "<"
            return f"({rank_no_sql} {lower_op} {lower} AND {rank_no_sql} {upper_op} {upper})"
        if node.op not in {"<=", "=", "<", ">", ">=", "!=", "~="}:
            raise OfficialSlotError("OFFICIAL_RANK_OPERATOR_ERROR", f"Unsupported rank comparison: {node.op}")
        limit_value = self._rank_bound_sql(node.right, partition_count_sql)
        return f"{rank_no_sql} {self._sql_operator(node.op)} {limit_value}"

    def _rank_bound_sql(self, node: OfficialNode, partition_count_sql: str = "") -> str:
        if (
            partition_count_sql
            and isinstance(node, OfficialLiteral)
            and isinstance(node.value, str)
            and _is_numeric_percent_literal(node.value)
        ):
            percent = node.value[:-1]
            return f"CEIL(({partition_count_sql} * {percent}) / 100.0)"
        if isinstance(node, OfficialLiteral) and not isinstance(node.value, bool):
            if isinstance(node.value, (int, float)):
                return self._literal_sql(node)
            if isinstance(node.value, str) and _is_numeric_percent_literal(node.value):
                return node.value[:-1]
        raise OfficialSlotError(
            "OFFICIAL_RANK_BOUND_ERROR",
            "rank comparison bound must be a numeric or percentage literal",
        )

    def _condition_sql(self, node: OfficialNode, warnings: List[str]) -> SqlExpr:
        if isinstance(node, OfficialBinaryOp) and node.op == "then":
            return self._then_membership_condition_sql(node, warnings)
        if isinstance(node, OfficialBinaryOp) and node.op in {"and", "or"}:
            left = self._condition_sql(node.left, warnings)
            right = self._condition_sql(node.right, warnings)
            if node.op == "or":
                return SqlExpr(
                    sql=f"({self._condition_with_constraints(left)} OR {self._condition_with_constraints(right)})",
                    kind="boolean",
                    tables=left.tables + right.tables,
                    constraints=[],
                )
            if self._has_conflicting_date_constraints(left, right):
                return SqlExpr(
                    sql=f"({self._condition_as_correlated_exists(left)} AND {self._condition_as_correlated_exists(right)})",
                    kind="boolean",
                    tables=["hsj_stock_hq_basic"],
                    constraints=[],
                    date_localized=True,
                )
            if left.date_localized or right.date_localized:
                left_sql = left.sql if left.date_localized else self._condition_as_correlated_exists(left)
                right_sql = right.sql if right.date_localized else self._condition_as_correlated_exists(right)
                return SqlExpr(
                    sql=f"({left_sql} AND {right_sql})",
                    kind="boolean",
                    tables=["hsj_stock_hq_basic"],
                    constraints=[],
                    date_localized=True,
                )
            return SqlExpr(
                sql=f"({left.sql} AND {right.sql})",
                kind="boolean",
                tables=left.tables + right.tables,
                constraints=left.constraints + right.constraints,
            )
        if self._is_rank_filter_comparison(node):
            return self._rank_condition_sql(node, warnings)
        if isinstance(node, OfficialComparison):
            return self._comparison_sql(node, warnings)
        expr = self._expr_sql(node, warnings)
        if expr.kind == "boolean":
            return expr
        raise OfficialSlotError("OFFICIAL_CONDITION_ERROR", "Top-level official DSL expression must be boolean")

    def _then_membership_condition_sql(self, node: OfficialBinaryOp, warnings: List[str]) -> SqlExpr:
        sql, tables = self._compile_query(node, warnings)
        if sql.lstrip().upper().startswith("WITH "):
            raise OfficialSlotError(
                "OFFICIAL_EXPR_ERROR",
                "then chain inside boolean conditions needs top-level query planning",
            )
        membership_sql = (
            "EXISTS (\n"
            "  SELECT 1\n"
            "  FROM (\n"
            f"{sql}\n"
            "  ) AS then_result\n"
            "  WHERE then_result.mktcode = base.mktcode\n"
            "    AND then_result.tgtcode = base.tgtcode\n"
            "    AND then_result.bizdate = base.bizdate\n"
            ")"
        )
        return SqlExpr(membership_sql, "boolean", tables, [])

    def _rank_condition_sql(self, node: OfficialNode, warnings: List[str]) -> SqlExpr:
        if not isinstance(node, OfficialComparison) or not isinstance(node.left, OfficialFunctionCall):
            raise OfficialSlotError("OFFICIAL_RANK_SHAPE_ERROR", "rank condition must be rank(...) comparison")
        rank_call = node.left
        if self._rank_count_exp(rank_call):
            return self._rank_count_condition_sql(node, None, warnings)
        rank_expr = self._rank_expr(rank_call, warnings)
        if node.op not in {"<=", "=", "<", ">", ">=", "!=", "between"}:
            raise OfficialSlotError("OFFICIAL_RANK_OPERATOR_ERROR", f"Unsupported rank comparison: {node.op}")
        rank_sql = _rank_alias_sql(rank_expr.sql)
        constraints = [_rank_alias_sql(item) for item in rank_expr.constraints]
        where = " AND ".join(_dedupe(constraints)) or "1=1"
        tables = self._ordered_tables(rank_expr.tables)
        joins = self._joins_for_aliases(tables, "rb", "rcode", "rext")
        sql = (
            "EXISTS (\n"
            "  SELECT 1 FROM (\n"
            "    SELECT rb.mktcode, rb.tgtcode, rb.bizdate,\n"
            f"           ROW_NUMBER() OVER (PARTITION BY rb.bizdate ORDER BY {rank_sql} {self._rank_order(rank_call)}, rb.tgtcode ASC) AS rank_no,\n"
            "           COUNT(*) OVER (PARTITION BY rb.bizdate) AS partition_count\n"
            "    FROM newzl.hsj_stock_hq_basic AS rb\n"
            f"{joins}"
            f"    WHERE {where}\n"
            "  ) AS ranked\n"
            "  WHERE ranked.mktcode = base.mktcode\n"
            "    AND ranked.tgtcode = base.tgtcode\n"
            "    AND ranked.bizdate = base.bizdate\n"
            f"    AND {self._rank_no_predicate(node, 'ranked.rank_no', 'ranked.partition_count')}\n"
            ")"
        )
        return SqlExpr(sql=sql, kind="boolean", tables=["hsj_stock_hq_basic"], constraints=[])

    def _rank_count_condition_sql(
        self,
        node: OfficialComparison,
        prefilter: Optional[SqlExpr],
        warnings: List[str],
    ) -> SqlExpr:
        rank_call = node.left
        if not isinstance(rank_call, OfficialFunctionCall) or rank_call.name != "rank":
            raise OfficialSlotError("OFFICIAL_RANK_SHAPE_ERROR", "rank count condition must start with rank(...)")
        if node.op not in {"<=", "=", "<", ">", ">=", "!=", "between"}:
            raise OfficialSlotError("OFFICIAL_RANK_OPERATOR_ERROR", f"Unsupported rank comparison: {node.op}")
        args = self._slot_args(rank_call, 8)
        market, filter_scope, indicator_name, direction, date, select_type, agg_func, count_exp = args[:8]
        if agg_func:
            return self._rank_aggregate_count_condition_sql(node, prefilter, warnings)
        if not indicator_name:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                "rank(..., count_exp) requires a grounded numeric indicator",
            )
        rule = _parse_count_exp_rule(count_exp)
        rank_expr = self._rank_expr_without_count_exp(rank_call, warnings)
        if rank_expr.kind not in {"numeric", "time"}:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                f"rank(..., count_exp) is only grounded for numeric/time indicators, got {rank_expr.kind}",
            )
        rank_sql = _rank_alias_sql(rank_expr.sql)
        constraints = [_rank_alias_sql(item) for item in rank_expr.constraints]
        tables = self._ordered_tables(rank_expr.tables + (prefilter.tables if prefilter else []))
        if prefilter:
            aliases = {"base": "rb", "code": "rcode", "ext": "rext", "tech": "rtech"}
            constraints.append(_rewrite_aliases(prefilter.sql, aliases))
            constraints.extend(_rewrite_aliases(item, aliases) for item in prefilter.constraints)
        where = " AND ".join(_dedupe(constraints)) or "1=1"
        bucket_expr = self._bucket_expr("rb", rule)
        joins = self._joins_for_aliases(tables, "rb", "rcode", "rext")
        predicate = self._rank_no_predicate(node, "ranked.rank_no", "ranked.partition_count")
        ranked_sql = (
            "SELECT rb.mktcode, rb.tgtcode,\n"
            f"       {bucket_expr} AS bucket_key,\n"
            f"       ROW_NUMBER() OVER (PARTITION BY {bucket_expr} ORDER BY {rank_sql} {self._rank_order(rank_call)}, rb.tgtcode ASC) AS rank_no,\n"
            f"       COUNT(*) OVER (PARTITION BY {bucket_expr}) AS partition_count\n"
            "FROM newzl.hsj_stock_hq_basic AS rb\n"
            f"{joins}"
            f"WHERE {where}"
        )
        if rule.every:
            subquery = (
                "(SELECT COUNT(*) > 0 AND "
                f"SUM(CASE WHEN {predicate} THEN 1 ELSE 0 END) = COUNT(*)\n"
                " FROM (\n"
                f"{ranked_sql}\n"
                ") AS ranked\n"
                " WHERE ranked.mktcode = base.mktcode AND ranked.tgtcode = base.tgtcode)"
            )
        else:
            threshold = 1 if rule.count is None else rule.count
            comparator = rule.operator or (">" if rule.mode == "EXIST" else ">=")
            subquery = (
                "(SELECT COUNT(*)\n"
                " FROM (\n"
                f"{ranked_sql}\n"
                ") AS ranked\n"
                " WHERE ranked.mktcode = base.mktcode\n"
                "   AND ranked.tgtcode = base.tgtcode\n"
                f"   AND {predicate}) "
                f"{self._sql_operator(comparator)} {threshold}"
            )
        return SqlExpr(
            subquery,
            "boolean",
            ["hsj_stock_hq_basic"],
            self._outer_snapshot_constraints(date),
        )

    def _rank_aggregate_count_condition_sql(
        self,
        node: OfficialComparison,
        prefilter: Optional[SqlExpr],
        warnings: List[str],
    ) -> SqlExpr:
        rank_call = node.left
        if not isinstance(rank_call, OfficialFunctionCall):
            raise OfficialSlotError("OFFICIAL_RANK_SHAPE_ERROR", "rank aggregate condition must start with rank(...)")
        args = self._slot_args(rank_call, 8)
        market, filter_scope, indicator_name, direction, date, select_type, agg_func, count_exp = args[:8]
        if not indicator_name:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                "rank(..., agg_func, count_exp) requires a grounded numeric indicator",
            )
        agg = agg_func.upper()
        if agg not in AGGREGATE_FUNCTIONS and agg not in GROWTH_FUNCTIONS:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_AGG_FUNC",
                f"Unsupported rank aggregate function for real-data SQL: {agg_func}",
            )
        rule = _parse_count_exp_rule(count_exp)
        meta = _resolve_indicator_meta(indicator_name)
        if not meta:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_INDICATOR",
                f"Official indicator is not mapped to the provided three-table dataset: {indicator_name}",
            )
        if meta.kind not in {"numeric", "time"}:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                f"rank(..., agg_func, count_exp) is only grounded for numeric/time indicators, got {meta.kind}",
            )
        aliases = {"base": "rb", "code": "rcode", "ext": "rext", "tech": "rtech"}
        value_sql = self._indicator_value_sql(meta, aliases)
        tables = self._ordered_tables(["hsj_stock_hq_basic", meta.table] + (prefilter.tables if prefilter else []))
        constraints = [
            _rewrite_aliases(item, aliases)
            for item in self._slot_constraints(market, filter_scope, date, select_type, warnings)
        ]
        if prefilter:
            constraints.append(_rewrite_aliases(prefilter.sql, aliases))
            constraints.extend(_rewrite_aliases(item, aliases) for item in prefilter.constraints)
        where = " AND ".join(_dedupe(constraints)) or "1=1"
        bucket_expr = self._bucket_expr("rb", rule)
        agg_value = self._aggregate_value_sql(agg, value_sql, "rb")
        joins = self._joins_for_aliases(tables, "rb", "rcode", "rext", "rtech")
        bucketed_sql = (
            "SELECT rb.mktcode, rb.tgtcode,\n"
            f"       {bucket_expr} AS bucket_key,\n"
            f"       {agg_value} AS agg_value\n"
            "FROM newzl.hsj_stock_hq_basic AS rb\n"
            f"{joins}"
            f"WHERE {where}\n"
            f"GROUP BY rb.mktcode, rb.tgtcode, {bucket_expr}"
        )
        ranked_sql = (
            "SELECT bucketed.mktcode, bucketed.tgtcode, bucketed.bucket_key,\n"
            f"       ROW_NUMBER() OVER (PARTITION BY bucketed.bucket_key ORDER BY bucketed.agg_value {self._rank_order(rank_call)}, bucketed.tgtcode ASC) AS rank_no,\n"
            "       COUNT(*) OVER (PARTITION BY bucketed.bucket_key) AS partition_count\n"
            "FROM (\n"
            f"{bucketed_sql}\n"
            ") AS bucketed\n"
            "WHERE bucketed.agg_value IS NOT NULL"
        )
        predicate = self._rank_no_predicate(node, "ranked.rank_no", "ranked.partition_count")
        if rule.every:
            subquery = (
                "(SELECT COUNT(*) > 0 AND "
                f"SUM(CASE WHEN {predicate} THEN 1 ELSE 0 END) = COUNT(*)\n"
                " FROM (\n"
                f"{ranked_sql}\n"
                ") AS ranked\n"
                " WHERE ranked.mktcode = base.mktcode AND ranked.tgtcode = base.tgtcode)"
            )
        else:
            threshold = 1 if rule.count is None else rule.count
            comparator = rule.operator or (">" if rule.mode == "EXIST" else ">=")
            subquery = (
                "(SELECT COUNT(*)\n"
                " FROM (\n"
                f"{ranked_sql}\n"
                ") AS ranked\n"
                " WHERE ranked.mktcode = base.mktcode\n"
                "   AND ranked.tgtcode = base.tgtcode\n"
                f"   AND {predicate}) "
                f"{self._sql_operator(comparator)} {threshold}"
            )
        return SqlExpr(
            subquery,
            "boolean",
            ["hsj_stock_hq_basic"],
            self._outer_snapshot_constraints(date),
        )

    def _aggregate_value_sql(self, agg: str, value_sql: str, base_alias: str) -> str:
        if agg in GROWTH_FUNCTIONS:
            first_value = f"MIN_BY({value_sql}, {base_alias}.bizdate)"
            last_value = f"MAX_BY({value_sql}, {base_alias}.bizdate)"
            delta = f"({last_value} - {first_value})" if agg == "GROWTH_RISE" else f"({first_value} - {last_value})"
            return f"({delta} * 100.0 / NULLIF(ABS({first_value}), 0))"
        return f"{agg}({value_sql})"

    def _comparison_sql(self, node: OfficialComparison, warnings: List[str]) -> SqlExpr:
        if isinstance(node.left, OfficialFunctionCall) and node.left.name == "indicator":
            args = self._slot_args(node.left, 7)
            if args[6] and args[5]:
                return self._count_exp_comparison_sql(node.left, node.op, node.right, warnings)
        if isinstance(node.left, OfficialFunctionCall) and node.left.name in {"cross_above", "cross_down", "golden_cross"}:
            args = self._slot_args(node.left, 7)
            if args[6]:
                return self._cross_count_exp_comparison_sql(node.left, node.op, node.right, warnings)
        if isinstance(node.left, OfficialFunctionCall) and node.left.name in {"reset", "close_together"}:
            args = self._slot_args(node.left, 7)
            if args[6]:
                return self._pattern_count_exp_comparison_sql(node.left, node.op, node.right, warnings)
        if self._comparison_has_grounded_count_exp(node):
            return self._count_exp_expression_comparison_sql(node, warnings)
        left = self._expr_sql(node.left, warnings)
        if node.op == "between":
            if not isinstance(node.right, OfficialRangeLiteral):
                right = self._expr_sql(node.right, warnings)
                return SqlExpr(
                    sql=f"{left.sql} BETWEEN {right.sql}",
                    kind="boolean",
                    tables=left.tables + right.tables,
                    constraints=left.constraints + right.constraints,
                )
            lower = self._expr_sql(node.right.lower, warnings)
            upper = self._expr_sql(node.right.upper, warnings)
            lower_op = ">=" if node.right.lower_inclusive else ">"
            upper_op = "<=" if node.right.upper_inclusive else "<"
            return SqlExpr(
                sql=f"({left.sql} {lower_op} {lower.sql} AND {left.sql} {upper_op} {upper.sql})",
                kind="boolean",
                tables=left.tables + lower.tables + upper.tables,
                constraints=left.constraints + lower.constraints + upper.constraints,
            )
        right = self._expr_sql(node.right, warnings)
        sql = self._comparison_predicate_sql(left.sql, left.kind, node.op, node.right, right.sql)
        return SqlExpr(
            sql=sql,
            kind="boolean",
            tables=left.tables + right.tables,
            constraints=left.constraints + right.constraints,
        )

    def _comparison_has_grounded_count_exp(self, node: OfficialComparison) -> bool:
        return bool(self._count_exp_specs_from_node(node))

    def _count_exp_expression_comparison_sql(self, node: OfficialComparison, warnings: List[str]) -> SqlExpr:
        specs = self._count_exp_specs_from_node(node)
        if not specs:
            raise OfficialSlotError("UNSUPPORTED_OFFICIAL_COUNT_EXP", "count_exp comparison has no grounded count slot")
        first = specs[0]
        first_scope = self._count_exp_scope_key(first)
        for spec in specs[1:]:
            if spec.count_exp != first.count_exp:
                raise OfficialSlotError(
                    "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                    "mixed count_exp values inside one comparison need an explicit temporal feature table",
                )
            if self._count_exp_scope_key(spec) != first_scope:
                raise OfficialSlotError(
                    "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                    "mixed market/filter/date/select scopes inside one count_exp comparison are not grounded",
                )
        rule = _parse_count_exp_rule(first.count_exp)
        if any(spec.agg_func for spec in specs):
            return self._aggregate_count_exp_expression_comparison_sql(node, first, rule, warnings)
        aliases = {"base": "wb", "code": "wc", "ext": "we", "tech": "wt"}
        predicate, predicate_tables, predicate_constraints = self._comparison_predicate_with_aliases(
            node,
            aliases,
            warnings,
        )
        tables = self._ordered_tables(["hsj_stock_hq_basic"] + predicate_tables)
        where_parts = self._window_correlated_where(first.date, "wb", warnings)
        where_parts.extend(_rewrite_aliases(item, aliases) for item in predicate_constraints)
        from_sql = (
            "FROM newzl.hsj_stock_hq_basic AS wb\n"
            f"{self._joins_for_aliases(tables, 'wb', 'wc', 'we', 'wt')}"
        )
        subquery = self._count_exp_predicate_subquery(
            from_sql=from_sql,
            where_parts=where_parts,
            predicate=predicate,
            rule=rule,
            base_alias="wb",
        )
        constraints = self._slot_constraints(first.market, first.filter_scope, "", first.select_type, warnings)
        constraints.extend(self._outer_snapshot_constraints(first.date))
        return SqlExpr(subquery, "boolean", tables, constraints)

    def _aggregate_count_exp_expression_comparison_sql(
        self,
        node: OfficialComparison,
        first: CountExpSpec,
        rule: CountExpRule,
        warnings: List[str],
    ) -> SqlExpr:
        if (rule.unit or "日") != "日":
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                "aggregate count_exp arithmetic expressions are only grounded for daily buckets",
            )
        aliases = {"base": "wb", "code": "wc", "ext": "we", "tech": "wt"}
        aggregate_columns: Dict[Tuple[str, ...], str] = {}
        value_columns: Dict[Tuple[str, ...], str] = {}
        aggregate_selects: List[str] = []
        value_selects: List[str] = []
        tables: List[str] = ["hsj_stock_hq_basic"]

        def indicator_bucket_expr(call: OfficialFunctionCall) -> SqlExpr:
            args = self._slot_args(call, 7)
            market, filter_scope, indicator_name, date, select_type, agg_func, count_exp = args[:7]
            if not indicator_name:
                raise OfficialSlotError(
                    "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                    "aggregate count_exp arithmetic expressions require grounded indicators",
                )
            candidate = CountExpSpec(first.count_exp, market, filter_scope, date, select_type, agg_func)
            if self._count_exp_scope_key(candidate) != self._count_exp_scope_key(first):
                raise OfficialSlotError(
                    "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                    "aggregate count_exp arithmetic expressions require one market/filter/date/select scope",
                )
            meta = _resolve_indicator_meta(indicator_name)
            if not meta:
                raise OfficialSlotError(
                    "UNSUPPORTED_OFFICIAL_INDICATOR",
                    f"Official indicator is not mapped to the provided three-table dataset: {indicator_name}",
                )
            if meta.kind not in {"numeric", "time"}:
                raise OfficialSlotError(
                    "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                    f"aggregate count_exp arithmetic expressions require numeric/time indicators, got {meta.kind}",
                )
            tables.append(meta.table)
            value_sql = self._indicator_value_sql(meta, aliases)
            key = tuple(args)
            if count_exp:
                if count_exp != first.count_exp or not agg_func:
                    raise OfficialSlotError(
                        "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                        "mixed aggregate and non-aggregate count_exp expressions are not yet grounded",
                    )
                agg = agg_func.upper()
                if agg in GROWTH_FUNCTIONS:
                    raise OfficialSlotError(
                        "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                        "growth aggregate count_exp arithmetic expressions need lag-aware bucket rows",
                    )
                if agg not in AGGREGATE_FUNCTIONS:
                    raise OfficialSlotError(
                        "UNSUPPORTED_OFFICIAL_AGG_FUNC",
                        f"Unsupported official aggregate function for real-data SQL: {agg_func}",
                    )
                alias = aggregate_columns.get(key)
                if not alias:
                    alias = f"agg_{len(aggregate_columns)}"
                    aggregate_columns[key] = alias
                    aggregate_selects.append(f"       {agg}({value_sql}) AS {alias}")
                return SqlExpr(f"bucketed.{alias}", meta.kind, [meta.table], [])
            if agg_func:
                raise OfficialSlotError(
                    "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                    "ordinary aggregate indicators inside aggregate count_exp expressions need explicit count_exp",
                )
            alias = value_columns.get(key)
            if not alias:
                alias = f"value_{len(value_columns)}"
                value_columns[key] = alias
                value_selects.append(f"       MAX({value_sql}) AS {alias}")
            return SqlExpr(f"bucketed.{alias}", meta.kind, [meta.table], [])

        def bucket_expr(node_part: OfficialNode) -> SqlExpr:
            if isinstance(node_part, OfficialLiteral):
                return self._expr_sql(node_part, warnings)
            if isinstance(node_part, OfficialBinaryOp) and node_part.op in {"+", "-", "*", "/"}:
                left = bucket_expr(node_part.left)
                right = bucket_expr(node_part.right)
                return SqlExpr(
                    f"({left.sql} {node_part.op} {right.sql})",
                    "numeric",
                    left.tables + right.tables,
                    [],
                )
            if isinstance(node_part, OfficialFunctionCall) and node_part.name == "indicator":
                return indicator_bucket_expr(node_part)
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                f"Unsupported aggregate count_exp arithmetic expression node: {type(node_part).__name__}",
            )

        left = bucket_expr(node.left)
        if node.op == "between":
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                "between with aggregate count_exp arithmetic expressions is not yet grounded",
            )
        right = bucket_expr(node.right)
        if not aggregate_selects:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                "aggregate count_exp arithmetic comparison has no aggregate bucket expression",
            )
        predicate = self._comparison_predicate_sql(left.sql, left.kind, node.op, node.right, right.sql)
        table_list = self._ordered_tables(tables + left.tables + right.tables)
        bucket_key = self._bucket_expr("wb", rule)
        where_parts = self._window_correlated_where(first.date, "wb", warnings)
        inner_sql = (
            f"SELECT {bucket_key} AS bucket_key,\n"
            + ",\n".join(aggregate_selects + value_selects)
            + "\n"
            " FROM newzl.hsj_stock_hq_basic AS wb\n"
            f"{self._window_joins(table_list)}"
            f" WHERE {' AND '.join(_dedupe(where_parts))}\n"
            f" GROUP BY {bucket_key}"
        )
        subquery = self._count_bucketed_predicate_sql(inner_sql, predicate, rule)
        constraints = self._slot_constraints(first.market, first.filter_scope, "", first.select_type, warnings)
        constraints.extend(self._outer_snapshot_constraints(first.date))
        return SqlExpr(subquery, "boolean", table_list, constraints)

    def _count_exp_scope_key(self, spec: CountExpSpec) -> Tuple[str, str, Any, str]:
        date_key: Any = spec.date
        if spec.date:
            normalized = normalize_official_date(
                spec.date,
                anchor_date=self.anchor_date,
                trading_dates=self.trading_dates,
                field="wb.bizdate",
            )
            if normalized.constraints and normalized.constraints != ["1=1"] and not normalized.warnings:
                date_key = tuple(normalized.constraints)
        return (spec.market, spec.filter_scope, date_key, spec.select_type)

    def _comparison_predicate_with_aliases(
        self,
        node: OfficialComparison,
        aliases: Dict[str, str],
        warnings: List[str],
    ) -> Tuple[str, List[str], List[str]]:
        left = self._expr_sql_with_aliases(node.left, aliases, warnings)
        if node.op == "between":
            if not isinstance(node.right, OfficialRangeLiteral):
                right = self._expr_sql_with_aliases(node.right, aliases, warnings)
                return (
                    f"{left.sql} BETWEEN {right.sql}",
                    left.tables + right.tables,
                    left.constraints + right.constraints,
                )
            lower = self._expr_sql_with_aliases(node.right.lower, aliases, warnings)
            upper = self._expr_sql_with_aliases(node.right.upper, aliases, warnings)
            lower_op = ">=" if node.right.lower_inclusive else ">"
            upper_op = "<=" if node.right.upper_inclusive else "<"
            return (
                f"({left.sql} {lower_op} {lower.sql} AND {left.sql} {upper_op} {upper.sql})",
                left.tables + lower.tables + upper.tables,
                left.constraints + lower.constraints + upper.constraints,
            )
        right = self._expr_sql_with_aliases(node.right, aliases, warnings)
        return (
            self._comparison_predicate_sql(left.sql, left.kind, node.op, node.right, right.sql),
            left.tables + right.tables,
            left.constraints + right.constraints,
        )

    def _expr_sql_with_aliases(
        self,
        node: OfficialNode,
        aliases: Dict[str, str],
        warnings: List[str],
    ) -> SqlExpr:
        if isinstance(node, OfficialFunctionCall) and node.name in {"record_high", "record_low", "position"}:
            return self._period_feature_expr_for_aliases(node, aliases, warnings)
        stripped = self._strip_count_exp(node)
        expr = self._expr_sql(stripped, warnings)
        return SqlExpr(
            _rewrite_aliases(expr.sql, aliases),
            expr.kind,
            expr.tables,
            [_rewrite_aliases(item, aliases) for item in expr.constraints],
            expr.date_localized,
        )

    def _period_feature_expr_for_aliases(
        self,
        node: OfficialFunctionCall,
        aliases: Dict[str, str],
        warnings: List[str],
    ) -> SqlExpr:
        name = node.name
        args = self._slot_args(node, 8)
        market, filter_scope, indicator_name, period, date, select_type, agg_func, _count_exp = args[:8]
        if agg_func:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_PERIOD_FUNCTION",
                f"{name} with agg_func is not grounded in expression-level count_exp SQL",
            )
        normalized_indicator = indicator_name or "最新价"
        constraints = [
            _rewrite_aliases(item, aliases)
            for item in self._slot_constraints(market, filter_scope, date, select_type, warnings)
        ]
        if name in {"record_high", "record_low"}:
            if self._can_use_official_price_extreme_days(name, normalized_indicator, period):
                days = _parse_period_day_count(period)
                column = "pxMkTopDays" if name == "record_high" else "pxMkBotDays"
                sql = f"{aliases['ext']}.{column} > 0" if days is None else f"{aliases['ext']}.{column} >= {days}"
                return SqlExpr(sql, "boolean", ["hsj_stock_hq_basic", "hsj_stock_hq_ext"], constraints)
            meta = _resolve_indicator_meta(normalized_indicator)
            if not meta:
                raise OfficialSlotError(
                    "UNSUPPORTED_OFFICIAL_INDICATOR",
                    f"Official indicator is not mapped to the provided three-table dataset: {normalized_indicator}",
                )
            if meta.kind not in {"numeric", "time"}:
                raise OfficialSlotError(
                    "UNSUPPORTED_OFFICIAL_PERIOD_FUNCTION",
                    f"{name} is only grounded for numeric/time indicators, got {meta.kind}",
                )
            current_sql = self._indicator_value_sql(meta, aliases)
            aggregate = "MAX" if name == "record_high" else "MIN"
            subquery = self._period_aggregate_subquery_for_aliases(aggregate, meta, period, aliases, warnings)
            comparator = ">=" if name == "record_high" else "<="
            return SqlExpr(
                f"{current_sql} {comparator} {subquery}",
                "boolean",
                self._ordered_tables(["hsj_stock_hq_basic", meta.table]),
                constraints,
            )
        if name == "position":
            meta = _resolve_indicator_meta(normalized_indicator)
            if not meta:
                raise OfficialSlotError(
                    "UNSUPPORTED_OFFICIAL_INDICATOR",
                    f"Official indicator is not mapped to the provided three-table dataset: {normalized_indicator}",
                )
            if meta.kind not in {"numeric", "time"}:
                raise OfficialSlotError(
                    "UNSUPPORTED_OFFICIAL_PERIOD_FUNCTION",
                    f"position is only grounded for numeric/time indicators, got {meta.kind}",
                )
            current_sql = self._indicator_value_sql(meta, aliases)
            min_sql = self._period_aggregate_subquery_for_aliases("MIN", meta, period, aliases, warnings)
            max_sql = self._period_aggregate_subquery_for_aliases("MAX", meta, period, aliases, warnings)
            ratio_sql = f"(({current_sql} - {min_sql}) / NULLIF(({max_sql} - {min_sql}), 0))"
            sql = (
                "CASE "
                f"WHEN {current_sql} IS NULL OR {min_sql} IS NULL OR {max_sql} IS NULL THEN NULL "
                f"WHEN {current_sql} <= {min_sql} THEN '最低' "
                f"WHEN {current_sql} >= {max_sql} THEN '最高' "
                f"WHEN {ratio_sql} <= 0.25 THEN '低' "
                f"WHEN {ratio_sql} >= 0.75 THEN '高' "
                "ELSE '中' END"
            )
            return SqlExpr(
                sql,
                "string",
                self._ordered_tables(["hsj_stock_hq_basic", meta.table]),
                constraints,
            )
        raise OfficialSlotError("UNSUPPORTED_OFFICIAL_PERIOD_FUNCTION", f"Unsupported period function: {name}")

    def _period_aggregate_subquery_for_aliases(
        self,
        aggregate: str,
        meta: IndicatorMeta,
        period: str,
        current_aliases: Dict[str, str],
        warnings: List[str],
    ) -> str:
        inner_aliases = {"base": "pw", "code": "pc", "ext": "pe", "tech": "pt"}
        value_sql = self._indicator_value_sql(meta, inner_aliases)
        tables = self._ordered_tables(["hsj_stock_hq_basic", meta.table])
        where_parts = self._period_window_where_for_aliases(period, "pw", current_aliases["base"], warnings)
        joins = self._joins_for_aliases(tables, "pw", "pc", "pe", "pt")
        return (
            f"(SELECT {aggregate}({value_sql})\n"
            " FROM newzl.hsj_stock_hq_basic AS pw\n"
            f"{joins}"
            f" WHERE {' AND '.join(_dedupe(where_parts))})"
        )

    def _period_window_where_for_aliases(
        self,
        period: str,
        inner_base_alias: str,
        current_base_alias: str,
        warnings: List[str],
    ) -> List[str]:
        where_parts = [
            f"{inner_base_alias}.mktcode = {current_base_alias}.mktcode",
            f"{inner_base_alias}.tgtcode = {current_base_alias}.tgtcode",
        ]
        days = _parse_period_day_count(period)
        if days is not None:
            lookback = max(days - 1, 0)
            where_parts.append(
                f"{inner_base_alias}.bizdate BETWEEN DATE_SUB({current_base_alias}.bizdate, INTERVAL {lookback} DAY) "
                f"AND {current_base_alias}.bizdate"
            )
            return where_parts
        where_parts.append(f"{inner_base_alias}.bizdate <= {current_base_alias}.bizdate")
        if period and period not in {"历史", "史高", "史低"}:
            warnings.append(
                f"period {period!r} is compiled as history-to-current because no exact relative window is grounded"
            )
        return where_parts

    def _count_exp_predicate_subquery(
        self,
        *,
        from_sql: str,
        where_parts: Sequence[str],
        predicate: str,
        rule: CountExpRule,
        base_alias: str,
    ) -> str:
        where = " AND ".join(_dedupe(where_parts))
        if rule.every:
            return (
                "(SELECT COUNT(*) > 0 AND "
                f"SUM(CASE WHEN {predicate} THEN 1 ELSE 0 END) = COUNT(*)\n"
                f" {from_sql}"
                f" WHERE {where})"
            )
        threshold = 1 if rule.count is None else rule.count
        comparator = rule.operator or (">" if rule.mode == "EXIST" else ">=")
        if rule.mode == "CONS" and threshold > 1 and (rule.unit in {"", "日"}):
            comparator = ">=" if comparator == "=" else comparator
            run_predicate = _count_rule_predicate_sql("MAX(run_length)", rule, comparator)
            return (
                f"(SELECT {run_predicate}\n"
                " FROM (\n"
                "   SELECT run_group, COUNT(*) AS run_length\n"
                "   FROM (\n"
                "     SELECT matched.bizdate,\n"
                "            DATEDIFF(matched.bizdate, '1970-01-01') "
                "- ROW_NUMBER() OVER (ORDER BY matched.bizdate) AS run_group\n"
                "     FROM (\n"
                f"       SELECT DISTINCT {base_alias}.bizdate\n"
                f"       {from_sql}"
                f"       WHERE {where} AND {predicate}\n"
                "     ) AS matched\n"
                "   ) AS grouped\n"
                "   GROUP BY run_group\n"
                " ) AS runs)"
            )
        comparator = comparator if comparator else (">" if rule.mode == "EXIST" else ">=")
        count_predicate = _count_rule_predicate_sql("COUNT(*)", rule, comparator)
        return (
            "(SELECT "
            f"{count_predicate}\n"
            f" {from_sql}"
            f" WHERE {where} AND {predicate})"
        )

    def _count_exp_specs_from_node(self, node: OfficialNode) -> List[CountExpSpec]:
        specs: List[CountExpSpec] = []
        for call in _iter_function_calls(node):
            if call.name == "indicator":
                args = self._slot_args(call, 7)
                if args[6]:
                    specs.append(CountExpSpec(args[6], args[0], args[1], args[3], args[4], args[5]))
            elif call.name in {"record_high", "record_low", "position"}:
                args = self._slot_args(call, 8)
                if args[7] and not args[6]:
                    specs.append(CountExpSpec(args[7], args[0], args[1], args[4], args[5]))
        return specs

    def _strip_count_exp(self, node: OfficialNode) -> OfficialNode:
        if isinstance(node, OfficialFunctionCall):
            args = [self._strip_count_exp(arg) for arg in node.args]
            if node.name == "indicator" and len(args) >= 7:
                args[6] = OfficialLiteral("")
            elif node.name in {"record_high", "record_low", "position"} and len(args) >= 8:
                args[7] = OfficialLiteral("")
            return OfficialFunctionCall(node.name, args)
        if isinstance(node, OfficialBinaryOp):
            return OfficialBinaryOp(node.op, self._strip_count_exp(node.left), self._strip_count_exp(node.right))
        if isinstance(node, OfficialComparison):
            return OfficialComparison(node.op, self._strip_count_exp(node.left), self._strip_count_exp(node.right))
        if isinstance(node, OfficialLimit):
            return OfficialLimit(self._strip_count_exp(node.expr), node.lower, node.upper)
        if isinstance(node, OfficialRangeLiteral):
            return OfficialRangeLiteral(
                self._strip_count_exp(node.lower),
                self._strip_count_exp(node.upper),
                node.lower_inclusive,
                node.upper_inclusive,
            )
        return node

    def _expr_sql(self, node: OfficialNode, warnings: List[str]) -> SqlExpr:
        if isinstance(node, OfficialLiteral):
            return SqlExpr(self._literal_sql(node), self._literal_kind(node.value), [], [])
        if isinstance(node, OfficialBinaryOp) and node.op in {"+", "-", "*", "/"}:
            left = self._expr_sql(node.left, warnings)
            right = self._expr_sql(node.right, warnings)
            return SqlExpr(
                f"({left.sql} {node.op} {right.sql})",
                "numeric",
                left.tables + right.tables,
                left.constraints + right.constraints,
            )
        if isinstance(node, OfficialFunctionCall):
            name = node.name
            if name == "indicator":
                return self._indicator_expr(node, warnings)
            if name == "belong_industry":
                return self._belong_industry_expr(node, warnings)
            if name == "queryData":
                return self._query_data_expr(node, warnings)
            if name == "rank":
                return self._rank_scalar_expr(node, warnings)
            if name in {"record_high", "record_low", "position"}:
                return self._period_feature_expr(node, warnings)
            if name in {"cross_above", "cross_down", "golden_cross"}:
                return self._cross_expr(node, name, warnings)
            if name in {"reset", "close_together"}:
                return self._technical_pattern_expr(node, warnings)
            raise OfficialSlotError("UNSUPPORTED_OFFICIAL_FUNCTION", f"Unsupported official function: {name}")
        if isinstance(node, OfficialIdentifier):
            return SqlExpr(node.name, "identifier", [], [])
        raise OfficialSlotError("OFFICIAL_EXPR_ERROR", f"Unsupported expression node: {type(node).__name__}")

    def _technical_pattern_expr(self, node: OfficialFunctionCall, warnings: List[str]) -> SqlExpr:
        predicate, tables, market, filter_scope, date, select_type, count_exp = self._technical_pattern_predicate(
            node,
            {"base": "base", "code": "code", "ext": "ext", "tech": "tech"},
        )
        if count_exp:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                f"{node.name} count_exp must be compiled together with a comparison: {count_exp}",
            )
        constraints = self._slot_constraints(market, filter_scope, date, select_type, warnings)
        return SqlExpr(predicate, "boolean", tables, constraints)

    def _technical_pattern_predicate(
        self,
        node: OfficialFunctionCall,
        aliases: Dict[str, str],
    ) -> Tuple[str, List[str], str, str, str, str, str]:
        args = self._slot_args(node, 7)
        market, filter_scope, left_indicator, right_indicator, date, select_type, count_exp = args[:7]
        left_name = left_indicator or "最新价"
        right_name = right_indicator
        if not right_name:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_FUNCTION",
                f"{node.name} requires a grounded right-side indicator",
            )
        left_sql, left_table = self._technical_pattern_operand_sql(left_name, aliases)
        right_sql, right_table = self._technical_pattern_operand_sql(right_name, aliases)
        tables = self._ordered_tables(["hsj_stock_hq_basic", left_table, right_table])
        if node.name == "close_together":
            threshold = self._pattern_threshold("close_together", "relative_threshold")
            denominator = f"NULLIF(GREATEST(ABS({left_sql}), ABS({right_sql})), 0)"
            predicate = f"(ABS({left_sql} - {right_sql}) / {denominator}) <= {threshold}"
        elif node.name == "reset":
            near_threshold = self._pattern_threshold("reset", "near_line_threshold")
            below_tolerance = self._pattern_threshold("reset", "below_line_tolerance")
            predicate = (
                f"((ABS({left_sql} - {right_sql}) / NULLIF(ABS({right_sql}), 0)) <= {near_threshold} "
                f"AND {left_sql} >= ({right_sql} * (1 - {below_tolerance})))"
            )
        else:
            raise OfficialSlotError("UNSUPPORTED_OFFICIAL_FUNCTION", f"Unsupported official function: {node.name}")
        return predicate, tables, market, filter_scope, date, select_type, count_exp

    def _technical_pattern_operand_sql(self, indicator_name: str, aliases: Dict[str, str]) -> Tuple[str, str]:
        meta = _resolve_indicator_meta(indicator_name)
        if not meta:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_INDICATOR",
                f"Official indicator is not mapped to the provided three-table dataset: {indicator_name}",
            )
        if meta.kind != "numeric":
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_FUNCTION",
                f"technical pattern functions require numeric indicators, got {meta.kind}: {indicator_name}",
            )
        return self._indicator_value_sql(meta, aliases), meta.table

    def _pattern_threshold(self, section: str, key: str) -> float:
        fallback = DEFAULT_TECHNICAL_PATTERN_CONFIG[section][key]
        value = self.technical_pattern_config.get(section, {}).get(key, fallback)
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(fallback)

    def _indicator_expr(self, node: OfficialFunctionCall, warnings: List[str]) -> SqlExpr:
        args = self._slot_args(node, 7)
        market, filter_scope, indicator_name, date, select_type, agg_func, count_exp = args[:7]
        if not indicator_name:
            return SqlExpr(
                "'all'",
                "string",
                ["hsj_stock_hq_basic"],
                self._slot_constraints(market, filter_scope, date, select_type, warnings),
            )
        meta = _resolve_indicator_meta(indicator_name)
        if not meta:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_INDICATOR",
                f"Official indicator is not mapped to the provided three-table dataset: {indicator_name}",
            )
        if count_exp:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                f"count_exp must be compiled together with a comparison: {count_exp}",
            )
        if agg_func:
            return self._aggregate_indicator_expr(
                meta=meta,
                market=market,
                filter_scope=filter_scope,
                date=date,
                select_type=select_type,
                agg_func=agg_func,
                warnings=warnings,
            )
        constraints = self._slot_constraints(market, filter_scope, date, select_type, warnings)
        tables = ["hsj_stock_hq_basic", meta.table]
        if meta.kind == "boolean":
            if meta.true_condition:
                return SqlExpr(meta.true_condition, "boolean", tables, constraints)
            assert meta.column is not None
            return SqlExpr(f"{self._alias(meta.table)}.{meta.column} = TRUE", "boolean", tables, constraints)
        if meta.expression:
            return SqlExpr(meta.expression, meta.kind, tables, constraints)
        assert meta.column is not None
        return SqlExpr(f"{self._alias(meta.table)}.{meta.column}", meta.kind, tables, constraints)

    def _aggregate_indicator_expr(
        self,
        *,
        meta: IndicatorMeta,
        market: str,
        filter_scope: str,
        date: str,
        select_type: str,
        agg_func: str,
        warnings: List[str],
    ) -> SqlExpr:
        agg = agg_func.upper()
        if agg not in AGGREGATE_FUNCTIONS and agg not in GROWTH_FUNCTIONS:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_AGG_FUNC",
                f"Unsupported official aggregate function for real-data SQL: {agg_func}",
            )
        if meta.kind not in {"numeric", "time"}:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_AGG_FUNC",
                f"Aggregate {agg_func} is only grounded for numeric/time indicators, got {meta.kind}",
            )
        aliases = {"base": "wb", "code": "wc", "ext": "we", "tech": "wt"}
        value_sql = self._indicator_value_sql(meta, aliases)
        tables = self._ordered_tables(["hsj_stock_hq_basic", meta.table])
        where_parts = self._window_correlated_where(date, "wb", warnings)
        select_sql = f"{agg}({value_sql})"
        if agg in GROWTH_FUNCTIONS:
            first_value = f"MIN_BY({value_sql}, wb.bizdate)"
            last_value = f"MAX_BY({value_sql}, wb.bizdate)"
            if agg == "GROWTH_RISE":
                delta = f"({last_value} - {first_value})"
            else:
                delta = f"({first_value} - {last_value})"
            select_sql = f"({delta} * 100.0 / NULLIF(ABS({first_value}), 0))"
        subquery = (
            f"(SELECT {select_sql}\n"
            " FROM newzl.hsj_stock_hq_basic AS wb\n"
            f"{self._window_joins(tables)}"
            f" WHERE {' AND '.join(_dedupe(where_parts))})"
        )
        constraints = self._slot_constraints(market, filter_scope, "", select_type, warnings)
        constraints.extend(self._outer_snapshot_constraints(date))
        return SqlExpr(subquery, meta.kind, tables, constraints)

    def _count_exp_comparison_sql(
        self,
        indicator_call: OfficialFunctionCall,
        op: str,
        right_node: OfficialNode,
        warnings: List[str],
    ) -> SqlExpr:
        args = self._slot_args(indicator_call, 7)
        market, filter_scope, indicator_name, date, select_type, agg_func, count_exp = args[:7]
        meta = _resolve_indicator_meta(indicator_name)
        if not meta:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_INDICATOR",
                f"Official indicator is not mapped to the provided three-table dataset: {indicator_name}",
            )
        rule = _parse_count_exp_rule(count_exp)
        if agg_func:
            return self._aggregate_count_exp_comparison_sql(
                meta=meta,
                market=market,
                filter_scope=filter_scope,
                date=date,
                select_type=select_type,
                agg_func=agg_func,
                rule=rule,
                op=op,
                right_node=right_node,
                warnings=warnings,
            )
        aliases = {"base": "wb", "code": "wc", "ext": "we", "tech": "wt"}
        value_sql = self._indicator_value_sql(meta, aliases)
        if op == "between":
            if not isinstance(right_node, OfficialRangeLiteral):
                right = self._expr_sql(right_node, warnings)
                predicate = f"{value_sql} BETWEEN {_rewrite_aliases(right.sql, aliases)}"
            else:
                lower = self._expr_sql(right_node.lower, warnings)
                upper = self._expr_sql(right_node.upper, warnings)
                lower_op = ">=" if right_node.lower_inclusive else ">"
                upper_op = "<=" if right_node.upper_inclusive else "<"
                predicate = (
                    f"({value_sql} {lower_op} {_rewrite_aliases(lower.sql, aliases)} "
                    f"AND {value_sql} {upper_op} {_rewrite_aliases(upper.sql, aliases)})"
                )
        else:
            right = self._expr_sql(right_node, warnings)
            right_sql = _rewrite_aliases(right.sql, aliases)
            predicate = self._comparison_predicate_sql(value_sql, meta.kind, op, right_node, right_sql)
        tables = self._ordered_tables(["hsj_stock_hq_basic", meta.table])
        where_parts = self._window_correlated_where(date, "wb", warnings)
        if rule.mode == "CONS" and rule.every:
            subquery = (
                "(SELECT COUNT(*) > 0 AND "
                f"SUM(CASE WHEN {predicate} THEN 1 ELSE 0 END) = COUNT(*)\n"
                " FROM newzl.hsj_stock_hq_basic AS wb\n"
                f"{self._window_joins(tables)}"
                f" WHERE {' AND '.join(_dedupe(where_parts))})"
            )
        else:
            threshold = 1 if rule.count is None else rule.count
            comparator = rule.operator or (">" if rule.mode == "EXIST" else ">=")
            if rule.mode == "CONS":
                warnings.append(
                    f"count_exp {count_exp!r} is compiled as a threshold count over the normalized window; "
                    "exact longest consecutive-run detection requires a dedicated Doris feature table"
                )
            count_predicate = _count_rule_predicate_sql("COUNT(*)", rule, comparator)
            subquery = (
                f"(SELECT {count_predicate}\n"
                " FROM newzl.hsj_stock_hq_basic AS wb\n"
                f"{self._window_joins(tables)}"
                f" WHERE {' AND '.join(_dedupe(where_parts + [predicate]))})"
            )
        constraints = self._slot_constraints(market, filter_scope, "", select_type, warnings)
        constraints.extend(self._outer_snapshot_constraints(date))
        return SqlExpr(subquery, "boolean", tables, constraints)

    def _pattern_count_exp_comparison_sql(
        self,
        pattern_call: OfficialFunctionCall,
        op: str,
        right_node: OfficialNode,
        warnings: List[str],
    ) -> SqlExpr:
        predicate, tables, market, filter_scope, date, select_type, count_exp = self._technical_pattern_predicate(
            pattern_call,
            {"base": "wb", "code": "wc", "ext": "we", "tech": "wt"},
        )
        right = self._expr_sql(right_node, warnings)
        predicate = self._comparison_predicate_sql(predicate, "boolean", op, right_node, right.sql)
        rule = _parse_count_exp_rule(count_exp)
        where_parts = self._window_correlated_where(date, "wb", warnings)
        joins = self._window_joins(tables)
        if rule.every:
            subquery = (
                "(SELECT COUNT(*) > 0 AND "
                f"SUM(CASE WHEN {predicate} THEN 1 ELSE 0 END) = COUNT(*)\n"
                " FROM newzl.hsj_stock_hq_basic AS wb\n"
                f"{joins}"
                f" WHERE {' AND '.join(_dedupe(where_parts))})"
            )
        elif rule.mode == "CONS":
            threshold = 1 if rule.count is None else rule.count
            warnings.append(
                f"count_exp {count_exp!r} for {pattern_call.name} is compiled as a threshold count over "
                "the normalized window; exact longest consecutive-run detection requires a dedicated Doris feature table"
            )
            count_predicate = _count_rule_predicate_sql(
                f"SUM(CASE WHEN {predicate} THEN 1 ELSE 0 END)",
                rule,
                rule.operator,
            )
            subquery = (
                "(SELECT COUNT(*) > 0 AND "
                f"{count_predicate}\n"
                " FROM newzl.hsj_stock_hq_basic AS wb\n"
                f"{joins}"
                f" WHERE {' AND '.join(_dedupe(where_parts))})"
            )
        else:
            threshold = 1 if rule.count is None else rule.count
            comparator = rule.operator or ">"
            count_predicate = _count_rule_predicate_sql("COUNT(*)", rule, comparator)
            subquery = (
                f"(SELECT {count_predicate}\n"
                " FROM newzl.hsj_stock_hq_basic AS wb\n"
                f"{joins}"
                f" WHERE {' AND '.join(_dedupe(where_parts + [predicate]))})"
            )
        constraints = self._slot_constraints(market, filter_scope, "", select_type, warnings)
        constraints.extend(self._outer_snapshot_constraints(date))
        return SqlExpr(subquery, "boolean", tables, constraints)

    def _cross_count_exp_comparison_sql(
        self,
        cross_call: OfficialFunctionCall,
        op: str,
        right_node: OfficialNode,
        warnings: List[str],
    ) -> SqlExpr:
        args = self._slot_args(cross_call, 7)
        market, filter_scope, left_indicator, right_indicator, date, select_type, count_exp = args[:7]
        left_name = left_indicator or "最新价"
        right_name = right_indicator
        if not right_name:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_FUNCTION",
                f"{cross_call.name} requires a grounded right-side indicator",
            )
        aliases = {"base": "wb", "code": "wc", "ext": "we", "tech": "wt"}
        left_sql, left_table = self._cross_operand_sql(left_name, aliases)
        right_sql, right_table = self._cross_operand_sql(right_name, aliases)
        tables = self._ordered_tables(["hsj_stock_hq_basic", left_table, right_table])
        lag_partition = "PARTITION BY wb.mktcode, wb.tgtcode ORDER BY wb.bizdate"
        if cross_call.name in {"cross_above", "golden_cross"}:
            event_expr = (
                f"({left_sql} > {right_sql} AND "
                f"LAG({left_sql}) OVER ({lag_partition}) <= "
                f"LAG({right_sql}) OVER ({lag_partition}))"
            )
        elif cross_call.name == "cross_down":
            event_expr = (
                f"({left_sql} < {right_sql} AND "
                f"LAG({left_sql}) OVER ({lag_partition}) >= "
                f"LAG({right_sql}) OVER ({lag_partition}))"
            )
        else:
            raise OfficialSlotError("UNSUPPORTED_OFFICIAL_FUNCTION", f"Unsupported official function: {cross_call.name}")
        right = self._expr_sql(right_node, warnings)
        predicate = self._comparison_predicate_sql("event_rows.event_value", "boolean", op, right_node, right.sql)
        rule = _parse_count_exp_rule(count_exp)
        source_where_parts, event_where_parts = self._lag_event_window_where(
            date,
            source_alias="wb",
            event_alias="event_rows",
            warnings=warnings,
        )
        event_rows_sql = (
            "FROM (\n"
            "  SELECT wb.bizdate AS bizdate,\n"
            f"         {event_expr} AS event_value\n"
            "  FROM newzl.hsj_stock_hq_basic AS wb\n"
            f"{self._window_joins(tables)}"
            f"  WHERE {' AND '.join(_dedupe(source_where_parts))}\n"
            ") AS event_rows\n"
        )
        subquery = self._count_exp_predicate_subquery(
            from_sql=event_rows_sql,
            where_parts=event_where_parts,
            predicate=predicate,
            rule=rule,
            base_alias="event_rows",
        )
        constraints = self._slot_constraints(market, filter_scope, "", select_type, warnings)
        constraints.extend(self._outer_snapshot_constraints(date))
        return SqlExpr(subquery, "boolean", tables, constraints)

    def _cross_operand_sql(self, indicator_name: str, aliases: Dict[str, str]) -> Tuple[str, str]:
        meta = _resolve_indicator_meta(indicator_name)
        if not meta:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_INDICATOR",
                f"Official indicator is not mapped to the provided three-table dataset: {indicator_name}",
            )
        if meta.kind != "numeric":
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_FUNCTION",
                f"cross functions require numeric indicators, got {meta.kind}: {indicator_name}",
            )
        return self._indicator_value_sql(meta, aliases), meta.table

    def _aggregate_count_exp_comparison_sql(
        self,
        *,
        meta: IndicatorMeta,
        market: str,
        filter_scope: str,
        date: str,
        select_type: str,
        agg_func: str,
        rule: CountExpRule,
        op: str,
        right_node: OfficialNode,
        warnings: List[str],
    ) -> SqlExpr:
        agg = agg_func.upper()
        if agg not in AGGREGATE_FUNCTIONS and agg not in GROWTH_FUNCTIONS:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_AGG_FUNC",
                f"Unsupported official aggregate function for real-data SQL: {agg_func}",
            )
        if meta.kind not in {"numeric", "time"}:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_AGG_FUNC",
                f"Aggregate count_exp is only grounded for numeric/time indicators, got {meta.kind}",
            )
        right_sql = self._right_sql_for_bucket_predicate(right_node, warnings)
        predicate = self._bucket_predicate_sql(op, right_node, right_sql)
        aliases = {"base": "wb", "code": "wc", "ext": "we", "tech": "wt"}
        value_sql = self._indicator_value_sql(meta, aliases)
        tables = self._ordered_tables(["hsj_stock_hq_basic", meta.table])
        if agg in GROWTH_FUNCTIONS and rule.unit in {"", "日"}:
            inner_sql = self._daily_growth_bucket_sql(agg, value_sql, tables, date, warnings)
        else:
            inner_sql = self._aggregate_bucket_sql(agg, value_sql, tables, date, rule, warnings)
        subquery = self._count_bucketed_predicate_sql(inner_sql, predicate, rule)
        constraints = self._slot_constraints(market, filter_scope, "", select_type, warnings)
        constraints.extend(self._outer_snapshot_constraints(date))
        return SqlExpr(subquery, "boolean", tables, constraints)

    def _right_sql_for_bucket_predicate(self, right_node: OfficialNode, warnings: List[str]) -> str:
        if isinstance(right_node, OfficialRangeLiteral):
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                "between with agg_func and count_exp is not yet grounded as a bucketed aggregate",
            )
        right = self._expr_sql(right_node, warnings)
        return _rewrite_aliases(right.sql, {"base": "bucketed", "code": "bucketed", "ext": "bucketed", "tech": "bucketed"})

    def _bucket_predicate_sql(self, op: str, right_node: OfficialNode, right_sql: str) -> str:
        if op == "between":
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                "between with agg_func and count_exp is not yet grounded as a bucketed aggregate",
            )
        return self._comparison_predicate_sql("bucketed.agg_value", "numeric", op, right_node, right_sql)

    def _aggregate_bucket_sql(
        self,
        agg: str,
        value_sql: str,
        tables: Sequence[str],
        date: str,
        rule: CountExpRule,
        warnings: List[str],
    ) -> str:
        bucket_expr = self._bucket_expr("wb", rule)
        if agg in GROWTH_FUNCTIONS:
            first_value = f"MIN_BY({value_sql}, wb.bizdate)"
            last_value = f"MAX_BY({value_sql}, wb.bizdate)"
            delta = f"({last_value} - {first_value})" if agg == "GROWTH_RISE" else f"({first_value} - {last_value})"
            agg_value = f"({delta} * 100.0 / NULLIF(ABS({first_value}), 0))"
        else:
            agg_value = f"{agg}({value_sql})"
        where_parts = self._window_correlated_where(date, "wb", warnings)
        return (
            f"SELECT {bucket_expr} AS bucket_key,\n"
            f"       {agg_value} AS agg_value\n"
            " FROM newzl.hsj_stock_hq_basic AS wb\n"
            f"{self._window_joins(tables)}"
            f" WHERE {' AND '.join(_dedupe(where_parts))}\n"
            f" GROUP BY {bucket_expr}"
        )

    def _daily_growth_bucket_sql(
        self,
        agg: str,
        value_sql: str,
        tables: Sequence[str],
        date: str,
        warnings: List[str],
    ) -> str:
        previous = f"LAG({value_sql}) OVER (PARTITION BY wb.mktcode, wb.tgtcode ORDER BY wb.bizdate)"
        delta = f"({value_sql} - {previous})" if agg == "GROWTH_RISE" else f"({previous} - {value_sql})"
        growth = f"({delta} * 100.0 / NULLIF(ABS({previous}), 0))"
        where_parts = self._window_correlated_where(date, "wb", warnings)
        return (
            "SELECT wb.bizdate AS bucket_key,\n"
            f"       {growth} AS agg_value\n"
            " FROM newzl.hsj_stock_hq_basic AS wb\n"
            f"{self._window_joins(tables)}"
            f" WHERE {' AND '.join(_dedupe(where_parts))}"
        )

    def _count_bucketed_predicate_sql(self, inner_sql: str, predicate: str, rule: CountExpRule) -> str:
        if rule.every:
            return (
                "(SELECT COUNT(*) > 0 AND "
                f"SUM(CASE WHEN {predicate} THEN 1 ELSE 0 END) = COUNT(*)\n"
                " FROM (\n"
                f"{inner_sql}\n"
                ") AS bucketed\n"
                " WHERE bucketed.agg_value IS NOT NULL)"
            )
        threshold = 1 if rule.count is None else rule.count
        comparator = rule.operator or (">" if rule.mode == "EXIST" else ">=")
        count_predicate = _count_rule_predicate_sql("COUNT(*)", rule, comparator)
        return (
            f"(SELECT {count_predicate}\n"
            " FROM (\n"
            f"{inner_sql}\n"
            ") AS bucketed\n"
            f" WHERE bucketed.agg_value IS NOT NULL AND {predicate})"
        )

    def _belong_industry_expr(self, node: OfficialFunctionCall, warnings: List[str]) -> SqlExpr:
        args = self._slot_args(node, 5)
        market, filter_scope, indicator_name, date, agg_func = args[:5]
        meta = _resolve_indicator_meta(indicator_name)
        if not meta:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_INDICATOR",
                f"Official indicator is not mapped to the provided three-table dataset: {indicator_name}",
            )
        if meta.kind not in {"numeric", "time"}:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_FUNCTION",
                f"belong_industry is only grounded for numeric/time indicators, got {meta.kind}",
            )
        aggregate = (agg_func or "AVG").upper()
        if aggregate not in AGGREGATE_FUNCTIONS:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_AGG_FUNC",
                f"Unsupported belong_industry aggregate function: {agg_func}",
            )
        aliases = {"base": "wb", "code": "wc", "ext": "we", "tech": "wt"}
        value_sql = self._indicator_value_sql(meta, aliases)
        tables = self._ordered_tables(["hsj_stock_hq_basic", "hsj_stock_code_info", meta.table])
        where_parts = [
            "wc.hyBlkRefName = code.hyBlkRefName",
            "wc.hyBlkRefName IS NOT NULL",
            "wc.hyBlkRefName != ''",
        ]
        local_constraints = self._slot_constraints(market, filter_scope, date, "", warnings)
        where_parts.extend(_rewrite_aliases(item, aliases) for item in local_constraints)
        subquery = (
            f"(SELECT {aggregate}({value_sql})\n"
            " FROM newzl.hsj_stock_hq_basic AS wb\n"
            f"{self._window_joins(tables)}"
            f" WHERE {' AND '.join(_dedupe(where_parts))})"
        )
        outer_constraints = self._slot_constraints(market, filter_scope, "", "", warnings)
        return SqlExpr(subquery, meta.kind, tables, outer_constraints)

    def _query_data_expr(self, node: OfficialFunctionCall, warnings: List[str]) -> SqlExpr:
        args = self._slot_args(node, 5)
        market, keywords, indicator_name, date, agg_func = args[:5]
        indicator_call = OfficialFunctionCall(
            "indicator",
            [
                OfficialLiteral(market),
                OfficialLiteral(""),
                OfficialLiteral(indicator_name),
                OfficialLiteral(date),
                OfficialLiteral(""),
                OfficialLiteral(agg_func),
                OfficialLiteral(""),
            ],
        )
        expr = self._indicator_expr(indicator_call, warnings)
        keyword_constraints = []
        if keywords:
            escaped = _sql_quote(keywords)
            keyword_constraints.append(f"(code.name = {escaped} OR code.tgtcode = {escaped} OR code.tztcode = {escaped})")
            expr.tables.append("hsj_stock_code_info")
        return SqlExpr(expr.sql, expr.kind, expr.tables, expr.constraints + keyword_constraints)

    def _period_feature_expr(self, node: OfficialFunctionCall, warnings: List[str]) -> SqlExpr:
        name = node.name
        args = self._slot_args(node, 8)
        market, filter_scope, indicator_name, period, date, select_type, agg_func, count_exp = args[:8]
        if agg_func or count_exp:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_PERIOD_FUNCTION",
                f"{name} with agg_func/count_exp is not grounded in the official three-table adapter",
            )
        normalized_indicator = indicator_name or "最新价"
        constraints = self._slot_constraints(market, filter_scope, date, select_type, warnings)
        if name in {"record_high", "record_low"}:
            return self._record_extreme_expr(
                function_name=name,
                indicator_name=normalized_indicator,
                period=period,
                constraints=constraints,
                warnings=warnings,
            )
        if name == "position":
            return self._position_expr(
                indicator_name=normalized_indicator,
                period=period,
                constraints=constraints,
                warnings=warnings,
            )
        raise OfficialSlotError(
            "UNSUPPORTED_OFFICIAL_PERIOD_FUNCTION",
            f"{name}({indicator_name}, period={period}) is not mapped in the official-data adapter",
        )

    def _record_extreme_expr(
        self,
        *,
        function_name: str,
        indicator_name: str,
        period: str,
        constraints: List[str],
        warnings: List[str],
    ) -> SqlExpr:
        if self._can_use_official_price_extreme_days(function_name, indicator_name, period):
            days = _parse_period_day_count(period)
            column = "pxMkTopDays" if function_name == "record_high" else "pxMkBotDays"
            if days is None:
                sql = f"ext.{column} > 0"
            else:
                sql = f"ext.{column} >= {days}"
            return SqlExpr(
                sql,
                "boolean",
                ["hsj_stock_hq_basic", "hsj_stock_hq_ext"],
                constraints,
            )

        meta = _resolve_indicator_meta(indicator_name)
        if not meta:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_INDICATOR",
                f"Official indicator is not mapped to the provided three-table dataset: {indicator_name}",
            )
        if meta.kind not in {"numeric", "time"}:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_PERIOD_FUNCTION",
                f"{function_name} is only grounded for numeric/time indicators, got {meta.kind}",
            )
        current_sql = self._indicator_value_sql(meta, {"base": "base", "code": "code", "ext": "ext", "tech": "tech"})
        aggregate = "MAX" if function_name == "record_high" else "MIN"
        subquery = self._period_aggregate_subquery(aggregate, meta, period, warnings)
        comparator = ">=" if function_name == "record_high" else "<="
        return SqlExpr(
            f"{current_sql} {comparator} {subquery}",
            "boolean",
            self._ordered_tables(["hsj_stock_hq_basic", meta.table]),
            constraints,
        )

    def _position_expr(
        self,
        *,
        indicator_name: str,
        period: str,
        constraints: List[str],
        warnings: List[str],
    ) -> SqlExpr:
        meta = _resolve_indicator_meta(indicator_name)
        if not meta:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_INDICATOR",
                f"Official indicator is not mapped to the provided three-table dataset: {indicator_name}",
            )
        if meta.kind not in {"numeric", "time"}:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_PERIOD_FUNCTION",
                f"position is only grounded for numeric/time indicators, got {meta.kind}",
            )
        current_sql = self._indicator_value_sql(meta, {"base": "base", "code": "code", "ext": "ext", "tech": "tech"})
        min_sql = self._period_aggregate_subquery("MIN", meta, period, warnings)
        max_sql = self._period_aggregate_subquery("MAX", meta, period, warnings)
        ratio_sql = f"(({current_sql} - {min_sql}) / NULLIF(({max_sql} - {min_sql}), 0))"
        sql = (
            "CASE "
            f"WHEN {current_sql} IS NULL OR {min_sql} IS NULL OR {max_sql} IS NULL THEN NULL "
            f"WHEN {current_sql} <= {min_sql} THEN '最低' "
            f"WHEN {current_sql} >= {max_sql} THEN '最高' "
            f"WHEN {ratio_sql} <= 0.25 THEN '低' "
            f"WHEN {ratio_sql} >= 0.75 THEN '高' "
            "ELSE '中' END"
        )
        return SqlExpr(
            sql,
            "string",
            self._ordered_tables(["hsj_stock_hq_basic", meta.table]),
            constraints,
        )

    def _period_aggregate_subquery(
        self,
        aggregate: str,
        meta: IndicatorMeta,
        period: str,
        warnings: List[str],
    ) -> str:
        aliases = {"base": "wb", "code": "wc", "ext": "we", "tech": "wt"}
        value_sql = self._indicator_value_sql(meta, aliases)
        tables = self._ordered_tables(["hsj_stock_hq_basic", meta.table])
        where_parts = self._period_window_where(period, "wb", warnings)
        return (
            f"(SELECT {aggregate}({value_sql})\n"
            " FROM newzl.hsj_stock_hq_basic AS wb\n"
            f"{self._window_joins(tables)}"
            f" WHERE {' AND '.join(_dedupe(where_parts))})"
        )

    def _period_window_where(self, period: str, base_alias: str, warnings: List[str]) -> List[str]:
        where_parts = [
            f"{base_alias}.mktcode = base.mktcode",
            f"{base_alias}.tgtcode = base.tgtcode",
        ]
        days = _parse_period_day_count(period)
        if days is not None:
            lookback = max(days - 1, 0)
            where_parts.append(
                f"{base_alias}.bizdate BETWEEN DATE_SUB(base.bizdate, INTERVAL {lookback} DAY) AND base.bizdate"
            )
            return where_parts
        where_parts.append(f"{base_alias}.bizdate <= base.bizdate")
        if period and period not in {"历史", "史高", "史低"}:
            warnings.append(
                f"period {period!r} is compiled as history-to-current because no exact relative window is grounded"
            )
        return where_parts

    def _can_use_official_price_extreme_days(self, function_name: str, indicator_name: str, period: str) -> bool:
        if period and period in {"历史", "史高", "史低"}:
            return False
        if function_name == "record_high":
            return indicator_name in {"最新价", "现价", "收盘价", "最高价"}
        if function_name == "record_low":
            return indicator_name in {"最新价", "现价", "收盘价", "最低价"}
        raise OfficialSlotError(
            "UNSUPPORTED_OFFICIAL_PERIOD_FUNCTION",
            f"{function_name}({indicator_name}, period={period}) is not mapped in the official-data adapter",
        )

    def _cross_expr(self, node: OfficialFunctionCall, name: str, warnings: List[str]) -> SqlExpr:
        args = self._slot_args(node, 7)
        left_name, right_name = args[2], args[3]
        left = self._indicator_expr(
            OfficialFunctionCall("indicator", [OfficialLiteral(args[0]), OfficialLiteral(args[1]), OfficialLiteral(left_name), OfficialLiteral(args[4]), OfficialLiteral(args[5]), OfficialLiteral(""), OfficialLiteral(args[6])]),
            warnings,
        )
        right = self._indicator_expr(
            OfficialFunctionCall("indicator", [OfficialLiteral(args[0]), OfficialLiteral(args[1]), OfficialLiteral(right_name), OfficialLiteral(args[4]), OfficialLiteral(args[5]), OfficialLiteral(""), OfficialLiteral(args[6])]),
            warnings,
        )
        if name in {"cross_above", "golden_cross"}:
            sql = (
                f"{left.sql} > {right.sql} AND "
                f"LAG({left.sql}) OVER (PARTITION BY base.tgtcode ORDER BY base.bizdate) <= "
                f"LAG({right.sql}) OVER (PARTITION BY base.tgtcode ORDER BY base.bizdate)"
            )
        else:
            sql = (
                f"{left.sql} < {right.sql} AND "
                f"LAG({left.sql}) OVER (PARTITION BY base.tgtcode ORDER BY base.bizdate) >= "
                f"LAG({right.sql}) OVER (PARTITION BY base.tgtcode ORDER BY base.bizdate)"
            )
        return SqlExpr(sql, "boolean", left.tables + right.tables, left.constraints + right.constraints)

    def _rank_expr(self, rank_call: OfficialFunctionCall, warnings: List[str]) -> SqlExpr:
        args = self._slot_args(rank_call, 8)
        indicator_name = args[2]
        if not indicator_name:
            return SqlExpr(
                "base.tgtcode",
                "string",
                ["hsj_stock_hq_basic"],
                self._slot_constraints(args[0], args[1], args[4], args[5], warnings),
            )
        indicator_call = OfficialFunctionCall(
            "indicator",
            [
                OfficialLiteral(args[0]),
                OfficialLiteral(args[1]),
                OfficialLiteral(indicator_name),
                OfficialLiteral(args[4]),
                OfficialLiteral(args[5]),
                OfficialLiteral(args[6]),
                OfficialLiteral(args[7]),
            ],
        )
        return self._indicator_expr(indicator_call, warnings)

    def _rank_expr_without_count_exp(self, rank_call: OfficialFunctionCall, warnings: List[str]) -> SqlExpr:
        args = self._slot_args(rank_call, 8)
        indicator_call = OfficialFunctionCall(
            "indicator",
            [
                OfficialLiteral(args[0]),
                OfficialLiteral(args[1]),
                OfficialLiteral(args[2]),
                OfficialLiteral(args[4]),
                OfficialLiteral(args[5]),
                OfficialLiteral(args[6]),
                OfficialLiteral(""),
            ],
        )
        return self._indicator_expr(indicator_call, warnings)

    def _rank_scalar_expr(self, rank_call: OfficialFunctionCall, warnings: List[str]) -> SqlExpr:
        if self._rank_count_exp(rank_call):
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                "rank(...) inside arithmetic expressions does not yet support count_exp",
            )
        rank_expr = self._rank_expr_without_count_exp(rank_call, warnings)
        rank_sql = _rank_alias_sql(rank_expr.sql)
        constraints = [_rank_alias_sql(item) for item in rank_expr.constraints]
        tables = self._ordered_tables(rank_expr.tables)
        joins = self._joins_for_aliases(tables, "rb", "rcode", "rext")
        where = " AND ".join(_dedupe(constraints)) or "1=1"
        sql = (
            "(SELECT ranked.rank_no\n"
            " FROM (\n"
            "   SELECT rb.mktcode, rb.tgtcode, rb.bizdate,\n"
            f"          ROW_NUMBER() OVER (PARTITION BY rb.bizdate ORDER BY {rank_sql} {self._rank_order(rank_call)}, rb.tgtcode ASC) AS rank_no\n"
            "   FROM newzl.hsj_stock_hq_basic AS rb\n"
            f"{joins}"
            f"   WHERE {where}\n"
            " ) AS ranked\n"
            " WHERE ranked.mktcode = base.mktcode\n"
            "   AND ranked.tgtcode = base.tgtcode\n"
            "   AND ranked.bizdate = base.bizdate)"
        )
        return SqlExpr(sql, "numeric", tables, [])

    def _rank_order(self, rank_call: OfficialFunctionCall) -> str:
        args = self._slot_args(rank_call, 8)
        direction = args[3].lower()
        if direction == "asc":
            return "ASC"
        if direction in {"desc", ""}:
            return "DESC"
        raise OfficialSlotError("OFFICIAL_RANK_DIRECTION_ERROR", f"Unsupported rank direction: {args[3]}")

    def _indicator_value_sql(self, meta: IndicatorMeta, aliases: Dict[str, str]) -> str:
        if meta.kind == "boolean":
            if meta.true_condition:
                return _rewrite_aliases(meta.true_condition, aliases)
            assert meta.column is not None
            return f"{aliases[self._alias(meta.table)]}.{meta.column} = TRUE"
        if meta.expression:
            return _rewrite_aliases(meta.expression, aliases)
        assert meta.column is not None
        return f"{aliases[self._alias(meta.table)]}.{meta.column}"

    def _comparison_predicate_sql(
        self,
        left_sql: str,
        left_kind: str,
        op: str,
        right_node: OfficialNode,
        right_sql: str,
    ) -> str:
        if left_kind == "boolean" and isinstance(right_node, OfficialLiteral):
            if right_node.value is True:
                return left_sql if op in {"=", "=="} else f"NOT ({left_sql})"
            if right_node.value is False:
                return f"NOT ({left_sql})" if op in {"=", "=="} else left_sql
        if (
            left_kind == "string"
            and isinstance(right_node, OfficialLiteral)
            and isinstance(right_node.value, str)
            and not _is_numeric_percent_literal(right_node.value)
            and any(ch in right_node.value for ch in {"%", "_"})
        ):
            if op in {"=", "==", "~="}:
                return f"{left_sql} LIKE {right_sql}"
            if op == "!=":
                return f"{left_sql} NOT LIKE {right_sql}"
        return f"{left_sql} {self._sql_operator(op)} {right_sql}"

    def _window_correlated_where(self, date: str, base_alias: str, warnings: List[str]) -> List[str]:
        where_parts = [
            f"{base_alias}.mktcode = base.mktcode",
            f"{base_alias}.tgtcode = base.tgtcode",
        ]
        if date:
            normalized = normalize_official_date(
                date,
                anchor_date=self.anchor_date,
                trading_dates=self.trading_dates,
                field=f"{base_alias}.bizdate",
            )
            where_parts.extend(normalized.constraints)
            warnings.extend(normalized.warnings)
            _mark_fallback(warnings, normalized.fallback_predicate)
        return where_parts

    def _lag_event_window_where(
        self,
        date: str,
        *,
        source_alias: str,
        event_alias: str,
        warnings: List[str],
    ) -> Tuple[List[str], List[str]]:
        source_where = [
            f"{source_alias}.mktcode = base.mktcode",
            f"{source_alias}.tgtcode = base.tgtcode",
        ]
        if not date:
            return source_where, ["1=1"]

        source_field = f"{source_alias}.bizdate"
        event_field = f"{event_alias}.bizdate"
        normalized = normalize_official_date(
            date,
            anchor_date=self.anchor_date,
            trading_dates=self.trading_dates,
            field=source_field,
        )
        warnings.extend(normalized.warnings)
        _mark_fallback(warnings, normalized.fallback_predicate)

        event_where: List[str] = []
        for constraint in normalized.constraints:
            exact = re.fullmatch(rf"{re.escape(source_field)} = '([^']+)'", constraint)
            if exact:
                end = exact.group(1)
                source_where.append(f"{source_field} <= '{end}'")
                event_where.append(f"{event_field} = '{end}'")
                continue
            between = re.fullmatch(
                rf"{re.escape(source_field)} BETWEEN '([^']+)' AND '([^']+)'",
                constraint,
            )
            if between:
                start, end = between.groups()
                source_where.append(f"{source_field} <= '{end}'")
                event_where.append(f"{event_field} BETWEEN '{start}' AND '{end}'")
                continue
            source_where.append(constraint)
            event_where.append(constraint.replace(source_field, event_field))
        return source_where, event_where or ["1=1"]

    def _outer_snapshot_constraints(self, date: str) -> List[str]:
        if not date:
            return []
        normalized = normalize_official_date(
            date,
            anchor_date=self.anchor_date,
            trading_dates=self.trading_dates,
            field="base.bizdate",
        )
        constraints: List[str] = []
        for constraint in normalized.constraints:
            exact = re.fullmatch(r"base\.bizdate = '([^']+)'", constraint)
            if exact:
                constraints.append(constraint)
                continue
            between = re.fullmatch(r"base\.bizdate BETWEEN '([^']+)' AND '([^']+)'", constraint)
            if between:
                constraints.append(f"base.bizdate = '{between.group(2)}'")
        return constraints

    def _window_joins(self, tables: Sequence[str]) -> str:
        joins = []
        table_set = set(tables)
        if "hsj_stock_code_info" in table_set:
            joins.append(
                " LEFT JOIN newzl.hsj_stock_code_info AS wc "
                "ON wc.mktcode = wb.mktcode AND wc.tgtcode = wb.tgtcode\n"
            )
        if "hsj_stock_hq_ext" in table_set:
            joins.append(
                " LEFT JOIN newzl.hsj_stock_hq_ext AS we "
                "ON we.mktcode = wb.mktcode "
                "AND we.tgtcode = wb.tgtcode "
                "AND we.bizdate = wb.bizdate\n"
            )
        if "hsj_stock_hq_basic_technical" in table_set:
            joins.append(
                " LEFT JOIN newzl.hsj_stock_hq_basic_technical AS wt "
                "ON wt.mktcode = wb.mktcode "
                "AND wt.tgtcode = wb.tgtcode "
                "AND wt.bizdate = wb.bizdate\n"
            )
        return "".join(joins)

    def _bucket_expr(self, base_alias: str, rule: CountExpRule) -> str:
        unit = rule.unit or "日"
        granularity = {
            "日": "day",
            "周": "week",
            "月": "month",
            "季度": "quarter",
            "年": "year",
        }.get(unit)
        if not granularity:
            raise OfficialSlotError("UNSUPPORTED_OFFICIAL_COUNT_EXP", f"Unsupported count_exp unit: {rule.unit}")
        return f"DATE_TRUNC({base_alias}.bizdate, '{granularity}')"

    def _slot_args(self, node: OfficialFunctionCall, min_count: int) -> List[str]:
        if len(node.args) < min_count:
            raise OfficialSlotError(
                "OFFICIAL_SLOT_ARITY_ERROR", f"{node.name}() expects at least {min_count} args, got {len(node.args)}"
            )
        return [self._literal_text(arg) for arg in node.args]

    def _slot_constraints(
        self,
        market: str,
        filter_scope: str,
        date: str,
        select_type: str,
        warnings: List[str],
    ) -> List[str]:
        constraints: List[str] = []
        constraints.extend(self._market_constraints(market, warnings))
        if filter_scope:
            escaped = _sql_quote(filter_scope)
            constraints.append(f"(code.hyBlkRefName = {escaped} OR code.name = {escaped})")
        if select_type:
            # The official CSV has stock-focused data only. Keep the constraint visible instead of fabricating fund rows.
            constraints.append("1=0")
            warnings.append(f"select_type {select_type!r} is not present in official A-share CSV tables")
            _mark_fallback(warnings, "1=0")
        if date:
            normalized = normalize_official_date(
                date,
                anchor_date=self.anchor_date,
                trading_dates=self.trading_dates,
                field="base.bizdate",
            )
            constraints.extend(normalized.constraints)
            warnings.extend(normalized.warnings)
            _mark_fallback(warnings, normalized.fallback_predicate)
        return constraints

    def _market_constraints(self, market: str, warnings: List[str]) -> List[str]:
        if not market:
            return []
        positives: List[int] = []
        negatives: List[int] = []
        flag_constraints: List[str] = []
        for raw in re.split(r"[|&]", market):
            item = raw.strip()
            if not item:
                continue
            negated = item.startswith("^")
            name = item[1:] if negated else item
            if name in MARKET_CODE_MAP:
                if negated:
                    negatives.append(MARKET_CODE_MAP[name])
                else:
                    positives.append(MARKET_CODE_MAP[name])
            elif name in MARKET_FLAG_MAP:
                flag = MARKET_FLAG_MAP[name]
                flag_constraints.append(f"NOT ({flag})" if negated else flag)
            elif name in {"沪深", "A股"}:
                flag_constraints.append("base.mktcode IN (0, 1)")
            elif name in {"沪深京"}:
                flag_constraints.append("base.mktcode IN (0, 1, 103)")
            else:
                flag_constraints.append("1=0")
                warnings.append(f"market {name!r} is not present in official A-share CSV tables")
                _mark_fallback(warnings, "1=0")
        constraints = []
        if positives:
            constraints.append(f"base.mktcode IN ({', '.join(str(v) for v in sorted(set(positives)))})")
        if negatives:
            constraints.append(f"base.mktcode NOT IN ({', '.join(str(v) for v in sorted(set(negatives)))})")
        constraints.extend(flag_constraints)
        return constraints

    def _literal_text(self, node: OfficialNode) -> str:
        if isinstance(node, OfficialLiteral):
            return "" if node.value is None else str(node.value)
        raise OfficialSlotError("OFFICIAL_SLOT_ARG_ERROR", "Official slot args must be literal values")

    def _literal_sql(self, node: OfficialNode) -> str:
        if not isinstance(node, OfficialLiteral):
            expr = self._expr_sql(node, [])
            return expr.sql
        value = node.value
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str) and _is_numeric_percent_literal(value):
            return value[:-1]
        return _sql_quote(str(value))

    def _literal_kind(self, value: Any) -> str:
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float)):
            return "numeric"
        if isinstance(value, str) and _is_numeric_percent_literal(value):
            return "numeric"
        return "string"

    def _sql_operator(self, op: str) -> str:
        return {
            "=": "=",
            "==": "=",
            "!=": "!=",
            "~=": "=",
            ">": ">",
            "<": "<",
            ">=": ">=",
            "<=": "<=",
        }[op]

    def _is_rank_comparison(self, node: OfficialNode) -> bool:
        return isinstance(node, OfficialComparison) and isinstance(node.left, OfficialFunctionCall) and node.left.name == "rank"

    def _is_rank_filter_comparison(self, node: OfficialNode) -> bool:
        return self._is_rank_comparison(node) and isinstance(node, OfficialComparison) and node.op in {
            "<=",
            "=",
            "<",
            ">",
            ">=",
            "!=",
            "between",
        }

    def _rank_count_exp(self, rank_call: OfficialFunctionCall) -> str:
        args = self._slot_args(rank_call, 8)
        return args[7]

    def _where_clause(self, condition: SqlExpr) -> str:
        parts = [condition.sql] + condition.constraints
        if condition.date_localized and not self._date_constraints(condition):
            parts.append(f"base.bizdate = '{self.anchor_date}'")
        return " AND ".join(_dedupe(parts)) or "1=1"

    def _condition_with_constraints(self, condition: SqlExpr) -> str:
        parts = _dedupe([condition.sql] + condition.constraints)
        if not parts:
            return "1=1"
        if len(parts) == 1:
            return parts[0]
        return "(" + " AND ".join(parts) + ")"

    def _has_conflicting_date_constraints(self, left: SqlExpr, right: SqlExpr) -> bool:
        left_dates = set(self._date_constraints(left))
        right_dates = set(self._date_constraints(right))
        return bool(left_dates and right_dates and left_dates != right_dates)

    def _date_constraints(self, condition: SqlExpr) -> List[str]:
        return [item for item in condition.constraints if self._is_base_date_constraint(item)]

    def _is_base_date_constraint(self, value: str) -> bool:
        return bool(
            re.fullmatch(r"base\.bizdate = '[^']+'", value)
            or re.fullmatch(r"base\.bizdate BETWEEN '[^']+' AND '[^']+'", value)
        )

    def _condition_as_correlated_exists(self, condition: SqlExpr) -> str:
        aliases = {"base": "lb", "code": "lc", "ext": "le", "tech": "lt"}
        tables = self._ordered_tables(condition.tables)
        condition_sql = _rewrite_aliases(condition.sql, aliases)
        constraints = [_rewrite_aliases(item, aliases) for item in condition.constraints]
        where_parts = [
            "lb.mktcode = base.mktcode",
            "lb.tgtcode = base.tgtcode",
            condition_sql,
            *constraints,
        ]
        joins = self._joins_for_aliases(tables, "lb", "lc", "le", "lt")
        return (
            "EXISTS (\n"
            "  SELECT 1\n"
            "  FROM newzl.hsj_stock_hq_basic AS lb\n"
            f"{joins}"
            f"  WHERE {' AND '.join(_dedupe(where_parts))}\n"
            ")"
        )

    def _select_sql(self, tables: List[str], where: str) -> str:
        joins = self._joins(tables)
        return (
            "SELECT base.mktcode, base.tgtcode, base.bizdate, code.name\n"
            "FROM newzl.hsj_stock_hq_basic AS base\n"
            f"{joins}"
            f"WHERE {where}"
        )

    def _joins(self, tables: Sequence[str]) -> str:
        joins = []
        table_set = set(tables)
        if "hsj_stock_code_info" in table_set or True:
            joins.append(
                "LEFT JOIN newzl.hsj_stock_code_info AS code "
                "ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode\n"
            )
        if "hsj_stock_hq_ext" in table_set:
            joins.append(
                "LEFT JOIN newzl.hsj_stock_hq_ext AS ext "
                "ON ext.mktcode = base.mktcode AND ext.tgtcode = base.tgtcode AND ext.bizdate = base.bizdate\n"
            )
        if "hsj_stock_hq_basic_technical" in table_set:
            joins.append(
                "LEFT JOIN newzl.hsj_stock_hq_basic_technical AS tech "
                "ON tech.mktcode = base.mktcode AND tech.tgtcode = base.tgtcode AND tech.bizdate = base.bizdate\n"
            )
        return "".join(joins)

    def _joins_for_aliases(
        self,
        tables: Sequence[str],
        base_alias: str,
        code_alias: str,
        ext_alias: str,
        tech_alias: str = "rtech",
    ) -> str:
        joins = []
        table_set = set(tables)
        if "hsj_stock_code_info" in table_set or True:
            joins.append(
                f"    LEFT JOIN newzl.hsj_stock_code_info AS {code_alias} "
                f"ON {code_alias}.mktcode = {base_alias}.mktcode "
                f"AND {code_alias}.tgtcode = {base_alias}.tgtcode\n"
            )
        if "hsj_stock_hq_ext" in table_set:
            joins.append(
                f"    LEFT JOIN newzl.hsj_stock_hq_ext AS {ext_alias} "
                f"ON {ext_alias}.mktcode = {base_alias}.mktcode "
                f"AND {ext_alias}.tgtcode = {base_alias}.tgtcode "
                f"AND {ext_alias}.bizdate = {base_alias}.bizdate\n"
            )
        if "hsj_stock_hq_basic_technical" in table_set:
            joins.append(
                f"    LEFT JOIN newzl.hsj_stock_hq_basic_technical AS {tech_alias} "
                f"ON {tech_alias}.mktcode = {base_alias}.mktcode "
                f"AND {tech_alias}.tgtcode = {base_alias}.tgtcode "
                f"AND {tech_alias}.bizdate = {base_alias}.bizdate\n"
            )
        return "".join(joins)

    def _ordered_tables(self, tables: Iterable[str]) -> List[str]:
        table_set = set(tables)
        ordered = []
        for item in [
            "hsj_stock_hq_basic",
            "hsj_stock_code_info",
            "hsj_stock_hq_ext",
            "hsj_stock_hq_basic_technical",
            "hsj_stock_hq_basic_prefix",
        ]:
            if item in table_set or item == "hsj_stock_hq_basic":
                ordered.append(item)
        return ordered

    def _alias(self, table: str) -> str:
        return {
            "hsj_stock_hq_basic": "base",
            "hsj_stock_code_info": "code",
            "hsj_stock_hq_ext": "ext",
            "hsj_stock_hq_basic_technical": "tech",
        }[table]


def _parse_count_exp_rule(value: str) -> CountExpRule:
    text = str(value or "").strip()
    match = re.fullmatch(
        r"(?P<mode>CONS|EXIST)\s*"
        r"(?P<op>>=|<=|!=|=|>|<)?\s*"
        r"(?P<count>每|\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百两]+)?\s*"
        r"(?P<count_unit>年|季度|月|周|日|天|分钟)?\s*"
        r"(?:[-~至到]\s*(?P<max_count>\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百两]+)\s*"
        r"(?P<max_unit>年|季度|月|周|日|天|分钟)?)?\s*"
        r"(?P<unit>年|季度|月|周|日|天|分钟)?",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        raise OfficialSlotError("UNSUPPORTED_OFFICIAL_COUNT_EXP", f"Unsupported official count_exp: {value}")
    mode = match.group("mode").upper()
    operator = match.group("op") or (">" if mode == "EXIST" else ">")
    count_text = match.group("count") or ""
    unit = _canonical_count_unit(match.group("unit") or match.group("max_unit") or match.group("count_unit") or "")
    if _canonical_count_unit(match.group("count_unit") or ""):
        unit = _canonical_count_unit(match.group("count_unit") or "")
    if count_text == "每":
        return CountExpRule(mode=mode, operator="=", count=None, unit=unit, every=True)
    count_amount = _parse_count_amount(count_text) if count_text else (0 if mode == "EXIST" else 1)
    max_count_text = match.group("max_count") or ""
    max_amount = _parse_count_amount(max_count_text) if max_count_text else None
    count, max_count, unit = _normalize_count_amounts(count_amount, max_amount, unit)
    return CountExpRule(mode=mode, operator=operator, count=count, unit=unit, every=False, max_count=max_count)


def _count_rule_predicate_sql(value_sql: str, rule: CountExpRule, comparator: str) -> str:
    threshold = 1 if rule.count is None else rule.count
    if rule.max_count is not None:
        return f"{value_sql} BETWEEN {threshold} AND {rule.max_count}"
    if rule.mode == "CONS" and comparator == "=":
        comparator = ">="
    return f"{value_sql} { _SQL_OPERATOR(comparator)} {threshold}"


def _SQL_OPERATOR(op: str) -> str:
    return {
        "=": "=",
        "==": "=",
        "!=": "!=",
        "~=": "=",
        ">": ">",
        "<": "<",
        ">=": ">=",
        "<=": "<=",
    }[op]


def _canonical_count_unit(unit: str) -> str:
    if unit == "天":
        return "日"
    return unit


def _parse_count_amount(value: str) -> float:
    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        return float(value)
    return float(_parse_small_count(value))


def _normalize_count_amounts(
    count: float,
    max_count: Optional[float],
    unit: str,
) -> Tuple[int, Optional[int], str]:
    if float(count).is_integer() and (max_count is None or float(max_count).is_integer()):
        return int(count), int(max_count) if max_count is not None else None, unit
    if unit == "年":
        normalized_count = int(round(count * 12))
        normalized_max = int(round(max_count * 12)) if max_count is not None else None
        return max(1, normalized_count), max(1, normalized_max) if normalized_max is not None else None, "月"
    if unit in {"月", ""}:
        normalized_count = int(round(count * 31))
        normalized_max = int(round(max_count * 31)) if max_count is not None else None
        return max(1, normalized_count), max(1, normalized_max) if normalized_max is not None else None, "日"
    raise OfficialSlotError("UNSUPPORTED_OFFICIAL_COUNT_EXP", f"Unsupported fractional count_exp unit: {unit}")


def _parse_period_day_count(value: str) -> Optional[int]:
    text = str(value or "").strip()
    if not text or text in {"历史", "史高", "史低", "阶段"}:
        return None
    aliases = {
        "本周": 7,
        "这周": 7,
        "本月": 31,
        "这个月": 31,
        "本月内": 31,
        "今年": 365,
        "年内": 365,
        "今年内": 365,
        "半年": 183,
        "半年内": 183,
        "半个月": 15,
        "半个月内": 15,
        "季度": 90,
        "本季度": 90,
    }
    if text in aliases:
        return aliases[text]
    match = re.fullmatch(
        r"(?P<count>\d+|[零〇一二两三四五六七八九十百两]+|半)"
        r"\s*(?:个)?(?P<unit>交易日|日|天|周|星期|月|个月|季度|季|年)(?:内)?",
        text,
    )
    if not match:
        return None
    count_text = match.group("count")
    if count_text == "半":
        amount = 0.5
    else:
        amount = float(_parse_small_count(count_text))
    unit = match.group("unit")
    multipliers = {
        "交易日": 1,
        "日": 1,
        "天": 1,
        "周": 7,
        "星期": 7,
        "月": 31,
        "个月": 31,
        "季度": 90,
        "季": 90,
        "年": 365,
    }
    return max(1, int(round(amount * multipliers[unit])))


def _parse_small_count(value: str) -> int:
    if value.isdigit():
        return int(value)
    digits = {
        "零": 0,
        "〇": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    if value in digits:
        return digits[value]
    if value == "十":
        return 10
    if "十" in value:
        left, _, right = value.partition("十")
        tens = digits[left] if left else 1
        ones = digits[right] if right else 0
        return tens * 10 + ones
    if "百" in value:
        left, _, right = value.partition("百")
        hundreds = digits[left] if left else 1
        return hundreds * 100 + (_parse_small_count(right) if right else 0)
    raise OfficialSlotError("UNSUPPORTED_OFFICIAL_COUNT_EXP", f"Unsupported count number: {value}")


def _rewrite_aliases(sql: str, aliases: Dict[str, str]) -> str:
    result = sql
    for source, target in aliases.items():
        result = re.sub(rf"\b{re.escape(source)}\.", f"{target}.", result)
    return result


def profile_training_workbook(path: str, sample_size: int = 100) -> Dict[str, Any]:
    import pandas as pd

    df = pd.read_excel(path, sheet_name="训练语料")
    function_counts: Counter[str] = Counter()
    indicator_counts: Counter[str] = Counter()
    count_exp_counts: Counter[str] = Counter()
    operator_counts: Counter[str] = Counter()
    parse_ok = 0
    parse_errors: Counter[str] = Counter()
    parse_error_samples: List[Dict[str, Any]] = []
    for row_index, row in df.iterrows():
        dsl = str(row["slot_dsl"])
        for op in [" then ", " and ", " or ", "between", "limit", "CONS", "EXIST", "~=", "!="]:
            if op in dsl:
                operator_counts[op.strip()] += 1
        try:
            ast = parse_official_slot(dsl)
            parse_ok += 1
        except OfficialSlotError as exc:
            parse_errors[exc.code] += 1
            if len(parse_error_samples) < sample_size:
                parse_error_samples.append(_workbook_error_sample(row_index, row, exc))
            for func in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", dsl):
                function_counts[func] += 1
            continue
        for call in _iter_function_calls(ast):
            function_counts[call.name] += 1
            for indicator_name in _indicator_names_from_call(call):
                indicator_counts[indicator_name] += 1
            count_exp = _count_exp_from_call(call)
            if count_exp:
                count_exp_counts[count_exp] += 1
    samples = [
        {"query": str(row["query"]), "slot_dsl": str(row["slot_dsl"])}
        for _, row in df.head(sample_size).iterrows()
    ]
    return {
        "path": path,
        "row_count": int(len(df)),
        "sample_size": int(min(sample_size, len(df))),
        "parse_ok": parse_ok,
        "parse_failed": int(len(df) - parse_ok),
        "function_counts": dict(function_counts.most_common(30)),
        "indicator_counts": dict(indicator_counts.most_common(50)),
        "count_exp_counts": dict(count_exp_counts.most_common(50)),
        "operator_counts": dict(operator_counts),
        "parse_errors": dict(parse_errors),
        "parse_error_samples": parse_error_samples,
        "samples": samples,
    }


def compile_training_workbook(
    path: str,
    sample_size: int = 20,
    mode: str = CompileMode.RECOVERY.value,
) -> Dict[str, Any]:
    import pandas as pd

    df = pd.read_excel(path, sheet_name="训练语料")
    compile_mode = CompileMode.parse(mode)
    recovery_compiler = OfficialSlotCompiler(mode=CompileMode.RECOVERY.value)
    strict_compiler = OfficialSlotCompiler(mode=CompileMode.STRICT.value)
    strict_parse_ok = 0
    recovery_parse_ok = 0
    repaired_rows = 0
    recovery_compile_ok = 0
    strict_compile_ok = 0
    warning_rows = 0
    degraded_rows = 0
    sql_false_fallback_rows = 0
    sql_true_fallback_rows = 0
    strict_parse_errors: Counter[str] = Counter()
    parse_errors: Counter[str] = Counter()
    compile_errors: Counter[str] = Counter()
    recovery_compile_errors: Counter[str] = Counter()
    strict_compile_errors: Counter[str] = Counter()
    repair_counts: Counter[str] = Counter()
    compile_error_details: Counter[str] = Counter()
    compile_error_domains: Counter[str] = Counter()
    recovery_compile_error_details: Counter[str] = Counter()
    recovery_compile_error_domains: Counter[str] = Counter()
    strict_compile_error_details: Counter[str] = Counter()
    strict_compile_error_domains: Counter[str] = Counter()
    strict_parse_error_samples: List[Dict[str, Any]] = []
    parse_error_samples: List[Dict[str, Any]] = []
    repair_samples: List[Dict[str, Any]] = []
    compile_error_samples: List[Dict[str, Any]] = []
    recovery_compile_error_samples: List[Dict[str, Any]] = []
    strict_compile_error_samples: List[Dict[str, Any]] = []
    degraded_samples: List[Dict[str, Any]] = []
    compiled_samples: List[Dict[str, Any]] = []
    strict_compiled_samples: List[Dict[str, Any]] = []
    for row_index, row in df.iterrows():
        dsl = str(row["slot_dsl"])
        strict_parse_error: Optional[OfficialSlotError] = None
        try:
            parse_official_slot_with_diagnostics(dsl, mode=CompileMode.STRICT.value)
        except OfficialSlotError as exc:
            strict_parse_error = exc
            strict_parse_errors[exc.code] += 1
            if len(strict_parse_error_samples) < sample_size:
                strict_parse_error_samples.append(_workbook_error_sample(row_index, row, exc))
        else:
            strict_parse_ok += 1

        try:
            strict_result = strict_compiler.compile(dsl)
            strict_compile_ok += 1
            if len(strict_compiled_samples) < sample_size:
                strict_compiled_samples.append(
                    {
                        "excel_row": int(row_index + 2),
                        "query": str(row.get("query", "")),
                        "slot_dsl": dsl,
                        "requires_tables": strict_result.requires_tables,
                        "strict_success": True,
                        "repair_codes": [],
                        "warnings": [],
                        "sql_preview": strict_result.sql[:600],
                    }
                )
        except OfficialSlotError as exc:
            strict_compile_errors[exc.code] += 1
            strict_compile_error_details[_compile_error_detail(exc)] += 1
            strict_compile_error_domains[classify_official_compile_error_domain(exc)] += 1
            if len(strict_compile_error_samples) < sample_size:
                strict_compile_error_samples.append(_workbook_error_sample(row_index, row, exc))

        parsed: Optional[OfficialParseResult] = None
        try:
            parsed = parse_official_slot_with_diagnostics(
                dsl,
                mode=CompileMode.RECOVERY.value,
            )
            recovery_parse_ok += 1
        except OfficialSlotError as exc:
            parse_errors[exc.code] += 1
            if len(parse_error_samples) < sample_size:
                parse_error_samples.append(_workbook_error_sample(row_index, row, exc))
        if parsed is not None and parsed.repairs:
            repaired_rows += 1
            repair_counts.update(repair.code for repair in parsed.repairs)
            if len(repair_samples) < sample_size:
                repair_samples.append(
                    {
                        "excel_row": int(row_index + 2),
                        "query": str(row.get("query", "")),
                        "slot_dsl": dsl,
                        "normalized_source": parsed.normalized_source,
                        "repairs": [repair.to_dict() for repair in parsed.repairs],
                    }
                )
        try:
            result = recovery_compiler.compile(dsl)
            recovery_compile_ok += 1
            if result.warnings:
                warning_rows += 1
            if result.degraded:
                degraded_rows += 1
                if len(degraded_samples) < sample_size:
                    degraded_samples.append(
                        {
                            "excel_row": int(row_index + 2),
                            "query": str(row.get("query", "")),
                            "slot_dsl": dsl,
                            "repair_codes": [repair.code for repair in result.repairs],
                            "warnings": result.warnings,
                        }
                    )
            if "1=0" in result.fallback_predicates:
                sql_false_fallback_rows += 1
            if "1=1" in result.fallback_predicates:
                sql_true_fallback_rows += 1
            if len(compiled_samples) < sample_size:
                compiled_samples.append(
                    {
                        "excel_row": int(row_index + 2),
                        "query": str(row.get("query", "")),
                        "slot_dsl": dsl,
                        "requires_tables": result.requires_tables,
                        "strict_success": result.strict_success and strict_parse_error is None,
                        "repair_codes": [repair.code for repair in result.repairs],
                        "warnings": result.warnings,
                        "sql_preview": result.sql[:600],
                    }
                )
        except OfficialSlotError as exc:
            recovery_compile_errors[exc.code] += 1
            recovery_compile_error_details[_compile_error_detail(exc)] += 1
            recovery_compile_error_domains[classify_official_compile_error_domain(exc)] += 1
            if len(recovery_compile_error_samples) < sample_size:
                recovery_compile_error_samples.append(_workbook_error_sample(row_index, row, exc))
            if parsed is not None:
                compile_errors[exc.code] += 1
                compile_error_details[_compile_error_detail(exc)] += 1
                compile_error_domains[classify_official_compile_error_domain(exc)] += 1
                if len(compile_error_samples) < sample_size:
                    compile_error_samples.append(_workbook_error_sample(row_index, row, exc))
    row_count = int(len(df))
    selected_parse_ok = strict_parse_ok if compile_mode is CompileMode.STRICT else recovery_parse_ok
    selected_compile_ok = strict_compile_ok if compile_mode is CompileMode.STRICT else recovery_compile_ok
    selected_compile_errors = (
        strict_compile_errors if compile_mode is CompileMode.STRICT else recovery_compile_errors
    )
    selected_compile_error_details = (
        strict_compile_error_details
        if compile_mode is CompileMode.STRICT
        else recovery_compile_error_details
    )
    selected_compile_error_domains = (
        strict_compile_error_domains
        if compile_mode is CompileMode.STRICT
        else recovery_compile_error_domains
    )
    selected_compile_error_samples = (
        strict_compile_error_samples
        if compile_mode is CompileMode.STRICT
        else recovery_compile_error_samples
    )
    selected_parse_error_samples = (
        strict_parse_error_samples
        if compile_mode is CompileMode.STRICT
        else parse_error_samples
    )
    selected_compiled_samples = (
        strict_compiled_samples if compile_mode is CompileMode.STRICT else compiled_samples
    )
    return {
        "path": path,
        "mode": compile_mode.value,
        "row_count": row_count,
        "strict_parse_ok": strict_parse_ok,
        "strict_parse_failed": row_count - strict_parse_ok,
        "recovery_parse_ok": recovery_parse_ok,
        "recovery_parse_failed": row_count - recovery_parse_ok,
        "repaired_rows": repaired_rows,
        "repair_counts": dict(repair_counts),
        "strict_compile_ok": strict_compile_ok,
        "strict_compile_failed": row_count - strict_compile_ok,
        "recovery_compile_ok": recovery_compile_ok,
        "recovery_compile_failed": row_count - recovery_compile_ok,
        "warning_rows": warning_rows,
        "degraded_rows": degraded_rows,
        "sql_false_fallback_rows": sql_false_fallback_rows,
        "sql_true_fallback_rows": sql_true_fallback_rows,
        "selected_parse_ok": selected_parse_ok,
        "selected_parse_failed": row_count - selected_parse_ok,
        "selected_compile_ok": selected_compile_ok,
        "selected_compile_failed": row_count - selected_compile_ok,
        "selected_compile_rate_on_all_rows": (
            round(selected_compile_ok / row_count, 6) if row_count else 0
        ),
        "selected_compile_errors": dict(selected_compile_errors),
        "selected_compile_error_details": dict(selected_compile_error_details.most_common(30)),
        "selected_compile_error_domains": dict(selected_compile_error_domains.most_common(30)),
        "selected_compile_error_samples": selected_compile_error_samples,
        "selected_parse_error_samples": selected_parse_error_samples,
        "selected_compiled_samples": selected_compiled_samples,
        "strict_compile_rate_on_all_rows": round(strict_compile_ok / row_count, 6) if row_count else 0,
        "recovery_compile_rate_on_all_rows": round(recovery_compile_ok / row_count, 6) if row_count else 0,
        "recovery_compile_rate_on_parse_ok": (
            round(recovery_compile_ok / recovery_parse_ok, 6) if recovery_parse_ok else 0
        ),
        "parse_ok": recovery_parse_ok,
        "parse_failed": row_count - recovery_parse_ok,
        "compile_ok": recovery_compile_ok,
        "compile_failed": recovery_parse_ok - recovery_compile_ok,
        "compile_rate_on_all_rows": round(recovery_compile_ok / row_count, 6) if row_count else 0,
        "compile_rate_on_parse_ok": (
            round(recovery_compile_ok / recovery_parse_ok, 6) if recovery_parse_ok else 0
        ),
        "strict_parse_errors": dict(strict_parse_errors),
        "parse_errors": dict(parse_errors),
        "compile_errors": dict(compile_errors),
        "recovery_compile_errors": dict(recovery_compile_errors),
        "strict_compile_errors": dict(strict_compile_errors),
        "compile_error_details": dict(compile_error_details.most_common(30)),
        "compile_error_domains": dict(compile_error_domains.most_common(30)),
        "recovery_compile_error_details": dict(recovery_compile_error_details.most_common(30)),
        "recovery_compile_error_domains": dict(recovery_compile_error_domains.most_common(30)),
        "strict_compile_error_details": dict(strict_compile_error_details.most_common(30)),
        "strict_compile_error_domains": dict(strict_compile_error_domains.most_common(30)),
        "strict_parse_error_samples": strict_parse_error_samples,
        "parse_error_samples": parse_error_samples,
        "repair_samples": repair_samples,
        "compile_error_samples": compile_error_samples,
        "recovery_compile_error_samples": recovery_compile_error_samples,
        "strict_compile_error_samples": strict_compile_error_samples,
        "degraded_samples": degraded_samples,
        "compiled_samples": compiled_samples,
        "strict_compiled_samples": strict_compiled_samples,
    }


def profile_official_csvs(root: str) -> Dict[str, Any]:
    base = Path(root)
    files = {
        "hsj_stock_code_info": base / "Doris A股行情数据集" / "股票代码表" / "hsj_stock_code_info.csv",
        "hsj_stock_hq_basic": base / "Doris A股行情数据集" / "行情基本数据宽表" / "hsj_stock_hq_basic.csv",
        "hsj_stock_hq_ext": base / "Doris A股行情数据集" / "行情衍生数据" / "hsj_stock_hq_ext.csv",
    }
    return {name: _profile_csv(path) for name, path in files.items()}


def _profile_csv(path: Path) -> Dict[str, Any]:
    row_count = 0
    fields: List[str] = []
    markets: Counter[str] = Counter()
    first_date = ""
    last_date = ""
    sample_rows: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        for row in reader:
            row_count += 1
            if len(sample_rows) < 3:
                sample_rows.append(dict(row))
            if row.get("mktcode"):
                markets[row["mktcode"]] += 1
            date_value = str(row.get("bizdate") or "").strip()
            if date_value:
                first_date = date_value if not first_date else min(first_date, date_value)
                last_date = date_value if not last_date else max(last_date, date_value)
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "row_count": row_count,
        "column_count": len(fields),
        "columns": fields,
        "markets": dict(markets),
        "first_date": first_date,
        "last_date": last_date,
        "sample_rows": sample_rows,
    }


def write_profile_report(profile: Dict[str, Any], output: str) -> None:
    path = Path(output)
    lines = [
        "# 官方真实数据画像报告",
        "",
        "本报告由 `findsl.official_slot` 读取官方 CSV 与训练语料生成，用于证明项目已经识别真实资料规模、字段和 DSL 分布。",
        "",
    ]
    csv_profile = profile.get("csv", {})
    if csv_profile:
        lines.extend(["## CSV 数据表", "", "| 表 | 行数 | 列数 | 文件大小 | 日期范围 |", "|---|---:|---:|---:|---|"])
        for name, item in csv_profile.items():
            date_range = f"{item.get('first_date', '')} 至 {item.get('last_date', '')}".strip(" 至")
            lines.append(
                f"| {name} | {item['row_count']} | {item['column_count']} | {item['bytes']} | {date_range} |"
            )
        lines.append("")
    workbook = profile.get("workbook")
    if workbook:
        lines.extend(
            [
                "## 官方 DSL 训练语料",
                "",
                f"- 样例总数：{workbook['row_count']}",
                f"- 语法解析成功：{workbook['parse_ok']}",
                f"- 语法解析失败：{workbook['parse_failed']}",
                "",
                "### 高频函数",
                "",
                "| 函数 | 次数 |",
                "|---|---:|",
            ]
        )
        for name, count in workbook["function_counts"].items():
            lines.append(f"| {name} | {count} |")
        lines.extend(["", "### 高频指标", "", "| 指标 | 次数 |", "|---|---:|"])
        for name, count in workbook["indicator_counts"].items():
            label = name if name else "空指标"
            lines.append(f"| {label} | {count} |")
        lines.extend(["", "### 高频出现方式", "", "| 出现方式 | 次数 |", "|---|---:|"])
        for name, count in workbook.get("count_exp_counts", {}).items():
            lines.append(f"| {name} | {count} |")
        if workbook.get("parse_error_samples"):
            lines.extend(["", "### 语法解析失败样本", "", "| Excel 行 | 错误码 | 原因 | DSL |", "|---:|---|---|---|"])
            for item in workbook["parse_error_samples"][:10]:
                lines.append(
                    f"| {item['excel_row']} | {item['code']} | {_md_escape(item['message'])} | `{_md_escape(item['slot_dsl'])}` |"
                )
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_coverage_report(coverage: Dict[str, Any], output: str) -> None:
    path = Path(output)
    lines = [
        "# 官方槽位 DSL 编译覆盖率报告",
        "",
        "本报告逐条读取官方 `选股提槽实例.xlsx`，先做语法解析，再尝试把可落地槽位编译为 `newzl` 三表上的 Doris SQL。它用于区分三类情况：语法可解析、可在本批官方三表落地、以及规范存在但当前官方数据没有对应字段。",
        "",
        "## 覆盖率总览",
        "",
        f"- 编译模式：{coverage.get('mode', CompileMode.RECOVERY.value)}",
        "",
        "| 指标 | 数值 |",
        "|---|---:|",
        f"| 官方样例总数 | {coverage['row_count']} |",
        f"| 主展示模式解析成功 | {coverage['selected_parse_ok']} |",
        f"| 主展示模式编译成功 | {coverage['selected_compile_ok']} |",
        f"| 严格解析成功 | {coverage['strict_parse_ok']} |",
        f"| 严格解析失败 | {coverage['strict_parse_failed']} |",
        f"| 恢复解析成功 | {coverage['recovery_parse_ok']} |",
        f"| 恢复解析失败 | {coverage['recovery_parse_failed']} |",
        f"| 发生源码修复 | {coverage['repaired_rows']} |",
        f"| 严格编译成功 | {coverage['strict_compile_ok']} |",
        f"| 严格编译失败 | {coverage['strict_compile_failed']} |",
        f"| 恢复编译成功 | {coverage['recovery_compile_ok']} |",
        f"| 恢复编译失败 | {coverage['recovery_compile_failed']} |",
        f"| 含 warning 的恢复结果 | {coverage['warning_rows']} |",
        f"| 降级恢复结果 | {coverage['degraded_rows']} |",
        f"| 含 1=0 降级谓词 | {coverage['sql_false_fallback_rows']} |",
        f"| 含 1=1 降级谓词 | {coverage['sql_true_fallback_rows']} |",
        f"| 严格全量编译率 | {coverage['strict_compile_rate_on_all_rows']:.2%} |",
        f"| 恢复全量编译率 | {coverage['recovery_compile_rate_on_all_rows']:.2%} |",
        "",
        "兼容字段 `parse_ok/compile_ok` 暂时保留，均指 recovery 口径，不代表严格正确率。",
        "",
        f"## {coverage.get('mode', CompileMode.RECOVERY.value)} 模式编译失败错误码",
        "",
        "| 错误码 | 次数 |",
        "|---|---:|",
    ]
    for code, count in coverage.get("selected_compile_errors", {}).items():
        lines.append(f"| {code} | {count} |")
    lines.extend(["", "## 编译失败细分原因 TopN", "", "| 原因 | 次数 |", "|---|---:|"])
    for detail, count in coverage.get("selected_compile_error_details", {}).items():
        lines.append(f"| {_md_escape(detail)} | {count} |")
    if coverage.get("selected_compile_error_domains"):
        lines.extend(
            [
                "",
                "## 缺失数据域分层",
                "",
                "这一节把不能落地的官方样例按根因归类。它不是为失败找借口，而是区分“本批三张官方 A 股行情表没有该数据域”和“编译器函数语义仍需增强”两类问题，避免生成看似可执行但实际无字段来源的伪 SQL。",
                "",
                "| 缺失或待增强类别 | 次数 |",
                "|---|---:|",
            ]
        )
        for domain, count in coverage["selected_compile_error_domains"].items():
            lines.append(f"| {_md_escape(domain)} | {count} |")
    if coverage.get("selected_parse_error_samples"):
        lines.extend(["", "## 语法解析失败样本", "", "| Excel 行 | 错误码 | 原因 | DSL |", "|---:|---|---|---|"])
        for item in coverage["selected_parse_error_samples"]:
            lines.append(
                f"| {item['excel_row']} | {item['code']} | {_md_escape(item['message'])} | `{_md_escape(item['slot_dsl'])}` |"
            )
    if coverage.get("selected_compile_error_samples"):
        lines.extend(["", "## 编译失败样本", "", "| Excel 行 | 错误码 | 原因 | DSL |", "|---:|---|---|---|"])
        for item in coverage["selected_compile_error_samples"]:
            lines.append(
                f"| {item['excel_row']} | {item['code']} | {_md_escape(item['message'])} | `{_md_escape(item['slot_dsl'])}` |"
            )
    if coverage.get("selected_compiled_samples"):
        sample_heading = (
            "strict 编译成功样本"
            if coverage.get("mode") == CompileMode.STRICT.value
            else "recovery 编译返回样本（含降级状态）"
        )
        lines.extend(
            [
                "",
                f"## {sample_heading}",
                "",
                "| Excel 行 | 严格成功 | repair | warning 数 | 依赖表 | SQL 预览 |",
                "|---:|---|---|---:|---|---|",
            ]
        )
        for item in coverage["selected_compiled_samples"]:
            tables = ", ".join(item["requires_tables"])
            repairs = ", ".join(item.get("repair_codes", [])) or "无"
            strict_success = "true" if item.get("strict_success") else "false"
            lines.append(
                f"| {item['excel_row']} | {strict_success} | {repairs} | "
                f"{len(item.get('warnings', []))} | {tables} | `{_md_escape(item['sql_preview'])}` |"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def profile_to_json(profile: Dict[str, Any], output: str) -> None:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")


INDICATOR_ARG_INDEXES: Dict[str, Tuple[int, ...]] = {
    "indicator": (2,),
    "rank": (2,),
    "belong_industry": (2,),
    "queryData": (2,),
    "cross_above": (2, 3),
    "cross_down": (2, 3),
    "close_together": (2, 3),
    "reset": (2, 3),
    "golden_cross": (2, 3),
    "record_high": (2,),
    "record_low": (2,),
    "position": (2,),
}

COUNT_EXP_ARG_INDEXES: Dict[str, int] = {
    "indicator": 6,
    "rank": 7,
    "cross_above": 6,
    "cross_down": 6,
    "close_together": 6,
    "reset": 6,
    "golden_cross": 6,
    "record_high": 7,
    "record_low": 7,
    "position": 7,
}


def _iter_function_calls(node: OfficialNode) -> Iterable[OfficialFunctionCall]:
    if isinstance(node, OfficialFunctionCall):
        yield node
        for arg in node.args:
            yield from _iter_function_calls(arg)
    elif isinstance(node, OfficialBinaryOp):
        yield from _iter_function_calls(node.left)
        yield from _iter_function_calls(node.right)
    elif isinstance(node, OfficialComparison):
        yield from _iter_function_calls(node.left)
        yield from _iter_function_calls(node.right)
    elif isinstance(node, OfficialLimit):
        yield from _iter_function_calls(node.expr)
    elif isinstance(node, OfficialRangeLiteral):
        yield from _iter_function_calls(node.lower)
        yield from _iter_function_calls(node.upper)


def _indicator_names_from_call(call: OfficialFunctionCall) -> List[str]:
    names: List[str] = []
    for index in INDICATOR_ARG_INDEXES.get(call.name, ()):
        if index < len(call.args):
            text = _node_literal_text(call.args[index])
            if text:
                names.append(text)
    return names


def _count_exp_from_call(call: OfficialFunctionCall) -> str:
    index = COUNT_EXP_ARG_INDEXES.get(call.name)
    if index is None or index >= len(call.args):
        return ""
    return _node_literal_text(call.args[index])


def _node_literal_text(node: OfficialNode) -> str:
    if isinstance(node, OfficialLiteral):
        return "" if node.value is None else str(node.value)
    return ""


def _workbook_error_sample(row_index: int, row: Any, exc: OfficialSlotError) -> Dict[str, Any]:
    return {
        "excel_row": int(row_index + 2),
        "query": str(row.get("query", "")),
        "slot_dsl": str(row.get("slot_dsl", "")),
        "code": exc.code,
        "message": str(exc),
    }


def _compile_error_detail(exc: OfficialSlotError) -> str:
    message = str(exc)
    if exc.code == "UNSUPPORTED_OFFICIAL_INDICATOR":
        match = re.search(r":\s*(?P<name>.+)$", message)
        if match:
            return f"{exc.code}: {match.group('name')}"
    if exc.code == "UNSUPPORTED_OFFICIAL_FUNCTION":
        match = re.search(r":\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)", message)
        if match:
            return f"{exc.code}: {match.group('name')}"
    return f"{exc.code}: {message}"


DOMAIN_KEYWORDS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    (
        "指数成分与权重数据缺失",
        ("成分股", "跟踪指数", "指数权重", "权重", "成份股"),
    ),
    (
        "基金产品与持仓数据缺失",
        ("基金", "ETF", "LOF", "REIT", "累计净值", "单位净值", "规模", "申购", "赎回", "限购"),
    ),
    (
        "财务报表数据缺失",
        (
            "归母",
            "净利润",
            "营业收入",
            "每股收益",
            "资产",
            "负债",
            "现金",
            "资本公积",
            "利润",
            "收入",
            "股息",
            "分红",
            "净资产收益率",
            "资产回报率",
            "销售净利率",
            "总资产",
            "净资产",
            "预测市盈率",
        ),
    ),
    (
        "用户账户与自选股数据缺失",
        ("我的", "持仓", "自选", "账户"),
    ),
    (
        "龙虎榜与交易异动数据缺失",
        ("龙虎榜", "上榜"),
    ),
    (
        "公司画像与题材热度数据缺失",
        ("主营业务", "热门", "龙头", "题材", "概念热度", "优质", "潜力", "强势", "估值"),
    ),
    (
        "公司事件与交易日历扩展数据缺失",
        ("上市日期", "复牌日期", "停牌日期", "除权除息", "财报期", "分红日"),
    ),
    (
        "高级形态/相似度模型数据缺失",
        ("相似K线", "KDJ", "RSI", "MACD", "波动率", "背离", "主力抢筹", "回调", "粘合"),
    ),
    (
        "交易规则与跨市场标的属性缺失",
        ("每手股数", "投资市场", "港股", "美股", "期货", "债券", "可转债", "新三板"),
    ),
)


def classify_official_indicator_domain(indicator_name: str) -> str:
    text = str(indicator_name or "").strip()
    for domain, keywords in DOMAIN_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return domain
    return "官方三表未覆盖的其他指标"


def classify_official_compile_error_domain(exc: OfficialSlotError) -> str:
    detail = _compile_error_detail(exc)
    if exc.code == "UNSUPPORTED_OFFICIAL_INDICATOR":
        indicator = detail.split(":", 1)[-1].strip()
        return classify_official_indicator_domain(indicator)
    if exc.code == "UNSUPPORTED_OFFICIAL_FUNCTION":
        return "函数语义待扩展"
    if exc.code == "UNSUPPORTED_OFFICIAL_COUNT_EXP":
        return "出现次数/连续次数时间语义待特征表增强"
    if exc.code == "UNSUPPORTED_OFFICIAL_PERIOD_FUNCTION":
        return "创新高低/位置函数复杂周期待增强"
    if exc.code.startswith("OFFICIAL_RANK"):
        return "排名表达式形态待规范或待扩展"
    if exc.code == "OFFICIAL_EXPR_ERROR":
        return "复杂表达式组合待扩展"
    return "其他解析或编译问题"


def _parse_range_text(value: str) -> Optional[OfficialRangeLiteral]:
    match = re.fullmatch(r"\s*([\[(])\s*(?P<lower>.+?)\s*,\s*(?P<upper>.+?)\s*([\])])\s*", value)
    if not match:
        return None
    return OfficialRangeLiteral(
        lower=_range_part_literal(match.group("lower")),
        upper=_range_part_literal(match.group("upper")),
        lower_inclusive=match.group(1) == "[",
        upper_inclusive=match.group(4) == "]",
    )


def _range_part_literal(value: str) -> OfficialLiteral:
    text = value.strip()
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?%", text):
        return OfficialLiteral(text)
    if re.fullmatch(r"[+-]?\d+", text):
        return OfficialLiteral(int(text))
    if re.fullmatch(r"[+-]?\d+\.\d+", text):
        return OfficialLiteral(float(text))
    return OfficialLiteral(text)


def _md_escape(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _rank_alias_sql(sql: str) -> str:
    return sql.replace("base.", "rb.").replace("code.", "rcode.").replace("ext.", "rext.").replace("tech.", "rtech.")


def _normalize_iso_date(value: str) -> str:
    text = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    return ""


def _sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _is_numeric_percent_literal(value: str) -> bool:
    return bool(re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)%", value))


def _dedupe(items: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result

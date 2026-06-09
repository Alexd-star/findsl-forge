from __future__ import annotations

import csv
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

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


@dataclass(frozen=True)
class OfficialCompileResult:
    source: str
    ast: Dict[str, Any]
    sql: str
    requires_tables: List[str]
    warnings: List[str]


OPERATORS = {">=", "<=", "!=", "~=", ">", "<", "=", "+", "-", "*", "/", "(", ")", "[", "]", ","}
KEYWORDS = {"and", "or", "then", "between", "limit", "true", "false"}
AGGREGATE_FUNCTIONS = {"MAX", "MIN", "AVG", "SUM"}
GROWTH_FUNCTIONS = {"GROWTH_RISE", "GROWTH_FALL"}


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
    "涨停封单价": IndicatorMeta("hsj_stock_hq_basic", kind="numeric", expression=_price_expr("upSealPx")),
    "涨停封单量": IndicatorMeta("hsj_stock_hq_basic", "upSealVol"),
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
    "股票名称": IndicatorMeta("hsj_stock_code_info", "name", kind="string"),
    "证券代码": IndicatorMeta("hsj_stock_code_info", "tztcode", kind="string"),
    "股票代码": IndicatorMeta("hsj_stock_code_info", "tgtcode", kind="string"),
    "所属行业": IndicatorMeta("hsj_stock_code_info", "hyBlkRefName", kind="string"),
}


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
    def __init__(self, source: str):
        self.source = source
        self.tokens = lex_official_slot(source)
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


def parse_official_slot(source: str) -> OfficialNode:
    return OfficialSlotParser(source).parse()


class OfficialSlotCompiler:
    def __init__(self, anchor_date: str = "2026-04-14", trading_dates: Optional[Sequence[str]] = None):
        self.anchor_date = anchor_date
        self.trading_dates = list(trading_dates or [])

    def compile(self, source: str) -> OfficialCompileResult:
        ast = parse_official_slot(source)
        warnings: List[str] = []
        sql, tables = self._compile_query(ast, warnings)
        return OfficialCompileResult(
            source=source,
            ast=ast.to_dict(),
            sql=sql,
            requires_tables=tables,
            warnings=warnings,
        )

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
        if self._is_rank_comparison(node):
            return self._compile_rank_query(node, None, warnings)
        condition = self._condition_sql(node, warnings)
        tables = self._ordered_tables(condition.tables)
        where = self._where_clause(condition)
        return self._select_sql(tables, where), tables

    def _compile_then(self, node: OfficialBinaryOp, warnings: List[str]) -> Tuple[str, List[str]]:
        left = self._condition_sql(node.left, warnings)
        return self._compile_rank_query(node.right, left, warnings)

    def _flatten_then_chain(self, node: OfficialNode) -> List[OfficialNode]:
        if isinstance(node, OfficialBinaryOp) and node.op == "then":
            return self._flatten_then_chain(node.left) + self._flatten_then_chain(node.right)
        return [node]

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
            if not self._is_rank_comparison(stage):
                raise OfficialSlotError(
                    "OFFICIAL_RANK_SHAPE_ERROR",
                    "all stages after then must be rank(...) comparisons in the grounded pipeline",
                )
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
        limit_value = self._literal_sql(node.right)
        if node.op not in {"<=", "=", "<", ">", ">=", "!="}:
            raise OfficialSlotError("OFFICIAL_RANK_OPERATOR_ERROR", f"Unsupported rank comparison: {node.op}")
        rank_limit = f"rank_no {self._sql_operator(node.op)} {limit_value}"
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
            f"         ROW_NUMBER() OVER (PARTITION BY base.bizdate ORDER BY {rank_expr.sql} {self._rank_order(rank_call)}, base.tgtcode ASC) AS rank_no\n"
            "  FROM newzl.hsj_stock_hq_basic AS base\n"
            f"{joins}"
            f"  WHERE {where}\n"
            ") AS ranked\n"
            f"WHERE {rank_limit}"
        )
        return sql, tables

    def _condition_sql(self, node: OfficialNode, warnings: List[str]) -> SqlExpr:
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
        if self._is_rank_comparison(node):
            return self._rank_condition_sql(node, warnings)
        if isinstance(node, OfficialComparison):
            return self._comparison_sql(node, warnings)
        expr = self._expr_sql(node, warnings)
        if expr.kind == "boolean":
            return expr
        raise OfficialSlotError("OFFICIAL_CONDITION_ERROR", "Top-level official DSL expression must be boolean")

    def _rank_condition_sql(self, node: OfficialNode, warnings: List[str]) -> SqlExpr:
        if not isinstance(node, OfficialComparison) or not isinstance(node.left, OfficialFunctionCall):
            raise OfficialSlotError("OFFICIAL_RANK_SHAPE_ERROR", "rank condition must be rank(...) comparison")
        rank_call = node.left
        if self._rank_count_exp(rank_call):
            return self._rank_count_condition_sql(node, None, warnings)
        rank_expr = self._rank_expr(rank_call, warnings)
        if node.op not in {"<=", "=", "<", ">", ">=", "!="}:
            raise OfficialSlotError("OFFICIAL_RANK_OPERATOR_ERROR", f"Unsupported rank comparison: {node.op}")
        rank_sql = _rank_alias_sql(rank_expr.sql)
        constraints = [_rank_alias_sql(item) for item in rank_expr.constraints]
        where = " AND ".join(_dedupe(constraints)) or "1=1"
        tables = self._ordered_tables(rank_expr.tables)
        joins = self._joins_for_aliases(tables, "rb", "rcode", "rext")
        limit_value = self._literal_sql(node.right)
        sql = (
            "EXISTS (\n"
            "  SELECT 1 FROM (\n"
            "    SELECT rb.mktcode, rb.tgtcode, rb.bizdate,\n"
            f"           ROW_NUMBER() OVER (PARTITION BY rb.bizdate ORDER BY {rank_sql} {self._rank_order(rank_call)}, rb.tgtcode ASC) AS rank_no\n"
            "    FROM newzl.hsj_stock_hq_basic AS rb\n"
            f"{joins}"
            f"    WHERE {where}\n"
            "  ) AS ranked\n"
            "  WHERE ranked.mktcode = base.mktcode\n"
            "    AND ranked.tgtcode = base.tgtcode\n"
            "    AND ranked.bizdate = base.bizdate\n"
            f"    AND ranked.rank_no {self._sql_operator(node.op)} {limit_value}\n"
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
        if node.op not in {"<=", "=", "<", ">", ">=", "!="}:
            raise OfficialSlotError("OFFICIAL_RANK_OPERATOR_ERROR", f"Unsupported rank comparison: {node.op}")
        args = self._slot_args(rank_call, 8)
        market, filter_scope, indicator_name, direction, date, select_type, agg_func, count_exp = args[:8]
        if agg_func:
            raise OfficialSlotError(
                "UNSUPPORTED_OFFICIAL_COUNT_EXP",
                "rank(..., count_exp) with agg_func needs a materialized rank feature table",
            )
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
        limit_value = self._literal_sql(node.right)
        predicate = f"ranked.rank_no {self._sql_operator(node.op)} {limit_value}"
        ranked_sql = (
            "SELECT rb.mktcode, rb.tgtcode,\n"
            f"       {bucket_expr} AS bucket_key,\n"
            f"       ROW_NUMBER() OVER (PARTITION BY {bucket_expr} ORDER BY {rank_sql} {self._rank_order(rank_call)}, rb.tgtcode ASC) AS rank_no\n"
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

    def _comparison_sql(self, node: OfficialComparison, warnings: List[str]) -> SqlExpr:
        if isinstance(node.left, OfficialFunctionCall) and node.left.name == "indicator":
            args = self._slot_args(node.left, 7)
            if args[6]:
                return self._count_exp_comparison_sql(node.left, node.op, node.right, warnings)
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
            if name in {"record_high", "record_low", "position"}:
                return self._period_feature_expr(node, warnings)
            if name in {"cross_above", "cross_down", "golden_cross"}:
                return self._cross_expr(node, name, warnings)
            raise OfficialSlotError("UNSUPPORTED_OFFICIAL_FUNCTION", f"Unsupported official function: {name}")
        if isinstance(node, OfficialIdentifier):
            return SqlExpr(node.name, "identifier", [], [])
        raise OfficialSlotError("OFFICIAL_EXPR_ERROR", f"Unsupported expression node: {type(node).__name__}")

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
        meta = INDICATORS.get(indicator_name)
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
        meta = INDICATORS.get(indicator_name)
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
            subquery = (
                f"(SELECT COUNT(*)\n"
                " FROM newzl.hsj_stock_hq_basic AS wb\n"
                f"{self._window_joins(tables)}"
                f" WHERE {' AND '.join(_dedupe(where_parts + [predicate]))}) "
                f"{self._sql_operator(comparator)} {threshold}"
            )
        constraints = self._slot_constraints(market, filter_scope, "", select_type, warnings)
        constraints.extend(self._outer_snapshot_constraints(date))
        return SqlExpr(subquery, "boolean", tables, constraints)

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
        return (
            "(SELECT COUNT(*)\n"
            " FROM (\n"
            f"{inner_sql}\n"
            ") AS bucketed\n"
            f" WHERE bucketed.agg_value IS NOT NULL AND {predicate}) "
            f"{self._sql_operator(comparator)} {threshold}"
        )

    def _belong_industry_expr(self, node: OfficialFunctionCall, warnings: List[str]) -> SqlExpr:
        args = self._slot_args(node, 5)
        market, filter_scope, indicator_name, date, agg_func = args[:5]
        meta = INDICATORS.get(indicator_name)
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

        meta = INDICATORS.get(indicator_name)
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
        meta = INDICATORS.get(indicator_name)
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
        return where_parts

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
        if date:
            normalized = normalize_official_date(
                date,
                anchor_date=self.anchor_date,
                trading_dates=self.trading_dates,
                field="base.bizdate",
            )
            constraints.extend(normalized.constraints)
            warnings.extend(normalized.warnings)
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
        for item in ["hsj_stock_hq_basic", "hsj_stock_code_info", "hsj_stock_hq_ext", "hsj_stock_hq_basic_technical"]:
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
        r"(?P<mode>CONS|EXIST)\s*(?P<op>>=|<=|!=|=|>|<)?\s*(?P<count>每|\d+|[零〇一二两三四五六七八九十百两]+)?\s*(?P<unit>年|季度|月|周|日|天)?",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        raise OfficialSlotError("UNSUPPORTED_OFFICIAL_COUNT_EXP", f"Unsupported official count_exp: {value}")
    mode = match.group("mode").upper()
    operator = match.group("op") or (">" if mode == "EXIST" else ">")
    count_text = match.group("count") or ""
    unit = match.group("unit") or ""
    if unit == "天":
        unit = "日"
    if count_text == "每":
        return CountExpRule(mode=mode, operator="=", count=None, unit=unit, every=True)
    count = _parse_small_count(count_text) if count_text else (0 if mode == "EXIST" else 1)
    return CountExpRule(mode=mode, operator=operator, count=count, unit=unit, every=False)


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


def compile_training_workbook(path: str, sample_size: int = 20) -> Dict[str, Any]:
    import pandas as pd

    df = pd.read_excel(path, sheet_name="训练语料")
    compiler = OfficialSlotCompiler()
    parse_ok = 0
    compile_ok = 0
    parse_errors: Counter[str] = Counter()
    compile_errors: Counter[str] = Counter()
    compile_error_details: Counter[str] = Counter()
    compile_error_domains: Counter[str] = Counter()
    parse_error_samples: List[Dict[str, Any]] = []
    compile_error_samples: List[Dict[str, Any]] = []
    compiled_samples: List[Dict[str, Any]] = []
    for row_index, row in df.iterrows():
        dsl = str(row["slot_dsl"])
        try:
            parse_official_slot(dsl)
            parse_ok += 1
        except OfficialSlotError as exc:
            parse_errors[exc.code] += 1
            if len(parse_error_samples) < sample_size:
                parse_error_samples.append(_workbook_error_sample(row_index, row, exc))
            continue
        try:
            result = compiler.compile(dsl)
            compile_ok += 1
            if len(compiled_samples) < sample_size:
                compiled_samples.append(
                    {
                        "excel_row": int(row_index + 2),
                        "query": str(row.get("query", "")),
                        "slot_dsl": dsl,
                        "requires_tables": result.requires_tables,
                        "sql_preview": result.sql[:600],
                    }
                )
        except OfficialSlotError as exc:
            compile_errors[exc.code] += 1
            compile_error_details[_compile_error_detail(exc)] += 1
            compile_error_domains[classify_official_compile_error_domain(exc)] += 1
            if len(compile_error_samples) < sample_size:
                compile_error_samples.append(_workbook_error_sample(row_index, row, exc))
    return {
        "path": path,
        "row_count": int(len(df)),
        "parse_ok": parse_ok,
        "parse_failed": int(len(df) - parse_ok),
        "compile_ok": compile_ok,
        "compile_failed": int(parse_ok - compile_ok),
        "compile_rate_on_all_rows": round(compile_ok / len(df), 6) if len(df) else 0,
        "compile_rate_on_parse_ok": round(compile_ok / parse_ok, 6) if parse_ok else 0,
        "parse_errors": dict(parse_errors),
        "compile_errors": dict(compile_errors),
        "compile_error_details": dict(compile_error_details.most_common(30)),
        "compile_error_domains": dict(compile_error_domains.most_common(30)),
        "parse_error_samples": parse_error_samples,
        "compile_error_samples": compile_error_samples,
        "compiled_samples": compiled_samples,
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
            if row.get("bizdate"):
                if not first_date:
                    first_date = row["bizdate"]
                last_date = row["bizdate"]
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
        "| 指标 | 数值 |",
        "|---|---:|",
        f"| 官方样例总数 | {coverage['row_count']} |",
        f"| 语法解析成功 | {coverage['parse_ok']} |",
        f"| 语法解析失败 | {coverage['parse_failed']} |",
        f"| Doris SQL 编译成功 | {coverage['compile_ok']} |",
        f"| Doris SQL 编译失败 | {coverage['compile_failed']} |",
        f"| 全量样例可落地编译率 | {coverage['compile_rate_on_all_rows']:.2%} |",
        f"| 解析成功样例可落地编译率 | {coverage['compile_rate_on_parse_ok']:.2%} |",
        "",
        "## 编译失败错误码",
        "",
        "| 错误码 | 次数 |",
        "|---|---:|",
    ]
    for code, count in coverage.get("compile_errors", {}).items():
        lines.append(f"| {code} | {count} |")
    lines.extend(["", "## 编译失败细分原因 TopN", "", "| 原因 | 次数 |", "|---|---:|"])
    for detail, count in coverage.get("compile_error_details", {}).items():
        lines.append(f"| {_md_escape(detail)} | {count} |")
    if coverage.get("compile_error_domains"):
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
        for domain, count in coverage["compile_error_domains"].items():
            lines.append(f"| {_md_escape(domain)} | {count} |")
    if coverage.get("parse_error_samples"):
        lines.extend(["", "## 语法解析失败样本", "", "| Excel 行 | 错误码 | 原因 | DSL |", "|---:|---|---|---|"])
        for item in coverage["parse_error_samples"]:
            lines.append(
                f"| {item['excel_row']} | {item['code']} | {_md_escape(item['message'])} | `{_md_escape(item['slot_dsl'])}` |"
            )
    if coverage.get("compile_error_samples"):
        lines.extend(["", "## 编译失败样本", "", "| Excel 行 | 错误码 | 原因 | DSL |", "|---:|---|---|---|"])
        for item in coverage["compile_error_samples"]:
            lines.append(
                f"| {item['excel_row']} | {item['code']} | {_md_escape(item['message'])} | `{_md_escape(item['slot_dsl'])}` |"
            )
    if coverage.get("compiled_samples"):
        lines.extend(["", "## 可落地编译样本", "", "| Excel 行 | 依赖表 | SQL 预览 |", "|---:|---|---|"])
        for item in coverage["compiled_samples"]:
            tables = ", ".join(item["requires_tables"])
            lines.append(f"| {item['excel_row']} | {tables} | `{_md_escape(item['sql_preview'])}` |")
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
    return bool(re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)%", value.strip()))


def _dedupe(items: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result

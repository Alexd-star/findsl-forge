from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence


CN_NUMBER_RE = r"[零一二两三四五六七八九十百千万]+"
ARABIC_NUMBER_RE = r"\d+(?:\.\d+)?(?:万|千|百)?"
NUMBER_RE = rf"(?:{ARABIC_NUMBER_RE}|{CN_NUMBER_RE})"


@dataclass(frozen=True)
class DslCandidate:
    title: str
    dsl: str
    confidence: float
    rule: str
    rationale: str
    matched_signals: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "title": self.title,
            "dsl": self.dsl,
            "confidence": round(self.confidence, 3),
            "rule": self.rule,
            "rationale": self.rationale,
            "matched_signals": list(self.matched_signals),
        }


@dataclass(frozen=True)
class NL2DSLResult:
    text: str
    candidates: List[DslCandidate]
    warnings: List[str]

    @property
    def top(self) -> Optional[DslCandidate]:
        return self.candidates[0] if self.candidates else None

    def to_dict(self) -> Dict[str, object]:
        return {
            "text": self.text,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "warnings": list(self.warnings),
        }


def suggest_dsl(text: str, max_candidates: int = 5) -> NL2DSLResult:
    normalized = _normalize(text)
    warnings: List[str] = []
    if not normalized:
        return NL2DSLResult(text=text, candidates=[], warnings=["empty natural-language request"])

    candidates = [
        candidate
        for candidate in [
            _rank_after_consecutive_inflow(normalized),
            _money_flow_low_price_rank(normalized),
            _turnover_percent_rank(normalized),
            _high_turnover_close_rank(normalized),
            _net_outflow_threshold(normalized),
            _close_new_high(normalized),
            _volume_breakout_exists(normalized),
            _rolling_volume_sum(normalized),
            _date_range_close_above_ma(normalized),
            _date_range_close_threshold(normalized),
        ]
        if candidate is not None
    ]
    candidates = _dedupe_sorted(candidates)
    if not candidates:
        warnings.append("no high-confidence template matched the request")
    return NL2DSLResult(text=text, candidates=candidates[:max_candidates], warnings=warnings)


def _rank_after_consecutive_inflow(text: str) -> Optional[DslCandidate]:
    signals = _signals(
        text,
        [
            ("main_net_inflow", ["主力净流入", "资金净流入", "main_net_inflow"]),
            ("positive", ["为正", "大于0", ">0", "流入为正"]),
            ("rank", ["排名", "排序", "排行"]),
            ("turnover_rate", ["换手率", "turnover"]),
        ],
    )
    if not {"main_net_inflow", "positive", "rank", "turnover_rate"}.issubset(signals):
        return None

    window = _window_after(text, ["连续"], default=3)
    top = _selection_n(text, default=100)
    order = _rank_order(text)
    limit = _rank_limit_arg(order, top)
    condition = f'CONS(indicator("main_net_inflow") > 0, {window})'
    market = _market_condition(text)
    if market:
        condition = f"{market} & {condition}"
    dsl = f'then(filter({condition}), rank(indicator("turnover_rate"), {order}, {limit}))'
    confidence = 0.93
    if not market:
        confidence -= 0.04
    return DslCandidate(
        title="Consecutive inflow then turnover ranking",
        dsl=dsl,
        confidence=confidence,
        rule="consecutive_inflow_rank",
        rationale=(
            "Matched consecutive positive main-net-inflow screening, then ranked by turnover_rate."
        ),
        matched_signals=sorted(signals),
    )


def _money_flow_low_price_rank(text: str) -> Optional[DslCandidate]:
    signals = _signals(
        text,
        [
            ("main_net_inflow", ["主力净流入", "资金净流入", "资金流入", "main_net_inflow"]),
            ("exists", ["存在", "任一", "出现", "有"]),
            ("low_price", ["低价", "价格低", "低收盘价", "收盘价低", "低位"]),
            ("select", ["取", "选", "筛", "排名", "排行", "只"]),
        ],
    )
    if not {"main_net_inflow", "low_price"}.issubset(signals):
        return None
    if "exists" not in signals and "select" not in signals:
        return None

    window = _window_after(text, ["近", "最近", "过去"], default=2)
    limit = _selection_n(text, default=2)
    condition = f'EXIST(indicator("main_net_inflow") > 0, {window})'
    market = _market_condition(text)
    if market:
        condition = f"{market} & {condition}"
    dsl = f'then(filter({condition}), rank(indicator("close"), asc, bottom={limit}))'
    confidence = 0.9 if market else 0.86
    return DslCandidate(
        title=f"Low-price picks after {window}-day money-flow signal",
        dsl=dsl,
        confidence=confidence,
        rule="money_flow_low_price_rank",
        rationale=(
            "Matched money-flow existence plus low-price selection and paired ascending rank with bottom=N."
        ),
        matched_signals=sorted(signals),
    )


def _turnover_percent_rank(text: str) -> Optional[DslCandidate]:
    signals = _signals(
        text,
        [
            ("turnover_rate", ["换手率", "turnover"]),
            ("percent", ["%", "百分比", "百分之"]),
            ("rank", ["排名", "排行", "排序", "前"]),
        ],
    )
    if not {"turnover_rate", "percent"}.issubset(signals):
        return None

    percent = _percent_n(text, default=50)
    order = _rank_order(text)
    market = _market_condition(text)
    rank_expr = f'rank(indicator("turnover_rate"), {order}, percent={_format_number(percent)})'
    dsl = f"then(filter({market}), {rank_expr})" if market else rank_expr
    confidence = 0.89 if market else 0.84
    return DslCandidate(
        title=f"Turnover-rate daily top {percent:g} percent",
        dsl=dsl,
        confidence=confidence,
        rule="turnover_percent_rank",
        rationale="Matched turnover-rate percentile ranking and mapped it to rank(..., percent=N).",
        matched_signals=sorted(signals),
    )


def _high_turnover_close_rank(text: str) -> Optional[DslCandidate]:
    signals = _signals(
        text,
        [
            ("turnover_rate", ["高换手", "换手率", "turnover"]),
            ("close", ["收盘价", "收盘", "close"]),
            ("rank", ["排名", "排行", "排序", "取", "前"]),
        ],
    )
    if not {"turnover_rate", "close", "rank"}.issubset(signals):
        return None
    if _contains_any(text, ["%", "百分比", "百分之", "低价", "低收盘价", "收盘价低"]):
        return None

    threshold = _threshold_after(text, ["大于", "超过", "高于", ">", ">="], default=1)
    limit = _selection_n(text, default=2)
    order = _rank_order(text)
    rank_limit = _rank_limit_arg(order, limit)
    condition = f'indicator("turnover_rate") > {_format_number(threshold)}'
    market = _market_condition(text)
    if market:
        condition = f"{market} & {condition}"
    dsl = f'then(filter({condition}), rank(indicator("close"), {order}, {rank_limit}))'
    confidence = 0.88 if market else 0.83
    return DslCandidate(
        title=f"High-turnover close ranking top {limit}",
        dsl=dsl,
        confidence=confidence,
        rule="high_turnover_close_rank",
        rationale="Matched high-turnover prefilter followed by close-price cross-sectional ranking.",
        matched_signals=sorted(signals),
    )


def _net_outflow_threshold(text: str) -> Optional[DslCandidate]:
    signals = _signals(
        text,
        [
            ("main_net_inflow", ["主力净流入", "主力净流出", "资金净流入", "资金净流出", "main_net_inflow"]),
            ("outflow", ["净流出", "流出"]),
            ("threshold", ["低于", "小于", "少于", "<", "超过", "大于"]),
        ],
    )
    if not {"main_net_inflow", "outflow", "threshold"}.issubset(signals):
        return None

    threshold = _signed_threshold_after(text, ["低于", "小于", "少于", "<", "超过", "大于"], default=-1.5)
    if threshold >= 0:
        threshold = -threshold
    dsl = f'filter(indicator("main_net_inflow") < {_format_number(threshold)})'
    return DslCandidate(
        title=f"Main-net-outflow below {threshold:g}",
        dsl=dsl,
        confidence=0.86,
        rule="net_outflow_threshold",
        rationale="Matched net-outflow wording and mapped it to a signed main_net_inflow threshold.",
        matched_signals=sorted(signals),
    )


def _close_new_high(text: str) -> Optional[DslCandidate]:
    signals = _signals(
        text,
        [
            ("close", ["收盘价", "收盘", "close"]),
            ("new_high", ["新高", "创新高", "创高"]),
        ],
    )
    if not {"close", "new_high"}.issubset(signals):
        return None

    window = _window_near(text, ["新高", "创新高", "创高"], default=250)
    dsl = f'filter(indicator("close") >= MAX(indicator("close"), {window}))'
    return DslCandidate(
        title=f"{window}-day close new high",
        dsl=dsl,
        confidence=0.91,
        rule="close_new_high",
        rationale="Matched close-price new-high intent and rewrote it as close >= rolling MAX(close).",
        matched_signals=sorted(signals),
    )


def _volume_breakout_exists(text: str) -> Optional[DslCandidate]:
    signals = _signals(
        text,
        [
            ("volume", ["成交量", "放量", "volume"]),
            ("exists", ["存在", "任一", "出现", "有"]),
            ("breakout", ["放量", "超过均量", "大于均量", "突破均量"]),
        ],
    )
    if not {"volume", "breakout"}.issubset(signals):
        return None
    if "exists" not in signals and not _contains_any(text, ["近", "最近", "过去"]):
        return None

    exist_window = _window_after(text, ["近", "最近", "过去"], default=10)
    ma_window = _window_after(text, ["均量", "均线", "平均"], default=20)
    dsl = (
        f'filter(EXIST(indicator("volume") > MA(indicator("volume"), {ma_window}), '
        f"{exist_window}))"
    )
    return DslCandidate(
        title=f"Volume breakout exists in {exist_window} days",
        dsl=dsl,
        confidence=0.88,
        rule="volume_breakout_exists",
        rationale="Matched volume-breakout wording and expressed it as EXIST(volume > MA(volume)).",
        matched_signals=sorted(signals),
    )


def _rolling_volume_sum(text: str) -> Optional[DslCandidate]:
    signals = _signals(
        text,
        [
            ("volume", ["成交量", "volume"]),
            ("rolling_sum", ["累计", "合计", "总和", "求和", "sum", "前缀和"]),
            ("threshold", ["大于", "超过", "高于", ">", ">="]),
        ],
    )
    if not {"volume", "rolling_sum"}.issubset(signals):
        return None

    window = _window_after(text, ["近", "最近", "过去"], default=3)
    threshold = _threshold_after(text, ["大于", "超过", "高于", ">", ">="], default=300)
    dsl = f'filter(SUM(indicator("volume"), {window}) > {_format_number(threshold)})'
    confidence = 0.86 if "threshold" in signals else 0.76
    return DslCandidate(
        title=f"{window}-day rolling volume sum",
        dsl=dsl,
        confidence=confidence,
        rule="rolling_volume_sum",
        rationale="Matched rolling volume aggregation and mapped it to SUM(volume, window).",
        matched_signals=sorted(signals),
    )


def _date_range_close_threshold(text: str) -> Optional[DslCandidate]:
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", text)
    if _contains_any(text, ["均线", "均价", "平均", "ma"]):
        return None
    signals = _signals(
        text,
        [
            ("close", ["收盘价", "收盘", "close"]),
            ("threshold", ["大于", "超过", "高于", ">", ">="]),
        ],
    )
    if len(dates) < 2 or not {"close", "threshold"}.issubset(signals):
        return None

    threshold = _threshold_after(text, ["大于", "超过", "高于", ">", ">="], default=10)
    dsl = (
        f'filter(date_between("{dates[0]}", "{dates[1]}") '
        f'& indicator("close") > {_format_number(threshold)})'
    )
    return DslCandidate(
        title="Date-range close threshold",
        dsl=dsl,
        confidence=0.87,
        rule="date_range_close_threshold",
        rationale="Matched explicit trade-date range plus close-price threshold and mapped it to date_between().",
        matched_signals=sorted(signals | {"date_range"}),
    )


def _date_range_close_above_ma(text: str) -> Optional[DslCandidate]:
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", text)
    signals = _signals(
        text,
        [
            ("close", ["收盘价", "收盘", "close"]),
            ("above", ["大于", "超过", "高于", ">"]),
            ("ma", ["均线", "均价", "平均", "ma"]),
        ],
    )
    if len(dates) < 2 or not {"close", "above", "ma"}.issubset(signals):
        return None

    window = _window_near(text, ["均线", "均价", "平均", "ma"], default=20)
    dsl = (
        f'filter(date_between("{dates[0]}", "{dates[1]}") '
        f'& indicator("close") > MA(indicator("close"), {window}))'
    )
    return DslCandidate(
        title=f"Date-range close above {window}-day MA",
        dsl=dsl,
        confidence=0.9,
        rule="date_range_close_above_ma",
        rationale="Matched explicit date range plus close-price moving-average comparison.",
        matched_signals=sorted(signals | {"date_range"}),
    )


def _signals(text: str, groups: Sequence[tuple[str, Sequence[str]]]) -> set[str]:
    return {name for name, words in groups if _contains_any(text, words)}


def _contains_any(text: str, needles: Sequence[str]) -> bool:
    return any(needle.lower() in text for needle in needles)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text.strip().lower().replace("，", ",").replace("。", "."))


def _market_condition(text: str) -> str:
    if _contains_any(text, ["a股", "a 股", "全a", "沪深a", "市场a"]):
        return 'market("A")'
    return ""


def _selection_n(text: str, default: int) -> int:
    for pattern in [
        rf"(?:前|top)(?P<num>{NUMBER_RE})",
        rf"(?:取|选|挑)(?:每日)?(?:前)?(?P<num>{NUMBER_RE})(?:只|个|名)?",
        rf"每日(?:前)?(?P<num>{NUMBER_RE})(?:只|个|名)",
    ]:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return int(_parse_number(match.group("num")))
    return default


def _percent_n(text: str, default: float) -> float:
    for pattern in [
        rf"(?P<num>{NUMBER_RE})%",
        rf"百分之(?P<num>{NUMBER_RE})",
        rf"(?P<num>{NUMBER_RE})百分比",
    ]:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _parse_number(match.group("num"))
    return float(default)


def _rank_order(text: str) -> str:
    if _contains_any(text, ["升序", "从低到高", "由低到高", "低到高", "最低", "低价"]):
        return "asc"
    return "desc"


def _rank_limit_arg(order: str, limit: int) -> str:
    kind = "bottom" if order == "asc" else "top"
    return f"{kind}={limit}"


def _window_after(text: str, anchors: Sequence[str], default: int) -> int:
    for anchor in anchors:
        match = re.search(rf"{re.escape(anchor)}(?P<num>{NUMBER_RE})(?:日|天|个交易日)", text)
        if match:
            return int(_parse_number(match.group("num")))
    return default


def _window_near(text: str, anchors: Sequence[str], default: int) -> int:
    for anchor in anchors:
        match = re.search(rf"(?P<num>{NUMBER_RE})(?:日|天|个交易日).{{0,8}}{re.escape(anchor)}", text)
        if match:
            return int(_parse_number(match.group("num")))
        match = re.search(rf"{re.escape(anchor)}.{{0,8}}(?P<num>{NUMBER_RE})(?:日|天|个交易日)", text)
        if match:
            return int(_parse_number(match.group("num")))
    if "一年" in text or "年度" in text:
        return 250
    return default


def _threshold_after(text: str, anchors: Sequence[str], default: float) -> float:
    for anchor in anchors:
        match = re.search(rf"{re.escape(anchor)}(?P<num>{NUMBER_RE})", text)
        if match:
            return _parse_number(match.group("num"))
    return default


def _signed_threshold_after(text: str, anchors: Sequence[str], default: float) -> float:
    signed_number_re = rf"[+-]?{NUMBER_RE}"
    for anchor in anchors:
        match = re.search(rf"{re.escape(anchor)}(?P<num>{signed_number_re})", text)
        if match:
            return _parse_signed_number(match.group("num"))
    return default


def _parse_number(raw: str) -> float:
    match = re.fullmatch(r"(?P<number>\d+(?:\.\d+)?)(?P<unit>万|千|百)?", raw)
    if match:
        number = float(match.group("number"))
        unit = match.group("unit")
        multiplier = {"万": 10000, "千": 1000, "百": 100}.get(unit, 1)
        return number * multiplier
    return float(_parse_cn_number(raw))


def _parse_signed_number(raw: str) -> float:
    sign = -1 if raw.startswith("-") else 1
    value = raw[1:] if raw[:1] in {"+", "-"} else raw
    return sign * _parse_number(value)


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.12f}".rstrip("0").rstrip(".")


def _parse_cn_number(raw: str) -> int:
    digits = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000}
    total = 0
    section = 0
    number = 0
    for char in raw:
        if char in digits:
            number = digits[char]
            continue
        unit = units.get(char)
        if unit is None:
            continue
        if unit == 10000:
            section = (section + number) * unit
            total += section
            section = 0
        else:
            section += (number or 1) * unit
        number = 0
    return total + section + number


def _dedupe_sorted(candidates: List[DslCandidate]) -> List[DslCandidate]:
    by_dsl: Dict[str, DslCandidate] = {}
    for candidate in candidates:
        previous = by_dsl.get(candidate.dsl)
        if previous is None or candidate.confidence > previous.confidence:
            by_dsl[candidate.dsl] = candidate
    return sorted(by_dsl.values(), key=lambda item: item.confidence, reverse=True)

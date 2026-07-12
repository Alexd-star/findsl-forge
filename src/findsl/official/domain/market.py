from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from ..ir.base import CanonicalIr


OFFICIAL_MARKETS = frozenset(
    {
        "沪",
        "深",
        "京",
        "港",
        "美",
        "新三板",
        "沪主板",
        "深主板",
        "科创板",
        "创业板",
        "日",
        "韩",
        "德",
        "法",
        "英",
        "其他",
        "A股",
        "沪深",
        "沪深京",
    }
)


class MarketParseError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class MarketExpression(CanonicalIr):
    @property
    def atoms(self) -> Tuple[str, ...]:
        raise NotImplementedError


@dataclass(frozen=True)
class MarketAtom(MarketExpression):
    name: str

    @property
    def atoms(self) -> Tuple[str, ...]:
        return (self.name,)

    def to_dict(self):
        return {"kind": "MarketAtom", "name": self.name}


@dataclass(frozen=True)
class MarketNot(MarketExpression):
    operand: MarketExpression

    @property
    def atoms(self) -> Tuple[str, ...]:
        return self.operand.atoms

    def to_dict(self):
        return {"kind": "MarketNot", "operand": self.operand.to_dict()}


@dataclass(frozen=True)
class MarketAnd(MarketExpression):
    left: MarketExpression
    right: MarketExpression

    @property
    def atoms(self) -> Tuple[str, ...]:
        return tuple(dict.fromkeys((*self.left.atoms, *self.right.atoms)))

    def to_dict(self):
        return {
            "kind": "MarketAnd",
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
        }


@dataclass(frozen=True)
class MarketOr(MarketExpression):
    left: MarketExpression
    right: MarketExpression

    @property
    def atoms(self) -> Tuple[str, ...]:
        return tuple(dict.fromkeys((*self.left.atoms, *self.right.atoms)))

    def to_dict(self):
        return {
            "kind": "MarketOr",
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
        }


def parse_market_expression(source: str) -> Optional[MarketExpression]:
    text = str(source).strip()
    if not text:
        return None
    parser = _MarketParser(text)
    expression = parser.parse_union()
    if parser.position != len(parser.tokens):
        raise MarketParseError(
            "MARKET_EXPRESSION_INVALID",
            f"unexpected market token {parser.tokens[parser.position]!r}",
        )
    return expression


class _MarketParser:
    def __init__(self, source: str):
        self.tokens = self._tokenize(source)
        self.position = 0

    @staticmethod
    def _tokenize(source: str):
        tokens = []
        start = 0
        for index, char in enumerate(source):
            if char in "|&^":
                if start < index:
                    value = source[start:index].strip()
                    if value:
                        tokens.append(value)
                tokens.append(char)
                start = index + 1
        if start < len(source):
            value = source[start:].strip()
            if value:
                tokens.append(value)
        if not tokens:
            raise MarketParseError("MARKET_EXPRESSION_INVALID", "market expression is empty")
        return tuple(tokens)

    def parse_union(self) -> MarketExpression:
        expression = self.parse_intersection()
        while self._accept("|"):
            expression = MarketOr(expression, self.parse_intersection())
        return expression

    def parse_intersection(self) -> MarketExpression:
        expression = self.parse_unary()
        while self._accept("&"):
            expression = MarketAnd(expression, self.parse_unary())
        return expression

    def parse_unary(self) -> MarketExpression:
        if self._accept("^"):
            return MarketNot(self.parse_unary())
        if self.position >= len(self.tokens):
            raise MarketParseError(
                "MARKET_EXPRESSION_INVALID",
                "market expression ends after an operator",
            )
        token = self.tokens[self.position]
        if token in {"|", "&"}:
            raise MarketParseError(
                "MARKET_EXPRESSION_INVALID",
                f"unexpected market operator {token}",
            )
        self.position += 1
        if token not in OFFICIAL_MARKETS:
            raise MarketParseError(
                "MARKET_TOKEN_UNSUPPORTED",
                f"unknown official market token {token}",
            )
        return MarketAtom(token)

    def _accept(self, token: str) -> bool:
        if self.position < len(self.tokens) and self.tokens[self.position] == token:
            self.position += 1
            return True
        return False

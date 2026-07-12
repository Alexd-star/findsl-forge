from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from ..ir.base import CanonicalIr


class ScopeParseError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ScopeExpression(CanonicalIr):
    @property
    def atoms(self) -> Tuple[str, ...]:
        raise NotImplementedError


@dataclass(frozen=True)
class ScopeAtom(ScopeExpression):
    name: str

    @property
    def atoms(self) -> Tuple[str, ...]:
        return (self.name,)

    def to_dict(self):
        return {"kind": "ScopeAtom", "name": self.name}


@dataclass(frozen=True)
class ScopeNot(ScopeExpression):
    operand: ScopeExpression

    @property
    def atoms(self) -> Tuple[str, ...]:
        return self.operand.atoms

    def to_dict(self):
        return {"kind": "ScopeNot", "operand": self.operand.to_dict()}


@dataclass(frozen=True)
class ScopeAnd(ScopeExpression):
    left: ScopeExpression
    right: ScopeExpression

    @property
    def atoms(self) -> Tuple[str, ...]:
        return tuple(dict.fromkeys((*self.left.atoms, *self.right.atoms)))

    def to_dict(self):
        return {"kind": "ScopeAnd", "left": self.left.to_dict(), "right": self.right.to_dict()}


@dataclass(frozen=True)
class ScopeOr(ScopeExpression):
    left: ScopeExpression
    right: ScopeExpression

    @property
    def atoms(self) -> Tuple[str, ...]:
        return tuple(dict.fromkeys((*self.left.atoms, *self.right.atoms)))

    def to_dict(self):
        return {"kind": "ScopeOr", "left": self.left.to_dict(), "right": self.right.to_dict()}


def parse_scope_expression(source: str) -> Optional[ScopeExpression]:
    text = str(source or "").strip()
    if not text:
        return None
    parser = _ScopeParser(text)
    expression = parser.parse_union()
    if parser.position != len(parser.tokens):
        raise ScopeParseError(
            "SCOPE_EXPRESSION_INVALID",
            f"unexpected scope token {parser.tokens[parser.position]!r}",
        )
    return expression


class _ScopeParser:
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
                    atom = source[start:index].strip()
                    if atom:
                        tokens.append(atom)
                tokens.append(char)
                start = index + 1
        if start < len(source):
            atom = source[start:].strip()
            if atom:
                tokens.append(atom)
        if not tokens:
            raise ScopeParseError("SCOPE_EXPRESSION_INVALID", "scope expression is empty")
        return tuple(tokens)

    def parse_union(self) -> ScopeExpression:
        expression = self.parse_intersection()
        while self._accept("|"):
            expression = ScopeOr(expression, self.parse_intersection())
        return expression

    def parse_intersection(self) -> ScopeExpression:
        expression = self.parse_unary()
        while self._accept("&"):
            expression = ScopeAnd(expression, self.parse_unary())
        return expression

    def parse_unary(self) -> ScopeExpression:
        if self._accept("^"):
            return ScopeNot(self.parse_unary())
        if self.position >= len(self.tokens):
            raise ScopeParseError(
                "SCOPE_EXPRESSION_INVALID",
                "scope expression ends after an operator",
            )
        token = self.tokens[self.position]
        if token in {"|", "&"}:
            raise ScopeParseError(
                "SCOPE_EXPRESSION_INVALID",
                f"unexpected scope operator {token}",
            )
        self.position += 1
        return ScopeAtom(token)

    def _accept(self, token: str) -> bool:
        if self.position < len(self.tokens) and self.tokens[self.position] == token:
            self.position += 1
            return True
        return False

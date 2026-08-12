from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Mapping, Optional, Tuple

from ..ir.base import CanonicalIr


class TargetParseError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class TargetExpression(CanonicalIr):
    @property
    def atoms(self) -> Tuple[str, ...]:
        raise NotImplementedError


@dataclass(frozen=True)
class TargetAtom(TargetExpression):
    name: str

    @property
    def atoms(self) -> Tuple[str, ...]:
        return (self.name,)

    def to_dict(self):
        return {"kind": "TargetAtom", "name": self.name}


@dataclass(frozen=True)
class TargetNot(TargetExpression):
    operand: TargetExpression

    @property
    def atoms(self) -> Tuple[str, ...]:
        return self.operand.atoms

    def to_dict(self):
        return {"kind": "TargetNot", "operand": self.operand.to_dict()}


@dataclass(frozen=True)
class TargetAnd(TargetExpression):
    left: TargetExpression
    right: TargetExpression

    @property
    def atoms(self) -> Tuple[str, ...]:
        return tuple(dict.fromkeys((*self.left.atoms, *self.right.atoms)))

    def to_dict(self):
        return {
            "kind": "TargetAnd",
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
        }


@dataclass(frozen=True)
class TargetOr(TargetExpression):
    left: TargetExpression
    right: TargetExpression

    @property
    def atoms(self) -> Tuple[str, ...]:
        return tuple(dict.fromkeys((*self.left.atoms, *self.right.atoms)))

    def to_dict(self):
        return {
            "kind": "TargetOr",
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
        }


@dataclass(frozen=True)
class EntityTargetSpec(CanonicalIr):
    source: str
    expression: Optional[TargetExpression]
    target_ids: Tuple[str, ...]
    logical_entities: Tuple[str, ...]
    execution_modes: Tuple[str, ...]
    required_data_domains: FrozenSet[str]
    data_domain_statuses: Tuple[Tuple[str, str], ...]
    result_keys: Tuple[str, ...]

    @property
    def is_security(self) -> bool:
        return self.target_ids == ("security",)

    @property
    def unavailable_data_domains(self) -> Tuple[str, ...]:
        return tuple(
            domain_id
            for domain_id, status in self.data_domain_statuses
            if status not in {"available", "derived"}
        )

    def to_dict(self):
        return {
            "kind": "EntityTargetSpec",
            "source": self.source,
            "expression": self.expression.to_dict() if self.expression else None,
            "target_ids": list(self.target_ids),
            "logical_entities": list(self.logical_entities),
            "execution_modes": list(self.execution_modes),
            "required_data_domains": sorted(self.required_data_domains),
            "data_domain_statuses": [
                {"domain_id": domain_id, "status": status}
                for domain_id, status in self.data_domain_statuses
            ],
            "result_keys": list(self.result_keys),
        }


def parse_target_expression(
    source: str,
    definitions: Mapping[str, object],
) -> Optional[TargetExpression]:
    text = str(source or "").strip()
    if not text:
        return None
    parser = _TargetParser(text, definitions)
    expression = parser.parse_union()
    if parser.position != len(parser.tokens):
        raise TargetParseError(
            "TARGET_EXPRESSION_INVALID",
            f"unexpected select_type token {parser.tokens[parser.position]!r}",
        )
    return expression


class _TargetParser:
    def __init__(self, source: str, definitions: Mapping[str, object]):
        self.tokens = self._tokenize(source)
        self.position = 0
        self.definitions = definitions

    @staticmethod
    def _tokenize(source: str) -> Tuple[str, ...]:
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
            raise TargetParseError(
                "TARGET_EXPRESSION_INVALID", "select_type expression is empty"
            )
        return tuple(tokens)

    def parse_union(self) -> TargetExpression:
        expression = self.parse_intersection()
        while self._accept("|"):
            expression = TargetOr(expression, self.parse_intersection())
        return expression

    def parse_intersection(self) -> TargetExpression:
        expression = self.parse_unary()
        while self._accept("&"):
            expression = TargetAnd(expression, self.parse_unary())
        return expression

    def parse_unary(self) -> TargetExpression:
        if self._accept("^"):
            return TargetNot(self.parse_unary())
        if self.position >= len(self.tokens):
            raise TargetParseError(
                "TARGET_EXPRESSION_INVALID", "select_type expression ends after an operator"
            )
        token = self.tokens[self.position]
        if token in {"|", "&"}:
            raise TargetParseError(
                "TARGET_EXPRESSION_INVALID", f"unexpected select_type operator {token}"
            )
        self.position += 1
        if token not in self.definitions:
            raise TargetParseError(
                "TARGET_TOKEN_UNSUPPORTED", f"unknown official select_type token {token}"
            )
        return TargetAtom(token)

    def _accept(self, token: str) -> bool:
        if self.position < len(self.tokens) and self.tokens[self.position] == token:
            self.position += 1
            return True
        return False

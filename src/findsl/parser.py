from __future__ import annotations

from typing import List, Optional

from .ast_nodes import BinaryOp, Comparison, FunctionCall, Identifier, Literal, NamedArg, Node
from .errors import ParseError
from .lexer import Token, lex


class Parser:
    def __init__(self, source: str):
        self.source = source
        self.tokens: List[Token] = lex(source)
        self.index = 0

    def parse(self) -> Node:
        expr = self._parse_or()
        self._expect("EOF")
        return expr

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
            raise ParseError(f"Expected {kind}, got {token.kind} at {token.position}")
        return self._advance()

    def _parse_or(self) -> Node:
        node = self._parse_xor()
        while self._match("|"):
            right = self._parse_xor()
            node = BinaryOp("|", node, right)
        return node

    def _parse_xor(self) -> Node:
        node = self._parse_and()
        while self._match("^"):
            right = self._parse_and()
            node = BinaryOp("^", node, right)
        return node

    def _parse_and(self) -> Node:
        node = self._parse_comparison()
        while self._match("&"):
            right = self._parse_comparison()
            node = BinaryOp("&", node, right)
        return node

    def _parse_comparison(self) -> Node:
        node = self._parse_additive()
        token = self._match(">=", "<=", "==", "!=", "=", ">", "<")
        if token:
            right = self._parse_additive()
            return Comparison(token.kind, node, right)
        return node

    def _parse_additive(self) -> Node:
        node = self._parse_multiplicative()
        while True:
            token = self._match("+", "-")
            if not token:
                return node
            right = self._parse_multiplicative()
            node = BinaryOp(token.kind, node, right)

    def _parse_multiplicative(self) -> Node:
        node = self._parse_primary()
        while True:
            token = self._match("*", "/")
            if not token:
                return node
            right = self._parse_primary()
            node = BinaryOp(token.kind, node, right)

    def _parse_primary(self) -> Node:
        token = self._peek()
        if self._match("("):
            expr = self._parse_or()
            self._expect(")")
            return expr
        if token.kind in {"+", "-"} and self.tokens[self.index + 1].kind == "NUMBER":
            sign = -1 if self._advance().kind == "-" else 1
            number = self._expect("NUMBER").value
            if "." in number:
                return Literal(sign * float(number))
            return Literal(sign * int(number))
        if token.kind == "STRING":
            self._advance()
            return Literal(token.value)
        if token.kind == "NUMBER":
            self._advance()
            if "." in token.value:
                return Literal(float(token.value))
            return Literal(int(token.value))
        if token.kind == "IDENT":
            ident = self._advance().value
            if self._match("("):
                return self._parse_call(ident)
            return Identifier(ident)
        raise ParseError(f"Unexpected token {token.kind} at {token.position}")

    def _parse_call(self, name: str) -> FunctionCall:
        args = []
        named_args = []
        seen_named_arg = False
        if self._match(")"):
            return FunctionCall(name, args, named_args)
        while True:
            if self._peek().kind == "IDENT" and self.tokens[self.index + 1].kind == "=":
                arg_name = self._advance().value
                self._expect("=")
                value = self._parse_or()
                named_args.append(NamedArg(arg_name, value))
                seen_named_arg = True
            else:
                if seen_named_arg:
                    raise ParseError(
                        f"Positional argument cannot follow named arguments in {name}() at {self._peek().position}"
                    )
                args.append(self._parse_or())
            if self._match(","):
                continue
            self._expect(")")
            return FunctionCall(name, args, named_args)


def parse(source: str) -> Node:
    return Parser(source).parse()

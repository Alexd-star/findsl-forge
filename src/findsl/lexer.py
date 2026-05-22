from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .errors import LexError


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    position: int


OPERATORS = {">=", "<=", "==", "!=", ">", "<", "&", "|", "+", "-", "*", "/", "=", ",", "(", ")"}


def lex(source: str) -> List[Token]:
    tokens: List[Token] = []
    i = 0
    while i < len(source):
        ch = source[i]
        if ch.isspace():
            i += 1
            continue
        if ch == '"':
            start = i
            i += 1
            chars = []
            while i < len(source):
                if source[i] == "\\":
                    if i + 1 >= len(source):
                        raise LexError(f"Unfinished escape at {i}")
                    chars.append(source[i + 1])
                    i += 2
                    continue
                if source[i] == '"':
                    tokens.append(Token("STRING", "".join(chars), start))
                    i += 1
                    break
                chars.append(source[i])
                i += 1
            else:
                raise LexError(f"Unclosed string starting at {start}")
            continue
        if ch.isdigit():
            start = i
            while i < len(source) and (source[i].isdigit() or source[i] == "."):
                i += 1
            tokens.append(Token("NUMBER", source[start:i], start))
            continue
        if ch.isalpha() or ch == "_":
            start = i
            while i < len(source) and (source[i].isalnum() or source[i] == "_"):
                i += 1
            tokens.append(Token("IDENT", source[start:i], start))
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
        raise LexError(f"Unexpected character {ch!r} at {i}")
    tokens.append(Token("EOF", "", len(source)))
    return tokens


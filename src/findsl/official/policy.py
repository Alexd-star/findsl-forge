from __future__ import annotations

from enum import Enum


class CompileMode(str, Enum):
    STRICT = "strict"
    RECOVERY = "recovery"

    @classmethod
    def parse(cls, value: str) -> "CompileMode":
        try:
            return cls(str(value).lower())
        except ValueError as exc:
            raise ValueError(f"Unsupported official compile mode: {value}") from exc

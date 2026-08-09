from __future__ import annotations


class OfficialSlotError(ValueError):
    """Stable error contract shared by the canonical and legacy compilers."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional, Protocol, Tuple

from ..diagnostics import SourceRepair


class FrontendName(str, Enum):
    HANDWRITTEN = "handwritten"
    ANTLR = "antlr"
    SHADOW = "shadow"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class SourceSpan:
    start_offset: int
    end_offset: int
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    fragment: str

    def __post_init__(self) -> None:
        if self.start_offset < 0 or self.end_offset < self.start_offset:
            raise ValueError("end_offset must be at least start_offset")
        if min(self.start_line, self.start_column, self.end_line, self.end_column) < 1:
            raise ValueError("line and column coordinates are one-based")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SourceMap:
    def __init__(self) -> None:
        self._spans: Dict[int, SourceSpan] = {}

    def record(self, node: Any, span: SourceSpan) -> Any:
        self._spans[id(node)] = span
        return node

    def span_for(self, node: Any) -> SourceSpan:
        return self._spans[id(node)]


@dataclass(frozen=True)
class FrontendDiagnostic:
    code: str
    severity: Severity
    message: str
    span: SourceSpan
    frontend: str

    def to_dict(self) -> Dict[str, Any]:
        value = asdict(self)
        value["severity"] = self.severity.value
        return value


@dataclass(frozen=True)
class ParseOutcome:
    ast: Optional[Any]
    diagnostics: Tuple[FrontendDiagnostic, ...]
    original_source: str
    normalized_source: str
    repairs: Tuple[SourceRepair, ...]
    frontend: str
    elapsed_ns: int
    source_map: Optional[SourceMap] = None

    @property
    def ok(self) -> bool:
        return self.ast is not None and not any(item.severity is Severity.ERROR for item in self.diagnostics)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "ast": self.ast.to_dict() if self.ast is not None else None,
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "original_source": self.original_source,
            "normalized_source": self.normalized_source,
            "repairs": [item.to_dict() for item in self.repairs],
            "frontend": self.frontend,
            "elapsed_ns": self.elapsed_ns,
        }


class OfficialFrontend(Protocol):
    name: str

    def parse(
        self,
        source: str,
        *,
        original_source: Optional[str] = None,
        repairs: Tuple[SourceRepair, ...] = (),
    ) -> ParseOutcome:
        ...

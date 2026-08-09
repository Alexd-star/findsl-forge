from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from ...official.frontend.antlr_frontend import AntlrOfficialFrontend
from ...official.policy import CompileMode
from ...official_slot import _normalize_official_slot_source
from .handwritten import HandwrittenOfficialFrontend


@dataclass(frozen=True)
class AstDifference:
    path: str
    handwritten: Any
    antlr: Any


@dataclass(frozen=True)
class FrontendComparison:
    classification: str
    input_sha256: str
    source: Optional[str]
    normalized_source: str
    handwritten_elapsed_ns: int
    antlr_elapsed_ns: int
    handwritten_diagnostics: tuple
    antlr_diagnostics: tuple
    difference: Optional[AstDifference]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "classification": self.classification,
            "input_sha256": self.input_sha256,
            "source": self.source,
            "normalized_source": self.normalized_source if self.source is not None else None,
            "handwritten_elapsed_ns": self.handwritten_elapsed_ns,
            "antlr_elapsed_ns": self.antlr_elapsed_ns,
            "handwritten_diagnostics": [item.to_dict() for item in self.handwritten_diagnostics],
            "antlr_diagnostics": [item.to_dict() for item in self.antlr_diagnostics],
            "difference": asdict(self.difference) if self.difference else None,
        }


def first_ast_difference(handwritten: Any, antlr: Any, path: str = "$") -> Optional[AstDifference]:
    if type(handwritten) is not type(antlr):
        return AstDifference(path, handwritten, antlr)
    if isinstance(handwritten, dict):
        if handwritten.keys() != antlr.keys():
            return AstDifference(path, sorted(handwritten), sorted(antlr))
        for key in handwritten:
            difference = first_ast_difference(handwritten[key], antlr[key], f"{path}.{key}")
            if difference:
                return difference
        return None
    if isinstance(handwritten, list):
        if len(handwritten) != len(antlr):
            return AstDifference(path, len(handwritten), len(antlr))
        for index, (left, right) in enumerate(zip(handwritten, antlr)):
            difference = first_ast_difference(left, right, f"{path}[{index}]")
            if difference:
                return difference
        return None
    if handwritten != antlr:
        return AstDifference(path, handwritten, antlr)
    return None


def compare_frontends(
    source: str,
    *,
    mode: str = CompileMode.RECOVERY.value,
    include_source: bool = False,
) -> FrontendComparison:
    compile_mode = CompileMode.parse(mode)
    if compile_mode is CompileMode.RECOVERY:
        normalized_source, repairs = _normalize_official_slot_source(source)
    else:
        normalized_source, repairs = str(source or ""), ()
    handwritten = HandwrittenOfficialFrontend().parse(
        normalized_source, original_source=source, repairs=repairs
    )
    antlr = AntlrOfficialFrontend().parse(
        normalized_source, original_source=source, repairs=repairs
    )
    difference = None
    if handwritten.ok and antlr.ok:
        difference = first_ast_difference(handwritten.ast.to_dict(), antlr.ast.to_dict())
        classification = "MATCH" if difference is None else "AST_MISMATCH"
    elif handwritten.ok:
        classification = "ANTLR_REJECTED"
    elif antlr.ok:
        classification = "HANDWRITTEN_REJECTED"
    elif _error_family(handwritten.diagnostics) == _error_family(antlr.diagnostics):
        classification = "ERROR_MATCH"
    else:
        classification = "ERROR_MISMATCH"
    return FrontendComparison(
        classification,
        hashlib.sha256(source.encode("utf-8")).hexdigest(),
        source if include_source else None,
        normalized_source,
        handwritten.elapsed_ns,
        antlr.elapsed_ns,
        handwritten.diagnostics,
        antlr.diagnostics,
        difference,
    )


def _error_family(diagnostics: tuple) -> str:
    if not diagnostics:
        return "none"
    code = diagnostics[0].code
    if "LEX" in code:
        return "lex"
    if "PARSE" in code:
        return "parse"
    return code

from __future__ import annotations

from time import perf_counter_ns
from typing import Optional, Tuple

from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener

from ..diagnostics import SourceRepair
from .ast_adapter import OfficialAstAdapter
from .generated.OfficialSlotLexer import OfficialSlotLexer
from .generated.OfficialSlotParser import OfficialSlotParser
from .protocol import FrontendDiagnostic, ParseOutcome, Severity, SourceSpan


class _DiagnosticListener(ErrorListener):
    def __init__(self, source: str, code: str):
        super().__init__()
        self.source = source
        self.code = code
        self.diagnostics = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        if offendingSymbol is not None and getattr(offendingSymbol, "start", -1) >= 0:
            start = offendingSymbol.start
            stop = getattr(offendingSymbol, "stop", start)
            end = min(len(self.source), max(start + 1, stop + 1))
        else:
            start = max(0, min(len(self.source), getattr(recognizer, "_tokenStartCharIndex", len(self.source))))
            end = min(len(self.source), start + 1)
        fragment = self.source[start:end] if start < len(self.source) else "<EOF>"
        end_line, end_column = _end_coordinates(line, column + 1, fragment)
        self.diagnostics.append(
            FrontendDiagnostic(
                self.code,
                Severity.ERROR,
                msg,
                SourceSpan(start, end, line, column + 1, end_line, end_column, fragment),
                "antlr",
            )
        )


def _end_coordinates(line: int, column: int, fragment: str):
    parts = fragment.splitlines(keepends=True)
    if len(parts) <= 1:
        return line, column + (0 if fragment == "<EOF>" else len(fragment))
    return line + len(parts) - 1, len(parts[-1].rstrip("\r\n")) + 1


class AntlrOfficialFrontend:
    name = "antlr"

    def parse(
        self,
        source: str,
        *,
        original_source: Optional[str] = None,
        repairs: Tuple[SourceRepair, ...] = (),
    ) -> ParseOutcome:
        started = perf_counter_ns()
        lexer = OfficialSlotLexer(InputStream(source))
        lex_listener = _DiagnosticListener(source, "OFFICIAL_ANTLR_LEX_ERROR")
        lexer.removeErrorListeners()
        lexer.addErrorListener(lex_listener)
        parser = OfficialSlotParser(CommonTokenStream(lexer))
        parse_listener = _DiagnosticListener(source, "OFFICIAL_ANTLR_PARSE_ERROR")
        parser.removeErrorListeners()
        parser.addErrorListener(parse_listener)
        tree = parser.program()
        diagnostics = tuple(lex_listener.diagnostics + parse_listener.diagnostics)
        if diagnostics:
            return ParseOutcome(
                None,
                diagnostics,
                source if original_source is None else original_source,
                source,
                repairs,
                self.name,
                perf_counter_ns() - started,
            )
        adapter = OfficialAstAdapter(source)
        try:
            ast = adapter.visit(tree)
        except (AttributeError, IndexError, TypeError, ValueError) as exc:
            span = SourceSpan(0, len(source), 1, 1, 1, len(source) + 1, source or "<EOF>")
            diagnostic = FrontendDiagnostic(
                "OFFICIAL_ANTLR_ADAPTER_ERROR", Severity.ERROR, str(exc), span, self.name
            )
            return ParseOutcome(
                None,
                (diagnostic,),
                source if original_source is None else original_source,
                source,
                repairs,
                self.name,
                perf_counter_ns() - started,
            )
        return ParseOutcome(
            ast,
            (),
            source if original_source is None else original_source,
            source,
            repairs,
            self.name,
            perf_counter_ns() - started,
            adapter.source_map,
        )

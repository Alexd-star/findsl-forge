from __future__ import annotations

from time import perf_counter_ns
from typing import Optional, Tuple

from antlr4 import CommonTokenStream, InputStream

from ..diagnostics import SourceRepair
from .ast_adapter import OfficialAstAdapter
from .generated.OfficialSlotLexer import OfficialSlotLexer
from .generated.OfficialSlotParser import OfficialSlotParser
from .protocol import ParseOutcome


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
        parser = OfficialSlotParser(CommonTokenStream(lexer))
        tree = parser.program()
        adapter = OfficialAstAdapter(source)
        ast = adapter.visit(tree)
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

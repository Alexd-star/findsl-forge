from __future__ import annotations

import re
from time import perf_counter_ns
from typing import Optional, Tuple

from ...official.diagnostics import SourceRepair
from ...official.frontend.protocol import FrontendDiagnostic, ParseOutcome, Severity, SourceSpan
from ...official_slot import OfficialSlotError, OfficialSlotParser


class HandwrittenOfficialFrontend:
    name = "handwritten"

    def parse(
        self,
        source: str,
        *,
        original_source: Optional[str] = None,
        repairs: Tuple[SourceRepair, ...] = (),
    ) -> ParseOutcome:
        started = perf_counter_ns()
        try:
            ast = OfficialSlotParser(source, normalized_source=source).parse()
            diagnostics = ()
        except OfficialSlotError as exc:
            ast = None
            match = re.search(r" at (\d+)$", str(exc))
            start = min(len(source), int(match.group(1))) if match else 0
            end = min(len(source), start + 1)
            fragment = source[start:end] if start < len(source) else "<EOF>"
            span = SourceSpan(start, end, 1, start + 1, 1, end + 1, fragment)
            diagnostics = (
                FrontendDiagnostic(exc.code, Severity.ERROR, str(exc), span, self.name),
            )
        return ParseOutcome(
            ast,
            diagnostics,
            source if original_source is None else original_source,
            source,
            repairs,
            self.name,
            perf_counter_ns() - started,
        )

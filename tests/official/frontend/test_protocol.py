import pytest

from findsl.official.frontend.protocol import (
    FrontendDiagnostic,
    ParseOutcome,
    Severity,
    SourceSpan,
)


def test_parse_outcome_serializes_grounded_diagnostic():
    span = SourceSpan(0, 3, 1, 1, 1, 4, "abc")
    diagnostic = FrontendDiagnostic("OFFICIAL_ANTLR_PARSE_ERROR", Severity.ERROR, "bad", span, "antlr")
    outcome = ParseOutcome(None, (diagnostic,), "abc", "abc", (), "antlr", 7)

    assert outcome.ok is False
    assert outcome.to_dict()["diagnostics"][0]["span"]["end_offset"] == 3


def test_source_span_rejects_non_half_open_offsets():
    with pytest.raises(ValueError, match="end_offset"):
        SourceSpan(3, 2, 1, 4, 1, 3, "")

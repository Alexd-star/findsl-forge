import pytest

from findsl.official.frontend.antlr_frontend import AntlrOfficialFrontend
from findsl.official_slot import OfficialSlotParser


@pytest.mark.parametrize(
    "source",
    [
        "indicator('', '', '涨幅', '今日', '', '', '') > 5%",
        "a + b * 2 >= 3 and c between [1, 4)",
        "a = 1 then rank('', '', '涨幅', 'desc', '今日', '', '', '') <= 10 limit 0,20",
        "x = -3.5 or y ~= -2%",
    ],
)
def test_antlr_ast_matches_handwritten_ast(source):
    outcome = AntlrOfficialFrontend().parse(source)

    assert outcome.ok, outcome.diagnostics
    handwritten = OfficialSlotParser(source, normalized_source=source).parse()
    assert outcome.ast.to_dict() == handwritten.to_dict()


def test_antlr_adapter_records_half_open_root_span():
    source = "a = 1"
    outcome = AntlrOfficialFrontend().parse(source)

    span = outcome.source_map.span_for(outcome.ast)
    assert (span.start_offset, span.end_offset, span.fragment) == (0, len(source), source)

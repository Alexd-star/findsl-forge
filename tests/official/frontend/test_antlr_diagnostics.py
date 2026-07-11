import pytest

from findsl.official.frontend.antlr_frontend import AntlrOfficialFrontend


@pytest.mark.parametrize(
    "source,code",
    [
        ("a =", "OFFICIAL_ANTLR_PARSE_ERROR"),
        ("a @ 1", "OFFICIAL_ANTLR_LEX_ERROR"),
        ("indicator('x)", "OFFICIAL_ANTLR_LEX_ERROR"),
    ],
)
def test_syntax_recovery_never_returns_success(source, code, capsys):
    outcome = AntlrOfficialFrontend().parse(source)

    assert outcome.ast is None
    assert outcome.ok is False
    assert outcome.diagnostics[0].code == code
    assert outcome.diagnostics[0].span.fragment
    assert capsys.readouterr().err == ""


def test_diagnostic_coordinates_are_one_based_and_offsets_are_half_open():
    outcome = AntlrOfficialFrontend().parse("a =\n@")
    span = outcome.diagnostics[0].span

    assert (span.start_line, span.start_column) == (2, 1)
    assert (span.start_offset, span.end_offset, span.fragment) == (4, 5, "@")

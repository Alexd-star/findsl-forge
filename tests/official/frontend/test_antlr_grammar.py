from findsl.official.frontend.antlr_frontend import AntlrOfficialFrontend


def test_keywords_are_case_insensitive_but_identifier_spelling_is_preserved():
    outcome = AntlrOfficialFrontend().parse("Alpha = 1 AnD beta = 2")

    assert outcome.ok
    value = outcome.ast.to_dict()
    assert value["op"] == "and"
    assert value["left"]["left"]["name"] == "Alpha"

from findsl.compat.official_frontend.handwritten import HandwrittenOfficialFrontend


def test_handwritten_frontend_returns_common_outcome():
    outcome = HandwrittenOfficialFrontend().parse("a = 1")

    assert outcome.ok
    assert outcome.frontend == "handwritten"
    assert outcome.ast.to_dict()["type"] == "Comparison"

from findsl.official.frontend.shadow import compare_frontends, first_ast_difference


def test_shadow_match_uses_canonical_ast_and_hash():
    comparison = compare_frontends("a = 1")

    assert comparison.classification == "MATCH"
    assert len(comparison.input_sha256) == 64
    assert comparison.source is None


def test_first_ast_difference_has_json_path():
    difference = first_ast_difference({"op": "and"}, {"op": "or"})

    assert difference.path == "$.op"
    assert difference.handwritten == "and"
    assert difference.antlr == "or"


def test_shadow_can_include_source_only_when_explicitly_requested():
    comparison = compare_frontends("a = 1", include_source=True)

    assert comparison.source == "a = 1"

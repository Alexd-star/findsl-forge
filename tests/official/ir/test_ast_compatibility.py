from dataclasses import FrozenInstanceError

import pytest

from findsl.official.ast import OfficialComparison as NewComparison
from findsl.official.ast import OfficialFunctionCall as NewFunctionCall
from findsl.official.ast import OfficialLiteral as NewLiteral
from findsl.official.ast import walk
from findsl.official_slot import OfficialComparison, OfficialFunctionCall, OfficialLiteral


def test_legacy_ast_exports_are_identical_class_objects():
    assert OfficialLiteral is NewLiteral
    assert OfficialFunctionCall is NewFunctionCall
    assert OfficialComparison is NewComparison


def test_ast_json_and_depth_first_walk_remain_stable():
    node = OfficialComparison(
        ">",
        OfficialFunctionCall("indicator", [OfficialLiteral("")] * 7),
        OfficialLiteral(5),
    )

    assert node.to_dict()["type"] == "Comparison"
    assert [type(item).__name__ for item in walk(node)][:3] == [
        "OfficialComparison",
        "OfficialFunctionCall",
        "OfficialLiteral",
    ]


def test_ast_dataclass_fields_remain_frozen():
    node = OfficialLiteral(1)
    with pytest.raises(FrozenInstanceError):
        node.value = 2

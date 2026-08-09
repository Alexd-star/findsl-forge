from findsl.official.pipeline import compile_official


def _crossing_union(temporal: str) -> str:
    return (
        "cross_above('', '', '', '压力位', '', '', "
        f"'{temporal}') = True or "
        "cross_down('', '', '', '压力位', '', '', "
        f"'{temporal}') = True"
    )


def test_exists_zero_union_shares_one_temporal_source_scan():
    result = compile_official(_crossing_union("EXIST>0")).to_dict()
    plan = result["physical"]["plan"]
    sql = result["backend"]["sql"]

    assert result["physical"]["selected_strategy"] == "shared_temporal_union"
    assert plan["kind"] == "PhysicalTemporal"
    assert len(plan["input"]["events"]) == 2
    assert plan["predicate"]["op"] == "or"
    assert "left_source_rows" not in sql
    assert "right_source_rows" not in sql


def test_consecutive_union_keeps_independent_temporal_plans():
    result = compile_official(_crossing_union("CONS>1")).to_dict()

    assert result["physical"]["selected_strategy"] == "set_union"
    assert result["physical"]["plan"]["kind"] == "PhysicalSetOperation"

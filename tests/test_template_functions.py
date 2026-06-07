from findsl import Compiler
from findsl.equivalence import verify_sql_equivalence
from findsl.registry import default_registry


def test_abs_template_function_compiles_from_config_metadata():
    result = Compiler().compile('filter(ABS(indicator("main_net_inflow")) > 0)')

    assert "ABS(main_net_inflow) AS" in result.sql
    assert any(
        step["rule"] == "TEMPLATE_NUMERIC_FUNCTION"
        and step["evidence"]["function"] == "ABS"
        for step in result.explain
    )


def test_abs_template_function_participates_in_reference_equivalence():
    result = verify_sql_equivalence(
        'filter(ABS(indicator("main_net_inflow")) > 150)',
        data_dir=__import__("pathlib").Path("data/samples"),
    )

    assert result.passed
    assert result.sql_row_count == result.reference_row_count


def test_abs_template_function_is_declared_in_registry_config():
    meta = default_registry().function("ABS")

    assert meta["sql_template"] == "ABS({arg0})"
    assert meta["reference_op"] == "abs"
    assert meta["arg_types"] == ["numeric"]

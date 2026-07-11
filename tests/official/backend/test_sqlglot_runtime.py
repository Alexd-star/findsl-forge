from importlib.metadata import version

import sqlglot
from sqlglot import exp


def test_sqlglot_version_is_pinned_and_doris_round_trip_is_stable():
    assert version("sqlglot") == "28.5.0"
    source = "SELECT `mktcode`, ROW_NUMBER() OVER (PARTITION BY `mktcode` ORDER BY `bizdate`) AS `rn` FROM `newzl`.`hsj_stock_hq_basic`"

    parsed = sqlglot.parse_one(source, read="doris")
    rendered = parsed.sql(dialect="doris")
    reparsed = sqlglot.parse_one(rendered, read="doris")

    assert isinstance(parsed, exp.Select)
    assert reparsed.sql(dialect="doris") == rendered


def test_sqlglot_literal_escapes_values_without_manual_quoting():
    expression = exp.select(exp.Literal.string("O'Reilly").as_("value"))
    sql = expression.sql(dialect="doris")

    assert "O''Reilly" in sql

from findsl.official.backend.diff import compare_doris_sql, hash_result_rows


def test_structural_diff_ignores_formatting_and_alias_spelling():
    legacy = "SELECT a.mktcode, a.tgtcode, a.bizdate FROM newzl.hsj_stock_hq_basic AS a WHERE a.volume > 100"
    shadow = "SELECT `q`.`mktcode`, `q`.`tgtcode`, `q`.`bizdate` FROM `newzl`.`hsj_stock_hq_basic` AS `q` WHERE `q`.`volume` > 100"

    result = compare_doris_sql(legacy, shadow)

    assert result.equivalent is True
    assert result.differences == ()
    assert result.shadow.tables == ("newzl.hsj_stock_hq_basic",)
    assert "GT" in result.shadow.operators


def test_result_hash_has_explicit_order_contract():
    rows = [("SH", "600000", 1.5), ("SZ", "000001", None)]
    reversed_rows = list(reversed(rows))

    assert hash_result_rows(rows, ordered=False) == hash_result_rows(reversed_rows, ordered=False)
    assert hash_result_rows(rows, ordered=True) != hash_result_rows(reversed_rows, ordered=True)
    assert hash_result_rows(rows, ordered=False) == hash_result_rows(rows, ordered=False)

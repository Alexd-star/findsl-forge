from pathlib import Path

import pytest

from findsl.official.physical.catalog import PhysicalCatalog, PhysicalCatalogError, default_physical_catalog


def test_default_catalog_resolves_direct_official_fields_and_resources():
    catalog = default_physical_catalog()
    field = catalog.indicator("成交量")

    assert field.resource_id == "official_basic"
    assert field.column == "volume"
    assert catalog.resource(field.resource_id).table == "hsj_stock_hq_basic"
    assert catalog.resource(field.resource_id).partition_key == "bizdate"


def test_catalog_excludes_missing_domains_and_is_cached():
    catalog = default_physical_catalog()
    assert default_physical_catalog() is catalog
    with pytest.raises(KeyError):
        catalog.indicator("营业收入")


def test_catalog_rejects_sql_fragments_and_unknown_resources(tmp_path):
    path = tmp_path / "physical.json"
    path.write_text(
        '{"resources":[{"resource_id":"r","database":"newzl","table":"bad table","logical_entity":"market_observation","partition_key":"bizdate","distribution_key":"tgtcode","capabilities":["scan"],"priority":1}],'
        '"fields":[{"indicator_id":"X","resource_id":"missing","column":"x; DROP TABLE y","value_type":"numeric","scale":1,"nullable":true}]}',
        encoding="utf-8",
    )
    with pytest.raises(PhysicalCatalogError):
        PhysicalCatalog.load(path)

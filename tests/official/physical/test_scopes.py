import pytest

from findsl.official.physical.scopes import (
    SecurityScopeCatalog,
    SecurityScopeCatalogError,
    default_security_scope_catalog,
)


def test_default_security_scope_catalog_is_grounded_in_official_master_data():
    catalog = default_security_scope_catalog()

    assert len(catalog.entries) == 5686
    assert catalog.source_table == "newzl.hsj_stock_code_info"
    assert catalog.source_sha256 == "606330117bced197063c7f9bb2531f8a135150c5c982d7289c62265f68f2a635"
    assert catalog.resolve("华泰证券").name == "华泰证券"
    explicit = catalog.resolve("珀莱雅(603605)")
    assert explicit.explicit_code is True
    assert explicit.identities[0].tgtcode == "603605"
    numeric = catalog.resolve("300084")
    assert numeric.name == "海默科技"
    assert numeric.explicit_code is True
    assert numeric.identities[0].tgtcode == "300084"


def test_security_scope_catalog_rejects_unknown_concept_membership():
    with pytest.raises(KeyError):
        default_security_scope_catalog().resolve("鸿蒙概念")


def test_security_scope_catalog_rejects_invalid_root():
    with pytest.raises(SecurityScopeCatalogError):
        SecurityScopeCatalog.from_dict({"schema_version": 1, "entries": []})

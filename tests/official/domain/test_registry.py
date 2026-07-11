from pathlib import Path

import pytest

from findsl.official.registry import OfficialIndicatorRegistry, RegistryValidationError, default_official_registry
from findsl.official_slot import INDICATORS


def test_default_registry_covers_every_static_legacy_indicator_type():
    registry = default_official_registry()

    assert len(registry) >= len(INDICATORS)
    for name, legacy in INDICATORS.items():
        assert registry.resolve(name).value_type == legacy.kind


def test_registry_is_cached_and_definitions_are_immutable():
    first = default_official_registry()
    second = default_official_registry()

    assert first is second
    with pytest.raises(Exception):
        first.resolve("涨幅").aliases += ("变化",)


def test_official_workbook_missing_domain_is_declared_not_unknown():
    definition = default_official_registry().resolve("营业收入")

    assert definition.availability == "missing"
    assert definition.domain == "financial"


def test_registry_rejects_duplicate_aliases_and_unknown_fields(tmp_path):
    path = tmp_path / "indicators.json"
    path.write_text(
        '[{"canonical_name":"A","aliases":["同名"],"value_type":"numeric","domain":"quote","logical_field":"a","unit":"count","scale":1,"nullable":true,"availability":"official_provided","capabilities":[],"extra":1},'
        '{"canonical_name":"B","aliases":["同名"],"value_type":"numeric","domain":"quote","logical_field":"b","unit":"count","scale":1,"nullable":true,"availability":"official_provided","capabilities":[]}]',
        encoding="utf-8",
    )

    with pytest.raises(RegistryValidationError):
        OfficialIndicatorRegistry.load(path)

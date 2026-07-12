import json

import pytest

from findsl.official.physical.patterns import (
    PhysicalPatternConfig,
    PhysicalPatternConfigError,
    default_physical_pattern_config,
)


def test_default_pattern_config_is_typed_and_bounded():
    config = default_physical_pattern_config()

    assert config.close_together_relative_threshold == 0.03
    assert config.reset_near_line_threshold == 0.02
    assert config.reset_below_line_tolerance == 0.005
    assert config.version


def test_pattern_config_rejects_out_of_range_threshold(tmp_path):
    path = tmp_path / "patterns.json"
    path.write_text(
        json.dumps(
            {
                "version": "test",
                "close_together": {"relative_threshold": 2},
                "reset": {"near_line_threshold": 0.02, "below_line_tolerance": 0.005},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(PhysicalPatternConfigError, match="out of range"):
        PhysicalPatternConfig.load(path)

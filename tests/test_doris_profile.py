import pytest

from findsl.doris_profile import (
    DorisProfileError,
    explain_partition_ratios,
    parse_doris_duration,
    parse_profile_summary,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("57ms", 57.0),
        ("1sec90ms", 1090.0),
        ("1min14sec", 74000.0),
        ("2hour3min4sec5ms", 7384005.0),
        ("125us", 0.125),
        ("900ns", 0.0009),
    ],
)
def test_parse_doris_duration(value, expected):
    assert parse_doris_duration(value) == pytest.approx(expected)


def test_parse_profile_summary_requires_uncached_success_metadata():
    summary = parse_profile_summary(
        """Summary:
   - Profile ID: abc-def
   - Total: 1sec90ms
   - Task State: OK
Execution Summary:
   - Doris Version: doris-4.1.0
   - Is Cached: No
"""
    )
    assert summary.profile_id == "abc-def"
    assert summary.total_ms == 1090.0
    assert summary.task_state == "OK"
    assert summary.doris_version == "doris-4.1.0"
    assert summary.is_cached is False


def test_parse_profile_summary_rejects_missing_cache_status():
    with pytest.raises(DorisProfileError, match="Is Cached"):
        parse_profile_summary(
            """Summary:
   - Profile ID: abc-def
   - Total: 57ms
   - Task State: OK
Execution Summary:
   - Doris Version: doris-4.1.0
"""
        )


def test_explain_partition_ratios_preserve_all_scan_nodes():
    explain = """
      TABLE: newzl.base
      partitions=1/1 (base)
      TABLE: newzl.rollup
      partitions=1/244 (p202604)
    """
    assert explain_partition_ratios(explain) == ((1, 1), (1, 244))

from pathlib import Path

import pytest

from findsl.official.backend.executor import DorisExecutionConfig, DorisExecutionResult
from findsl.official.watermark import (
    OfficialWatermarkError,
    assert_official_watermarks,
    collect_official_watermarks,
)


def _executor(_config, _sql):
    return DorisExecutionResult(
        rows=(("13650347", "4631", "2006-01-04", "2026-04-14"),),
        elapsed_ms=1.0,
        ordered_hash="ordered",
        unordered_hash="unordered",
    )


def test_official_watermark_gate_requires_all_materialized_paths_to_match():
    report = collect_official_watermarks(
        statistics_path=Path("configs/official/physical_statistics.json"),
        catalog_path=Path("configs/official/physical_catalog.json"),
        doris=DorisExecutionConfig("localhost", 9030, "root", "", "newzl"),
        executor=_executor,
    )

    assert report["passed"] is True
    assert report["cross_resource_watermark_coherent"] is True
    assert len(report["resources"]) == 5
    assert_official_watermarks(report)


def test_official_watermark_gate_rejects_stale_materialization():
    calls = 0

    def stale_executor(config, sql):
        nonlocal calls
        calls += 1
        result = _executor(config, sql)
        if calls == 3:
            return DorisExecutionResult(
                rows=(("13650346", "4631", "2006-01-04", "2026-04-14"),),
                elapsed_ms=1.0,
                ordered_hash="ordered",
                unordered_hash="unordered",
            )
        return result

    report = collect_official_watermarks(
        statistics_path=Path("configs/official/physical_statistics.json"),
        catalog_path=Path("configs/official/physical_catalog.json"),
        doris=DorisExecutionConfig("localhost", 9030, "root", "", "newzl"),
        executor=stale_executor,
    )

    with pytest.raises(OfficialWatermarkError, match="watermark gate failed"):
        assert_official_watermarks(report)

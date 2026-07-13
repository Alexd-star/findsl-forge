from types import SimpleNamespace

import pytest

from findsl.official.backend.executor import DorisExecutionConfig
from findsl.official.physical.catalog import default_physical_catalog
from findsl.official.physical.statistics import (
    PhysicalStatisticsError,
    collect_physical_statistics,
    parse_doris_size,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("296.573 KB", 303691),
        ("392.052 MB", 411096318),
        ("1.313 GB", 1409823015),
        ("0.000 B", 0),
    ],
)
def test_doris_size_units_are_converted_to_bytes(value, expected):
    assert parse_doris_size(value) == expected


def test_collector_uses_controlled_metadata_commands_and_hides_password():
    catalog = default_physical_catalog()
    config = DorisExecutionConfig("127.0.0.1", 9030, "root", "secret", "newzl")
    calls = []

    sizes = {
        "hsj_stock_hq_basic": "392.052 MB",
        "hsj_stock_hq_ext": "292.684 MB",
        "hsj_stock_code_info": "296.573 KB",
        "hsj_stock_hq_basic_technical": "1.313 GB",
        "hsj_stock_hq_basic_prefix": "375.350 MB",
        "hsj_stock_hq_ext_prefix": "135.735 MB",
        "scope_membership": "4.000 MB",
        "industry_membership": "2.000 MB",
        "instrument_rule": "512.000 KB",
        "index_quote": "1.000 MB",
    }
    rows = {
        "hsj_stock_hq_basic": 13650347,
        "hsj_stock_hq_ext": 6170822,
        "hsj_stock_code_info": 5686,
        "hsj_stock_hq_basic_technical": 13650347,
        "hsj_stock_hq_basic_prefix": 13650347,
        "hsj_stock_hq_ext_prefix": 13650347,
        "scope_membership": 35421,
        "industry_membership": 23226,
        "instrument_rule": 5686,
        "index_quote": 14533,
    }

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        sql = command[command.index("--execute") + 1]
        if sql == "SHOW FRONTENDS":
            return SimpleNamespace(
                returncode=0,
                stdout="Name\tIsMaster\tVersion\nfe-1\ttrue\tdoris-4.1.0-rc03-5960d4cea0e\n",
                stderr="",
            )
        if sql == "SHOW DATA":
            database = command[command.index("--database") + 1]
            expected = {
                resource.table
                for resource in catalog.resources
                if resource.database == database
            }
            lines = ["TableName\tSize\tReplicaCount\tRemoteSize"]
            lines.extend(
                f"{name}\t{sizes[name]}\t16\t0.000" for name in sorted(expected)
            )
            return SimpleNamespace(returncode=0, stdout="\n".join(lines) + "\n", stderr="")
        table = sql.split("`")[1]
        return SimpleNamespace(
            returncode=0,
            stdout=f"updated_rows\trow_count\tenable_auto_analyze\n\t{rows[table]}\ttrue\n",
            stderr="",
        )

    snapshot = collect_physical_statistics(
        catalog,
        config,
        runner=runner,
        collected_at="2026-07-11T16:00:00+08:00",
    )

    assert snapshot.resource("official_ext").row_count == 6170822
    assert snapshot.resource("official_basic").data_size_bytes == 411096318
    assert snapshot.doris_version == "doris-4.1.0-rc03-5960d4cea0e"
    assert all("secret" not in part for command, _ in calls for part in command)
    assert all(kwargs["env"]["MYSQL_PWD"] == "secret" for _, kwargs in calls)
    assert len(calls) == 13


def test_collector_rejects_missing_show_data_resource():
    catalog = default_physical_catalog()
    config = DorisExecutionConfig("127.0.0.1", 9030, "root", "", "newzl")

    def runner(command, **kwargs):
        sql = command[command.index("--execute") + 1]
        if sql == "SHOW FRONTENDS":
            return SimpleNamespace(
                returncode=0,
                stdout="Name\tIsMaster\tVersion\nfe-1\ttrue\tdoris-4.1.0\n",
                stderr="",
            )
        if sql == "SHOW DATA":
            return SimpleNamespace(returncode=0, stdout="TableName\tSize\n", stderr="")
        raise AssertionError("table stats must not run after an incomplete SHOW DATA result")

    with pytest.raises(PhysicalStatisticsError, match="SHOW DATA missing"):
        collect_physical_statistics(catalog, config, runner=runner)

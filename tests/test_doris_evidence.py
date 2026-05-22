import json

import pytest

from findsl import doris_evidence
from findsl.doris_evidence import DorisClientConfig, collect_doris_evidence


def test_collect_doris_evidence_writes_validated_markdown_and_json(tmp_path, monkeypatch):
    clock = [0.0]

    def fake_perf_counter():
        return clock[0]

    def fake_run_sql(config, sql, password_mode):
        if sql.startswith("EXPLAIN") and "dwd_stock_daily_quote_prefix" in sql:
            return "PLAN FRAGMENT\nOLAP_SCAN_NODE table=dwd_stock_daily_quote_prefix\nHASH JOIN\n"
        if sql.startswith("EXPLAIN"):
            return "PLAN FRAGMENT\nANALYTIC_EVAL_NODE WINDOW\nROWS BETWEEN\n"
        if sql.startswith("SELECT COUNT(*)"):
            clock[0] += 0.01 if "dwd_stock_daily_quote_prefix" in sql else 0.20
            return "42\n"
        raise AssertionError(f"unexpected SQL: {sql}")

    monkeypatch.setattr(doris_evidence, "_run_sql", fake_run_sql)
    monkeypatch.setattr(doris_evidence.time, "perf_counter", fake_perf_counter)
    output = tmp_path / "doris_cluster_evidence.md"

    result = collect_doris_evidence(
        DorisClientConfig(host="127.0.0.1", port=9030, user="root", database="findsl_demo"),
        output,
        iterations=2,
    )

    assert result.passed
    assert result.row_counts_match
    assert result.baseline.row_count == 42
    assert result.optimized.row_count == 42
    assert result.baseline.plan_contains_window
    assert result.optimized.plan_contains_prefix
    assert result.speedup >= 10.0
    assert result.speedup_target_met

    markdown = output.read_text(encoding="utf-8")
    assert "Doris Cluster Evidence" in markdown
    assert "Evidence passed: True" in markdown
    assert "Baseline success: True" in markdown
    assert "Optimized success: True" in markdown
    assert "Row counts match: True" in markdown
    assert "Client command template:" in markdown
    assert "Minimum Doris speedup target: 10.00x" in markdown
    assert "Doris speedup target met: True" in markdown
    assert "Optimized plan contains prefix table: True" in markdown
    assert "Baseline plan contains window: True" in markdown

    payload = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert "mysql" in payload["client_command"]
    assert payload["row_counts_match"] is True
    assert payload["min_speedup"] == 10.0
    assert payload["speedup_target_met"] is True
    assert payload["baseline_plan_contains_window"] is True
    assert payload["optimized_plan_contains_prefix"] is True


def test_collect_doris_evidence_fails_when_speedup_target_is_not_met(tmp_path, monkeypatch):
    clock = [0.0]

    def fake_perf_counter():
        return clock[0]

    def fake_run_sql(config, sql, password_mode):
        if sql.startswith("EXPLAIN") and "dwd_stock_daily_quote_prefix" in sql:
            return "OLAP_SCAN_NODE table=dwd_stock_daily_quote_prefix\n"
        if sql.startswith("EXPLAIN"):
            return "ANALYTIC_EVAL_NODE WINDOW\n"
        if sql.startswith("SELECT COUNT(*)"):
            clock[0] += 0.10 if "dwd_stock_daily_quote_prefix" in sql else 0.20
            return "42\n"
        raise AssertionError(f"unexpected SQL: {sql}")

    monkeypatch.setattr(doris_evidence, "_run_sql", fake_run_sql)
    monkeypatch.setattr(doris_evidence.time, "perf_counter", fake_perf_counter)
    output = tmp_path / "doris_cluster_evidence.md"

    result = collect_doris_evidence(
        DorisClientConfig(host="127.0.0.1", port=9030, user="root", database="findsl_demo"),
        output,
        iterations=2,
    )

    assert not result.passed
    assert result.row_counts_match
    assert result.baseline.plan_contains_window
    assert result.optimized.plan_contains_prefix
    assert not result.speedup_target_met
    assert "Doris speedup target met: False" in output.read_text(encoding="utf-8")


def test_collect_doris_evidence_preserves_cluster_failure(tmp_path, monkeypatch):
    def fake_run_sql(config, sql, password_mode):
        if sql.startswith("EXPLAIN") and "dwd_stock_daily_quote_prefix" in sql:
            raise RuntimeError("prefix table is missing")
        if sql.startswith("EXPLAIN"):
            return "ANALYTIC_EVAL_NODE WINDOW\n"
        return "7\n"

    monkeypatch.setattr(doris_evidence, "_run_sql", fake_run_sql)
    output = tmp_path / "doris_cluster_evidence.md"

    result = collect_doris_evidence(
        DorisClientConfig(host="127.0.0.1", port=9030, user="root", database="findsl_demo"),
        output,
        iterations=1,
    )

    assert not result.passed
    assert result.baseline.success
    assert not result.optimized.success
    assert "prefix table is missing" in result.optimized.error

    markdown = output.read_text(encoding="utf-8")
    assert "Evidence passed: False" in markdown
    assert "Optimized success: False" in markdown
    assert "prefix table is missing" in markdown


def test_doris_client_command_places_and_redacts_password():
    config = DorisClientConfig(
        host="doris-fe.local",
        port=9030,
        user="root",
        password="secret",
        database="findsl_demo",
    )

    command = config.command("SELECT 1", password_mode="inline")

    assert command[:7] == ["mysql", "-h", "doris-fe.local", "-P", "9030", "-u", "root"]
    assert "-psecret" in command
    assert command[-3:] == ["findsl_demo", "-e", "SELECT 1"]
    assert "secret" not in doris_evidence._redacted_command(command)
    assert "-p***" in doris_evidence._redacted_command(command)


def test_doris_client_prompt_mode_requests_password_without_inline_secret():
    config = DorisClientConfig(
        host="doris-fe.local",
        port=9030,
        user="root",
        database="findsl_demo",
    )

    command = config.command("SELECT 1", password_mode="prompt")

    assert "-p" in command
    assert all(not part.startswith("-p") or part == "-p" for part in command)


def test_collect_doris_evidence_rejects_non_positive_iterations(tmp_path):
    with pytest.raises(ValueError, match="iterations must be positive"):
        collect_doris_evidence(
            DorisClientConfig(host="127.0.0.1", port=9030, user="root", database="findsl_demo"),
            tmp_path / "doris_cluster_evidence.md",
            iterations=0,
        )


def test_collect_doris_evidence_rejects_negative_min_speedup(tmp_path):
    with pytest.raises(ValueError, match="min_speedup must be non-negative"):
        collect_doris_evidence(
            DorisClientConfig(host="127.0.0.1", port=9030, user="root", database="findsl_demo"),
            tmp_path / "doris_cluster_evidence.md",
            min_speedup=-1,
        )


def test_collect_doris_evidence_requires_explicit_password_mode(tmp_path):
    with pytest.raises(ValueError, match="password_mode is none"):
        collect_doris_evidence(
            DorisClientConfig(
                host="127.0.0.1",
                port=9030,
                user="root",
                password="secret",
                database="findsl_demo",
            ),
            tmp_path / "doris_cluster_evidence.md",
            iterations=1,
        )

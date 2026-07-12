import os
import json
import subprocess
import sys
from pathlib import Path


def test_cli_official_physical_stats_writes_versioned_snapshot(tmp_path, monkeypatch, capsys):
    from findsl import cli
    from findsl.official.physical.catalog import default_physical_catalog
    from findsl.official.physical.statistics import PhysicalStatisticsSnapshot
    import findsl.official.physical.statistics as statistics_module

    output = tmp_path / "physical_statistics.json"
    catalog = default_physical_catalog()
    snapshot = PhysicalStatisticsSnapshot.from_dict(
        {
            "schema_version": 1,
            "catalog_sha256": catalog.fingerprint,
            "collected_at": "2026-07-11T16:00:00+08:00",
            "doris_version": "4.1.0",
            "resources": [
                {"resource_id": "official_basic", "row_count": 10, "data_size_bytes": 400, "row_count_available": True},
            ],
        },
        catalog,
    )
    seen = {}

    def collect(received_catalog, config):
        seen["host"] = config.host
        seen["port"] = config.port
        return snapshot

    monkeypatch.setattr(statistics_module, "collect_physical_statistics", collect)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "findsl",
            "official-physical-stats",
            "--output",
            str(output),
            "--host",
            "doris.local",
            "--port",
            "19030",
            "--json",
        ],
    )

    cli.main()

    payload = json.loads(capsys.readouterr().out)
    assert seen == {"host": "doris.local", "port": 19030}
    assert payload["schema_version"] == 1
    assert output.exists()


def test_official_physical_cli_path_uses_real_statistics_by_default():
    from findsl.cli import _build_official_physical

    result = _build_official_physical("indicator('', '', '成交量', '', '', '', '') > 100")

    assert result.decisions[0].estimated is False
    assert result.decisions[0].cost_unit == "bytes"


def test_cli_official_prefix_evidence_wires_doris_config_and_outputs(tmp_path, monkeypatch, capsys):
    from findsl import cli
    import findsl.official_prefix_evidence as evidence_module

    json_output = tmp_path / "prefix.json"
    report_output = tmp_path / "prefix.md"
    seen = {}

    def build(*, config):
        seen["host"] = config.host
        return {"status": "PASS", "case_count": 2, "matched": 2, "errors": 0, "results": []}

    def write(report, json_path, markdown_path):
        json_output.write_text(json.dumps(report), encoding="utf-8")
        report_output.write_text("# PASS", encoding="utf-8")

    monkeypatch.setattr(evidence_module, "build_official_prefix_evidence", build)
    monkeypatch.setattr(evidence_module, "write_official_prefix_evidence", write)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "findsl", "official-prefix-evidence",
            "--json-output", str(json_output),
            "--report-output", str(report_output),
            "--host", "doris.local",
        ],
    )

    cli.main()

    assert seen["host"] == "doris.local"
    assert "Prefix gate: PASS" in capsys.readouterr().out
    assert json_output.exists() and report_output.exists()


def test_cli_official_coverage_funnel_writes_both_artifacts(tmp_path, monkeypatch, capsys):
    from findsl import cli
    import findsl.official_coverage_funnel as funnel_module

    json_output = tmp_path / "funnel.json"
    report_output = tmp_path / "funnel.md"
    seen = {}

    def build(workbook):
        seen["workbook"] = workbook
        return {
            "row_count": 4,
            "legacy_strict_success": 2,
            "new_backend_success": 1,
            "legacy_to_new_migrated": 1,
            "migration_coverage": 0.5,
        }

    def write(report, json_path, markdown_path):
        Path(json_path).write_text(json.dumps(report), encoding="utf-8")
        Path(markdown_path).write_text("# funnel", encoding="utf-8")

    monkeypatch.setattr(funnel_module, "build_official_workbook_coverage_funnel", build)
    monkeypatch.setattr(funnel_module, "write_official_coverage_funnel", write)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "findsl",
            "official-coverage-funnel",
            "--workbook",
            "official.xlsx",
            "--json-output",
            str(json_output),
            "--report-output",
            str(report_output),
        ],
    )

    cli.main()

    assert seen["workbook"] == "official.xlsx"
    assert "Migration coverage: 1/2 (50.00%)" in capsys.readouterr().out
    assert json_output.exists() and report_output.exists()


def test_cli_evaluate_returns_nonzero_when_cases_fail(tmp_path):
    cases = tmp_path / "cases.jsonl"
    cases.write_text(
        (
            '{"name":"bad fragment","dsl":"filter(indicator(\\"close\\") > 10)",'
            '"expected_sql_fragments":["definitely_missing_fragment"]}\n'
        ),
        encoding="utf-8",
    )
    output = tmp_path / "evaluation_report.md"
    env = os.environ.copy()
    env["PYTHONPATH"] = "src" + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "findsl.cli",
            "evaluate",
            "--input",
            str(cases),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )

    assert completed.returncode == 1
    assert "Failed cases: 1" in completed.stdout
    assert output.exists()


def test_cli_official_performance_matrix_writes_json_and_markdown(tmp_path):
    evidence = tmp_path / "official_doris_evidence.json"
    json_output = tmp_path / "official_query_performance_matrix.json"
    report_output = tmp_path / "official_query_performance_matrix.md"
    evidence.write_text(
        json.dumps(
            {
                "generated_at": "2026-07-06T08:00:00Z",
                "row_counts": {"hsj_stock_hq_basic": 10},
                "baseline_prefix_row_count_match": True,
                "baseline_vs_prefix_speedup": 36.24,
                "queries": [
                    {
                        "name": "prefix_case",
                        "row_count": 5,
                        "avg_ms": 12.3,
                        "p95_ms": 15.7,
                        "plan_contains_prefix": True,
                        "plan_contains_window": False,
                        "sql": "SELECT * FROM newzl.hsj_stock_hq_basic_prefix",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = "src" + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "findsl.cli",
            "official-performance-matrix",
            "--evidence",
            str(evidence),
            "--json-output",
            str(json_output),
            "--report-output",
            str(report_output),
            "--json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["summary"]["query_count"] == 1
    assert payload["queries"][0]["plan_kind"] == "prefix"
    assert json_output.exists()
    assert "# 官方真实数据逐问句性能矩阵" in report_output.read_text(encoding="utf-8")


def test_cli_official_parse_recovery_preserves_ast_json_contract():
    env = os.environ.copy()
    env["PYTHONPATH"] = "src" + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONIOENCODING"] = "utf-8"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "findsl.cli",
            "official-slot-parse",
            "and indicator('', '', '涨停', '', '', '', '') = True",
            "--mode",
            "recovery",
            "--json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["type"] == "Comparison"
    assert payload["left"]["name"] == "indicator"
    assert payload["repairs"][0]["code"] == "LEADING_BOOLEAN_OPERATOR"
    assert payload["normalized_source"].startswith("indicator(")
    assert payload["mode"] == "recovery"


def test_cli_official_compile_strict_reports_strict_success():
    env = os.environ.copy()
    env["PYTHONPATH"] = "src" + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONIOENCODING"] = "utf-8"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "findsl.cli",
            "official-slot-compile",
            "indicator('沪', '', '成交量', '2026-04-14', '', '', '') > 1000",
            "--mode",
            "strict",
            "--json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["strict_success"] is True
    assert payload["degraded"] is False
    assert payload["repairs"] == []


def test_cli_official_compile_strict_json_error_is_structured():
    env = os.environ.copy()
    env["PYTHONPATH"] = "src" + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONIOENCODING"] = "utf-8"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "findsl.cli",
            "official-slot-compile",
            "indicator('', '', '收盘价', '收盘后', '', '', '') > 1",
            "--mode",
            "strict",
            "--json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )

    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "OFFICIAL_DEGRADED_SEMANTICS"


def test_cli_official_compile_recovery_text_exposes_degraded_status():
    env = os.environ.copy()
    env["PYTHONPATH"] = "src" + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONIOENCODING"] = "utf-8"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "findsl.cli",
            "official-slot-compile",
            "and indicator('港', '', '收盘价', '收盘后', '', '', '') > 1",
            "--mode",
            "recovery",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )

    assert completed.returncode == 0
    assert "Strict success: False" in completed.stdout
    assert "Degraded: True" in completed.stdout
    assert "LEADING_BOOLEAN_OPERATOR" in completed.stdout
    assert "Fallback predicates: 1=0, 1=1" in completed.stdout

import os
import json
import subprocess
import sys


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

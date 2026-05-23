import os
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

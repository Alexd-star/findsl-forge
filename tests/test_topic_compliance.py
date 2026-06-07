import json
import os
import subprocess
import sys
from pathlib import Path

from findsl.topic_compliance import build_topic_compliance_report, render_topic_compliance_markdown


def test_topic_compliance_report_classifies_core_requirements():
    report = build_topic_compliance_report()
    by_id = {item.requirement_id: item for item in report.items}

    assert by_id["T19-R1"].status == "implemented"
    assert by_id["T19-R4"].status == "partial"
    assert by_id["T19-R7"].status == "needs_evidence"
    assert report.summary["implemented"] >= 8
    assert report.summary["partial"] >= 1
    assert report.summary["needs_evidence"] >= 1


def test_topic_compliance_markdown_contains_next_step_plan():
    report = build_topic_compliance_report()
    markdown = render_topic_compliance_markdown(report)

    assert "# 赛题 19 完成度与下一步规划" in markdown
    assert "| T19-R9 | 新指标/新函数 0 行核心代码改动 | partial |" in markdown
    assert "下一步开发规划" in markdown
    assert "官方 DSL 规范" in markdown


def test_topic_compliance_cli_writes_markdown_and_json(tmp_path: Path):
    output = tmp_path / "topic_compliance.md"
    env = os.environ.copy()
    env["PYTHONPATH"] = "src" + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONIOENCODING"] = "utf-8"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "findsl.cli",
            "topic-compliance",
            "--output",
            str(output),
            "--json",
        ],
        check=True,
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=env,
    )

    payload = json.loads(completed.stdout)
    assert payload["summary"]["implemented"] >= 8
    assert output.exists()
    assert "赛题 19 完成度与下一步规划" in output.read_text(encoding="utf-8")

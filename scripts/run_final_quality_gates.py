from __future__ import annotations

import argparse
import json
import re
import shutil
import site
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run final source quality gates")
    parser.add_argument(
        "--json-output", type=Path, default=Path("reports/final_quality_gates.json")
    )
    parser.add_argument(
        "--report-output", type=Path, default=Path("reports/final_quality_gates.md")
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    lint_imports = _find_lint_imports()
    commands = [
        ("ANTLR generated sources", [sys.executable, "scripts/generate_antlr.py", "--check"]),
        ("Ruff", [sys.executable, "-m", "ruff", "check", "."]),
        ("Architecture boundaries", [lint_imports]),
        ("Pytest", [sys.executable, "-m", "pytest"]),
        (
            "Official positive and negative suites",
            [
                sys.executable,
                "-m",
                "findsl.cli",
                "official-suite",
                "--positive-input",
                "data/samples/official_positive_cases.jsonl",
                "--negative-input",
                "data/samples/official_negative_cases.jsonl",
                "--data-dir",
                "data/samples",
                "--output",
                "reports/official_suite_report.md",
            ],
        ),
    ]
    results = []
    for name, command in commands:
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        output = _sanitize(completed.stdout + "\n" + completed.stderr, root)
        results.append(
            {
                "name": name,
                "command": _display_command(command),
                "exit_code": completed.returncode,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "output_tail": "\n".join(output.strip().splitlines()[-20:]),
                "passed": completed.returncode == 0,
            }
        )
        if completed.returncode != 0:
            break
    combined = "\n".join(item["output_tail"] for item in results)
    pytest_match = re.search(r"(\d+) passed", combined)
    warning_match = re.search(r"(\d+) warnings?", combined)
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "git_head": _git_head(root),
        "all_passed": len(results) == len(commands)
        and all(item["passed"] for item in results),
        "pytest_passed": int(pytest_match.group(1)) if pytest_match else None,
        "warning_count": int(warning_match.group(1)) if warning_match else 0,
        "commands": results,
    }
    _write(report, args.json_output, args.report_output)
    print(
        f"status={'PASS' if report['all_passed'] else 'FAIL'} "
        f"pytest={report['pytest_passed']} warnings={report['warning_count']}"
    )
    return 0 if report["all_passed"] else 1


def _write(report: dict, json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# 最终源码质量门禁",
        "",
        f"- Git HEAD：`{report['git_head']}`",
        f"- 总状态：`{'PASS' if report['all_passed'] else 'FAIL'}`",
        f"- Pytest：`{report['pytest_passed']} passed`",
        f"- Warning：`{report['warning_count']}`",
        "",
        "| 门禁 | 耗时（秒） | 状态 |",
        "|---|---:|---|",
    ]
    for item in report["commands"]:
        lines.append(
            f"| {item['name']} | {item['elapsed_seconds']:.3f} | "
            f"{'PASS' if item['passed'] else 'FAIL'} |"
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _display_command(command: list[str]) -> str:
    normalized = [
        "python"
        if index == 0 and Path(value).name.lower().startswith("python")
        else "lint-imports"
        if index == 0 and Path(value).name.lower().startswith("lint-imports")
        else value
        for index, value in enumerate(command)
    ]
    return subprocess.list2cmdline(normalized)


def _sanitize(value: str, root: Path) -> str:
    return value.replace(str(root), "<PROJECT_ROOT>").replace(str(Path.home()), "<USER_HOME>")


def _git_head(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _find_lint_imports() -> str:
    candidates = (
        shutil.which("lint-imports"),
        str(Path(sys.executable).parent / "lint-imports.exe"),
        str(Path(site.USER_BASE) / "Scripts" / "lint-imports.exe"),
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("lint-imports is not available; install the dev dependency set")


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from findsl.official.context import CompileContext
from findsl.official.pipeline import compile_official


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prove config-only function extension without modifying core compiler code"
    )
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    before = _core_tree_hash(root / "src/findsl/official")
    with tempfile.TemporaryDirectory(prefix="findsl-blind-extension-") as temporary:
        sandbox = Path(temporary)
        shutil.copytree(root / "configs", sandbox / "configs")
        function_path = sandbox / "configs/official/functions.json"
        payload = json.loads(function_path.read_text(encoding="utf-8"))
        extension = {
            "name": "blind_demo_margin",
            "aliases": [],
            "argument_mode": "expressions",
            "arg_types": ["numeric", "numeric", "numeric"],
            "result_kind": "boolean",
            "expression_template": {
                "op": "greater_equal",
                "args": [
                    {
                        "op": "safe_divide",
                        "args": [
                            {"op": "subtract", "args": [{"arg": 0}, {"arg": 1}]},
                            {"op": "abs", "args": [{"arg": 1}]},
                        ],
                    },
                    {"arg": 2},
                ],
            },
            "version": "blind-demo-v1",
        }
        payload["functions"].append(extension)
        function_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        context = CompileContext.load(sandbox)
        dsl = (
            "blind_demo_margin("
            "indicator('', '', '收盘价', '今日', '', '', ''), "
            "indicator('', '', '最低价', '今日', '', '', ''), 0.01) = True"
        )
        compiled = compile_official(dsl, context=context)
    after = _core_tree_hash(root / "src/findsl/official")
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "git_head": _git_head(root),
        "extension": extension,
        "dsl": dsl,
        "core_tree_sha256_before": before,
        "core_tree_sha256_after": after,
        "core_code_unchanged": before == after,
        "compile_passed": compiled.backend["validation_passed"]
        and compiled.backend["safety_passed"],
        "selected_strategy": compiled.physical["selected_strategy"],
        "sql": compiled.backend["sql"],
        "gate": {"passed": before == after and compiled.backend["safety_passed"]},
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.report_output.write_text(_markdown(report), encoding="utf-8")
    if not report["gate"]["passed"]:
        raise SystemExit(1)


def _core_tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def _markdown(report) -> str:
    return "\n".join(
        [
            "# 声明式新函数盲扩展证据",
            "",
            f"- Git HEAD：`{report['git_head']}`",
            f"- 新函数：`{report['extension']['name']}`",
            f"- 核心代码哈希（扩展前）：`{report['core_tree_sha256_before']}`",
            f"- 核心代码哈希（扩展后）：`{report['core_tree_sha256_after']}`",
            f"- 核心代码未修改：`{report['core_code_unchanged']}`",
            f"- 编译与 SQL 安全校验：`{report['compile_passed']}`",
            f"- Gate：`{'PASS' if report['gate']['passed'] else 'FAIL'}`",
            "",
            "## 演示 DSL",
            "",
            f"```text\n{report['dsl']}\n```",
            "",
            "## 生成 SQL",
            "",
            f"```sql\n{report['sql']}\n```",
            "",
        ]
    )


if __name__ == "__main__":
    main()

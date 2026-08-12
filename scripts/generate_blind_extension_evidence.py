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
from findsl.official.physical.catalog import PhysicalCatalog
from findsl.official.pipeline import OfficialPipelineError, compile_official


EXPECTED_CHANGED_CONFIGS = {
    "official/functions.json",
    "official/indicators.json",
    "official/physical_catalog.json",
    "official/physical_statistics.json",
    "official/physical_strategies.json",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Prove config-only indicator and function extension without "
            "modifying core compiler code"
        )
    )
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    before = _core_tree_hash(root / "src/findsl/official")
    with tempfile.TemporaryDirectory(prefix="findsl-blind-extension-") as temporary:
        sandbox = Path(temporary)
        shutil.copytree(root / "configs", sandbox / "configs")
        config_root = sandbox / "configs"
        config_before = _tree_hashes(config_root)

        function_path = config_root / "official/functions.json"
        functions = json.loads(function_path.read_text(encoding="utf-8"))
        function_extension = {
            "name": "blind_demo_in_band",
            "aliases": [],
            "argument_mode": "expressions",
            "arg_types": ["numeric", "numeric", "numeric"],
            "result_kind": "boolean",
            "expression_template": {
                "op": "and",
                "args": [
                    {
                        "op": "greater_equal",
                        "args": [{"arg": 0}, {"arg": 1}],
                    },
                    {
                        "op": "less_equal",
                        "args": [{"arg": 0}, {"arg": 2}],
                    },
                ],
            },
            "version": "blind-demo-v2",
        }
        functions["functions"].append(function_extension)
        _write_json(function_path, functions)

        indicator_path = config_root / "official/indicators.json"
        indicators = json.loads(indicator_path.read_text(encoding="utf-8"))
        source_indicator = next(
            item for item in indicators if item["canonical_name"] == "成交量"
        )
        indicator_extension = dict(source_indicator)
        indicator_extension.update(
            {
                "canonical_name": "盲扩展成交量",
                "aliases": ["blind_extension_volume"],
            }
        )
        indicators.append(indicator_extension)
        _write_json(indicator_path, indicators)

        catalog_path = config_root / "official/physical_catalog.json"
        catalog_payload = json.loads(catalog_path.read_text(encoding="utf-8"))
        source_field = next(
            item
            for item in catalog_payload["fields"]
            if item["indicator_id"] == "成交量"
        )
        field_extension = dict(source_field)
        field_extension["indicator_id"] = "盲扩展成交量"
        catalog_payload["fields"].append(field_extension)
        _write_json(catalog_path, catalog_payload)

        catalog_fingerprint = PhysicalCatalog.load(catalog_path).fingerprint
        for filename in ("physical_statistics.json", "physical_strategies.json"):
            path = config_root / "official" / filename
            runtime_payload = json.loads(path.read_text(encoding="utf-8"))
            runtime_payload["catalog_sha256"] = catalog_fingerprint
            _write_json(path, runtime_payload)

        config_after = _tree_hashes(config_root)
        changed_configs = sorted(
            path
            for path in set(config_before) | set(config_after)
            if config_before.get(path) != config_after.get(path)
        )
        context = CompileContext.load(sandbox)
        dsl = (
            "blind_demo_in_band("
            "indicator('', '', '盲扩展成交量', '今日', '', '', ''), "
            "1000000, 100000000) = True"
        )
        compiled = compile_official(dsl, context=context)
        type_guard_code = None
        try:
            compile_official(
                "blind_demo_in_band('invalid', 1, 2) = True",
                context=context,
            )
        except OfficialPipelineError as exc:
            type_guard_code = exc.code

    after = _core_tree_hash(root / "src/findsl/official")
    typed_binding = compiled.typed_ast["children"][0]["binding"]
    config_only = set(changed_configs) == EXPECTED_CHANGED_CONFIGS
    compile_passed = (
        compiled.backend["validation_passed"]
        and compiled.backend["safety_passed"]
    )
    report = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "git_head": _git_head(root),
        "function_extension": function_extension,
        "indicator_extension": indicator_extension,
        "physical_field_extension": field_extension,
        "dsl": dsl,
        "catalog_fingerprint": catalog_fingerprint,
        "changed_config_files": changed_configs,
        "expected_changed_config_files": sorted(EXPECTED_CHANGED_CONFIGS),
        "only_declared_configs_changed": config_only,
        "core_tree_sha256_before": before,
        "core_tree_sha256_after": after,
        "core_code_unchanged": before == after,
        "compile_passed": compile_passed,
        "typed_template_kind": typed_binding["template_kind"],
        "type_guard_error_code": type_guard_code,
        "type_guard_passed": type_guard_code == "OFFICIAL_FUNCTION_ARG_TYPE",
        "selected_strategy": compiled.physical["selected_strategy"],
        "sql": compiled.backend["sql"],
        "gate": {
            "passed": (
                before == after
                and config_only
                and compile_passed
                and type_guard_code == "OFFICIAL_FUNCTION_ARG_TYPE"
            )
        },
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    _write_json(args.json_output, report)
    args.report_output.write_text(_markdown(report), encoding="utf-8")
    if not report["gate"]["passed"]:
        raise SystemExit(1)


def _write_json(path: Path, payload) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


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


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def _markdown(report) -> str:
    return "\n".join(
        [
            "# 声明式指标与函数复合盲扩展证据",
            "",
            f"- Git HEAD：`{report['git_head']}`",
            f"- 新指标：`{report['indicator_extension']['canonical_name']}`",
            f"- 新函数：`{report['function_extension']['name']}`",
            f"- 仅声明配置发生变化：`{report['only_declared_configs_changed']}`",
            f"- 变更配置：`{', '.join(report['changed_config_files'])}`",
            f"- 核心代码哈希（扩展前）：`{report['core_tree_sha256_before']}`",
            f"- 核心代码哈希（扩展后）：`{report['core_tree_sha256_after']}`",
            f"- 核心代码未修改：`{report['core_code_unchanged']}`",
            f"- 类型错误拦截：`{report['type_guard_passed']}`（`{report['type_guard_error_code']}`）",
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

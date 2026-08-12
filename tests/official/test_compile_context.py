from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from findsl.official.context import CatalogSnapshot, CompileContext, CompileContextError
from findsl.official.physical.runtime import (
    current_numeric_approximation_policy,
    use_physical_runtime,
)
from findsl.official.pipeline import compile_official


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = "indicator('沪|深', '', '成交量', '今日', '', '', '') > 100 limit 0,20"


def test_compile_context_freezes_every_manifest_catalog() -> None:
    context = CompileContext.load(REPO_ROOT)

    assert context.snapshot.profile_id == "competition-v1"
    assert context.snapshot.policy_id == "official-semantic-policy-v1"
    assert len(context.snapshot.files) == 15
    assert len(context.context_id) == 64
    context.assert_current()


def test_compile_context_uses_explicit_runtime_root(monkeypatch) -> None:
    monkeypatch.setenv("FINDSL_REPO_ROOT", str(REPO_ROOT))

    context = CompileContext.load()

    assert context.snapshot.repo_root == REPO_ROOT.resolve()


def test_pipeline_exposes_versioned_reproducible_plan_id() -> None:
    context = CompileContext.load(REPO_ROOT)

    first = compile_official(SOURCE, context=context).to_dict()
    second = compile_official(SOURCE, context=context).to_dict()

    assert first["physical"]["physical_node_id"] == second["physical"]["physical_node_id"]
    assert first["physical"]["plan_id"] == second["physical"]["plan_id"]
    assert first["physical"]["plan_id"] != first["physical"]["physical_node_id"]
    assert first["physical"]["catalog_snapshot_id"] == context.context_id
    assert first["physical"]["policy_id"] == "official-semantic-policy-v1"
    assert first["compile_context"]["context_id"] == context.context_id


def test_catalog_snapshot_detects_mid_lifetime_config_change(tmp_path: Path) -> None:
    _copy_compiler_configs(tmp_path)
    snapshot = CatalogSnapshot.capture(tmp_path)
    policy_path = tmp_path / "configs/official/approximation_policy.json"
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    payload["version"] = "changed-after-capture"
    policy_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(CompileContextError, match="changed during"):
        snapshot.assert_current()


def test_catalog_snapshot_hot_check_avoids_rehash_when_file_metadata_is_stable(
    monkeypatch,
) -> None:
    snapshot = CatalogSnapshot.capture(REPO_ROOT)

    def unexpected_capture(*args, **kwargs):
        raise AssertionError("stable catalog metadata must not trigger a full rehash")

    monkeypatch.setattr(CatalogSnapshot, "capture", unexpected_capture)

    snapshot.assert_current()


def test_physical_runtime_is_request_scoped_and_restored() -> None:
    context = CompileContext.load(REPO_ROOT)
    default_version = current_numeric_approximation_policy().version

    with use_physical_runtime(context.physical_runtime):
        assert current_numeric_approximation_policy() is context.physical_runtime.approximation_policy

    assert current_numeric_approximation_policy().version == default_version


def test_manifest_rejects_paths_outside_repository(tmp_path: Path) -> None:
    _copy_compiler_configs(tmp_path)
    manifest_path = tmp_path / "configs/official/compiler_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["entries"][0]["path"] = "../outside.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(CompileContextError, match="outside repository"):
        CatalogSnapshot.capture(tmp_path)


def _copy_compiler_configs(target: Path) -> None:
    shutil.copytree(REPO_ROOT / "configs", target / "configs")

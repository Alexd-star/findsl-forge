from pathlib import Path

from findsl.versioning import resolve_release_head


def test_resolve_release_head_uses_archive_marker_without_git(tmp_path: Path):
    expected = "a" * 40
    (tmp_path / "RELEASE_COMMIT.txt").write_text(expected + "\n", encoding="utf-8")

    assert resolve_release_head(tmp_path) == expected

from pathlib import Path

from conftest import external_file_available


def test_external_file_probe_treats_platform_path_errors_as_unavailable(monkeypatch):
    def fail_for_foreign_path(_path):
        raise OSError(36, "file name too long")

    monkeypatch.setattr(Path, "is_file", fail_for_foreign_path)

    assert external_file_available(r"D:\external\official.xlsx") is False

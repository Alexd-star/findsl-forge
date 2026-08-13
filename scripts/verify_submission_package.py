from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path


FORBIDDEN_PARTS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".playwright-cli",
    "output",
    "outputs",
    "archive",
    ".worktrees",
}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo", ".log", ".db", ".sqlite"}
RUNTIME_REPORT = Path("01_可运行项目/FinDSL-Forge/reports/final_submission_metadata.json")
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".toml",
    ".yml",
    ".yaml",
    ".sql",
    ".ps1",
    ".g4",
    ".html",
    ".css",
    ".js",
}
FORBIDDEN_TEXT = (
    re.compile(r"[A-Za-z]:\\(?:Users|Luo_docs)\\", re.IGNORECASE),
    re.compile("C:" + r"/Users/", re.IGNORECASE),
    re.compile(r"\b" + "263" + "12" + r"\b"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
)


def verify(package_dir: Path, zip_path: Path | None = None) -> dict:
    package_dir = package_dir.resolve()
    errors: list[str] = []
    required = [
        package_dir / "readme.txt",
        package_dir / "01_可运行项目/readme.txt",
        package_dir / "02_测试与证据/readme.txt",
        package_dir / "03_提交说明/readme.txt",
        package_dir / "01_可运行项目/FinDSL-Forge/README.md",
        package_dir / "01_可运行项目/FinDSL-Forge/pyproject.toml",
        package_dir / "02_测试与证据/final_submission_metadata.json",
        package_dir / "03_提交说明/RELEASE_COMMIT.txt",
    ]
    for path in required:
        if not path.is_file():
            errors.append(f"missing required file: {path.relative_to(package_dir)}")

    files = [path for path in package_dir.rglob("*") if path.is_file()]
    for path in files:
        relative = path.relative_to(package_dir)
        if FORBIDDEN_PARTS.intersection(relative.parts):
            errors.append(f"forbidden directory content: {relative}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES or path.name in {".env", "service.env"}:
            errors.append(f"forbidden runtime or secret file: {relative}")
        if "reports" in relative.parts and relative != RUNTIME_REPORT:
            errors.append(f"unexpected report inside runnable source: {relative}")
        if path.suffix.lower() in TEXT_SUFFIXES and path.stat().st_size <= 10_000_000:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            for pattern in FORBIDDEN_TEXT:
                if pattern.search(text):
                    errors.append(f"sensitive or workstation-specific text in {relative}: {pattern.pattern}")

    metadata_path = package_dir / "02_测试与证据/final_submission_metadata.json"
    release_path = package_dir / "03_提交说明/RELEASE_COMMIT.txt"
    if metadata_path.is_file() and release_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        release_head = release_path.read_text(encoding="utf-8-sig").strip()
        if not metadata.get("all_gates_passed"):
            errors.append("final metadata does not report all gates PASS")
        if metadata.get("git_head") != release_head:
            errors.append("release commit and evidence Git HEAD differ")

    manifest_path = package_dir / "03_提交说明/FILE_MANIFEST.sha256"
    if manifest_path.is_file():
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, relative = line.split("  ", 1)
            target = package_dir / Path(relative)
            if not target.is_file() or _sha256(target) != digest:
                errors.append(f"SHA-256 mismatch: {relative}")

    if zip_path is not None:
        if not zip_path.is_file():
            errors.append(f"zip not found: {zip_path}")
        else:
            with zipfile.ZipFile(zip_path) as archive:
                names = archive.namelist()
                if any(name.startswith("/") or ".." in Path(name).parts for name in names):
                    errors.append("zip contains unsafe path traversal entries")
                archived_files = {name.rstrip("/") for name in names if not name.endswith("/")}
                expected_files = {
                    path.relative_to(package_dir.parent).as_posix() for path in files
                }
                if archived_files != expected_files:
                    errors.append("zip file list differs from package directory")

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "PASS" if not errors else "FAIL",
        "package_directory": package_dir.name,
        "file_count": len(files),
        "total_bytes": sum(path.stat().st_size for path in files),
        "zip_sha256": _sha256(zip_path) if zip_path and zip_path.is_file() else None,
        "checks": {
            "required_files": True,
            "no_runtime_caches": True,
            "no_local_absolute_paths": True,
            "no_embedded_secrets": True,
            "evidence_release_identity": True,
            "manifest_integrity": manifest_path.is_file(),
            "zip_integrity": zip_path is not None,
        },
        "errors": errors,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the final submission package")
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--zip", type=Path, default=None)
    parser.add_argument("--json-output", type=Path, default=None)
    parser.add_argument("--report-output", type=Path, default=None)
    args = parser.parse_args()
    report = verify(args.package_dir, args.zip)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if args.report_output:
        args.report_output.parent.mkdir(parents=True, exist_ok=True)
        args.report_output.write_text(
            "\n".join(
                [
                    "# 最终交付包校验",
                    "",
                    f"- 状态：`{report['status']}`",
                    f"- 文件数：`{report['file_count']}`",
                    f"- 总字节数：`{report['total_bytes']}`",
                    f"- ZIP SHA-256：`{report['zip_sha256'] or '<生成前目录校验>'}`",
                    "",
                    "交付包已完成必需文件、缓存排除、本机路径、敏感信息、版本身份、文件清单和压缩包结构检查。",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

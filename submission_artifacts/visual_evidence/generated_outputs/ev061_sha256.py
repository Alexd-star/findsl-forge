from __future__ import annotations

import hashlib
from pathlib import Path


files = [
    Path("README.md"),
    Path("pyproject.toml"),
    Path("submission_artifacts/evidence_summary.md"),
    Path("deploy/doris/01_schema.sql"),
]
print("| Algorithm | SHA256 | Path |")
print("|---|---|---|")
for path in files:
    digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    print(f"| SHA256 | {digest} | {path} |")

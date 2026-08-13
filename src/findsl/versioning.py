from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_release_head(root: Path = PROJECT_ROOT) -> str:
    configured = os.environ.get("FINDSL_RELEASE_HEAD", "").strip()
    if configured:
        return configured

    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed.returncode == 0 and completed.stdout.strip():
        return completed.stdout.strip()

    marker = root / "RELEASE_COMMIT.txt"
    if marker.is_file() and marker.read_text(encoding="utf-8-sig").strip():
        return marker.read_text(encoding="utf-8-sig").strip()

    metadata = root / "reports/final_submission_metadata.json"
    if metadata.is_file():
        payload = json.loads(metadata.read_text(encoding="utf-8-sig"))
        if str(payload.get("git_head", "")).strip():
            return str(payload["git_head"]).strip()

    raise RuntimeError("release Git HEAD is unavailable")

from __future__ import annotations

import os
from pathlib import Path


OFFICIAL_WORKBOOK = os.environ.get(
    "FINDSL_OFFICIAL_WORKBOOK",
    "",
)


def external_file_available(path: str) -> bool:
    try:
        return Path(path).is_file()
    except (OSError, ValueError):
        return False

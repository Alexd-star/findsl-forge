from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


class PhysicalPatternConfigError(ValueError):
    pass


@dataclass(frozen=True)
class PhysicalPatternConfig:
    close_together_relative_threshold: float
    reset_near_line_threshold: float
    reset_below_line_tolerance: float
    version: str

    @classmethod
    def load(cls, path: Path) -> "PhysicalPatternConfig":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        try:
            close = float(raw["close_together"]["relative_threshold"])
            near = float(raw["reset"]["near_line_threshold"])
            below = float(raw["reset"]["below_line_tolerance"])
            version = str(raw["version"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PhysicalPatternConfigError("invalid physical technical-pattern config") from exc
        if not version or not 0 < close < 1 or not 0 < near < 1 or not 0 <= below < 1:
            raise PhysicalPatternConfigError("physical technical-pattern thresholds are out of range")
        return cls(close, near, below, version)


@lru_cache(maxsize=1)
def default_physical_pattern_config() -> PhysicalPatternConfig:
    root = Path(__file__).resolve().parents[4]
    return PhysicalPatternConfig.load(
        root / "configs" / "official_technical_patterns.json"
    )

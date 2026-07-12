from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


class ApproximationPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class NumericApproximationPolicy:
    relative_tolerance: float
    absolute_tolerance: float
    version: str

    @classmethod
    def load(cls, path: Path) -> "NumericApproximationPolicy":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if raw.get("schema_version") != 1:
            raise ApproximationPolicyError("approximation policy requires schema_version=1")
        try:
            relative = float(raw["numeric"]["relative_tolerance"])
            absolute = float(raw["numeric"]["absolute_tolerance"])
            version = str(raw["version"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ApproximationPolicyError("invalid numeric approximation policy") from exc
        if not version or not 0 < relative < 1 or not 0 <= absolute < 1:
            raise ApproximationPolicyError("numeric approximation tolerances are out of range")
        return cls(relative, absolute, version)


@lru_cache(maxsize=1)
def default_numeric_approximation_policy() -> NumericApproximationPolicy:
    root = Path(__file__).resolve().parents[4]
    return NumericApproximationPolicy.load(
        root / "configs" / "official" / "approximation_policy.json"
    )

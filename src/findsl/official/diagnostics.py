from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Union


@dataclass(frozen=True)
class SourceRepair:
    code: str
    message: str
    position: int

    def to_dict(self) -> Dict[str, Union[str, int]]:
        return asdict(self)

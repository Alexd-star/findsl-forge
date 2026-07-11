from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


class CanonicalIr:
    def to_dict(self) -> Dict[str, Any]:
        raise NotImplementedError

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @property
    def node_id(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()[:16]

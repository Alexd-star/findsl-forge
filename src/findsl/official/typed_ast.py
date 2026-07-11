from __future__ import annotations

import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple

from .ast import OfficialNode
from .signatures import FunctionSignature
from .types import OfficialType


@dataclass(frozen=True)
class FunctionBinding:
    signature: FunctionSignature
    slots: Mapping[str, str]

    @classmethod
    def create(cls, signature: FunctionSignature, slots: Mapping[str, str]) -> "FunctionBinding":
        return cls(signature, MappingProxyType(dict(slots)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.signature.name,
            "arity": self.signature.arity,
            "slots": {name: self.slots[name] for name in self.signature.slots},
        }


@dataclass(frozen=True)
class TypedNode:
    node: OfficialNode
    type: OfficialType
    children: Tuple["TypedNode", ...] = ()
    binding: Optional[FunctionBinding] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node": self.node.to_dict(),
            "type": self.type.to_dict(),
            "children": [child.to_dict() for child in self.children],
            "binding": self.binding.to_dict() if self.binding else None,
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

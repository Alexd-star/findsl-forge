from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Tuple

from ..ir.relational import LogicalPlan


class Rule(Protocol):
    rule_id: str
    version: str
    proof_obligation: str

    def apply(self, plan: LogicalPlan) -> LogicalPlan:
        ...


@dataclass(frozen=True)
class RewriteEvent:
    rule_id: str
    version: str
    before_hash: str
    after_hash: str
    node_path: str
    elapsed_ns: int
    proof_obligation: str

    def to_dict(self):
        return self.__dict__.copy()


@dataclass(frozen=True)
class OptimizedPlan:
    plan: LogicalPlan
    trace: Tuple[RewriteEvent, ...]
    diagnostics: Tuple[str, ...] = ()

    def to_dict(self):
        return {"plan": self.plan.to_dict(), "plan_id": self.plan.node_id, "trace": [item.to_dict() for item in self.trace], "diagnostics": list(self.diagnostics)}

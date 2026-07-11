from __future__ import annotations

from time import perf_counter_ns
from typing import Iterable

from ..ir.validate import validate_plan
from .base import OptimizedPlan, RewriteEvent


class Optimizer:
    def __init__(self, rules: Iterable, *, max_passes: int = 4):
        self.rules = tuple(rules)
        self.max_passes = max_passes

    def optimize(self, plan) -> OptimizedPlan:
        original = plan
        current = plan
        events = []
        try:
            validate_plan(current)
            for _ in range(self.max_passes):
                pass_changed = False
                for rule in self.rules:
                    before = current.node_id
                    started = perf_counter_ns()
                    candidate = rule.apply(current)
                    elapsed = perf_counter_ns() - started
                    after = candidate.node_id
                    if before != after:
                        validate_plan(candidate)
                        events.append(RewriteEvent(rule.rule_id, rule.version, before, after, "$", elapsed, rule.proof_obligation))
                        current = candidate
                        pass_changed = True
                if not pass_changed:
                    break
            return OptimizedPlan(current, tuple(events))
        except Exception as exc:
            return OptimizedPlan(original, (), (f"{type(exc).__name__}: {exc}",))

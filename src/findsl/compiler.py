from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List

from .parser import parse
from .registry import Registry, default_registry
from .semantic import SemanticAnalyzer
from .sqlgen import SqlGenerator


@dataclass(frozen=True)
class CompileResult:
    dsl: str
    ast: Dict[str, Any]
    sql: str
    trace: List[str]
    elapsed_ms: float


class Compiler:
    def __init__(self, registry: Registry = None, enable_prefix_sum: bool = True):
        self.registry = registry or default_registry()
        self.enable_prefix_sum = enable_prefix_sum

    def compile(self, dsl: str, enable_prefix_sum: bool = None) -> CompileResult:
        started = time.perf_counter()
        ast = parse(dsl)
        SemanticAnalyzer(self.registry).validate(ast)
        use_prefix_sum = self.enable_prefix_sum if enable_prefix_sum is None else enable_prefix_sum
        plan = SqlGenerator(self.registry, enable_prefix_sum=use_prefix_sum).generate(ast)
        elapsed_ms = (time.perf_counter() - started) * 1000
        return CompileResult(
            dsl=dsl,
            ast=ast.to_dict(),
            sql=plan.sql,
            trace=plan.trace,
            elapsed_ms=elapsed_ms,
        )

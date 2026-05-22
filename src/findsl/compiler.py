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
    def __init__(self, registry: Registry = None):
        self.registry = registry or default_registry()

    def compile(self, dsl: str) -> CompileResult:
        started = time.perf_counter()
        ast = parse(dsl)
        SemanticAnalyzer(self.registry).validate(ast)
        plan = SqlGenerator(self.registry).generate(ast)
        elapsed_ms = (time.perf_counter() - started) * 1000
        return CompileResult(
            dsl=dsl,
            ast=ast.to_dict(),
            sql=plan.sql,
            trace=plan.trace,
            elapsed_ms=elapsed_ms,
        )


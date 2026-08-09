from __future__ import annotations

import hashlib
import json
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Dict, Mapping, Optional

from .backend.executor import DorisExecutionConfig, execute_doris_query
from .context import CompileContext, default_compile_context
from .pipeline import (
    OfficialPipelineError,
    OfficialPipelineOptions,
    compile_official,
)


class OfficialServiceError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class ServiceLimits:
    max_dsl_chars: int = 16_384
    max_result_rows: int = 10_000
    max_doris_timeout_seconds: float = 10.0

    def __post_init__(self):
        if self.max_dsl_chars <= 0 or self.max_result_rows <= 0:
            raise ValueError("service limits must be positive")
        if not 0 < self.max_doris_timeout_seconds <= 60:
            raise ValueError("Doris timeout must be between 0 and 60 seconds")


class ServiceMetrics:
    def __init__(self):
        self._lock = threading.Lock()
        self._counters: Dict[tuple[str, str], int] = {}
        self._durations: Dict[str, list[float]] = {}

    def record(self, operation: str, status: str, elapsed_ms: float) -> None:
        with self._lock:
            key = (operation, status)
            self._counters[key] = self._counters.get(key, 0) + 1
            values = self._durations.setdefault(operation, [])
            values.append(float(elapsed_ms))
            if len(values) > 2048:
                del values[: len(values) - 2048]

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            counters = {
                f"{operation}:{status}": value
                for (operation, status), value in sorted(self._counters.items())
            }
            durations = {
                operation: _duration_summary(values)
                for operation, values in sorted(self._durations.items())
            }
        return {"counters": counters, "durations_ms": durations}

    def prometheus(self) -> str:
        snapshot = self.snapshot()
        lines = [
            "# HELP findsl_requests_total FinDSL service requests.",
            "# TYPE findsl_requests_total counter",
        ]
        for key, value in snapshot["counters"].items():
            operation, status = key.split(":", 1)
            lines.append(
                f'findsl_requests_total{{operation="{operation}",status="{status}"}} {value}'
            )
        lines.extend(
            [
                "# HELP findsl_request_duration_ms FinDSL recent request latency.",
                "# TYPE findsl_request_duration_ms gauge",
            ]
        )
        for operation, summary in snapshot["durations_ms"].items():
            for statistic in ("count", "p50", "p95", "p99", "max"):
                lines.append(
                    "findsl_request_duration_ms"
                    f'{{operation="{operation}",stat="{statistic}"}} '
                    f"{summary[statistic]}"
                )
        return "\n".join(lines) + "\n"


class JsonlAuditSink:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path).resolve() if path else None
        self._lock = threading.Lock()

    def write(self, event: Mapping[str, Any]) -> None:
        if self.path is None:
            return
        payload = json.dumps(dict(event), ensure_ascii=False, sort_keys=True)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(payload + "\n")


class OfficialCompilerService:
    def __init__(
        self,
        *,
        context: CompileContext | None = None,
        limits: ServiceLimits = ServiceLimits(),
        metrics: ServiceMetrics | None = None,
        audit_sink: JsonlAuditSink | None = None,
        executor: Callable = execute_doris_query,
    ):
        self.context = context or default_compile_context()
        self.limits = limits
        self.metrics = metrics or ServiceMetrics()
        self.audit_sink = audit_sink or JsonlAuditSink()
        self.executor = executor

    def health(self) -> Dict[str, Any]:
        try:
            self.context.assert_current()
            status = "ready"
            ready = True
            detail = "compiler context is current"
        except Exception as exc:  # noqa: BLE001 - health must report context failures.
            status = "not_ready"
            ready = False
            detail = str(exc)
        return {
            "status": status,
            "ready": ready,
            "detail": detail,
            "context_id": self.context.context_id,
            "policy_id": self.context.snapshot.policy_id,
            "profile_id": self.context.snapshot.profile_id,
        }

    def compile(
        self,
        dsl: str,
        *,
        options: OfficialPipelineOptions = OfficialPipelineOptions(),
        request_id: str | None = None,
        principal: str = "local",
    ) -> Dict[str, Any]:
        request_id = request_id or uuid.uuid4().hex
        normalized = self._validate_dsl(dsl)
        started = perf_counter()
        try:
            result = compile_official(normalized, options=options, context=self.context)
        except OfficialPipelineError as exc:
            elapsed_ms = (perf_counter() - started) * 1000.0
            self.metrics.record("compile", "rejected", elapsed_ms)
            self._audit(
                request_id,
                principal,
                "compile",
                "rejected",
                normalized,
                elapsed_ms,
                code=exc.code,
            )
            raise OfficialServiceError(
                exc.code,
                str(exc),
                status_code=422,
            ) from exc
        elapsed_ms = (perf_counter() - started) * 1000.0
        self.metrics.record("compile", "ok", elapsed_ms)
        self._audit(
            request_id,
            principal,
            "compile",
            "ok",
            normalized,
            elapsed_ms,
            plan_id=result.physical["plan_id"],
        )
        return {
            "request_id": request_id,
            "generated_at": _utc_now(),
            "result": result.to_dict(),
        }

    def execute(
        self,
        dsl: str,
        *,
        doris: DorisExecutionConfig,
        options: OfficialPipelineOptions = OfficialPipelineOptions(),
        request_id: str | None = None,
        principal: str = "local",
    ) -> Dict[str, Any]:
        request_id = request_id or uuid.uuid4().hex
        if options.strategy_mode == "force_candidate":
            raise OfficialServiceError(
                "UNSAFE_STRATEGY_MODE",
                "force_candidate is restricted to compile-time validation",
                status_code=422,
            )
        compiled = self.compile(
            dsl,
            options=options,
            request_id=request_id,
            principal=principal,
        )
        sql = compiled["result"]["backend"]["sql"]
        limited_sql = _limit_result(sql, self.limits.max_result_rows + 1)
        bounded_doris = DorisExecutionConfig(
            doris.host,
            doris.port,
            doris.user,
            doris.password,
            doris.database,
            doris.mysql_executable,
            min(doris.timeout_seconds, self.limits.max_doris_timeout_seconds),
        )
        started = perf_counter()
        try:
            execution = self.executor(bounded_doris, limited_sql)
        except Exception as exc:  # noqa: BLE001 - external execution errors are normalized.
            elapsed_ms = (perf_counter() - started) * 1000.0
            self.metrics.record("execute", "error", elapsed_ms)
            self._audit(
                request_id,
                principal,
                "execute",
                "error",
                dsl,
                elapsed_ms,
                code=type(exc).__name__,
                error_sha256=hashlib.sha256(str(exc).encode("utf-8")).hexdigest(),
            )
            raise OfficialServiceError(
                "DORIS_EXECUTION_FAILED",
                "Doris execution failed",
                status_code=503,
            ) from exc
        elapsed_ms = (perf_counter() - started) * 1000.0
        truncated = len(execution.rows) > self.limits.max_result_rows
        rows = execution.rows[: self.limits.max_result_rows]
        self.metrics.record("execute", "ok", elapsed_ms)
        self._audit(
            request_id,
            principal,
            "execute",
            "ok",
            dsl,
            elapsed_ms,
            plan_id=compiled["result"]["physical"]["plan_id"],
            row_count=len(rows),
            truncated=truncated,
        )
        return {
            **compiled,
            "execution": {
                "rows": [list(row) for row in rows],
                "row_count": len(rows),
                "truncated": truncated,
                "elapsed_ms": execution.elapsed_ms,
                "ordered_hash": execution.ordered_hash if not truncated else None,
                "unordered_hash": execution.unordered_hash if not truncated else None,
                "timeout_seconds": bounded_doris.timeout_seconds,
            },
        }

    def _validate_dsl(self, dsl: str) -> str:
        normalized = str(dsl or "").strip()
        if not normalized:
            raise OfficialServiceError("DSL_REQUIRED", "DSL must not be empty")
        if len(normalized) > self.limits.max_dsl_chars:
            raise OfficialServiceError(
                "DSL_TOO_LARGE",
                f"DSL exceeds {self.limits.max_dsl_chars} characters",
                status_code=413,
            )
        if "\x00" in normalized:
            raise OfficialServiceError("DSL_INVALID_CHARACTER", "DSL contains a null character")
        return normalized

    def _audit(
        self,
        request_id: str,
        principal: str,
        operation: str,
        status: str,
        dsl: str,
        elapsed_ms: float,
        **details,
    ) -> None:
        self.audit_sink.write(
            {
                "timestamp": _utc_now(),
                "request_id": request_id,
                "principal": principal,
                "operation": operation,
                "status": status,
                "elapsed_ms": round(elapsed_ms, 6),
                "dsl_sha256": hashlib.sha256(str(dsl).encode("utf-8")).hexdigest(),
                "dsl_chars": len(str(dsl)),
                "context_id": self.context.context_id,
                **details,
            }
        )


def _limit_result(sql: str, count: int) -> str:
    return (
        "SELECT * FROM (\n"
        f"{sql.rstrip(';')}\n"
        ") AS service_result\n"
        f"LIMIT {int(count)}"
    )


def _duration_summary(values):
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "p50": round(_percentile(ordered, 0.50), 6),
        "p95": round(_percentile(ordered, 0.95), 6),
        "p99": round(_percentile(ordered, 0.99), 6),
        "max": round(ordered[-1], 6),
    }


def _percentile(ordered, fraction: float) -> float:
    index = min(len(ordered) - 1, max(0, int(len(ordered) * fraction + 0.999999) - 1))
    return float(ordered[index])


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

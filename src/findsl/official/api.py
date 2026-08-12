from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, Literal, Optional

from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from .backend.executor import DorisExecutionConfig
from .pipeline import OfficialPipelineOptions
from .service import (
    JsonlAuditSink,
    OfficialCompilerService,
    OfficialServiceError,
    ServiceLimits,
)


@dataclass(frozen=True)
class ApiSettings:
    environment: str = "development"
    api_key: str = ""
    jwt_secret: str = ""
    jwt_issuer: str = "findsl-forge"
    jwt_audience: str = "findsl-api"
    max_concurrency: int = 8
    queue_timeout_seconds: float = 1.0
    requests_per_minute: int = 120
    enable_execute: bool = False
    audit_log_path: Optional[Path] = None
    doris: Optional[DorisExecutionConfig] = None

    def __post_init__(self):
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("environment must be development, test, or production")
        if self.environment == "production" and not (self.api_key or self.jwt_secret):
            raise ValueError("production API requires an API key or JWT secret")
        if self.environment == "production" and self.api_key and len(self.api_key) < 32:
            raise ValueError("production API key must contain at least 32 characters")
        if self.environment == "production" and self.jwt_secret and len(self.jwt_secret) < 32:
            raise ValueError("production JWT secret must contain at least 32 characters")
        if self.max_concurrency <= 0 or self.requests_per_minute <= 0:
            raise ValueError("API concurrency and rate limits must be positive")
        if self.queue_timeout_seconds <= 0:
            raise ValueError("API queue timeout must be positive")

    @classmethod
    def from_env(cls) -> "ApiSettings":
        environment = os.getenv("FINDSL_ENV", "development").strip().lower()
        enable_execute = _env_bool("FINDSL_ENABLE_EXECUTE", False)
        doris = None
        if enable_execute:
            doris = DorisExecutionConfig(
                os.getenv("FINDSL_DORIS_HOST", "127.0.0.1"),
                _env_int("FINDSL_DORIS_PORT", 9030),
                os.getenv("FINDSL_DORIS_USER", "findsl_readonly"),
                os.getenv("FINDSL_DORIS_PASSWORD", ""),
                os.getenv("FINDSL_DORIS_DATABASE", "newzl"),
                os.getenv("FINDSL_MYSQL_CLIENT", "mysql"),
                _env_float("FINDSL_DORIS_TIMEOUT_SECONDS", 10.0),
            )
        audit = os.getenv("FINDSL_AUDIT_LOG", "").strip()
        return cls(
            environment=environment,
            api_key=os.getenv("FINDSL_API_KEY", ""),
            jwt_secret=os.getenv("FINDSL_JWT_SECRET", ""),
            jwt_issuer=os.getenv("FINDSL_JWT_ISSUER", "findsl-forge"),
            jwt_audience=os.getenv("FINDSL_JWT_AUDIENCE", "findsl-api"),
            max_concurrency=_env_int("FINDSL_MAX_CONCURRENCY", 8),
            queue_timeout_seconds=_env_float("FINDSL_QUEUE_TIMEOUT_SECONDS", 1.0),
            requests_per_minute=_env_int("FINDSL_REQUESTS_PER_MINUTE", 120),
            enable_execute=enable_execute,
            audit_log_path=Path(audit) if audit else None,
            doris=doris,
        )


class CompileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dsl: str = Field(min_length=1)
    strategy_mode: Literal["auto", "force_baseline", "force_candidate"] = "auto"
    use_statistics: bool = True


class ExecuteRequest(CompileRequest):
    pass


class _RateLimiter:
    def __init__(self, requests_per_minute: int):
        self.limit = requests_per_minute
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, principal: str) -> bool:
        now = time.monotonic()
        cutoff = now - 60.0
        with self._lock:
            events = self._events[principal]
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True


def create_app(
    *,
    service: OfficialCompilerService | None = None,
    settings: ApiSettings | None = None,
) -> FastAPI:
    settings = settings or ApiSettings.from_env()
    service = service or OfficialCompilerService(
        limits=ServiceLimits(
            max_doris_timeout_seconds=(
                settings.doris.timeout_seconds if settings.doris else 10.0
            )
        ),
        audit_sink=JsonlAuditSink(settings.audit_log_path),
    )
    app = FastAPI(
        title="FinDSL Forge API",
        version="1.0.0",
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
    )
    app.state.service = service
    app.state.settings = settings
    semaphore = asyncio.Semaphore(settings.max_concurrency)
    limiter = _RateLimiter(settings.requests_per_minute)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", "").strip() or uuid.uuid4().hex
        if len(request_id) > 128:
            request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Server-Timing"] = (
            f"app;dur={(time.perf_counter() - started) * 1000.0:.3f}"
        )
        return response

    @app.exception_handler(OfficialServiceError)
    async def service_error_handler(request: Request, exc: OfficialServiceError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "ok": False,
                "request_id": request.state.request_id,
                "error": {"code": exc.code, "message": str(exc)},
            },
            headers=(
                {"WWW-Authenticate": "Bearer"}
                if exc.status_code == 401
                else ({"Retry-After": "1"} if exc.status_code == 429 else None)
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        issues = [
            {
                "location": [str(item) for item in error.get("loc", ())],
                "message": error.get("msg", "invalid request"),
                "type": error.get("type", "validation_error"),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "ok": False,
                "request_id": request.state.request_id,
                "error": {
                    "code": "REQUEST_VALIDATION_ERROR",
                    "message": "request payload is invalid",
                    "issues": issues,
                },
            },
        )

    async def authenticate(
        request: Request,
        x_api_key: str = Header(default="", alias="X-API-Key"),
        authorization: str = Header(default="", alias="Authorization"),
    ) -> str:
        principal = "anonymous"
        authenticated = False
        if settings.api_key and hmac.compare_digest(x_api_key, settings.api_key):
            principal = "api-key:" + hashlib.sha256(x_api_key.encode()).hexdigest()[:12]
            authenticated = True
        elif settings.jwt_secret and authorization.startswith("Bearer "):
            principal = _verify_hs256_jwt(
                authorization[7:].strip(),
                secret=settings.jwt_secret,
                issuer=settings.jwt_issuer,
                audience=settings.jwt_audience,
            )
            authenticated = True
        if (settings.api_key or settings.jwt_secret) and not authenticated:
            raise OfficialServiceError(
                "AUTHENTICATION_REQUIRED",
                "valid API credentials are required",
                status_code=401,
            )
        if not limiter.allow(principal):
            raise OfficialServiceError(
                "RATE_LIMIT_EXCEEDED",
                "request rate limit exceeded",
                status_code=429,
            )
        request.state.principal = principal
        return principal

    async def run_bounded(operation):
        try:
            await asyncio.wait_for(
                semaphore.acquire(),
                timeout=settings.queue_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise OfficialServiceError(
                "SERVICE_BUSY",
                "service concurrency budget is exhausted",
                status_code=429,
            ) from exc
        try:
            return await asyncio.to_thread(operation)
        finally:
            semaphore.release()

    @app.get("/v1/health/live")
    async def live():
        return {"ok": True, "status": "live"}

    @app.get("/v1/health/ready")
    async def ready():
        health = service.health()
        return JSONResponse(status_code=200 if health["ready"] else 503, content=health)

    @app.get("/v1/catalog")
    async def catalog(principal: str = Depends(authenticate)):
        return {
            "ok": True,
            "principal": principal,
            "context": service.health(),
            "configured_functions": [
                item.name for item in service.context.function_catalog.configured
            ],
            "resources": [
                {
                    "resource_id": item.resource_id,
                    "capabilities": list(item.capabilities),
                }
                for item in service.context.physical_catalog.resources
            ],
        }

    @app.post("/v1/compile")
    async def compile_endpoint(
        payload: CompileRequest,
        request: Request,
        principal: str = Depends(authenticate),
    ):
        options = OfficialPipelineOptions(
            use_statistics=payload.use_statistics,
            strategy_mode=payload.strategy_mode,
        )
        result = await run_bounded(
            lambda: service.compile(
                payload.dsl,
                options=options,
                request_id=request.state.request_id,
                principal=principal,
            )
        )
        return {"ok": True, **result}

    @app.post("/v1/explain")
    async def explain_endpoint(
        payload: CompileRequest,
        request: Request,
        principal: str = Depends(authenticate),
    ):
        options = OfficialPipelineOptions(
            use_statistics=payload.use_statistics,
            strategy_mode=payload.strategy_mode,
        )
        result = await run_bounded(
            lambda: service.compile(
                payload.dsl,
                options=options,
                request_id=request.state.request_id,
                principal=principal,
            )
        )
        return {
            "ok": True,
            "request_id": result["request_id"],
            "generated_at": result["generated_at"],
            "explain": result["result"]["explain"],
        }

    @app.post("/v1/result")
    async def result_endpoint(
        payload: CompileRequest,
        request: Request,
        principal: str = Depends(authenticate),
    ):
        from .result_report import render_compilation_result_markdown

        options = OfficialPipelineOptions(
            use_statistics=payload.use_statistics,
            strategy_mode=payload.strategy_mode,
        )
        result = await run_bounded(
            lambda: service.compile(
                payload.dsl,
                options=options,
                request_id=request.state.request_id,
                principal=principal,
            )
        )
        return {
            "ok": True,
            "request_id": result["request_id"],
            "generated_at": result["generated_at"],
            "filename": "findsl-result.md",
            "markdown": render_compilation_result_markdown(result["result"]),
        }

    @app.post("/v1/execute")
    async def execute_endpoint(
        payload: ExecuteRequest,
        request: Request,
        principal: str = Depends(authenticate),
    ):
        if not settings.enable_execute or settings.doris is None:
            raise OfficialServiceError(
                "EXECUTION_DISABLED",
                "Doris execution is disabled for this service instance",
                status_code=403,
            )
        options = OfficialPipelineOptions(
            use_statistics=payload.use_statistics,
            strategy_mode=payload.strategy_mode,
        )
        result = await run_bounded(
            lambda: service.execute(
                payload.dsl,
                doris=settings.doris,
                options=options,
                request_id=request.state.request_id,
                principal=principal,
            )
        )
        return {"ok": True, **result}

    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics(_principal: str = Depends(authenticate)):
        return service.metrics.prometheus()

    return app


def _verify_hs256_jwt(token: str, *, secret: str, issuer: str, audience: str) -> str:
    if not token or len(token) > 8192:
        raise OfficialServiceError("INVALID_TOKEN", "bearer token size is invalid", status_code=401)
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        header = json.loads(_b64url_decode(encoded_header))
        payload = json.loads(_b64url_decode(encoded_payload))
        signature = _b64url_decode(encoded_signature, raw=True)
    except Exception as exc:  # noqa: BLE001 - malformed credentials are one auth failure.
        raise OfficialServiceError("INVALID_TOKEN", "bearer token is malformed", status_code=401) from exc
    if header.get("alg") != "HS256" or header.get("typ") not in {None, "JWT"}:
        raise OfficialServiceError("INVALID_TOKEN", "bearer token algorithm is not allowed", status_code=401)
    expected = hmac.new(
        secret.encode("utf-8"),
        f"{encoded_header}.{encoded_payload}".encode("ascii"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(signature, expected):
        raise OfficialServiceError("INVALID_TOKEN", "bearer token signature is invalid", status_code=401)
    now = int(time.time())
    if payload.get("iss") != issuer or not _audience_matches(payload.get("aud"), audience):
        raise OfficialServiceError("INVALID_TOKEN", "bearer token issuer or audience is invalid", status_code=401)
    if not isinstance(payload.get("exp"), (int, float)) or int(payload["exp"]) <= now:
        raise OfficialServiceError("INVALID_TOKEN", "bearer token is expired", status_code=401)
    if isinstance(payload.get("nbf"), (int, float)) and int(payload["nbf"]) > now + 30:
        raise OfficialServiceError("INVALID_TOKEN", "bearer token is not active", status_code=401)
    subject = str(payload.get("sub") or "").strip()
    if not subject:
        raise OfficialServiceError("INVALID_TOKEN", "bearer token subject is missing", status_code=401)
    return "jwt:" + subject[:128]


def _b64url_decode(value: str, *, raw: bool = False):
    padded = value + "=" * (-len(value) % 4)
    decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
    return decoded if raw else decoded.decode("utf-8")


def _audience_matches(value, expected: str) -> bool:
    if isinstance(value, str):
        return hmac.compare_digest(value, expected)
    if isinstance(value, list):
        return any(isinstance(item, str) and hmac.compare_digest(item, expected) for item in value)
    return False


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc

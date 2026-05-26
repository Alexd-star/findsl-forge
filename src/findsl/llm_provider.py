from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib import error, request

from .llm_adapter import LLMAdapterResult, validate_llm_candidates


DEFAULT_LLM_BASE_URL = "https://api.openai.com/v1"
DEFAULT_API_KEY_ENV = "FINDSL_LLM_API_KEY"
DEFAULT_MODEL_ENV = "FINDSL_LLM_MODEL"


@dataclass(frozen=True)
class LLMProviderConfig:
    base_url: str
    model: str
    api_key: str = ""
    timeout_seconds: float = 30.0
    temperature: float = 0.1
    max_tokens: int = 700
    response_format_json: bool = False

    @property
    def chat_completions_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def public_dict(self) -> Dict[str, Any]:
        return {
            "base_url": self.base_url,
            "model": self.model,
            "api_key_configured": bool(self.api_key),
            "timeout_seconds": self.timeout_seconds,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format_json": self.response_format_json,
        }


@dataclass(frozen=True)
class LLMProviderValidationResult:
    provider: Dict[str, Any]
    raw_response: str
    validation: LLMAdapterResult

    @property
    def passed(self) -> bool:
        return self.validation.passed

    def to_dict(self) -> Dict[str, Any]:
        payload = self.validation.to_dict()
        payload["provider"] = dict(self.provider)
        payload["raw_response"] = self.raw_response
        return payload


def config_from_env(
    *,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    api_key_env: str = DEFAULT_API_KEY_ENV,
    allow_missing_api_key: bool = False,
    timeout_seconds: float = 30.0,
    temperature: float = 0.1,
    max_tokens: int = 700,
    response_format_json: bool = False,
) -> LLMProviderConfig:
    resolved_base_url = base_url or os.getenv("FINDSL_LLM_BASE_URL") or DEFAULT_LLM_BASE_URL
    resolved_model = model or os.getenv(DEFAULT_MODEL_ENV) or ""
    if not resolved_model:
        raise ValueError(f"LLM model is required; pass --model or set {DEFAULT_MODEL_ENV}.")

    api_key = os.getenv(api_key_env, "") if api_key_env else ""
    if not api_key and not allow_missing_api_key:
        raise ValueError(
            f"LLM API key is required; set {api_key_env} or pass --no-api-key for a local provider."
        )

    return LLMProviderConfig(
        base_url=resolved_base_url,
        model=resolved_model,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format_json=response_format_json,
    )


def build_chat_messages(text: str) -> List[Dict[str, str]]:
    system_prompt = (
        "You convert Chinese stock-screening requests into FinDSL candidates only. "
        "Never output SQL, never invent table names, and never ask to execute anything. "
        "Return compact JSON with this shape: "
        '{"candidates":[{"dsl":"filter(...)", "confidence":0.0, "rationale":"..."}]}. '
        "Supported top-level forms are filter(boolean), rank(indicator(...), asc|desc, "
        "top=N|bottom=N|percent=N), and then(filter(...), rank(...)). "
        "Supported predicates/functions include market(\"A\"), market(\"B\"), "
        "indicator(\"close\"), indicator(\"volume\"), indicator(\"turnover_rate\"), "
        "indicator(\"main_net_inflow\"), date_between(\"YYYY-MM-DD\", \"YYYY-MM-DD\"), "
        "CONS(condition, window), EXIST(condition, window), MA(indicator(...), window), "
        "SUM(indicator(...), window), MAX(indicator(...), window), "
        "MIN(indicator(...), window), and RET(indicator(\"close\"), window). "
        "Use positive integer windows and numeric thresholds. If the request is ambiguous, "
        "return two or three DSL candidates with conservative rationales."
    )
    user_prompt = (
        "Natural-language stock-screening request:\n"
        f"{text.strip()}\n\n"
        "Return only JSON. Do not include markdown fences or SQL."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_chat_completion_payload(text: str, config: LLMProviderConfig) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": config.model,
        "messages": build_chat_messages(text),
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }
    if config.response_format_json:
        payload["response_format"] = {"type": "json_object"}
    return payload


def request_llm_candidates(
    text: str,
    config: LLMProviderConfig,
    *,
    urlopen: Callable[..., Any] = request.urlopen,
) -> str:
    payload = json.dumps(
        build_chat_completion_payload(text, config),
        ensure_ascii=False,
    ).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    http_request = request.Request(
        config.chat_completions_url,
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(http_request, timeout=config.timeout_seconds) as response:
            return response.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM provider HTTP {exc.code}: {body[:500]}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"LLM provider request failed: {exc.reason}") from exc


def request_and_validate_llm_candidates(
    text: str,
    config: LLMProviderConfig,
    *,
    data_dir: Path = Path("data/samples"),
    enable_prefix_sum: bool = True,
    verify: bool = True,
    max_candidates: int = 5,
    urlopen: Callable[..., Any] = request.urlopen,
) -> LLMProviderValidationResult:
    raw_response = request_llm_candidates(text, config, urlopen=urlopen)
    validation = validate_llm_candidates(
        text=text,
        payload=raw_response,
        data_dir=data_dir,
        enable_prefix_sum=enable_prefix_sum,
        verify=verify,
        max_candidates=max_candidates,
    )
    return LLMProviderValidationResult(
        provider=config.public_dict(),
        raw_response=raw_response,
        validation=validation,
    )

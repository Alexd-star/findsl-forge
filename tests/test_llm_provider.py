import json
from pathlib import Path

import pytest

from findsl.llm_provider import (
    LLMProviderConfig,
    build_chat_completion_payload,
    build_chat_messages,
    config_from_env,
    request_and_validate_llm_candidates,
    request_llm_candidates,
)


DATA_DIR = Path("data/samples")


class FakeResponse:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return self._body


def test_builds_provider_prompt_with_findsl_contract():
    messages = build_chat_messages("A股近2日收盘价涨幅超过5%")

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "Never output SQL" in messages[0]["content"]
    assert "RET(indicator(\"close\"), window)" in messages[0]["content"]
    assert "Return only JSON" in messages[1]["content"]
    assert "A股近2日收盘价涨幅超过5%" in messages[1]["content"]


def test_config_from_env_requires_model_and_api_key(monkeypatch):
    monkeypatch.delenv("FINDSL_LLM_MODEL", raising=False)
    monkeypatch.delenv("FINDSL_LLM_API_KEY", raising=False)

    with pytest.raises(ValueError, match="FINDSL_LLM_MODEL"):
        config_from_env()

    monkeypatch.setenv("FINDSL_LLM_MODEL", "local-findsl-model")
    with pytest.raises(ValueError, match="FINDSL_LLM_API_KEY"):
        config_from_env()

    config = config_from_env(allow_missing_api_key=True)
    assert config.model == "local-findsl-model"
    assert config.api_key == ""


def test_request_llm_candidates_posts_openai_compatible_payload():
    captured = {}
    provider_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "candidates": [
                                {
                                    "dsl": 'filter(RET(indicator("close"), 2) > 0.05)',
                                    "confidence": 0.88,
                                    "rationale": "close return threshold",
                                }
                            ]
                        }
                    )
                }
            }
        ]
    }

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse(provider_response)

    config = LLMProviderConfig(
        base_url="http://127.0.0.1:8000/v1",
        model="findsl-test-model",
        api_key="secret-token",
        timeout_seconds=7.5,
        response_format_json=True,
    )
    raw = request_llm_candidates("近2日收益率大于5%", config, urlopen=fake_urlopen)

    assert json.loads(raw) == provider_response
    assert captured["url"] == "http://127.0.0.1:8000/v1/chat/completions"
    assert captured["timeout"] == 7.5
    assert captured["headers"]["Authorization"] == "Bearer secret-token"
    assert captured["body"]["model"] == "findsl-test-model"
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert captured["body"]["messages"][1]["content"].count("近2日收益率大于5%") == 1


def test_provider_response_is_validated_through_safety_loop():
    provider_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "candidates": [
                                {
                                    "dsl": 'filter(SUM(indicator("volume"), 3) > 300)',
                                    "confidence": 0.91,
                                    "rationale": "rolling volume sum",
                                },
                                {
                                    "dsl": "SELECT * FROM dwd_stock_daily_quote",
                                    "confidence": 0.2,
                                    "rationale": "unsafe direct SQL",
                                },
                            ]
                        }
                    )
                }
            }
        ]
    }

    def fake_urlopen(req, timeout):
        return FakeResponse(provider_response)

    result = request_and_validate_llm_candidates(
        text="近3日成交量累计大于300",
        config=LLMProviderConfig(
            base_url="http://127.0.0.1:8000/v1",
            model="findsl-test-model",
            api_key="secret-token",
        ),
        data_dir=DATA_DIR,
        urlopen=fake_urlopen,
    )

    assert result.passed
    assert result.validation.accepted_count == 1
    assert result.validation.rejected_count == 1
    assert result.provider["api_key_configured"] is True
    rejected_codes = {
        diagnostic["code"]
        for candidate in result.validation.candidates
        if not candidate.accepted
        for diagnostic in candidate.diagnostics
    }
    assert rejected_codes == {"UNSAFE_DIRECT_SQL"}
    assert result.validation.candidates[0].analysis["verification"]["passed"]


def test_build_chat_completion_payload_can_omit_provider_specific_response_format():
    payload = build_chat_completion_payload(
        "A股每日换手率前50%",
        LLMProviderConfig(
            base_url="http://localhost:8000/v1",
            model="generic-openai-compatible",
            api_key="",
            response_format_json=False,
        ),
    )

    assert "response_format" not in payload
    assert payload["temperature"] == 0.1

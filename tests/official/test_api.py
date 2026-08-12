import base64
import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient

from findsl.official.api import ApiSettings, create_app
from findsl.official.service import OfficialCompilerService


DSL = "indicator('', '', '成交量', '今日', '', '', '') > 100"


def test_api_requires_credentials_and_compiles_with_request_id():
    app = create_app(
        service=OfficialCompilerService(),
        settings=ApiSettings(environment="test", api_key="secret"),
    )
    client = TestClient(app)

    unauthorized = client.post("/v1/compile", json={"dsl": DSL})
    response = client.post(
        "/v1/compile",
        headers={"X-API-Key": "secret", "X-Request-ID": "trace-1"},
        json={"dsl": DSL},
    )

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "trace-1"
    assert response.json()["result"]["physical"]["plan_id"]
    assert response.headers["Cache-Control"] == "no-store"


def test_api_rejects_unknown_fields_and_disables_execution_by_default():
    client = TestClient(
        create_app(
            service=OfficialCompilerService(),
            settings=ApiSettings(environment="test"),
        )
    )

    invalid = client.post("/v1/compile", json={"dsl": DSL, "sql": "DROP TABLE x"})
    execution = client.post("/v1/execute", json={"dsl": DSL})

    assert invalid.status_code == 422
    assert execution.status_code == 403
    assert execution.json()["error"]["code"] == "EXECUTION_DISABLED"


def test_api_exposes_structured_explain_and_markdown_result():
    client = TestClient(
        create_app(
            service=OfficialCompilerService(),
            settings=ApiSettings(environment="test"),
        )
    )

    explain = client.post("/v1/explain", json={"dsl": DSL})
    result = client.post("/v1/result", json={"dsl": DSL})

    assert explain.status_code == 200
    assert explain.json()["explain"]["adaptive_route"]["selected_route"]
    assert result.status_code == 200
    assert result.json()["filename"] == "findsl-result.md"
    assert "## 自适应路由候选" in result.json()["markdown"]


def test_api_accepts_valid_hs256_bearer_and_rejects_bad_signature():
    settings = ApiSettings(
        environment="test",
        jwt_secret="jwt-secret",
        jwt_issuer="issuer",
        jwt_audience="audience",
    )
    client = TestClient(create_app(service=OfficialCompilerService(), settings=settings))
    payload = {
        "sub": "analyst-1",
        "iss": "issuer",
        "aud": "audience",
        "exp": int(time.time()) + 300,
    }
    valid = _jwt(payload, "jwt-secret")
    invalid = _jwt(payload, "wrong-secret")

    accepted = client.get("/v1/catalog", headers={"Authorization": f"Bearer {valid}"})
    rejected = client.get("/v1/catalog", headers={"Authorization": f"Bearer {invalid}"})

    assert accepted.status_code == 200
    assert accepted.json()["principal"] == "jwt:analyst-1"
    assert rejected.status_code == 401


def test_production_settings_require_authentication():
    try:
        ApiSettings(environment="production")
    except ValueError as exc:
        assert "requires an API key or JWT secret" in str(exc)
    else:
        raise AssertionError("production settings accepted an unauthenticated service")


def test_production_settings_reject_short_credentials():
    for kwargs in ({"api_key": "short"}, {"jwt_secret": "short"}):
        try:
            ApiSettings(environment="production", **kwargs)
        except ValueError as exc:
            assert "at least 32 characters" in str(exc)
        else:
            raise AssertionError("production settings accepted a weak credential")


def _jwt(payload, secret):
    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = _b64(json.dumps(header, separators=(",", ":")).encode())
    encoded_payload = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(
        secret.encode(),
        f"{encoded_header}.{encoded_payload}".encode(),
        hashlib.sha256,
    ).digest()
    return f"{encoded_header}.{encoded_payload}.{_b64(signature)}"


def _b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

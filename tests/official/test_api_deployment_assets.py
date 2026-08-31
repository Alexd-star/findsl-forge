from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_api_container_is_non_root_read_only_and_health_checked():
    dockerfile = (ROOT / "deploy/api/Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "deploy/api/compose.yaml").read_text(encoding="utf-8")
    constraints = (ROOT / "deploy/api/constraints.txt").read_text(encoding="utf-8")

    assert "python:3.11-slim-bookworm@sha256:" in dockerfile
    assert "PYTHONPATH=/app/src" in dockerfile
    assert "-c /tmp/constraints.txt" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "/v1/health/ready" in dockerfile
    assert "[service]" in dockerfile
    assert "read_only: true" in compose
    assert "no-new-privileges:true" in compose
    assert "cap_drop:" in compose and "- ALL" in compose
    assert "mem_limit:" in compose and "pids_limit:" in compose
    assert "fastapi==" in constraints and "uvicorn==" in constraints


def test_api_example_configuration_contains_no_real_secret():
    example = (ROOT / "deploy/api/service.env.example").read_text(encoding="utf-8")

    assert "replace-with-a-long-random-secret" in example
    assert "FINDSL_DORIS_USER=findsl_readonly" in example
    assert "FINDSL_DORIS_PASSWORD=\n" in example

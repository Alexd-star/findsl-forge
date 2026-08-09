import json
from pathlib import Path

import pytest

from findsl.official.backend.diff import hash_result_rows
from findsl.official.backend.executor import DorisExecutionConfig, DorisExecutionResult
from findsl.official.pipeline import OfficialPipelineOptions
from findsl.official.service import (
    JsonlAuditSink,
    OfficialCompilerService,
    OfficialServiceError,
    ServiceLimits,
)


DSL = "indicator('', '', '成交量', '今日', '', '', '') > 100"


def test_service_compiles_through_canonical_pipeline_and_audits_hash(tmp_path: Path):
    audit_path = tmp_path / "audit.jsonl"
    service = OfficialCompilerService(audit_sink=JsonlAuditSink(audit_path))

    response = service.compile(DSL, request_id="req-1", principal="tester")

    assert response["request_id"] == "req-1"
    assert response["result"]["ok"] is True
    assert response["result"]["physical"]["plan_id"]
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["principal"] == "tester"
    assert audit["dsl_chars"] == len(DSL)
    assert DSL not in audit_path.read_text(encoding="utf-8")


def test_service_rejects_empty_and_oversized_dsl():
    service = OfficialCompilerService(limits=ServiceLimits(max_dsl_chars=10))

    with pytest.raises(OfficialServiceError, match="must not be empty"):
        service.compile("")
    with pytest.raises(OfficialServiceError) as excinfo:
        service.compile("x" * 11)
    assert excinfo.value.code == "DSL_TOO_LARGE"
    assert excinfo.value.status_code == 413


def test_service_execution_applies_timeout_and_result_budget():
    captured = {}

    def executor(config, sql):
        captured["config"] = config
        captured["sql"] = sql
        rows = tuple((str(index),) for index in range(4))
        return DorisExecutionResult(
            rows,
            2.5,
            hash_result_rows(rows, ordered=True),
            hash_result_rows(rows, ordered=False),
        )

    service = OfficialCompilerService(
        limits=ServiceLimits(max_result_rows=3, max_doris_timeout_seconds=5),
        executor=executor,
    )
    response = service.execute(
        DSL,
        doris=DorisExecutionConfig("127.0.0.1", 9030, "root", "", "newzl", timeout_seconds=30),
    )

    assert response["execution"]["row_count"] == 3
    assert response["execution"]["truncated"] is True
    assert response["execution"]["ordered_hash"] is None
    assert captured["config"].timeout_seconds == 5
    assert "LIMIT 4" in captured["sql"]


def test_service_rejects_shadow_candidate_execution():
    service = OfficialCompilerService()

    with pytest.raises(OfficialServiceError) as excinfo:
        service.execute(
            DSL,
            doris=DorisExecutionConfig("127.0.0.1", 9030, "root", "", "newzl"),
            options=OfficialPipelineOptions(strategy_mode="force_candidate"),
        )

    assert excinfo.value.code == "UNSAFE_STRATEGY_MODE"


def test_service_metrics_expose_compile_latency():
    service = OfficialCompilerService()
    service.compile(DSL)

    metrics = service.metrics.snapshot()

    assert metrics["counters"]["compile:ok"] == 1
    assert metrics["durations_ms"]["compile"]["p95"] >= 0
    assert "findsl_requests_total" in service.metrics.prometheus()

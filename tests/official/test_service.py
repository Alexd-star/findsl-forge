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


def test_service_negotiates_supported_data_invalid_and_capability_cases():
    service = OfficialCompilerService()

    supported = service.negotiate(DSL)["capability"]
    unavailable = service.negotiate(
        "indicator('', '', '营业收入', '', '', '', '') > 1"
    )["capability"]
    invalid = service.negotiate("indicator(")["capability"]
    gap = service.negotiate(
        "indicator('', '', '涨幅', '', 'AVG', '', '') > 1"
    )["capability"]

    assert supported["status"] == "SUPPORTED"
    assert supported["plan_id"]
    assert "official_basic" in supported["required_resources"]
    assert unavailable["status"] == "DATA_UNAVAILABLE"
    assert unavailable["data_requirements"][0]["domain_id"] == "financial_statement"
    assert unavailable["data_requirements"][0]["profile"]["status"] == "not_loaded"
    assert unavailable["data_requirements"][0]["providers"][0]["provider_id"] == "tushare-optional"
    assert invalid["status"] == "INVALID_INPUT"
    assert gap["status"] == "CAPABILITY_GAP"
    assert service.metrics.snapshot()["counters"]["negotiate:supported"] == 1


def test_service_repair_requires_explicit_hash_confirmation_and_never_executes():
    source = (
        "rank('其他&法', '', '市盈率', 'desc', '', '', '', '') > 0\""
    )
    service = OfficialCompilerService()

    proposed = service.repair(source, request_id="repair-1")["repair"]
    accepted = service.repair(
        source,
        accept_candidate_sha256=proposed["candidate"]["candidate_sha256"],
        request_id="repair-2",
    )["repair"]

    assert proposed["status"] == "CONFIRMATION_REQUIRED"
    assert proposed["accepted"] is False
    assert proposed["auto_execute"] is False
    assert proposed["candidate"]["repair_code"] == "DANGLING_EDGE_QUOTE"
    assert accepted["status"] == "ACCEPTED"
    assert accepted["accepted"] is True
    assert accepted["auto_execute"] is False


def test_service_repair_does_not_guess_for_unregistered_invalid_dsl():
    repair = OfficialCompilerService().repair("indicator(")["repair"]

    assert repair == {
        "status": "NO_SAFE_CANDIDATE",
        "candidate": None,
        "accepted": False,
        "auto_execute": False,
        "message": (
            "No exact, ledger-backed repair exists; the original DSL was preserved "
            "and must be corrected manually."
        ),
    }


def test_service_distinguishes_missing_intraday_data_from_ambiguous_date() -> None:
    service = OfficialCompilerService()

    intraday = service.negotiate(
        "rank('', '', '主力净流入', 'desc', '今天开盘30分钟以内', '', '', '') = 1"
    )["capability"]
    ambiguous = service.negotiate(
        "indicator('', '', '涨幅', '最近', '', '', '') > 1"
    )["capability"]

    assert intraday["status"] == "DATA_UNAVAILABLE"
    assert any(
        item["domain_id"] == "intraday_quote"
        and item["profile"]["status"] == "not_loaded"
        for item in intraday["data_requirements"]
    )
    assert ambiguous["status"] == "INVALID_INPUT"


@pytest.mark.parametrize(
    "date",
    [
        "曾经",
        "以前",
        "板块调整阶段后期",
        "回落之后",
        "今天前",
        "一直以来",
        "2025年4月23号第二天开始",
        "2月第一周开始3周",
    ],
)
def test_service_requests_clarification_for_ungrounded_date_semantics(date):
    capability = OfficialCompilerService().negotiate(
        f"indicator('', '', '涨幅', '{date}', '', '', '') > 1"
    )["capability"]

    assert capability["status"] == "INVALID_INPUT"
    assert capability["clarification"]["required"] is True
    assert capability["clarification"]["field"] == "date"
    assert date in capability["clarification"]["values"]


@pytest.mark.parametrize(
    "date",
    [
        "盘中",
        "今天上午",
        "午盘",
        "9月19日16.30",
        "4月30日下午两点半后",
    ],
)
def test_service_classifies_unloaded_intraday_phrases_as_data_requirements(date):
    capability = OfficialCompilerService().negotiate(
        f"indicator('', '', '成交量', '{date}', '', '', '') > 1"
    )["capability"]

    assert capability["status"] == "DATA_UNAVAILABLE"
    assert any(
        item["domain_id"] == "intraday_quote"
        and item["profile"]["status"] == "not_loaded"
        for item in capability["data_requirements"]
    )


@pytest.mark.parametrize("date", ["上市以来", "上市后", "上市的第一个交易日"])
def test_service_classifies_listing_relative_dates_as_corporate_event_data(date):
    capability = OfficialCompilerService().negotiate(
        f"indicator('', '', '成交量', '{date}', '', '', '') > 1"
    )["capability"]

    assert capability["status"] == "DATA_UNAVAILABLE"
    assert any(
        item["domain_id"] == "corporate_event"
        and item["profile"]["status"] == "not_loaded"
        for item in capability["data_requirements"]
    )


def test_service_detects_intraday_indicator_and_cross_market_dependencies():
    service = OfficialCompilerService()
    intraday = service.negotiate(
        "rank('', '', '10分钟涨速', 'desc', '', '板块', '', '') > 0"
    )["capability"]
    cross_market = service.negotiate(
        "indicator('港', '', '收盘价', '', '概念', '', '') > 10"
    )["capability"]

    assert intraday["status"] == "DATA_UNAVAILABLE"
    assert any(
        item["domain_id"] == "intraday_quote"
        for item in intraday["data_requirements"]
    )
    assert cross_market["status"] == "DATA_UNAVAILABLE"
    assert any(
        item["domain_id"] == "cross_market_quote"
        for item in cross_market["data_requirements"]
    )

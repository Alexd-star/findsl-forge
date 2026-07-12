from findsl.official.backend.executor import DorisExecutionResult
from findsl.official_backend_evidence import (
    _baseline_gate_from_domain_report,
    _phase5_gates,
    audit_official_backend_sources,
    execute_official_backend_equivalence,
)


def test_backend_evidence_separates_grounded_sql_from_unavailable_domains():
    report = audit_official_backend_sources(
        [
            "indicator('', '', '成交量', '', '', '', '') > 100",
            "indicator('', '', '3分钟涨速', '', '', '', '') > 1",
            "indicator('', '', '营业收入', '今日', '', '', '') > 1",
        ],
        sample_size=5,
    )

    assert report["row_count"] == 3
    assert report["typed_ok"] == 3
    assert report["logical_ok"] == 2
    assert report["physical_ok"] == 1
    assert report["sqlglot_ok"] == 1
    assert report["safety_ok"] == 1
    assert report["errors"]["PHYSICAL_PLAN_UNAVAILABLE"] == 1
    assert report["errors"]["DOMAIN_DATA_UNAVAILABLE"] == 1
    assert report["static_gate"]["passed"] is True
    assert report["real_doris_execution"]["status"] == "NOT_RUN"
    assert report["gates"]["static_backend"]["passed"] is True
    assert report["gates"]["compile_latency"]["target_ms"] == 50.0
    assert report["gates"]["phase1_4_baseline"]["status"] == "NOT_EVALUATED"
    assert report["gates"]["structural_diff"]["status"] == "NOT_RUN"
    assert report["gates"]["real_doris_equivalence"]["status"] == "NOT_RUN"
    assert report["gates"]["phase5_completion"]["passed"] is False


def test_phase5_completion_requires_every_independent_gate():
    baseline = {"status": "PASS", "passed": True}
    structural = {"status": "PASS", "passed": True}
    execution = {"status": "PASS", "passed": True}

    passed = _phase5_gates(
        static_passed=True,
        latency_p95_ms=6.0,
        baseline_gate=baseline,
        structural_diff=structural,
        real_doris_execution=execution,
    )
    slow = _phase5_gates(
        static_passed=True,
        latency_p95_ms=50.0,
        baseline_gate=baseline,
        structural_diff=structural,
        real_doris_execution=execution,
    )

    assert passed["phase5_completion"]["passed"] is True
    assert slow["compile_latency"]["passed"] is False
    assert slow["phase5_completion"]["passed"] is False


def test_phase1_4_gate_carries_exact_floor_evidence():
    gate = _baseline_gate_from_domain_report(
        {
            "strict_parse_ok": 5792,
            "strict_compile_ok": 1097,
            "phase3_lowering_ok": 2034,
            "domain_lowering_ok": 1322,
            "optimized_validated": 1322,
            "gate": {"passed": True},
        }
    )

    assert gate["passed"] is True
    assert gate["strict_parse_ok"] == 5792
    assert gate["domain_lowering_ok"] == 1322


def test_structural_diff_gate_means_every_shadow_success_is_classified():
    class LegacyResult:
        sql = "SELECT mktcode, tgtcode, bizdate, name FROM newzl.hsj_stock_hq_basic WHERE volume > 100"

    class LegacyCompiler:
        def compile(self, source):
            return LegacyResult()

    report = audit_official_backend_sources(
        ["indicator('', '', '成交量', '', '', '', '') > 100"],
        legacy_compiler=LegacyCompiler(),
    )

    structural = report["structural_diff"]
    assert structural["status"] == "PASS"
    assert structural["eligible"] == 1
    assert structural["compared"] == 1
    assert structural["classified_differences"] == 1
    assert len(report["eligible_queries"]) == 1
    assert report["eligible_queries"][0]["excel_row"] == 2
    assert report["gates"]["structural_diff"]["passed"] is True


def test_real_doris_equivalence_requires_row_and_hash_parity():
    calls = []

    def executor(config, sql):
        calls.append(sql)
        return DorisExecutionResult(
            rows=(("0", "600000", "2026-04-14"),),
            elapsed_ms=2.5,
            ordered_hash="ordered",
            unordered_hash="same-hash",
        )

    report = execute_official_backend_equivalence(
        [
            {
                "excel_row": 2,
                "source": "dsl",
                "legacy_sql": "SELECT mktcode,tgtcode,bizdate,name FROM newzl.hsj_stock_hq_basic",
                "shadow_sql": "SELECT mktcode,tgtcode,bizdate FROM newzl.hsj_stock_hq_basic",
                "ordered": False,
            }
        ],
        config=object(),
        executor=executor,
    )

    assert report["status"] == "PASS"
    assert report["matched"] == 1
    assert len(calls) == 2
    assert all("evidence_rows" in sql for sql in calls)


def test_real_equivalence_skips_unordered_limit_queries_as_nondeterministic():
    calls = []

    report = execute_official_backend_equivalence(
        [
            {
                "excel_row": 2,
                "source": "dsl",
                "legacy_sql": "SELECT mktcode,tgtcode,bizdate FROM newzl.hsj_stock_hq_basic LIMIT 2",
                "shadow_sql": "SELECT mktcode,tgtcode,bizdate FROM newzl.hsj_stock_hq_basic LIMIT 2",
                "ordered": False,
            }
        ],
        config=object(),
        executor=lambda config, sql: calls.append(sql),
    )

    assert report["status"] == "NOT_EVALUATED"
    assert report["deterministic_eligible"] == 0
    assert report["skipped"] == 1
    assert report["skipped_reasons"] == {"NONDETERMINISTIC_LIMIT": 1}
    assert report["results"][0]["status"] == "SKIPPED"
    assert calls == []

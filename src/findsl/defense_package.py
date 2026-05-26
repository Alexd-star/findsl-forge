from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

from .compiler import Compiler
from .demo import DEFAULT_NL_REQUEST, analyze_dsl, suggest_from_text
from .diagnostics import diagnose_exception
from .doris import render_doris_assets
from .evaluation import evaluate_file, load_cases
from .equivalence import verify_sql_equivalence
from .llm_adapter import DEFAULT_LLM_CANDIDATE_RESPONSE, validate_llm_candidates
from .llm_provider import LLMProviderConfig, build_chat_completion_payload
from .official_suite import DEFAULT_NEGATIVE_CASES, DEFAULT_POSITIVE_CASES, run_official_suite
from .registry import Registry, default_registry

REAL_MARKET_SAMPLE_DIR = Path("data/real_samples/eastmoney_a_share_sample")


@dataclass(frozen=True)
class DefenseCheck:
    name: str
    scoring_point: str
    demo_action: str
    expected_signal: str
    passed: bool
    evidence: List[str]


@dataclass(frozen=True)
class DefensePackageResult:
    checks: List[DefenseCheck]
    output_path: Path

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def passed_count(self) -> int:
        return sum(1 for check in self.checks if check.passed)

    @property
    def passed(self) -> bool:
        return self.total > 0 and self.passed_count == self.total

    def to_markdown(self) -> str:
        lines = [
            "# FinDSL Forge Defense Package",
            "",
            "## Summary",
            "",
            f"- Package passed: {self.passed}",
            f"- Checks passed: {self.passed_count}/{self.total}",
            "- Scope: local reproducible evidence for live defense; attach the latest Doris 10x+ proof from the exported evidence snapshots.",
            "",
            "## Live Walkthrough",
            "",
            "1. Start the demo with `powershell -ExecutionPolicy Bypass -File .\\scripts\\serve_demo.ps1`.",
            "2. Let the default Chinese request produce a validated DSL candidate and SQL/reference PASS.",
            "3. Try `A股存在资金流入后按低价取每日2只`, `A股每日换手率前50%`, `B股近2日均量不低于80`, `2026-01-02到2026-01-04收盘价大于3日均线`, `主力净流出低于-1.5`, `近3日最低收盘价低于10`, `A股近2日收盘价涨幅超过5%`, and `2026-01-02到2026-01-04近3日成交量累计大于300`; confirm each suggested DSL validates.",
            "4. Select `Official positive: 主力净流入3日滚动求和走资金流前缀表 [money_flow_prefix_sum]` and run it.",
            "5. Confirm the UI shows verification PASS, optimizer `Applied`, and SQL containing `dwd_stock_money_flow_prefix`.",
            "6. Select `Diagnostic negative: 未知指标名 [UNKNOWN_INDICATOR]` and run it.",
            "7. Confirm the UI shows `Diagnostic`, expected/actual `UNKNOWN_INDICATOR`, and the `indicator(\"close\")` repair hint.",
            "8. Show the semantic hardening evidence for bare identifiers, invalid windows, invalid top-level expressions, bad market arguments, and literal division by zero.",
            "9. Run `python -m findsl.cli validate-llm-candidates --response-file data\\samples\\llm_candidate_response.json --json` to prove the LLM path accepts only compiler-validated DSL.",
            "10. If a provider key is available, run `python -m findsl.cli llm-suggest-dsl \"近3日成交量累计大于300\" --model <model> --json`; otherwise show the offline provider-contract check in this package.",
            "11. Run the real-market quote sample verification from `data\\real_samples\\eastmoney_a_share_sample\\queries.jsonl` to show the same checker works on public A-share fields.",
            "12. Run `scripts\\official_suite.ps1` and `scripts\\submission_readiness.ps1` to show repeatable report evidence.",
            "",
            "## Score Mapping",
            "",
            "| Check | Scoring point | Passed | Demo action | Expected signal | Evidence |",
            "|---|---|---:|---|---|---|",
        ]
        for check in self.checks:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(check.name),
                        _cell(check.scoring_point),
                        str(check.passed),
                        _cell(check.demo_action),
                        _cell(check.expected_signal),
                        _cell("<br>".join(check.evidence) or "<none>"),
                    ]
                )
                + " |"
            )
        lines.extend(
            [
                "",
                "## Submission Narrative",
                "",
                "- Deterministic compiler path keeps correctness auditable: DSL -> AST -> semantic validation -> Doris SQL.",
                "- AI assistance is constrained to NL2DSL/LLM DSL candidates; every candidate must compile and match the independent reference oracle.",
                "- The LLM adapter rejects direct SQL and invalid DSL with stable diagnostic evidence before any SQL reaches Doris.",
                "- The optional OpenAI-compatible provider path is wired as a candidate source only; provider responses still enter the same safety loop.",
                "- The compiler validates Doris-safe SQL shape and escapes string literals before generated SQL is accepted.",
                "- Public Eastmoney quote samples show the product story on real A-share codes and dates, while performance claims remain tied to 5M Doris evidence.",
                "- Prefix-sum optimization is visible in SQL, structured explain records, and benchmark/readiness evidence.",
                "- Negative cases demonstrate controlled, repairable failure rather than uncaught exceptions.",
                "- Semantic hardening evidence proves hidden-eval style invalid DSL fails before SQL generation.",
                "- Generated Doris assets include trade-date auto partitions and colocated stock-code distribution from the same compiler registry.",
            ]
        )
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "passed_count": self.passed_count,
            "total": self.total,
            "output": str(self.output_path),
            "checks": [
                {
                    "name": check.name,
                    "scoring_point": check.scoring_point,
                    "demo_action": check.demo_action,
                    "expected_signal": check.expected_signal,
                    "passed": check.passed,
                    "evidence": list(check.evidence),
                }
                for check in self.checks
            ],
        }


def generate_defense_package(
    output_path: Path = Path("reports/defense_package.md"),
    data_dir: Path = Path("data/samples"),
    cases_path: Path = Path("data/samples/queries.jsonl"),
    official_positive_path: Path = DEFAULT_POSITIVE_CASES,
    official_negative_path: Path = DEFAULT_NEGATIVE_CASES,
    llm_response_path: Path = DEFAULT_LLM_CANDIDATE_RESPONSE,
    repo_root: Path = Path("."),
) -> DefensePackageResult:
    output_path = Path(output_path)
    reports_dir = output_path.parent
    repo_root = Path(repo_root)
    checks = [
        _check_nl2dsl(data_dir),
        _check_nl2dsl_official_template_coverage(data_dir),
        _check_llm_candidate_safety(data_dir, _resolve_repo_path(repo_root, llm_response_path)),
        _check_llm_provider_contract(data_dir),
        _check_money_flow_prefix(data_dir, official_positive_path),
        _check_unknown_indicator_diagnostic(official_negative_path),
        _check_semantic_hardening_diagnostics(official_negative_path),
        _check_doris_sql_validation(),
        _check_real_market_sample(repo_root),
        _check_config_only_indicator_extension(),
        _check_official_suite(data_dir, official_positive_path, official_negative_path, reports_dir),
        _check_evaluation_report(cases_path, reports_dir),
        _check_doris_assets(repo_root, data_dir),
    ]
    result = DefensePackageResult(checks=checks, output_path=output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.to_markdown(), encoding="utf-8")
    return result


def _check_nl2dsl(data_dir: Path) -> DefenseCheck:
    try:
        result = suggest_from_text(DEFAULT_NL_REQUEST, data_dir=data_dir, verify=True)
        candidates = result.get("candidates", [])
        top = candidates[0] if candidates else {}
        analysis = top.get("analysis") or {}
        verification = analysis.get("verification") or {}
        passed = bool(top.get("validated")) and bool(verification.get("passed"))
        return DefenseCheck(
            name="NL2DSL validated candidate",
            scoring_point="AI-assisted entry without SQL hallucination",
            demo_action="Use the default Chinese request in the Web Demo.",
            expected_signal="Candidate is validated and verification is PASS.",
            passed=passed,
            evidence=[
                f"candidate_count={len(candidates)}",
                f"top_dsl={top.get('dsl', '<none>')}",
                f"sql_rows={verification.get('sql_row_count', 0)}",
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "NL2DSL validated candidate",
            "AI-assisted entry without SQL hallucination",
            "Use the default Chinese request in the Web Demo.",
            "Candidate is validated and verification is PASS.",
            exc,
        )


def _check_nl2dsl_official_template_coverage(data_dir: Path) -> DefenseCheck:
    prompts = [
        (
            "low_price_bottom",
            "A股存在资金流入后按低价取每日2只",
            "money_flow_low_price_rank",
            "bottom=2",
        ),
        (
            "turnover_percent",
            "A股每日换手率前50%",
            "turnover_percent_rank",
            "percent=50",
        ),
        (
            "b_market_average_volume",
            "B股近2日均量不低于80",
            "volume_ma_threshold",
            'market("B") & MA(indicator("volume"), 2) >= 80',
        ),
        (
            "date_window_pruning",
            "2026-01-02到2026-01-04收盘价大于3日均线",
            "date_range_close_above_ma",
            "MA(indicator(\"close\"), 3)",
        ),
        (
            "signed_outflow_threshold",
            "主力净流出低于-1.5",
            "net_outflow_threshold",
            "< -1.5",
        ),
        (
            "rolling_min_threshold",
            "近3日最低收盘价低于10",
            "close_rolling_min_threshold",
            "MIN(indicator(\"close\"), 3)",
        ),
        (
            "close_return_threshold",
            "A股近2日收盘价涨幅超过5%",
            "close_return_threshold",
            "RET(indicator(\"close\"), 2) > 0.05",
        ),
        (
            "date_prefix_sum_pruning",
            "2026-01-02到2026-01-04近3日成交量累计大于300",
            "date_range_rolling_volume_sum",
            "SUM(indicator(\"volume\"), 3)",
        ),
    ]
    try:
        evidence = []
        passed_items = 0
        for name, text, expected_rule, expected_fragment in prompts:
            result = suggest_from_text(text, data_dir=data_dir, verify=True)
            candidates = result.get("candidates", [])
            top = candidates[0] if candidates else {}
            ok = (
                top.get("rule") == expected_rule
                and expected_fragment in str(top.get("dsl", ""))
                and bool(top.get("validated"))
            )
            passed_items += int(ok)
            evidence.append(
                f"{name}: rule={top.get('rule', '<none>')}, validated={top.get('validated', False)}"
            )
        passed = passed_items == len(prompts)
        return DefenseCheck(
            name="NL2DSL official template coverage",
            scoring_point="AI-assisted coverage for bottom-rank, percent-rank, B-market average-volume, date-window, signed-threshold, rolling-min, return-rate, and prefix-pruning official scenarios",
            demo_action="Enter official-style Chinese prompts for low-price bottom, turnover percent, B-market average volume, date-window MA, net-outflow threshold, rolling-min, close-return, and date-prefix-sum cases.",
            expected_signal="Each prompt yields a compiler-validated DSL candidate whose rule matches the intended official scenario.",
            passed=passed,
            evidence=[
                f"covered={passed_items}/{len(prompts)}",
                *evidence,
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "NL2DSL official template coverage",
            "AI-assisted coverage for bottom-rank, percent-rank, B-market average-volume, date-window, signed-threshold, rolling-min, and prefix-pruning official scenarios",
            "Enter official-style Chinese prompts for low-price bottom, turnover percent, B-market average volume, date-window MA, net-outflow threshold, rolling-min, and date-prefix-sum cases.",
            "Each prompt yields a compiler-validated DSL candidate whose rule matches the intended official scenario.",
            exc,
        )


def _check_llm_candidate_safety(data_dir: Path, response_path: Path) -> DefenseCheck:
    try:
        result = validate_llm_candidates(
            text="近3日成交量累计大于300",
            payload=response_path.read_text(encoding="utf-8"),
            data_dir=data_dir,
            verify=True,
        )
        rejected_codes = [
            str(diagnostic.get("code", ""))
            for candidate in result.candidates
            if not candidate.accepted
            for diagnostic in candidate.diagnostics
        ]
        accepted_verified = any(
            candidate.accepted
            and bool((candidate.analysis or {}).get("verification", {}).get("passed"))
            for candidate in result.candidates
        )
        passed = (
            accepted_verified
            and result.accepted_count >= 1
            and "UNSAFE_DIRECT_SQL" in rejected_codes
            and "UNKNOWN_INDICATOR" in rejected_codes
        )
        return DefenseCheck(
            name="LLM candidate safety loop",
            scoring_point="LLM assistance with deterministic compiler guardrails",
            demo_action="Run validate-llm-candidates against data\\samples\\llm_candidate_response.json.",
            expected_signal="One valid DSL is accepted, direct SQL is rejected, and misspelled indicators produce diagnostics.",
            passed=passed,
            evidence=[
                f"accepted={result.accepted_count}",
                f"rejected={result.rejected_count}",
                f"rejected_codes={', '.join(rejected_codes) or '<none>'}",
                f"response={response_path}",
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "LLM candidate safety loop",
            "LLM assistance with deterministic compiler guardrails",
            "Run validate-llm-candidates against data\\samples\\llm_candidate_response.json.",
            "One valid DSL is accepted, direct SQL is rejected, and misspelled indicators produce diagnostics.",
            exc,
        )


def _check_llm_provider_contract(data_dir: Path) -> DefenseCheck:
    try:
        config = LLMProviderConfig(
            base_url="https://provider.example/v1",
            model="configured-at-runtime",
            api_key="configured",
            response_format_json=True,
        )
        request_payload = build_chat_completion_payload("近3日成交量累计大于300", config)
        raw_response = json.dumps(
            {
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
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
            ensure_ascii=False,
        )
        result = validate_llm_candidates(
            text="近3日成交量累计大于300",
            payload=raw_response,
            data_dir=data_dir,
            verify=True,
        )
        rejected_codes = [
            str(diagnostic.get("code", ""))
            for candidate in result.candidates
            if not candidate.accepted
            for diagnostic in candidate.diagnostics
        ]
        system_prompt = str(request_payload["messages"][0]["content"])
        user_prompt = str(request_payload["messages"][1]["content"])
        prompt_contract = (
            "Never output SQL" in system_prompt
            and "Return only JSON" in user_prompt
            and request_payload.get("response_format") == {"type": "json_object"}
        )
        passed = (
            prompt_contract
            and result.accepted_count == 1
            and result.rejected_count == 1
            and "UNSAFE_DIRECT_SQL" in rejected_codes
        )
        return DefenseCheck(
            name="OpenAI-compatible LLM provider contract",
            scoring_point="Real-provider AI entry point without relaxing deterministic safety",
            demo_action="Use llm-suggest-dsl with a configured provider, or inspect this offline provider-contract check.",
            expected_signal="Provider prompt asks for JSON DSL only; returned candidates are validated by the same compiler and reference oracle.",
            passed=passed,
            evidence=[
                f"endpoint={config.chat_completions_url}",
                f"messages={len(request_payload['messages'])}",
                f"json_response_format={request_payload.get('response_format') == {'type': 'json_object'}}",
                f"prompt_contract={prompt_contract}",
                f"accepted={result.accepted_count}",
                f"rejected={result.rejected_count}",
                f"rejected_codes={', '.join(rejected_codes) or '<none>'}",
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "OpenAI-compatible LLM provider contract",
            "Real-provider AI entry point without relaxing deterministic safety",
            "Use llm-suggest-dsl with a configured provider, or inspect this offline provider-contract check.",
            "Provider prompt asks for JSON DSL only; returned candidates are validated by the same safety loop.",
            exc,
        )


def _check_money_flow_prefix(data_dir: Path, positive_path: Path) -> DefenseCheck:
    try:
        case = _find_case(load_cases(Path(positive_path)), "scenario", "money_flow_prefix_sum")
        result = analyze_dsl(case["dsl"], data_dir=data_dir, enable_prefix_sum=True, verify=True)
        explain = result["compile"]["explain"]
        sql = result["compile"]["sql"]
        verification = result["verification"] or {}
        prefix_applied = any(step.get("rule") == "PREFIX_SUM" and step.get("status") == "applied" for step in explain)
        passed = (
            bool(verification.get("passed"))
            and prefix_applied
            and "dwd_stock_money_flow_prefix" in sql
        )
        return DefenseCheck(
            name="Official prefix-sum positive preset",
            scoring_point="Long-window optimization with explainable SQL rewrite",
            demo_action="Select the money_flow_prefix_sum official positive preset and run it.",
            expected_signal="Verification PASS, optimizer Applied, and money-flow prefix table in SQL.",
            passed=passed,
            evidence=[
                f"case={case.get('name', '<unnamed>')}",
                f"compile_ms={result['compile']['elapsed_ms']:.3f}",
                f"sql_rows={verification.get('sql_row_count', 0)}",
                "sql_contains=dwd_stock_money_flow_prefix",
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "Official prefix-sum positive preset",
            "Long-window optimization with explainable SQL rewrite",
            "Select the money_flow_prefix_sum official positive preset and run it.",
            "Verification PASS, optimizer Applied, and money-flow prefix table in SQL.",
            exc,
        )


def _check_unknown_indicator_diagnostic(negative_path: Path) -> DefenseCheck:
    try:
        case = _find_case(load_cases(Path(negative_path)), "expected_code", "UNKNOWN_INDICATOR")
        try:
            Compiler().compile(case["dsl"])
            diagnostics = []
        except Exception as exc:  # noqa: BLE001 - this case is expected to fail diagnostically.
            diagnostics = diagnose_exception(exc)
        actual_code = diagnostics[0].code if diagnostics else ""
        suggestions = [hint for item in diagnostics for hint in item.suggestions]
        passed = (
            actual_code == "UNKNOWN_INDICATOR"
            and any('indicator("close")' in hint for hint in suggestions)
        )
        return DefenseCheck(
            name="Official diagnostic negative preset",
            scoring_point="Interactive error explainability and repair guidance",
            demo_action="Select the UNKNOWN_INDICATOR negative preset and run it.",
            expected_signal="Expected and actual diagnostic codes match, with a close-indicator repair hint.",
            passed=passed,
            evidence=[
                f"case={case.get('name', '<unnamed>')}",
                f"expected=UNKNOWN_INDICATOR",
                f"actual={actual_code or '<none>'}",
                f"suggestions={len(suggestions)}",
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "Official diagnostic negative preset",
            "Interactive error explainability and repair guidance",
            "Select the UNKNOWN_INDICATOR negative preset and run it.",
            "Expected and actual diagnostic codes match, with a close-indicator repair hint.",
            exc,
        )


def _check_semantic_hardening_diagnostics(negative_path: Path) -> DefenseCheck:
    required_cases = [
        ("裸指标列名绕过", 'indicator("close")'),
        ("窗口不是整数字面量", "positive integer window"),
        ("顶层表达式不是关系或布尔", 'filter(indicator("close") > 10)'),
        ("市场参数不是字符串或标识符", 'market("A")'),
        ("除数为零字面量", "non-zero denominator"),
        ("除数为零常量表达式", "non-zero denominator"),
    ]
    try:
        cases = load_cases(Path(negative_path))
        evidence = []
        passed_items = 0
        for case_name, expected_hint in required_cases:
            case = _find_case(cases, "name", case_name)
            try:
                Compiler().compile(case["dsl"])
                diagnostics = []
            except Exception as exc:  # noqa: BLE001 - these hardening cases should fail diagnostically.
                diagnostics = diagnose_exception(exc)
            actual_code = diagnostics[0].code if diagnostics else ""
            suggestion_blob = "\n".join(
                hint for diagnostic in diagnostics for hint in diagnostic.suggestions
            )
            ok = (
                actual_code == case.get("expected_code")
                and expected_hint in suggestion_blob
            )
            passed_items += int(ok)
            evidence.append(
                f"{case_name}: code={actual_code or '<none>'}, hint={expected_hint in suggestion_blob}"
            )
        passed = passed_items == len(required_cases)
        return DefenseCheck(
            name="Semantic hardening diagnostics",
            scoring_point="Hidden-eval style invalid DSL fails before SQL generation with repairable diagnostics",
            demo_action="Run the official negative corpus or select the hardening negative presets in the Web Demo.",
            expected_signal="Bare identifiers, invalid windows, bad top-level expressions, invalid market arguments, and static division by zero are rejected with stable hints.",
            passed=passed,
            evidence=[
                f"hardened={passed_items}/{len(required_cases)}",
                *evidence,
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "Semantic hardening diagnostics",
            "Hidden-eval style invalid DSL fails before SQL generation with repairable diagnostics",
            "Run the official negative corpus or select the hardening negative presets in the Web Demo.",
            "All hardening cases are rejected with stable hints.",
            exc,
        )


def _check_doris_sql_validation() -> DefenseCheck:
    try:
        result = Compiler().compile('filter(market("A\' OR 1=1 --"))')
        validation_steps = [step for step in result.explain if step.get("rule") == "DORIS_SQL_VALIDATION"]
        issue_count = (
            validation_steps[0].get("evidence", {}).get("issue_count", -1)
            if validation_steps
            else -1
        )
        escaped = "market = 'A'' OR 1=1 --'" in result.sql
        passed = bool(validation_steps) and issue_count == 0 and escaped
        return DefenseCheck(
            name="Doris SQL validation boundary",
            scoring_point="Generated SQL shape and literal safety",
            demo_action="Compile a market literal containing a quote and SQL-looking text.",
            expected_signal="DORIS_SQL_VALIDATION appears in explain with zero issues and the SQL literal is escaped.",
            passed=passed,
            evidence=[
                f"validation_steps={len(validation_steps)}",
                f"issue_count={issue_count}",
                f"escaped_literal={escaped}",
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "Doris SQL validation boundary",
            "Generated SQL shape and literal safety",
            "Compile a market literal containing a quote and SQL-looking text.",
            "DORIS_SQL_VALIDATION appears in explain with zero issues and the SQL literal is escaped.",
            exc,
        )


def _check_real_market_sample(repo_root: Path) -> DefenseCheck:
    try:
        data_dir = Path(repo_root).resolve() / REAL_MARKET_SAMPLE_DIR
        metadata = json.loads((data_dir / "source_metadata.json").read_text(encoding="utf-8"))
        raw_payload_count = len(list((data_dir / "raw").glob("*.json")))
        cases = [
            json.loads(line)
            for line in (data_dir / "queries.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        case_evidence = []
        passed_cases = 0
        for case in cases:
            result = verify_sql_equivalence(case["dsl"], data_dir)
            passed_cases += int(result.passed)
            case_evidence.append(
                f"{case.get('scenario', '<unnamed>')}: passed={result.passed}, rows={result.sql_row_count}"
            )
        source = str(metadata.get("source", ""))
        passed = (
            "Eastmoney" in source
            and raw_payload_count >= 2
            and bool(cases)
            and passed_cases == len(cases)
        )
        return DefenseCheck(
            name="Public real-market quote sample",
            scoring_point="Business credibility with real A-share codes and dates, separated from performance proof",
            demo_action="Run the Eastmoney sample DSL cases under data\\real_samples\\eastmoney_a_share_sample.",
            expected_signal="All quote-only DSL cases pass SQL/reference equivalence with cached raw JSON and source metadata present.",
            passed=passed,
            evidence=[
                f"source={source}",
                f"raw_payloads={raw_payload_count}",
                f"cases={passed_cases}/{len(cases)}",
                *case_evidence,
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "Public real-market quote sample",
            "Business credibility with real A-share codes and dates, separated from performance proof",
            "Run the Eastmoney sample DSL cases under data\\real_samples\\eastmoney_a_share_sample.",
            "All quote-only DSL cases pass SQL/reference equivalence with cached raw JSON and source metadata present.",
            exc,
        )


def _check_config_only_indicator_extension() -> DefenseCheck:
    try:
        base = default_registry()
        registry = Registry(
            indicators={
                **base.indicators,
                "alpha_score": {
                    "type": "numeric",
                    "table": "daily_quote",
                    "column": "alpha_score",
                    "adjustment": "none",
                    "supports_prefix_sum": False,
                },
            },
            tables=base.tables,
            functions=base.functions,
        )
        result = Compiler(registry=registry).compile('filter(indicator("alpha_score") > 0)')
        validation_ok = any(
            step.get("rule") == "DORIS_SQL_VALIDATION"
            and step.get("evidence", {}).get("issue_count") == 0
            for step in result.explain
        )
        sql_contains_indicator = "alpha_score > 0" in result.sql
        passed = validation_ok and sql_contains_indicator
        return DefenseCheck(
            name="Config-only indicator extension",
            scoring_point="New indicator support without compiler-core changes",
            demo_action="Compile a temporary registry extension containing indicator alpha_score.",
            expected_signal="Generated SQL references alpha_score and still passes Doris SQL validation.",
            passed=passed,
            evidence=[
                "indicator=alpha_score",
                f"sql_contains_indicator={sql_contains_indicator}",
                f"doris_validation={validation_ok}",
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "Config-only indicator extension",
            "New indicator support without compiler-core changes",
            "Compile a temporary registry extension containing indicator alpha_score.",
            "Generated SQL references alpha_score and still passes Doris SQL validation.",
            exc,
        )


def _check_official_suite(
    data_dir: Path,
    positive_path: Path,
    negative_path: Path,
    reports_dir: Path,
) -> DefenseCheck:
    try:
        result = run_official_suite(
            positive_cases_path=Path(positive_path),
            negative_cases_path=Path(negative_path),
            data_dir=Path(data_dir),
            output_path=reports_dir / "official_suite_report.md",
        )
        return DefenseCheck(
            name="Official-style coverage suite",
            scoring_point="Representative task coverage and negative-case proof",
            demo_action="Run scripts\\official_suite.ps1.",
            expected_signal="All official-style positive and negative cases pass.",
            passed=result.passed,
            evidence=[
                f"positive={result.positive_passed}/{result.positive_total}",
                f"negative={result.negative_passed}/{result.negative_total}",
                f"report={result.output_path}",
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "Official-style coverage suite",
            "Representative task coverage and negative-case proof",
            "Run scripts\\official_suite.ps1.",
            "All official-style positive and negative cases pass.",
            exc,
        )


def _check_evaluation_report(cases_path: Path, reports_dir: Path) -> DefenseCheck:
    try:
        result = evaluate_file(Path(cases_path), reports_dir / "evaluation_report.md")
        passed = (
            result.failed == 0
            and result.compile_success_rate == 1.0
            and result.fragment_accuracy == 1.0
            and result.p95_elapsed_ms < 50
        )
        return DefenseCheck(
            name="Compiler accuracy and latency",
            scoring_point="Correct SQL generation under compile P95 target",
            demo_action="Run scripts\\evaluate.ps1 or submission_readiness.ps1.",
            expected_signal="100% compile/fragment accuracy and P95 below 50 ms.",
            passed=passed,
            evidence=[
                f"cases={result.passed}/{result.total}",
                f"fragments={result.fragment_accuracy:.2%}",
                f"p95_ms={result.p95_elapsed_ms:.3f}",
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "Compiler accuracy and latency",
            "Correct SQL generation under compile P95 target",
            "Run scripts\\evaluate.ps1 or submission_readiness.ps1.",
            "100% compile/fragment accuracy and P95 below 50 ms.",
            exc,
        )


def _check_doris_assets(repo_root: Path, data_dir: Path) -> DefenseCheck:
    try:
        expected_assets = render_doris_assets(Path(data_dir)).files()
        asset_dir = Path(repo_root).resolve() / "deploy" / "doris"
        matched = []
        missing = []
        for filename, expected in expected_assets.items():
            path = asset_dir / filename
            if path.exists() and path.read_text(encoding="utf-8") == expected:
                matched.append(filename)
            else:
                missing.append(filename)
        schema_path = asset_dir / "01_schema.sql"
        schema_sql = schema_path.read_text(encoding="utf-8") if schema_path.exists() else ""
        has_auto_partitions = "AUTO PARTITION BY RANGE (date_trunc(`trade_date`, 'month'))" in schema_sql
        has_colocated_distribution = '"colocate_with" = "findsl_stock_by_ts"' in schema_sql
        passed = (
            not missing
            and len(matched) == len(expected_assets)
            and has_auto_partitions
            and has_colocated_distribution
        )
        return DefenseCheck(
            name="Doris deployment asset integrity",
            scoring_point="Reproducible partitioned and colocated Doris deployment path",
            demo_action="Run scripts\\generate_doris_assets.ps1, then inspect deploy\\doris.",
            expected_signal="All generated Doris SQL assets match, with auto partitions and colocated distribution visible in schema SQL.",
            passed=passed,
            evidence=[
                f"matched={len(matched)}/{len(expected_assets)}",
                f"missing={', '.join(missing) or '<none>'}",
                f"auto_partitions={has_auto_partitions}",
                f"colocated_distribution={has_colocated_distribution}",
                f"asset_dir={asset_dir}",
            ],
        )
    except Exception as exc:  # noqa: BLE001 - defense reports should preserve failure evidence.
        return _failed_check(
            "Doris deployment asset integrity",
            "Reproducible Doris deployment path",
            "Run scripts\\generate_doris_assets.ps1, then inspect deploy\\doris.",
            "All generated Doris SQL assets match the registry-driven generator.",
            exc,
        )


def _find_case(cases: Sequence[Dict[str, Any]], key: str, value: str) -> Dict[str, Any]:
    for case in cases:
        if case.get(key) == value:
            return case
    raise ValueError(f"Missing case where {key}={value}")


def _failed_check(
    name: str,
    scoring_point: str,
    demo_action: str,
    expected_signal: str,
    exc: Exception,
) -> DefenseCheck:
    return DefenseCheck(
        name=name,
        scoring_point=scoring_point,
        demo_action=demo_action,
        expected_signal=expected_signal,
        passed=False,
        evidence=[f"{type(exc).__name__}: {exc}"],
    )


def _cell(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _resolve_repo_path(repo_root: Path, path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else Path(repo_root).resolve() / path

import json
from pathlib import Path

from findsl.llm_adapter import extract_llm_dsl_candidates, validate_llm_candidates


DATA_DIR = Path("data/samples")


def test_extracts_structured_json_candidates_with_metadata():
    payload = json.dumps(
        {
            "candidates": [
                {
                    "dsl": 'filter(SUM(indicator("volume"), 3) > 300)',
                    "confidence": 0.91,
                    "rationale": "rolling volume sum",
                }
            ]
        }
    )

    candidates = extract_llm_dsl_candidates(payload)

    assert len(candidates) == 1
    assert candidates[0].dsl == 'filter(SUM(indicator("volume"), 3) > 300)'
    assert candidates[0].confidence == 0.91
    assert candidates[0].rationale == "rolling volume sum"


def test_extracts_openai_style_message_content_and_markdown_fences():
    payload = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": (
                            "Candidate DSL:\n"
                            "```findsl\n"
                            "filter(SUM(indicator(\"main_net_inflow\"), 3) > 4)\n"
                            "```"
                        )
                    }
                }
            ]
        }
    )

    candidates = extract_llm_dsl_candidates(payload)

    assert len(candidates) == 1
    assert candidates[0].dsl == 'filter(SUM(indicator("main_net_inflow"), 3) > 4)'
    assert candidates[0].source.endswith(".fence")


def test_extracts_openai_style_message_content_when_model_returns_json_text():
    payload = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "candidates": [
                                    {
                                        "dsl": 'filter(RET(indicator("close"), 2) > 0.05)',
                                        "confidence": 0.87,
                                        "rationale": "close return threshold",
                                    }
                                ]
                            }
                        )
                    }
                }
            ]
        }
    )

    candidates = extract_llm_dsl_candidates(payload)

    assert len(candidates) == 1
    assert candidates[0].dsl == 'filter(RET(indicator("close"), 2) > 0.05)'
    assert candidates[0].confidence == 0.87
    assert ".json_text" in candidates[0].source


def test_validate_llm_candidates_accepts_valid_dsl_and_rejects_unsafe_sql():
    payload = Path("data/samples/llm_candidate_response.json").read_text(encoding="utf-8")

    result = validate_llm_candidates(
        text="近3日成交量累计大于300",
        payload=payload,
        data_dir=DATA_DIR,
    )

    assert result.passed
    assert result.accepted_count == 1
    assert result.rejected_count == 2
    accepted = [candidate for candidate in result.candidates if candidate.accepted]
    rejected_codes = {
        diagnostic["code"]
        for candidate in result.candidates
        if not candidate.accepted
        for diagnostic in candidate.diagnostics
    }
    assert accepted[0].analysis["verification"]["passed"]
    assert "dwd_stock_daily_quote_prefix" in accepted[0].analysis["compile"]["sql"]
    assert "UNKNOWN_INDICATOR" in rejected_codes
    assert "UNSAFE_DIRECT_SQL" in rejected_codes


def test_validate_llm_candidates_reports_warning_when_everything_is_rejected():
    result = validate_llm_candidates(
        text="请选出收盘价大于10的股票",
        payload="SELECT * FROM dwd_stock_daily_quote WHERE close > 10",
        data_dir=DATA_DIR,
    )

    assert not result.passed
    assert result.accepted_count == 0
    assert result.rejected_count == 1
    assert result.warnings == ["all LLM candidates were rejected by the deterministic safety loop"]
    assert result.candidates[0].diagnostics[0]["code"] == "UNSAFE_DIRECT_SQL"

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .demo import analyze_dsl
from .diagnostics import diagnose_exception


SQL_KEYWORD_RE = re.compile(
    r"\b(SELECT|WITH|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE|MERGE|"
    r"EXPLAIN|FROM|JOIN|WHERE|GROUP\s+BY|ORDER\s+BY)\b",
    flags=re.IGNORECASE,
)
DSL_START_RE = re.compile(
    r"^\s*(?:then|filter|rank|CONS|EXIST|MA|SUM|MAX|MIN|market|indicator)\s*\(",
    flags=re.IGNORECASE,
)
CODE_FENCE_RE = re.compile(r"```(?:findsl|dsl|text|json)?\s*(?P<body>.*?)```", re.IGNORECASE | re.DOTALL)
LABELED_DSL_RE = re.compile(
    r"^[ \t]*(?:[-*][ \t]*)?(?:dsl|findsl|candidate(?:\s+dsl)?|候选dsl)[ \t]*[:：][ \t]*(?P<dsl>.+?)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
INLINE_DSL_RE = re.compile(
    r"`(?P<dsl>(?:then|filter|rank|CONS|EXIST|MA|SUM|MAX|MIN|market|indicator)\s*\([^`]+)`",
    re.IGNORECASE,
)

JSON_DSL_KEYS = {"dsl", "candidate", "candidate_dsl", "findsl", "expression"}
JSON_CONTAINER_KEYS = {"candidates", "dsl_candidates", "outputs", "choices", "items", "proposals", "results"}
JSON_TEXT_KEYS = {"content", "text", "answer", "message"}
DEFAULT_LLM_CANDIDATE_RESPONSE = Path("data/samples/llm_candidate_response.json")


@dataclass(frozen=True)
class LLMRawCandidate:
    dsl: str
    source: str
    rank: int
    confidence: Optional[float] = None
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dsl": self.dsl,
            "source": self.source,
            "rank": self.rank,
            "confidence": self.confidence,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class LLMValidatedCandidate:
    dsl: str
    source: str
    rank: int
    accepted: bool
    reason: str
    diagnostics: List[Dict[str, Any]]
    analysis: Optional[Dict[str, Any]] = None
    confidence: Optional[float] = None
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dsl": self.dsl,
            "source": self.source,
            "rank": self.rank,
            "accepted": self.accepted,
            "reason": self.reason,
            "diagnostics": list(self.diagnostics),
            "analysis": self.analysis,
            "confidence": self.confidence,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class LLMAdapterResult:
    text: str
    candidates: List[LLMValidatedCandidate]
    warnings: List[str]

    @property
    def raw_candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def accepted_count(self) -> int:
        return sum(1 for candidate in self.candidates if candidate.accepted)

    @property
    def rejected_count(self) -> int:
        return self.raw_candidate_count - self.accepted_count

    @property
    def passed(self) -> bool:
        return self.accepted_count > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "passed": self.passed,
            "text": self.text,
            "raw_candidate_count": self.raw_candidate_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "warnings": list(self.warnings),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


def extract_llm_dsl_candidates(payload: str, max_candidates: int = 5) -> List[LLMRawCandidate]:
    if max_candidates <= 0:
        return []

    raw_items: List[Dict[str, Any]] = []
    text = payload.strip()
    if not text:
        return []

    parsed = _try_json(text)
    if parsed is not None:
        _collect_from_json(parsed, raw_items, "json")
    else:
        _collect_from_text(text, raw_items, "text")

    if not raw_items:
        raw_items.append({"dsl": text, "source": "plain"})

    candidates: List[LLMRawCandidate] = []
    seen = set()
    for item in raw_items:
        cleaned = _clean_candidate(str(item.get("dsl", "")))
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        candidates.append(
            LLMRawCandidate(
                dsl=cleaned,
                source=str(item.get("source", "unknown")),
                rank=len(candidates) + 1,
                confidence=_as_optional_float(item.get("confidence")),
                rationale=str(item.get("rationale", "")),
            )
        )
        if len(candidates) >= max_candidates:
            break
    return candidates


def validate_llm_candidates(
    text: str,
    payload: str,
    data_dir: Path = Path("data/samples"),
    enable_prefix_sum: bool = True,
    verify: bool = True,
    max_candidates: int = 5,
) -> LLMAdapterResult:
    raw_candidates = extract_llm_dsl_candidates(payload, max_candidates=max_candidates)
    warnings: List[str] = []
    if not raw_candidates:
        warnings.append("no DSL candidates found in LLM payload")

    validated = [
        _validate_candidate(
            candidate,
            data_dir=Path(data_dir),
            enable_prefix_sum=enable_prefix_sum,
            verify=verify,
        )
        for candidate in raw_candidates
    ]
    if validated and not any(candidate.accepted for candidate in validated):
        warnings.append("all LLM candidates were rejected by the deterministic safety loop")
    return LLMAdapterResult(text=text, candidates=validated, warnings=warnings)


def _validate_candidate(
    candidate: LLMRawCandidate,
    data_dir: Path,
    enable_prefix_sum: bool,
    verify: bool,
) -> LLMValidatedCandidate:
    if _looks_like_sql(candidate.dsl):
        return _rejected(
            candidate,
            reason="direct SQL is rejected; LLM output must be FinDSL and pass the compiler",
            code="UNSAFE_DIRECT_SQL",
            message="The candidate contains SQL keywords and would bypass the deterministic compiler.",
            suggestions=[
                "Ask the model to return only a FinDSL expression such as filter(indicator(\"close\") > 10).",
                "Do not accept SELECT/WITH/JOIN SQL text from the LLM path.",
            ],
        )

    if not _looks_like_dsl(candidate.dsl):
        return _rejected(
            candidate,
            reason="payload item does not look like a FinDSL expression",
            code="NOT_DSL_CANDIDATE",
            message="The candidate does not start with a supported FinDSL function call.",
            suggestions=[
                "Return a complete FinDSL expression beginning with filter(...), then(...), or rank(...)."
            ],
        )

    try:
        analysis = analyze_dsl(
            candidate.dsl,
            data_dir=data_dir,
            enable_prefix_sum=enable_prefix_sum,
            verify=verify,
        )
        verification = analysis.get("verification") or {}
        accepted = bool(analysis.get("ok")) and (not verify or bool(verification.get("passed")))
        if accepted:
            reason = "compiled successfully and matched the independent SQL/reference oracle"
        else:
            reason = "compiled but failed SQL/reference equivalence verification"
        return LLMValidatedCandidate(
            dsl=candidate.dsl,
            source=candidate.source,
            rank=candidate.rank,
            accepted=accepted,
            reason=reason,
            diagnostics=[],
            analysis=analysis,
            confidence=candidate.confidence,
            rationale=candidate.rationale,
        )
    except Exception as exc:  # noqa: BLE001 - LLM candidate failures must become reviewable evidence.
        return LLMValidatedCandidate(
            dsl=candidate.dsl,
            source=candidate.source,
            rank=candidate.rank,
            accepted=False,
            reason=f"{type(exc).__name__}: {exc}",
            diagnostics=[diagnostic.to_dict() for diagnostic in diagnose_exception(exc)],
            analysis=None,
            confidence=candidate.confidence,
            rationale=candidate.rationale,
        )


def _collect_from_json(value: Any, out: List[Dict[str, Any]], source: str) -> None:
    if isinstance(value, dict):
        lowered = {str(key).lower(): key for key in value.keys()}
        for key_name in JSON_DSL_KEYS:
            original = lowered.get(key_name)
            if original is not None and isinstance(value[original], str):
                out.append(
                    {
                        "dsl": value[original],
                        "source": f"{source}.{key_name}",
                        "confidence": value.get("confidence"),
                        "rationale": value.get("rationale", ""),
                    }
                )
                return
        for key_name in JSON_CONTAINER_KEYS:
            original = lowered.get(key_name)
            if original is not None:
                _collect_from_json(value[original], out, f"{source}.{key_name}")
        for key_name in JSON_TEXT_KEYS:
            original = lowered.get(key_name)
            if original is not None and isinstance(value[original], str):
                _collect_from_text(value[original], out, f"{source}.{key_name}")
            elif original is not None and isinstance(value[original], (dict, list)):
                _collect_from_json(value[original], out, f"{source}.{key_name}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value, 1):
            if isinstance(item, str):
                if _looks_like_dsl(item) or _looks_like_sql(item):
                    out.append({"dsl": item, "source": f"{source}[{index}]"})
                else:
                    _collect_from_text(item, out, f"{source}[{index}]")
            else:
                _collect_from_json(item, out, f"{source}[{index}]")
        return
    if isinstance(value, str):
        _collect_from_text(value, out, source)


def _collect_from_text(text: str, out: List[Dict[str, Any]], source: str) -> None:
    parsed = _try_json(text.strip())
    if isinstance(parsed, (dict, list)):
        _collect_from_json(parsed, out, f"{source}.json_text")
        return

    for match in CODE_FENCE_RE.finditer(text):
        body = match.group("body").strip()
        parsed = _try_json(body)
        if parsed is not None:
            _collect_from_json(parsed, out, f"{source}.fence_json")
        elif body:
            out.append({"dsl": body, "source": f"{source}.fence"})

    for match in LABELED_DSL_RE.finditer(text):
        out.append({"dsl": match.group("dsl"), "source": f"{source}.label"})

    for match in INLINE_DSL_RE.finditer(text):
        out.append({"dsl": match.group("dsl"), "source": f"{source}.inline"})

    if (_looks_like_dsl(text) or _looks_like_sql(text)) and "\n" not in text.strip():
        out.append({"dsl": text, "source": source})


def _rejected(
    candidate: LLMRawCandidate,
    reason: str,
    code: str,
    message: str,
    suggestions: Sequence[str],
) -> LLMValidatedCandidate:
    return LLMValidatedCandidate(
        dsl=candidate.dsl,
        source=candidate.source,
        rank=candidate.rank,
        accepted=False,
        reason=reason,
        diagnostics=[
            {
                "code": code,
                "severity": "error",
                "message": message,
                "suggestions": list(suggestions),
            }
        ],
        analysis=None,
        confidence=candidate.confidence,
        rationale=candidate.rationale,
    )


def _try_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _clean_candidate(raw: str) -> str:
    text = raw.strip()
    text = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", text)
    if (text.startswith("`") and text.endswith("`")) or (text.startswith('"') and text.endswith('"')):
        text = text[1:-1].strip()
    if text.endswith(";") and not _looks_like_sql(text):
        text = text[:-1].rstrip()
    return text


def _looks_like_sql(text: str) -> bool:
    return bool(SQL_KEYWORD_RE.search(text))


def _looks_like_dsl(text: str) -> bool:
    return bool(DSL_START_RE.match(text.strip()))


def _as_optional_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

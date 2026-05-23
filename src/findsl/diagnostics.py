from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Dict, List, Sequence

from .errors import ConfigError, LexError, ParseError, SemanticError
from .registry import Registry, default_registry


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    message: str
    suggestions: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "suggestions": list(self.suggestions),
        }


def diagnose_exception(exc: Exception, registry: Registry = None) -> List[Diagnostic]:
    registry = registry or default_registry()
    message = str(exc)
    if isinstance(exc, ConfigError):
        return [_diagnose_config_error(message, registry)]
    if isinstance(exc, ParseError):
        return [_diagnose_parse_error(message)]
    if isinstance(exc, LexError):
        return [_diagnose_lex_error(message)]
    if isinstance(exc, SemanticError):
        return [_diagnose_semantic_error(message)]
    return [
        Diagnostic(
            code="GENERIC_ERROR",
            severity="error",
            message=message,
            suggestions=["Check the DSL syntax, indicator names, function names, and window arguments."],
        )
    ]


def _diagnose_config_error(message: str, registry: Registry) -> Diagnostic:
    indicator = _extract_after_colon(message, "Unknown indicator")
    if indicator:
        matches = _closest(indicator, registry.indicators.keys())
        suggestions = [
            f"Use a configured indicator such as {', '.join(matches)}."
            if matches
            else f"Add `{indicator}` to configs/indicators.json before using it."
        ]
        if matches:
            suggestions.append(f"Try indicator(\"{matches[0]}\") if that is the intended field.")
        return Diagnostic(
            code="UNKNOWN_INDICATOR",
            severity="error",
            message=message,
            suggestions=suggestions,
        )

    function = _extract_after_colon(message, "Unknown function")
    if function:
        matches = _closest(function, registry.functions.keys())
        suggestions = [
            f"Use a configured function such as {', '.join(matches)}."
            if matches
            else f"Add `{function}` to configs/functions.json before using it."
        ]
        return Diagnostic(
            code="UNKNOWN_FUNCTION",
            severity="error",
            message=message,
            suggestions=suggestions,
        )

    return Diagnostic(
        code="CONFIG_ERROR",
        severity="error",
        message=message,
        suggestions=["Inspect configs/indicators.json, configs/functions.json, and configs/tables.json."],
    )


def _diagnose_parse_error(message: str) -> Diagnostic:
    suggestions = ["Use function-call syntax such as filter(indicator(\"close\") > 10)."]
    if "Expected )" in message or "got EOF" in message:
        suggestions.insert(0, "Check for a missing closing parenthesis or quote near the end of the DSL.")
    if "Expected ," in message or "Expected )" in message:
        suggestions.append("Separate function arguments with commas and put named args after positional args.")
    return Diagnostic(
        code="PARSE_ERROR",
        severity="error",
        message=message,
        suggestions=_dedupe(suggestions),
    )


def _diagnose_lex_error(message: str) -> Diagnostic:
    suggestions = [
        "Use double quotes for string literals, for example indicator(\"close\").",
        "Keep DSL punctuation in ASCII form: parentheses, commas, comparison operators, &, and |.",
    ]
    if "Unclosed string" in message:
        suggestions.insert(0, "Add the missing closing double quote.")
    if "Invalid number literal" in message:
        suggestions.insert(0, "Use plain numeric literals such as 10, -5, or 0.25.")
    return Diagnostic(
        code="LEX_ERROR",
        severity="error",
        message=message,
        suggestions=_dedupe(suggestions),
    )


def _diagnose_semantic_error(message: str) -> Diagnostic:
    lower = message.lower()
    suggestions = ["Check function argument types against configs/functions.json."]
    if "then() stages" in lower:
        suggestions.insert(0, "Build pipelines as then(filter(...), rank(...)) or then(filter(...), filter(...)).")
    if "filter() condition" in lower:
        suggestions.insert(0, "filter() expects a boolean condition such as indicator(\"close\") > 10.")
    if "indicator()" in lower and "string or identifier" in lower:
        suggestions.insert(0, "Use indicator(\"close\") or another configured field name.")
    if "top-level dsl" in lower:
        suggestions.insert(0, "Wrap numeric expressions in filter(...), for example filter(indicator(\"close\") > 10).")
    if "bare identifier" in lower:
        match = re.search(r"bare identifier (?P<name>[A-Za-z_][A-Za-z0-9_]*)", message)
        name = match.group("name") if match else "close"
        suggestions.insert(0, f"Wrap configured fields as indicator(\"{name}\") instead of using bare column names.")
    if "window" in lower:
        suggestions.insert(0, "Use a positive integer window, for example MA(indicator(\"close\"), 20).")
    if "boolean" in lower:
        suggestions.insert(0, "Wrap numeric expressions in comparisons before using CONS/EXIST/filter.")
    if "numeric" in lower:
        suggestions.insert(0, "Use indicator(...), a numeric literal, or a numeric window function in numeric positions.")
    if "does not allow named arg" in lower:
        named_match = re.search(
            r"(?P<function>[A-Za-z_][A-Za-z0-9_]*) does not allow named arg (?P<name>[A-Za-z_][A-Za-z0-9_]*)",
            message,
        )
        function_name = named_match.group("function").lower() if named_match else ""
        arg_name = named_match.group("name") if named_match else "close"
        if function_name == "filter":
            suggestions.insert(0, f"Use a comparison expression such as filter(indicator(\"{arg_name}\") = 10).")
        elif function_name == "rank":
            suggestions.insert(0, "For rank(), supported named args are top, bottom, and percent.")
        else:
            suggestions.insert(0, "Remove unsupported named arguments or move them into positional expressions.")
    if "rank()" in lower and "named arg" in lower:
        suggestions.insert(0, "For rank(), supported named args are top, bottom, and percent.")
    if "rank()" in lower and ("top" in lower or "bottom" in lower):
        suggestions.insert(0, "Use rank(..., desc, top=N) for high values or rank(..., asc, bottom=N) for low values.")
    if "percent" in lower:
        suggestions.insert(0, "For rank(..., percent=N), use 0 < N <= 100 and do not combine it with top/bottom.")
    if "date_between" in lower or "iso date" in lower:
        suggestions.insert(0, "Use date_between(\"YYYY-MM-DD\", \"YYYY-MM-DD\") with start date <= end date.")
    if "market()" in lower:
        suggestions.insert(0, "Use market(\"A\") or market(\"B\") with a string market code.")
    if "division by zero" in lower:
        suggestions.insert(0, "Use a non-zero denominator or remove the literal `/ 0` from the numeric expression.")
    return Diagnostic(
        code="SEMANTIC_ERROR",
        severity="error",
        message=message,
        suggestions=_dedupe(suggestions),
    )


def _extract_after_colon(message: str, prefix: str) -> str:
    match = re.search(rf"{re.escape(prefix)}:\s*(?P<value>[A-Za-z0-9_]+)", message)
    return match.group("value") if match else ""


def _closest(value: str, choices: Sequence[str]) -> List[str]:
    return difflib.get_close_matches(value, list(choices), n=3, cutoff=0.45)


def _dedupe(items: Sequence[str]) -> List[str]:
    return list(dict.fromkeys(items))

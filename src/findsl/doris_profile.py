from __future__ import annotations

import re
from dataclasses import dataclass


class DorisProfileError(ValueError):
    pass


_DURATION = re.compile(
    r"(?:(?P<hours>\d+)hour)?"
    r"(?:(?P<minutes>\d+)min)?"
    r"(?:(?P<seconds>\d+)sec)?"
    r"(?:(?P<milliseconds>\d+(?:\.\d+)?)ms)?"
    r"(?:(?P<microseconds>\d+(?:\.\d+)?)us)?"
    r"(?:(?P<nanoseconds>\d+(?:\.\d+)?)ns)?\Z"
)


@dataclass(frozen=True)
class DorisProfileSummary:
    profile_id: str
    total_text: str
    total_ms: float
    task_state: str
    doris_version: str
    is_cached: bool


def parse_doris_duration(value: str) -> float:
    text = str(value).strip()
    match = _DURATION.fullmatch(text)
    if match is None or not any(match.groupdict().values()):
        raise DorisProfileError(f"invalid Doris duration: {value}")
    parts = {key: float(item or 0) for key, item in match.groupdict().items()}
    return (
        parts["hours"] * 3_600_000
        + parts["minutes"] * 60_000
        + parts["seconds"] * 1_000
        + parts["milliseconds"]
        + parts["microseconds"] / 1_000
        + parts["nanoseconds"] / 1_000_000
    )


def parse_profile_summary(profile: str) -> DorisProfileSummary:
    text = str(profile)
    summary_text = text.split("Execution Summary:", 1)[0]
    fields = {
        key.strip(): value.strip()
        for key, value in re.findall(r"^\s*-\s+([^:]+):\s*(.*?)\s*$", summary_text, re.M)
    }
    execution_fields = {
        key.strip(): value.strip()
        for key, value in re.findall(r"^\s*-\s+([^:]+):\s*(.*?)\s*$", text, re.M)
    }
    required = ("Profile ID", "Total", "Task State")
    missing = [key for key in required if not fields.get(key)]
    if missing:
        raise DorisProfileError(
            f"Doris profile summary is missing: {', '.join(missing)}"
        )
    cached = execution_fields.get("Is Cached", "").casefold()
    if cached not in {"yes", "no", "true", "false"}:
        raise DorisProfileError("Doris profile does not expose a valid Is Cached field")
    total_text = fields["Total"]
    return DorisProfileSummary(
        profile_id=fields["Profile ID"],
        total_text=total_text,
        total_ms=parse_doris_duration(total_text),
        task_state=fields["Task State"],
        doris_version=execution_fields.get("Doris Version", ""),
        is_cached=cached in {"yes", "true"},
    )


def explain_partition_ratios(explain: str):
    return tuple(
        (int(selected), int(total))
        for selected, total in re.findall(r"partitions=(\d+)/(\d+)", str(explain))
    )

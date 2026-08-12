from __future__ import annotations

from typing import Optional

from sqlglot import exp

from ..physical.catalog import PhysicalCatalog
from .errors import DorisBackendError


def calendar_bucket_key(relation_name: str, unit: str):
    granularity = {"周": "WEEK", "月": "MONTH", "季度": "QUARTER", "年": "YEAR"}[unit]
    return exp.DateTrunc(
        this=exp.column("bizdate", table=relation_name, quoted=True),
        unit=exp.Literal.string(granularity),
    )


def calendar_bucket_ordinal(bucket_key, unit: str):
    if unit == "年":
        return exp.func("YEAR", bucket_key.copy())
    if unit == "月":
        return exp.Add(
            this=exp.Mul(this=exp.func("YEAR", bucket_key.copy()), expression=exp.convert(12)),
            expression=exp.func("MONTH", bucket_key.copy()),
        )
    if unit == "季度":
        return exp.Add(
            this=exp.Mul(this=exp.func("YEAR", bucket_key.copy()), expression=exp.convert(4)),
            expression=exp.func("QUARTER", bucket_key.copy()),
        )
    return exp.Floor(
        this=exp.Div(
            this=exp.func("UNIX_TIMESTAMP", bucket_key.copy()),
            expression=exp.convert(604800),
        )
    )


def date_shift(value, amount: int, unit: str):
    if amount == 0:
        return value
    operator = exp.DateAdd if amount > 0 else exp.DateSub
    return operator(
        this=value,
        expression=exp.Literal.string(str(abs(amount))),
        unit=exp.Var(this=unit.upper()),
    )


def date_trunc(value, unit: str):
    return exp.DateTrunc(this=value, unit=exp.Literal.string(unit.upper()))


def dynamic_date_bounds(
    catalog: PhysicalCatalog,
    resource_id: str,
    range_kind: str,
    unit: str,
    amount: int,
    offset: int,
    month: Optional[int],
    day: Optional[int],
    end_month: Optional[int] = None,
    anchor_resource_id: Optional[str] = None,
    weekday_start: Optional[int] = None,
    weekday_end: Optional[int] = None,
):
    anchor = latest_resource_anchor(catalog, anchor_resource_id or resource_id)
    validity = None
    if range_kind == "period":
        current_start = date_trunc(anchor.copy(), unit)
        lower = date_shift(current_start.copy(), offset, unit)
        upper = anchor.copy() if offset == 0 else date_shift(date_shift(current_start.copy(), offset + 1, unit), -1, "day")
        return lower, upper, validity
    if range_kind == "weekday_range":
        if weekday_start is None or weekday_end is None or weekday_start > weekday_end:
            raise DorisBackendError(
                "DORIS_DATE_RANGE_UNSUPPORTED",
                "weekday range requires ordered weekday boundaries",
            )
        week_start = date_shift(date_trunc(anchor.copy(), "week"), offset, "week")
        return (
            date_shift(week_start.copy(), weekday_start - 1, "day"),
            date_shift(week_start.copy(), weekday_end - 1, "day"),
            validity,
        )
    if range_kind == "recent":
        if unit == "week":
            lower = date_shift(anchor.copy(), -(amount * 7 - 1), "day")
        elif unit == "month":
            lower = date_shift(date_shift(anchor.copy(), -amount, "month"), 1, "day")
        elif unit == "year":
            lower = date_trunc(date_shift(anchor.copy(), -(amount - 1), "year"), "year")
        else:
            raise DorisBackendError(
                "DORIS_DATE_RANGE_UNSUPPORTED",
                f"unsupported recent calendar unit {unit}",
            )
        return lower, anchor.copy(), validity
    if range_kind == "anchor_calendar":
        base = date_trunc(anchor.copy(), "month") if month is None else date_shift(
            date_trunc(anchor.copy(), "year"), month - 1 + offset, "month"
        )
        if day is not None:
            lower = date_shift(base.copy(), day - 1, "day")
            upper = lower.copy()
            expected_month = exp.convert(month) if month is not None else exp.func("MONTH", anchor.copy())
            validity = exp.EQ(this=exp.func("MONTH", lower.copy()), expression=expected_month)
        else:
            lower = base.copy()
            upper = date_shift(date_shift(base.copy(), 1, "month"), -1, "day")
        return lower, upper, validity
    if range_kind == "year_month_range":
        if month is None or end_month is None:
            raise DorisBackendError(
                "DORIS_DATE_RANGE_UNSUPPORTED",
                "year month range requires both month boundaries",
            )
        year_start = date_trunc(anchor.copy(), "year")
        lower = date_shift(year_start.copy(), month - 1, "month")
        upper = date_shift(date_shift(year_start.copy(), end_month, "month"), -1, "day")
        return lower, upper, validity
    raise DorisBackendError(
        "DORIS_DATE_RANGE_UNSUPPORTED",
        f"unsupported dynamic date range kind {range_kind}",
    )


def latest_resource_anchor(catalog: PhysicalCatalog, resource_id: str) -> exp.Subquery:
    resource = catalog.resource(resource_id)
    if resource.partition_key is None:
        raise DorisBackendError(
            "DORIS_DATE_ANCHOR_UNAVAILABLE",
            f"resource {resource_id} has no partition key",
        )
    query = exp.select(
        exp.Max(this=exp.column(resource.partition_key, table="calendar_anchor", quoted=True))
    ).from_(
        exp.table_(resource.table, db=resource.database, quoted=True, alias="calendar_anchor")
    )
    return exp.Subquery(this=query)

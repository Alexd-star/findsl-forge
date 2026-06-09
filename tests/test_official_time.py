from findsl.official_time import normalize_official_date


def test_normalize_empty_official_date_has_no_constraint_or_warning():
    result = normalize_official_date("", anchor_date="2026-04-14")

    assert result.constraints == []
    assert result.warnings == []


def test_normalize_current_day_aliases_to_official_anchor_date():
    for text in ["今天", "今日", "当前", "目前", "当日", "当天", "本日"]:
        result = normalize_official_date(text, anchor_date="2026-04-14")

        assert result.constraints == ["base.bizdate = '2026-04-14'"]
        assert result.warnings == []


def test_normalize_relative_day_uses_trading_calendar_when_supplied():
    trading_dates = ["2026-04-09", "2026-04-10", "2026-04-13", "2026-04-14"]

    yesterday = normalize_official_date("昨天", anchor_date="2026-04-14", trading_dates=trading_dates)
    previous = normalize_official_date("上个交易日", anchor_date="2026-04-14", trading_dates=trading_dates)
    before_yesterday = normalize_official_date("前天", anchor_date="2026-04-14", trading_dates=trading_dates)

    assert yesterday.constraints == ["base.bizdate = '2026-04-13'"]
    assert previous.constraints == ["base.bizdate = '2026-04-13'"]
    assert before_yesterday.constraints == ["base.bizdate = '2026-04-10'"]


def test_normalize_recent_n_days_uses_trading_calendar_window():
    trading_dates = ["2026-04-08", "2026-04-09", "2026-04-10", "2026-04-13", "2026-04-14"]

    result = normalize_official_date("近3日", anchor_date="2026-04-14", trading_dates=trading_dates)

    assert result.constraints == ["base.bizdate BETWEEN '2026-04-10' AND '2026-04-14'"]
    assert result.warnings == []


def test_normalize_common_chinese_year_and_period_forms():
    cases = {
        "2024年": "base.bizdate BETWEEN '2024-01-01' AND '2024-12-31'",
        "24年": "base.bizdate BETWEEN '2024-01-01' AND '2024-12-31'",
        "二二年": "base.bizdate BETWEEN '2022-01-01' AND '2022-12-31'",
        "零八年": "base.bizdate BETWEEN '2008-01-01' AND '2008-12-31'",
        "今年": "base.bizdate BETWEEN '2026-01-01' AND '2026-04-14'",
        "本月": "base.bizdate BETWEEN '2026-04-01' AND '2026-04-14'",
        "本周": "base.bizdate BETWEEN '2026-04-13' AND '2026-04-14'",
    }

    for text, expected in cases.items():
        result = normalize_official_date(text, anchor_date="2026-04-14")

        assert result.constraints == [expected]
        assert result.warnings == []


def test_unknown_official_date_returns_visible_warning_without_fabricating_filter():
    result = normalize_official_date("本周的后3日", anchor_date="2026-04-14")

    assert result.constraints == ["1=0"]
    assert result.warnings == [
        "date slot '本周的后3日' starts after official anchor date 2026-04-14; no official rows can satisfy it"
    ]


def test_normalize_composite_relative_day_before_anchor_expression():
    trading_dates = ["2026-04-09", "2026-04-10", "2026-04-13", "2026-04-14"]

    result = normalize_official_date(
        "昨天的前1日",
        anchor_date="2026-04-14",
        trading_dates=trading_dates,
    )

    assert result.constraints == ["base.bizdate = '2026-04-10'"]
    assert result.warnings == []


def test_normalize_composite_previous_week_from_month_interval():
    result = normalize_official_date("本月的前一周", anchor_date="2026-04-14")

    assert result.constraints == ["base.bizdate BETWEEN '2026-03-25' AND '2026-03-31'"]
    assert result.warnings == []


def test_normalize_composite_year_offsets_are_calendar_intervals():
    cases = {
        "2012年的后4年": "base.bizdate BETWEEN '2013-01-01' AND '2016-12-31'",
        "一二年的第4年": "base.bizdate BETWEEN '2015-01-01' AND '2015-12-31'",
        "2018年的第五年": "base.bizdate BETWEEN '2022-01-01' AND '2022-12-31'",
    }

    for text, expected in cases.items():
        result = normalize_official_date(text, anchor_date="2026-04-14")

        assert result.constraints == [expected]
        assert result.warnings == []


def test_normalize_explicit_official_year_ranges():
    cases = {
        "2006年-12年": "base.bizdate BETWEEN '2006-01-01' AND '2012-12-31'",
        "2006年-2012年": "base.bizdate BETWEEN '2006-01-01' AND '2012-12-31'",
        "2006年至12年": "base.bizdate BETWEEN '2006-01-01' AND '2012-12-31'",
        "06年到12年": "base.bizdate BETWEEN '2006-01-01' AND '2012-12-31'",
    }

    for text, expected in cases.items():
        result = normalize_official_date(text, anchor_date="2026-04-14")

        assert result.constraints == [expected]
        assert result.warnings == []


def test_normalize_recent_nth_day_and_following_window():
    trading_dates = ["2026-04-09", "2026-04-10", "2026-04-13", "2026-04-14"]

    second_latest = normalize_official_date(
        "最近的第二天",
        anchor_date="2026-04-14",
        trading_dates=trading_dates,
    )
    following = normalize_official_date(
        "最近的第二天的后3日",
        anchor_date="2026-04-14",
        trading_dates=trading_dates,
    )

    assert second_latest.constraints == ["base.bizdate = '2026-04-13'"]
    assert second_latest.warnings == []
    assert following.constraints == ["base.bizdate = '2026-04-14'"]
    assert following.warnings == [
        "date slot '最近的第二天的后3日' extends beyond official anchor date 2026-04-14; clipped to available official data"
    ]

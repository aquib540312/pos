"""Business-day helpers for local timezone.

Documents (invoices, GRNs, returns) carry a tax compliance date, and every
date-filtered report (sales summary, P&L, dashboard) must slice on the
*business* day -- midnight-to-midnight in the local timezone -- not the
UTC day.  All timestamps are stored UTC; these helpers translate between a
business date and the UTC instants that bound it.

The module exposes AST (Saudi Arabia, UTC+3) as the default, keeping the
legacy IST names as aliases so existing call-sites don't break.
"""

from datetime import date, datetime, time, timedelta, timezone

# AST = Arabia Standard Time (UTC+3)
AST = timezone(timedelta(hours=3))
# Legacy alias kept for backward compatibility
IST = AST


def ist_now() -> datetime:
    return datetime.now(tz=AST)


def ist_today() -> date:
    return ist_now().date()


def as_ist_day(value: datetime) -> date:
    """The business calendar date an aware UTC timestamp falls on. Naive
    timestamps (SQLite) are assumed to already be UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(AST).date()


def ist_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """(start, end) UTC instants that span the business day `day`, i.e.
    [midnight local, 23:59:59.999999 local] expressed in UTC."""
    start = datetime.combine(day, time.min, tzinfo=AST).astimezone(timezone.utc)
    end = datetime.combine(day, time.max, tzinfo=AST).astimezone(timezone.utc)
    return start, end


def ist_range_bounds_utc(start_day: date, end_day: date) -> tuple[datetime, datetime]:
    """(start, end) UTC instants covering a whole date range as business
    days: [start_day's midnight, end_day's 23:59:59.999999] in UTC."""
    start, _ = ist_day_bounds_utc(start_day)
    _, end = ist_day_bounds_utc(end_day)
    return start, end

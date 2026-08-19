"""Asia/Kolkata (IST) business-day helpers.

The platform is an Indian retail POS: documents (invoices, GRNs, returns)
carry a GST compliance date, and every date-filtered report (sales summary,
GSTR-1, P&L, dashboard) must slice on the *business* day -- midnight-to-
midnight in IST -- not the UTC day. All timestamps are stored UTC; these
helpers translate between a Kolkata business date and the UTC instants that
bound it, so SQL comparisons over UTC columns stay correct on every dialect.

`as_ist_day` is lenient about naive datetimes because SQLite returns naive
values for DateTime(timezone=True) columns while Postgres returns aware ones.
"""

from datetime import date, datetime, time, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def ist_now() -> datetime:
    return datetime.now(tz=IST)


def ist_today() -> date:
    return ist_now().date()


def as_ist_day(value: datetime) -> date:
    """The Kolkata calendar date an aware UTC timestamp falls on. Naive
    timestamps (SQLite) are assumed to already be UTC, matching how the app
    stores `datetime.now(timezone.utc)` everywhere else."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(IST).date()


def ist_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """(start, end) UTC instants that span the IST business day `day`, i.e.
    [midnight IST, 23:59:59.999999 IST] expressed in UTC. Use these against
    UTC-stored DateTime columns in WHERE clauses."""
    start = datetime.combine(day, time.min, tzinfo=IST).astimezone(timezone.utc)
    end = datetime.combine(day, time.max, tzinfo=IST).astimezone(timezone.utc)
    return start, end


def ist_range_bounds_utc(start_day: date, end_day: date) -> tuple[datetime, datetime]:
    """(start, end) UTC instants covering a whole date range as IST business
    days: [start_day's IST midnight, end_day's IST 23:59:59.999999] in UTC.
    This is the one to use for date-filtered reports -- slicing with the
    start day's bounds alone would drop every sale after the first day."""
    start, _ = ist_day_bounds_utc(start_day)
    _, end = ist_day_bounds_utc(end_day)
    return start, end

"""
Date and time utilities.
"""

from datetime import datetime, timedelta

import pandas as pd


def get_trading_days(
    start_date: datetime,
    end_date: datetime,
    calendar: str = "NYSE"
) -> pd.DatetimeIndex:
    """
    Get trading days between two dates.
    
    Args:
        start_date: Start date
        end_date: End date
        calendar: Trading calendar to use
    
    Returns:
        DatetimeIndex of trading days
    """
    try:
        from pandas.tseries.holiday import USFederalHolidayCalendar
        from pandas.tseries.offsets import CustomBusinessDay

        cal = USFederalHolidayCalendar()
        bday = CustomBusinessDay(calendar=cal)

        return pd.date_range(start=start_date, end=end_date, freq=bday)
    except:
        # Fallback to simple business days
        return pd.bdate_range(start=start_date, end=end_date)


def is_trading_day(date: datetime, calendar: str = "NYSE") -> bool:
    """Check if date is a trading day."""
    trading_days = get_trading_days(date, date, calendar)
    return len(trading_days) > 0


def next_trading_day(date: datetime, calendar: str = "NYSE") -> datetime:
    """Get next trading day."""
    next_day = date + timedelta(days=1)
    trading_days = get_trading_days(next_day, next_day + timedelta(days=7), calendar)
    return trading_days[0].to_pydatetime() if len(trading_days) > 0 else next_day


def previous_trading_day(date: datetime, calendar: str = "NYSE") -> datetime:
    """Get previous trading day."""
    prev_day = date - timedelta(days=1)
    trading_days = get_trading_days(prev_day - timedelta(days=7), prev_day, calendar)
    return trading_days[-1].to_pydatetime() if len(trading_days) > 0 else prev_day


def trading_days_between(
    start_date: datetime,
    end_date: datetime,
    calendar: str = "NYSE"
) -> int:
    """Count trading days between two dates."""
    trading_days = get_trading_days(start_date, end_date, calendar)
    return len(trading_days)


def add_trading_days(
    date: datetime,
    n_days: int,
    calendar: str = "NYSE"
) -> datetime:
    """Add N trading days to a date."""
    if n_days == 0:
        return date

    direction = 1 if n_days > 0 else -1
    n_days = abs(n_days)

    current = date
    count = 0

    while count < n_days:
        if direction > 0:
            current = next_trading_day(current, calendar)
        else:
            current = previous_trading_day(current, calendar)
        count += 1

    return current

"""
Time utilities for market hours and trading days
"""

from datetime import datetime, time, timedelta
from typing import Tuple, List, Optional
import pytz
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay
from loguru import logger


class MarketCalendar:
    """US Stock Market calendar utilities"""

    # Market hours (NYSE/NASDAQ)
    MARKET_OPEN = time(9, 30)
    MARKET_CLOSE = time(16, 0)
    PRE_MARKET_OPEN = time(4, 0)
    AFTER_MARKET_CLOSE = time(20, 0)

    # Timezone
    MARKET_TZ = pytz.timezone("America/New_York")

    # Business day calendar (excludes weekends and US federal holidays)
    _calendar = USFederalHolidayCalendar()
    _business_day = CustomBusinessDay(calendar=_calendar)

    @classmethod
    def get_market_hours(cls, date: Optional[datetime] = None) -> Tuple[datetime, datetime]:
        """
        Get market open and close times for a given date

        Args:
            date: Date to check (default: today)

        Returns:
            Tuple of (market_open, market_close) datetimes
        """
        if date is None:
            date = datetime.now(cls.MARKET_TZ)
        elif date.tzinfo is None:
            date = cls.MARKET_TZ.localize(date)

        market_open = datetime.combine(date.date(), cls.MARKET_OPEN)
        market_close = datetime.combine(date.date(), cls.MARKET_CLOSE)

        market_open = cls.MARKET_TZ.localize(market_open)
        market_close = cls.MARKET_TZ.localize(market_close)

        return market_open, market_close

    @classmethod
    def is_market_open(cls, dt: Optional[datetime] = None) -> bool:
        """
        Check if market is currently open

        Args:
            dt: Datetime to check (default: now)

        Returns:
            True if market is open
        """
        if dt is None:
            dt = datetime.now(cls.MARKET_TZ)
        elif dt.tzinfo is None:
            dt = cls.MARKET_TZ.localize(dt)

        # Check if it's a weekday
        if dt.weekday() >= 5:  # Saturday or Sunday
            return False

        # Check if it's a holiday
        if cls.is_holiday(dt):
            return False

        # Check if it's within market hours
        market_open, market_close = cls.get_market_hours(dt)
        return market_open <= dt <= market_close

    @classmethod
    def is_holiday(cls, date: datetime) -> bool:
        """Check if date is a market holiday"""
        holidays = cls._calendar.holidays(
            start=date.date(), end=date.date(), return_name=True
        )
        return len(holidays) > 0

    @classmethod
    def get_next_market_open(cls, dt: Optional[datetime] = None) -> datetime:
        """
        Get the next market open time

        Args:
            dt: Starting datetime (default: now)

        Returns:
            Next market open datetime
        """
        if dt is None:
            dt = datetime.now(cls.MARKET_TZ)
        elif dt.tzinfo is None:
            dt = cls.MARKET_TZ.localize(dt)

        # If market is currently open, return current time
        if cls.is_market_open(dt):
            return dt

        # Check today's market open
        market_open, market_close = cls.get_market_hours(dt)

        # If before today's open and not a holiday, return today's open
        if dt < market_open and not cls.is_holiday(dt):
            return market_open

        # Otherwise, find next trading day
        next_day = dt.date() + timedelta(days=1)
        while True:
            if cls.is_trading_day(next_day):
                return cls.MARKET_TZ.localize(
                    datetime.combine(next_day, cls.MARKET_OPEN)
                )
            next_day += timedelta(days=1)

    @classmethod
    def get_next_market_close(cls, dt: Optional[datetime] = None) -> datetime:
        """Get the next market close time"""
        if dt is None:
            dt = datetime.now(cls.MARKET_TZ)
        elif dt.tzinfo is None:
            dt = cls.MARKET_TZ.localize(dt)

        market_open, market_close = cls.get_market_hours(dt)

        # If before today's close and market is open today, return today's close
        if dt < market_close and cls.is_trading_day(dt.date()):
            return market_close

        # Otherwise, get next trading day's close
        next_open = cls.get_next_market_open(dt)
        return cls.get_market_hours(next_open)[1]

    @classmethod
    def is_trading_day(cls, date) -> bool:
        """Check if date is a trading day"""
        if isinstance(date, datetime):
            date = date.date()

        # Check weekday
        if pd.Timestamp(date).weekday() >= 5:
            return False

        # Check holiday
        holidays = cls._calendar.holidays(start=date, end=date)
        return len(holidays) == 0

    @classmethod
    def get_trading_days(
        cls, start_date: datetime, end_date: datetime
    ) -> List[datetime]:
        """
        Get list of trading days between two dates

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of trading days
        """
        trading_days = pd.bdate_range(
            start=start_date, end=end_date, freq=cls._business_day
        )
        return [day.to_pydatetime() for day in trading_days]

    @classmethod
    def get_trading_days_count(
        cls, start_date: datetime, end_date: datetime
    ) -> int:
        """Get number of trading days between two dates"""
        return len(cls.get_trading_days(start_date, end_date))

    @classmethod
    def time_to_market_open(cls, dt: Optional[datetime] = None) -> timedelta:
        """Get time remaining until market opens"""
        if dt is None:
            dt = datetime.now(cls.MARKET_TZ)

        next_open = cls.get_next_market_open(dt)
        return next_open - dt

    @classmethod
    def time_to_market_close(cls, dt: Optional[datetime] = None) -> timedelta:
        """Get time remaining until market closes"""
        if dt is None:
            dt = datetime.now(cls.MARKET_TZ)

        next_close = cls.get_next_market_close(dt)
        return next_close - dt


# Convenience functions
def get_market_hours(date: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """Get market open and close times"""
    return MarketCalendar.get_market_hours(date)


def is_market_open(dt: Optional[datetime] = None) -> bool:
    """Check if market is currently open"""
    return MarketCalendar.is_market_open(dt)


def get_next_market_open(dt: Optional[datetime] = None) -> datetime:
    """Get next market open time"""
    return MarketCalendar.get_next_market_open(dt)


def get_next_market_close(dt: Optional[datetime] = None) -> datetime:
    """Get next market close time"""
    return MarketCalendar.get_next_market_close(dt)


def is_trading_day(date) -> bool:
    """Check if date is a trading day"""
    return MarketCalendar.is_trading_day(date)


def get_trading_days(start_date: datetime, end_date: datetime) -> List[datetime]:
    """Get list of trading days"""
    return MarketCalendar.get_trading_days(start_date, end_date)


def get_current_market_status() -> dict:
    """
    Get comprehensive market status

    Returns:
        Dictionary with market status information
    """
    now = datetime.now(MarketCalendar.MARKET_TZ)
    is_open = is_market_open(now)

    status = {
        "current_time": now,
        "is_open": is_open,
        "is_trading_day": is_trading_day(now),
        "is_holiday": MarketCalendar.is_holiday(now),
    }

    if is_open:
        status["time_to_close"] = MarketCalendar.time_to_market_close(now)
        status["next_close"] = get_next_market_close(now)
    else:
        status["time_to_open"] = MarketCalendar.time_to_market_open(now)
        status["next_open"] = get_next_market_open(now)

    return status


def wait_for_market_open(check_interval: int = 60):
    """
    Wait until market opens (blocking)

    Args:
        check_interval: How often to check (seconds)
    """
    import time

    while not is_market_open():
        time_to_open = MarketCalendar.time_to_market_open()
        logger.info(f"Market closed. Opens in {time_to_open}")
        time.sleep(min(check_interval, time_to_open.total_seconds()))

    logger.info("Market is now open!")

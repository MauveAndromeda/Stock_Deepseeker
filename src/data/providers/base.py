"""
Base data provider interface.

Defines the contract that all data providers must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd


class DataProviderType(Enum):
    """Data provider types."""
    YAHOO_FINANCE = "yahoo"
    POLYGON = "polygon"
    ALPACA = "alpaca"
    IEX = "iex"
    ALPHA_VANTAGE = "alpha_vantage"
    QUANDL = "quandl"
    CACHED = "cached"


class DataProviderError(Exception):
    """Base exception for data provider errors."""


class DataFetchError(DataProviderError):
    """Raised when data fetching fails."""


class DataValidationError(DataProviderError):
    """Raised when data validation fails."""


@dataclass
class PriceData:
    """
    Price data container.

    Attributes:
        symbol: Stock symbol
        data: DataFrame with OHLCV data
        start_date: Start date of data
        end_date: End date of data
        adjusted: Whether data is adjusted for splits/dividends
        provider: Source provider
        fetch_time: When data was fetched
        metadata: Additional metadata
    """
    symbol: str
    data: pd.DataFrame
    start_date: datetime
    end_date: datetime
    adjusted: bool = True
    provider: DataProviderType = DataProviderType.YAHOO_FINANCE
    fetch_time: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate price data after initialization."""
        required_columns = ["open", "high", "low", "close", "volume"]
        missing = set(required_columns) - set(self.data.columns.str.lower())
        if missing:
            raise DataValidationError(f"Missing required columns: {missing}")

        # Ensure datetime index
        if not isinstance(self.data.index, pd.DatetimeIndex):
            raise DataValidationError("Data must have DatetimeIndex")

        # Validate data integrity
        if len(self.data) == 0:
            raise DataValidationError(f"Empty data for {self.symbol}")

        # Check for negative prices
        price_cols = ["open", "high", "low", "close"]
        for col in price_cols:
            if (self.data[col] < 0).any():
                raise DataValidationError(f"Negative prices found in {col}")

        # Check high >= low
        if (self.data["high"] < self.data["low"]).any():
            raise DataValidationError("High prices less than low prices")

    def get_returns(self, periods: int = 1) -> pd.Series:
        """Calculate returns."""
        return self.data["close"].pct_change(periods=periods)

    def get_log_returns(self, periods: int = 1) -> pd.Series:
        """Calculate log returns."""
        return np.log(self.data["close"] / self.data["close"].shift(periods))

    def resample(self, freq: str = "1D") -> pd.DataFrame:
        """Resample data to different frequency."""
        resampled = self.data.resample(freq).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        })
        return resampled.dropna()


@dataclass
class FundamentalData:
    """
    Fundamental data container.

    Attributes:
        symbol: Stock symbol
        data: Dict of fundamental metrics
        report_date: Date of the report
        period_type: quarterly or annual
        provider: Source provider
        fetch_time: When data was fetched
    """
    symbol: str
    data: dict[str, Any]
    report_date: datetime
    period_type: str = "quarterly"  # or "annual"
    provider: DataProviderType = DataProviderType.YAHOO_FINANCE
    fetch_time: datetime = field(default_factory=datetime.now)

    def get_metric(self, name: str, default: Any = None) -> Any:
        """Get a specific fundamental metric."""
        return self.data.get(name, default)

    def to_series(self) -> pd.Series:
        """Convert to pandas Series."""
        return pd.Series(self.data, name=self.report_date)


@dataclass
class CorporateAction:
    """
    Corporate action (split, dividend, etc.).

    Attributes:
        symbol: Stock symbol
        action_type: Type of action (split, dividend, etc.)
        ex_date: Ex-dividend or ex-split date
        value: Numerical value (split ratio, dividend amount)
        currency: Currency for dividends
        metadata: Additional metadata
    """
    symbol: str
    action_type: str  # 'split', 'dividend', 'merger', 'spinoff'
    ex_date: datetime
    value: float
    currency: str = "USD"
    metadata: dict[str, Any] = field(default_factory=dict)


class DataProvider(ABC):
    """
    Abstract base class for data providers.

    All data providers must implement these methods.
    """

    def __init__(self, api_key: str | None = None, **kwargs: Any) -> None:
        """
        Initialize data provider.

        Args:
            api_key: API key for the provider
            **kwargs: Additional provider-specific parameters
        """
        self.api_key = api_key
        self.config = kwargs

    @abstractmethod
    def get_historical_prices(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        adjusted: bool = True,
        **kwargs: Any
    ) -> PriceData:
        """
        Fetch historical price data.

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            adjusted: Whether to adjust for splits/dividends
            **kwargs: Additional parameters

        Returns:
            PriceData object

        Raises:
            DataFetchError: If fetching fails
            DataValidationError: If validation fails
        """

    @abstractmethod
    def get_fundamentals(
        self,
        symbol: str,
        report_date: datetime | None = None,
        **kwargs: Any
    ) -> FundamentalData:
        """
        Fetch fundamental data.

        Args:
            symbol: Stock symbol
            report_date: Specific report date (None for latest)
            **kwargs: Additional parameters

        Returns:
            FundamentalData object

        Raises:
            DataFetchError: If fetching fails
        """

    @abstractmethod
    def get_corporate_actions(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any
    ) -> list[CorporateAction]:
        """
        Fetch corporate actions (splits, dividends).

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            **kwargs: Additional parameters

        Returns:
            List of CorporateAction objects

        Raises:
            DataFetchError: If fetching fails
        """

    @abstractmethod
    def search_symbols(
        self,
        query: str,
        limit: int = 10,
        **kwargs: Any
    ) -> list[dict[str, Any]]:
        """
        Search for symbols.

        Args:
            query: Search query
            limit: Maximum results
            **kwargs: Additional parameters

        Returns:
            List of symbol information dicts

        Raises:
            DataFetchError: If search fails
        """

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if provider is available/healthy.

        Returns:
            True if provider is operational
        """

    def get_multiple_symbols(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        adjusted: bool = True,
        **kwargs: Any
    ) -> dict[str, PriceData]:
        """
        Fetch historical data for multiple symbols.

        Args:
            symbols: List of symbols
            start_date: Start date
            end_date: End date
            adjusted: Whether to adjust for splits/dividends
            **kwargs: Additional parameters

        Returns:
            Dict mapping symbols to PriceData objects
        """
        results = {}
        for symbol in symbols:
            try:
                data = self.get_historical_prices(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    adjusted=adjusted,
                    **kwargs
                )
                results[symbol] = data
            except (DataFetchError, DataValidationError) as e:
                print(f"Warning: Failed to fetch {symbol}: {e}")
                continue

        return results


class CachedDataProvider(DataProvider):
    """
    Data provider with caching capabilities.

    Wraps another provider and caches results to reduce API calls.
    """

    def __init__(
        self,
        provider: DataProvider,
        cache_dir: str = ".cache/data",
        cache_ttl_seconds: int = 3600
    ) -> None:
        """
        Initialize cached provider.

        Args:
            provider: Underlying data provider
            cache_dir: Directory to store cache files
            cache_ttl_seconds: Cache time-to-live in seconds
        """
        super().__init__()
        self.provider = provider
        self.cache_dir = cache_dir
        self.cache_ttl_seconds = cache_ttl_seconds

        # Create cache directory
        import os
        os.makedirs(cache_dir, exist_ok=True)

    def _get_cache_path(self, key: str) -> str:
        """Generate cache file path."""
        import hashlib
        hash_key = hashlib.md5(key.encode()).hexdigest()
        return f"{self.cache_dir}/{hash_key}.pkl"

    def _is_cache_valid(self, cache_path: str) -> bool:
        """Check if cache is still valid."""
        import os
        import time

        if not os.path.exists(cache_path):
            return False

        cache_age = time.time() - os.path.getmtime(cache_path)
        return cache_age < self.cache_ttl_seconds

    def _read_cache(self, cache_path: str) -> Any:
        """Read data from cache.

        Security: pickle is safe here as we only load files created by
        this application's _write_cache method, not external data.
        """
        import pickle
        with open(cache_path, "rb") as f:
            return pickle.load(f)

    def _write_cache(self, cache_path: str, data: Any) -> None:
        """Write data to cache."""
        import pickle
        with open(cache_path, "wb") as f:
            pickle.dump(data, f)

    def get_historical_prices(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        adjusted: bool = True,
        **kwargs: Any
    ) -> PriceData:
        """Fetch with caching."""
        cache_key = f"prices_{symbol}_{start_date.date()}_{end_date.date()}_{adjusted}"
        cache_path = self._get_cache_path(cache_key)

        if self._is_cache_valid(cache_path):
            return self._read_cache(cache_path)

        data = self.provider.get_historical_prices(
            symbol, start_date, end_date, adjusted, **kwargs
        )
        self._write_cache(cache_path, data)
        return data

    def get_fundamentals(
        self,
        symbol: str,
        report_date: datetime | None = None,
        **kwargs: Any
    ) -> FundamentalData:
        """Fetch with caching."""
        cache_key = f"fundamentals_{symbol}_{report_date}"
        cache_path = self._get_cache_path(cache_key)

        if self._is_cache_valid(cache_path):
            return self._read_cache(cache_path)

        data = self.provider.get_fundamentals(symbol, report_date, **kwargs)
        self._write_cache(cache_path, data)
        return data

    def get_corporate_actions(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any
    ) -> list[CorporateAction]:
        """Fetch with caching."""
        cache_key = f"actions_{symbol}_{start_date.date()}_{end_date.date()}"
        cache_path = self._get_cache_path(cache_key)

        if self._is_cache_valid(cache_path):
            return self._read_cache(cache_path)

        data = self.provider.get_corporate_actions(symbol, start_date, end_date, **kwargs)
        self._write_cache(cache_path, data)
        return data

    def search_symbols(
        self,
        query: str,
        limit: int = 10,
        **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Delegate to underlying provider (no caching for search)."""
        return self.provider.search_symbols(query, limit, **kwargs)

    def is_available(self) -> bool:
        """Check underlying provider availability."""
        return self.provider.is_available()

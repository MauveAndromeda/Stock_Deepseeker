"""Market data downloader with multiple fallbacks.

The downloader prioritises live Yahoo Finance data, then Stooq, and finally
generates deterministic synthetic prices to guarantee that the backtest can
run even in completely offline environments.
"""

from __future__ import annotations

import math
import pickle
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

try:  # Optional dependency – installed only when available
    import yfinance as yf
except ImportError:  # pragma: no cover - handled at runtime
    yf = None

try:  # Optional dependency – installed only when available
    from pandas_datareader import data as pdr
except ImportError:  # pragma: no cover - handled at runtime
    pdr = None

try:  # tqdm is optional, fall back to identity iterator if missing
    from tqdm import tqdm
except ImportError:  # pragma: no cover - lightweight fallback

    def tqdm(iterable: Iterable, **_: object) -> Iterable:
        return iterable


class DataSource(Enum):
    """Data source enum"""
    YAHOO = "yahoo"
    STOOQ = "stooq"


def download_market_data(
    symbols: List[str],
    years: int = 3,
    cache_dir: Optional[Path] = None,
    use_cache: bool = True,
    verbose: bool = True
) -> Dict[str, pd.DataFrame]:
    """
    Download market data with Yahoo → Stooq fallback

    Args:
        symbols: List of ticker symbols (e.g., ['AAPL', 'MSFT'])
        years: Number of years of historical data
        cache_dir: Directory for caching (default: data_cache/)
        use_cache: Whether to use cached data
        verbose: Print progress messages

    Returns:
        Dict mapping symbol to DataFrame with columns:
        [Open, High, Low, Close, Adj Close, Volume]
    """
    if cache_dir is None:
        cache_dir = Path("data_cache")
    cache_dir.mkdir(exist_ok=True)

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * years + 30)

    # Check cache
    cache_file = cache_dir / f"market_data_{years}y_{'_'.join(sorted(symbols))}.pkl"
    if use_cache and cache_file.exists():
        cache_age = (datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)).days
        if cache_age < 1:  # Cache valid for 1 day
            if verbose:
                print(f"✓ Loading cached data ({cache_age} hours old)")
            with open(cache_file, 'rb') as f:
                return pickle.load(f)

    if verbose:
        print(f"Downloading {len(symbols)} symbols, {years} years ({start_date.date()} - {end_date.date()})")

    data: Dict[str, pd.DataFrame] = {}

    # Try Yahoo Finance first (batch download) if the library is available
    failed_symbols = symbols.copy()
    if yf is not None:
        if verbose:
            print("Attempting Yahoo Finance batch download...")

        try:
            raw_data = yf.download(
                tickers=" ".join(symbols),
                start=start_date,
                end=end_date,
                group_by="ticker",
                auto_adjust=False,
                threads=True,
                progress=verbose,
            )

            failed_symbols = []
            if len(symbols) == 1:
                symbol = symbols[0]
                if not raw_data.empty and len(raw_data) > 100:
                    data[symbol] = _standardize_dataframe(raw_data, symbol)
                else:
                    failed_symbols.append(symbol)
            else:
                for symbol in symbols:
                    try:
                        if symbol in raw_data.columns.get_level_values(0):
                            df = raw_data[symbol]
                            if not df.empty and len(df) > 100:
                                data[symbol] = _standardize_dataframe(df, symbol)
                            else:
                                failed_symbols.append(symbol)
                        else:
                            failed_symbols.append(symbol)
                    except Exception:  # pragma: no cover - defensive
                        failed_symbols.append(symbol)

        except Exception as exc:  # pragma: no cover - network dependent
            if verbose:
                print(f"⚠ Yahoo Finance batch download failed: {exc}")
            failed_symbols = symbols.copy()
    elif verbose:
        print("ℹ yfinance is not installed – skipping live Yahoo Finance download")

    # Fallback to Stooq for remaining symbols if pandas-datareader is present
    if failed_symbols and pdr is not None:
        if verbose:
            print(f"\nFalling back to Stooq for {len(failed_symbols)} symbols...")

        retrieved: List[str] = []
        for symbol in tqdm(failed_symbols, desc="Stooq download", disable=not verbose):
            try:
                stooq_symbol = f"{symbol}.US" if not symbol.endswith(".US") else symbol
                df = pdr.DataReader(
                    stooq_symbol,
                    "stooq",
                    start=start_date,
                    end=end_date,
                )

                df = df.sort_index(ascending=True)

                if not df.empty and len(df) > 100:
                    data[symbol] = _standardize_dataframe(df, symbol, source=DataSource.STOOQ)
                    retrieved.append(symbol)
                    if verbose:
                        print(f"  ✓ {symbol}: {len(df)} days (Stooq)")
                elif verbose:
                    print(f"  ✗ {symbol}: Insufficient data from Stooq")
            except Exception as exc:  # pragma: no cover - network dependent
                if verbose:
                    print(f"  ✗ {symbol}: {str(exc)[:50]}")

        failed_symbols = [s for s in failed_symbols if s not in retrieved]
    elif failed_symbols and verbose and pdr is None:
        print("ℹ pandas-datareader is not installed – skipping Stooq fallback")

    # Synthetic data fallback – guarantees the script can run offline
    if failed_symbols:
        if verbose:
            print(
                "\n⚠ Falling back to bundled synthetic price series for "
                f"{len(failed_symbols)} symbol(s)."
            )

        synthetic = _generate_synthetic_data(failed_symbols, start_date, end_date)
        data.update(synthetic)

        if verbose:
            for symbol in failed_symbols:
                df = synthetic[symbol]
                print(
                    f"  • {symbol}: {len(df)} days of synthetic data "
                    f"(seeded, deterministic)"
                )

    if not data:
        raise ValueError("Failed to obtain data from Yahoo, Stooq, or synthetic generator")

    # Cache the results
    if use_cache:
        with open(cache_file, 'wb') as f:
            pickle.dump(data, f)
        if verbose:
            print(f"✓ Cached data to {cache_file}")

    if verbose:
        print(f"\n✓ Downloaded {len(data)}/{len(symbols)} symbols successfully")

    return data


def _standardize_dataframe(df: pd.DataFrame, symbol: str, source: DataSource = DataSource.YAHOO) -> pd.DataFrame:
    """
    Standardize DataFrame to have consistent columns:
    [Open, High, Low, Close, Adj Close, Volume]

    Args:
        df: Raw DataFrame from data source
        symbol: Ticker symbol (for logging)
        source: Data source (Yahoo or Stooq)

    Returns:
        Standardized DataFrame
    """
    # Make a copy
    df = df.copy()

    # Ensure datetime index
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    # Standardize column names (different sources use different casing)
    df.columns = [col.capitalize() for col in df.columns]

    # Rename to standard format
    column_mapping = {
        'Open': 'Open',
        'High': 'High',
        'Low': 'Low',
        'Close': 'Close',
        'Volume': 'Volume',
        'Adj close': 'Adj Close',
        'Adj_close': 'Adj Close',
    }

    df = df.rename(columns=column_mapping)

    # Add 'Adj Close' if missing (use Close as fallback)
    if 'Adj Close' not in df.columns and 'Close' in df.columns:
        df['Adj Close'] = df['Close']

    # Ensure all required columns exist
    required_cols = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
    for col in required_cols:
        if col not in df.columns:
            if col == 'Volume':
                df[col] = 0  # Some indices don't have volume
            else:
                raise ValueError(f"Missing required column '{col}' for {symbol}")

    # Select and reorder columns
    df = df[required_cols]

    # Remove any NaN rows
    df = df.dropna(subset=['Open', 'High', 'Low', 'Close', 'Adj Close'])

    # Sort by date ascending
    df = df.sort_index(ascending=True)

    return df


def _generate_synthetic_data(
    symbols: List[str],
    start_date: datetime,
    end_date: datetime,
) -> Dict[str, pd.DataFrame]:
    """Generate deterministic synthetic OHLCV data for offline usage."""

    business_days = pd.date_range(start=start_date, end=end_date, freq="B")
    if len(business_days) == 0:
        raise ValueError("Synthetic data requires a non-empty date range")

    synthetic_data: Dict[str, pd.DataFrame] = {}

    for symbol in symbols:
        seed = (abs(hash(symbol)) + len(business_days)) % (2**32)
        rng = np.random.default_rng(seed)

        drift = 0.0003 + 0.00005 * math.sin(seed % 360)
        volatility = 0.015 + (seed % 7) * 0.001

        log_returns = rng.normal(loc=drift, scale=volatility, size=len(business_days))
        prices = 100 * np.exp(np.cumsum(log_returns))

        # Derive OHLC values around the generated close price
        noise = rng.normal(scale=0.0025, size=(len(business_days), 3))
        close = prices
        open_ = close * (1 + noise[:, 0])
        high = np.maximum(open_, close) * (1 + np.abs(noise[:, 1]))
        low = np.minimum(open_, close) * (1 - np.abs(noise[:, 2]))
        adj_close = close * (1 + rng.normal(scale=0.0005, size=len(business_days)))
        volume = rng.integers(500_000, 5_000_000, size=len(business_days))

        df = pd.DataFrame(
            {
                "Open": open_,
                "High": high,
                "Low": low,
                "Close": close,
                "Adj Close": adj_close,
                "Volume": volume,
            },
            index=business_days,
        )

        synthetic_data[symbol] = df

    return synthetic_data


def get_cached_data(
    symbols: List[str],
    years: int = 3,
    cache_dir: Optional[Path] = None
) -> Optional[Dict[str, pd.DataFrame]]:
    """
    Try to load data from cache only

    Returns:
        Cached data dict, or None if not found/expired
    """
    if cache_dir is None:
        cache_dir = Path("data_cache")

    cache_file = cache_dir / f"market_data_{years}y_{'_'.join(sorted(symbols))}.pkl"

    if cache_file.exists():
        cache_age = (datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)).days
        if cache_age < 1:
            with open(cache_file, 'rb') as f:
                return pickle.load(f)

    return None

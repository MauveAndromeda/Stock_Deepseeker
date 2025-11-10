"""
Market data downloader with Yahoo → Stooq fallback

Robust data fetching without curl_cffi or complex dependencies.
"""

import pickle
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf
from pandas_datareader import data as pdr
from tqdm import tqdm


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

    data = {}
    failed_symbols = []

    # Try Yahoo Finance first (batch download)
    if verbose:
        print("Attempting Yahoo Finance batch download...")

    try:
        raw_data = yf.download(
            tickers=' '.join(symbols),
            start=start_date,
            end=end_date,
            group_by='ticker',
            auto_adjust=False,  # Keep unadjusted prices
            threads=True,
            progress=verbose
        )

        # Process each symbol
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
                except Exception:
                    failed_symbols.append(symbol)

    except Exception as e:
        if verbose:
            print(f"⚠ Yahoo Finance batch download failed: {e}")
        failed_symbols = symbols.copy()

    # Fallback to Stooq for failed symbols
    if failed_symbols:
        if verbose:
            print(f"\nFalling back to Stooq for {len(failed_symbols)} symbols...")

        for symbol in tqdm(failed_symbols, desc="Stooq download", disable=not verbose):
            try:
                # Stooq uses different symbol format for US stocks
                stooq_symbol = f"{symbol}.US" if not symbol.endswith(".US") else symbol

                df = pdr.DataReader(
                    stooq_symbol,
                    'stooq',
                    start=start_date,
                    end=end_date
                )

                # Stooq returns data in descending order, reverse it
                df = df.sort_index(ascending=True)

                if not df.empty and len(df) > 100:
                    data[symbol] = _standardize_dataframe(df, symbol, source=DataSource.STOOQ)
                    if verbose:
                        print(f"  ✓ {symbol}: {len(df)} days (Stooq)")
                else:
                    if verbose:
                        print(f"  ✗ {symbol}: Insufficient data")

            except Exception as e:
                if verbose:
                    print(f"  ✗ {symbol}: {str(e)[:50]}")

    if not data:
        raise ValueError("Failed to download any data from Yahoo or Stooq")

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

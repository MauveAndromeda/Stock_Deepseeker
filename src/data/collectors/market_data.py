"""
Market Data Collector
Collects price, volume, and market data for S&P 500 stocks from multiple sources
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union
import pandas as pd
import numpy as np
from dataclasses import dataclass
import yfinance as yf
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger

from src.utils.config import get_config
from src.utils.helpers import is_market_open, get_trading_days


@dataclass
class Quote:
    """Real-time quote data"""

    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    last_price: float
    last_size: int
    volume: int
    open: float
    high: float
    low: float
    close: float


@dataclass
class OHLCV:
    """OHLCV bar data"""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None
    trades: Optional[int] = None


class SP500Universe:
    """Manages S&P 500 stock universe"""

    # S&P 500 ticker list (sample - in production, fetch from official source)
    SP500_TICKERS = [
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "NVDA",
        "META",
        "TSLA",
        "BRK.B",
        "UNH",
        "JNJ",
        "JPM",
        "V",
        "WMT",
        "PG",
        "MA",
        "HD",
        "CVX",
        "LLY",
        "ABBV",
        "MRK",
        "KO",
        "PEP",
        "COST",
        "AVGO",
        "TMO",
        "MCD",
        "CSCO",
        "ACN",
        "ABT",
        "DHR",
        "VZ",
        "ADBE",
        "TXN",
        "NEE",
        "CRM",
        "PM",
        "NKE",
        "CMCSA",
        "HON",
        "WFC",
        "UPS",
        "ORCL",
        "QCOM",
        "BMY",
        "RTX",
        "LOW",
        "UNP",
        "MS",
        "INTC",
        "BA",
        # Add more tickers...
        # This is a sample subset. In production, fetch all 500 from:
        # - Wikipedia S&P 500 list
        # - Official S&P API
        # - Financial data provider
    ]

    @classmethod
    def get_all_tickers(cls) -> List[str]:
        """Get all S&P 500 tickers"""
        return cls.SP500_TICKERS.copy()

    @classmethod
    def update_universe(cls) -> List[str]:
        """
        Update S&P 500 universe from Wikipedia
        Returns updated ticker list
        """
        try:
            # Fetch S&P 500 list from Wikipedia
            url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
            tables = pd.read_html(url)
            sp500_table = tables[0]

            # Extract tickers
            tickers = sp500_table["Symbol"].tolist()

            # Clean tickers (replace dots with dashes for Yahoo Finance)
            tickers = [ticker.replace(".", "-") for ticker in tickers]

            cls.SP500_TICKERS = tickers
            logger.info(f"Updated S&P 500 universe: {len(tickers)} stocks")

            return tickers

        except Exception as e:
            logger.error(f"Failed to update S&P 500 universe: {e}")
            return cls.SP500_TICKERS

    @classmethod
    def get_ticker_info(cls, ticker: str) -> Dict:
        """Get detailed information about a ticker"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            return info
        except Exception as e:
            logger.error(f"Failed to get info for {ticker}: {e}")
            return {}

    @classmethod
    def filter_by_criteria(
        cls,
        min_market_cap: Optional[float] = None,
        min_volume: Optional[int] = None,
        sectors: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Filter stocks by criteria

        Args:
            min_market_cap: Minimum market cap
            min_volume: Minimum average volume
            sectors: List of sectors to include

        Returns:
            Filtered ticker list
        """
        filtered = []

        for ticker in cls.SP500_TICKERS:
            try:
                info = cls.get_ticker_info(ticker)

                # Check market cap
                if min_market_cap:
                    market_cap = info.get("marketCap", 0)
                    if market_cap < min_market_cap:
                        continue

                # Check volume
                if min_volume:
                    avg_volume = info.get("averageVolume", 0)
                    if avg_volume < min_volume:
                        continue

                # Check sector
                if sectors:
                    sector = info.get("sector", "")
                    if sector not in sectors:
                        continue

                filtered.append(ticker)

            except Exception as e:
                logger.warning(f"Error filtering {ticker}: {e}")
                continue

        logger.info(f"Filtered {len(filtered)} stocks from {len(cls.SP500_TICKERS)}")
        return filtered


class MarketDataCollector:
    """Collects market data from multiple sources"""

    def __init__(self):
        self.config = get_config()
        self.universe = SP500Universe()

        # API clients
        self._init_api_clients()

    def _init_api_clients(self):
        """Initialize API clients for various data sources"""
        # Polygon.io
        self.polygon_key = self.config.api.polygon_key

        # Alpha Vantage
        self.alpha_vantage_key = self.config.api.alpha_vantage_key

        # Finnhub
        self.finnhub_key = self.config.api.finnhub_key

        logger.info("Market data API clients initialized")

    def get_historical_data(
        self,
        symbol: str,
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        Get historical OHLCV data

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            interval: Data interval (1m, 5m, 15m, 1h, 1d)

        Returns:
            DataFrame with OHLCV data
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date, interval=interval)

            if df.empty:
                logger.warning(f"No data for {symbol}")
                return pd.DataFrame()

            # Standardize column names
            df.columns = [col.lower() for col in df.columns]

            # Add symbol column
            df["symbol"] = symbol

            logger.debug(
                f"Fetched {len(df)} bars for {symbol} from {start_date} to {end_date}"
            )

            return df

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()

    def get_historical_data_bulk(
        self,
        symbols: List[str],
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        interval: str = "1d",
        max_workers: int = 10,
    ) -> Dict[str, pd.DataFrame]:
        """
        Get historical data for multiple symbols in parallel

        Args:
            symbols: List of stock symbols
            start_date: Start date
            end_date: End date
            interval: Data interval
            max_workers: Number of parallel workers

        Returns:
            Dictionary of symbol -> DataFrame
        """
        results = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_symbol = {
                executor.submit(
                    self.get_historical_data,
                    symbol,
                    start_date,
                    end_date,
                    interval,
                ): symbol
                for symbol in symbols
            }

            # Collect results
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    df = future.result()
                    if not df.empty:
                        results[symbol] = df
                except Exception as e:
                    logger.error(f"Error fetching {symbol}: {e}")

        logger.info(f"Fetched data for {len(results)}/{len(symbols)} symbols")
        return results

    def get_realtime_quote(self, symbol: str) -> Optional[Quote]:
        """Get real-time quote"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            quote = Quote(
                symbol=symbol,
                timestamp=datetime.now(),
                bid=info.get("bid", 0),
                ask=info.get("ask", 0),
                bid_size=info.get("bidSize", 0),
                ask_size=info.get("askSize", 0),
                last_price=info.get("currentPrice", 0),
                last_size=0,
                volume=info.get("volume", 0),
                open=info.get("open", 0),
                high=info.get("dayHigh", 0),
                low=info.get("dayLow", 0),
                close=info.get("previousClose", 0),
            )

            return quote

        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return None

    def get_intraday_data(
        self, symbol: str, interval: str = "1m", days: int = 5
    ) -> pd.DataFrame:
        """
        Get intraday data

        Args:
            symbol: Stock symbol
            interval: Interval (1m, 5m, 15m, etc.)
            days: Number of days of history

        Returns:
            DataFrame with intraday data
        """
        try:
            ticker = yf.Ticker(symbol)

            # Yahoo Finance allows max 7 days for 1m data
            if interval == "1m":
                days = min(days, 7)

            df = ticker.history(period=f"{days}d", interval=interval)

            if df.empty:
                logger.warning(f"No intraday data for {symbol}")
                return pd.DataFrame()

            df.columns = [col.lower() for col in df.columns]
            df["symbol"] = symbol

            return df

        except Exception as e:
            logger.error(f"Error fetching intraday data for {symbol}: {e}")
            return pd.DataFrame()

    def get_options_data(self, symbol: str) -> Dict:
        """Get options data"""
        try:
            ticker = yf.Ticker(symbol)
            options_dates = ticker.options

            if not options_dates:
                return {}

            # Get options for nearest expiration
            nearest_exp = options_dates[0]
            options_chain = ticker.option_chain(nearest_exp)

            return {
                "expiration": nearest_exp,
                "calls": options_chain.calls,
                "puts": options_chain.puts,
            }

        except Exception as e:
            logger.error(f"Error fetching options for {symbol}: {e}")
            return {}

    def calculate_technical_snapshot(self, symbol: str) -> Dict:
        """
        Calculate technical indicators snapshot

        Args:
            symbol: Stock symbol

        Returns:
            Dictionary of technical indicators
        """
        try:
            # Get recent data
            df = self.get_historical_data(
                symbol,
                start_date=datetime.now() - timedelta(days=100),
                end_date=datetime.now(),
                interval="1d",
            )

            if df.empty:
                return {}

            # Calculate basic indicators
            close = df["close"].values
            high = df["high"].values
            low = df["low"].values
            volume = df["volume"].values

            # Moving averages
            sma_20 = np.mean(close[-20:])
            sma_50 = np.mean(close[-50:]) if len(close) >= 50 else np.nan
            sma_200 = np.mean(close[-200:]) if len(close) >= 200 else np.nan

            # RSI
            rsi = self._calculate_rsi(close, 14)

            # ATR
            atr = self._calculate_atr(high, low, close, 14)

            # Bollinger Bands
            bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(
                close, 20, 2
            )

            snapshot = {
                "symbol": symbol,
                "last_price": close[-1],
                "sma_20": sma_20,
                "sma_50": sma_50,
                "sma_200": sma_200,
                "rsi_14": rsi,
                "atr_14": atr,
                "bb_upper": bb_upper,
                "bb_middle": bb_middle,
                "bb_lower": bb_lower,
                "volume": volume[-1],
                "avg_volume_20": np.mean(volume[-20:]),
            }

            return snapshot

        except Exception as e:
            logger.error(f"Error calculating snapshot for {symbol}: {e}")
            return {}

    @staticmethod
    def _calculate_rsi(prices: np.ndarray, period: int = 14) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50.0

        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def _calculate_atr(
        high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
    ) -> float:
        """Calculate ATR"""
        if len(high) < period + 1:
            return 0.0

        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])
            ),
        )

        atr = np.mean(tr[-period:])
        return atr

    @staticmethod
    def _calculate_bollinger_bands(
        prices: np.ndarray, period: int = 20, std_dev: float = 2.0
    ) -> tuple:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            return 0.0, 0.0, 0.0

        sma = np.mean(prices[-period:])
        std = np.std(prices[-period:])

        upper = sma + (std_dev * std)
        lower = sma - (std_dev * std)

        return upper, sma, lower


def download_sp500_historical_data(
    start_date: str = "2020-01-01",
    end_date: str = None,
    interval: str = "1d",
    output_dir: str = "data/historical",
) -> Dict[str, pd.DataFrame]:
    """
    Download historical data for all S&P 500 stocks

    Args:
        start_date: Start date
        end_date: End date (default: today)
        interval: Data interval
        output_dir: Output directory for CSV files

    Returns:
        Dictionary of symbol -> DataFrame
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    collector = MarketDataCollector()
    symbols = SP500Universe.get_all_tickers()

    logger.info(f"Downloading data for {len(symbols)} stocks...")

    data = collector.get_historical_data_bulk(
        symbols, start_date, end_date, interval
    )

    # Save to CSV
    import os

    os.makedirs(output_dir, exist_ok=True)

    for symbol, df in data.items():
        filepath = os.path.join(output_dir, f"{symbol}.csv")
        df.to_csv(filepath)
        logger.debug(f"Saved {symbol} to {filepath}")

    logger.info(f"Downloaded and saved data for {len(data)} stocks")

    return data

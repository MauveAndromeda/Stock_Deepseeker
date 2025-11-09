"""
数据提供者 - 多源市场数据获取
支持Yahoo Finance, Alpaca, Polygon等
"""

from abc import ABC, abstractmethod
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import time
from typing import Any

import aiohttp
import pandas as pd
import yfinance as yf


class DataProvider(ABC):
    """数据提供者基类"""

    @abstractmethod
    def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1d"
    ) -> pd.DataFrame:
        """获取历史数据"""

    @abstractmethod
    def get_realtime_quote(self, symbol: str) -> dict[str, Any]:
        """获取实时报价"""

    @abstractmethod
    def get_multiple_quotes(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """获取多个股票报价"""


class YahooFinanceProvider(DataProvider):
    """Yahoo Finance数据提供者"""

    def __init__(self):
        self.cache = {}
        self.cache_ttl = 60  # 缓存60秒

    def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1d"
    ) -> pd.DataFrame:
        """
        获取历史数据

        Args:
            symbol: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            interval: 时间间隔 (1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo)

        Returns:
            DataFrame with OHLCV data
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date, interval=interval)

            if df.empty:
                return pd.DataFrame()

            # 标准化列名
            df = df.rename(columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume"
            })

            # 添加symbol列
            df["symbol"] = symbol

            return df

        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()

    def get_realtime_quote(self, symbol: str) -> dict[str, Any]:
        """获取实时报价"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            return {
                "symbol": symbol,
                "price": info.get("currentPrice", 0),
                "bid": info.get("bid", 0),
                "ask": info.get("ask", 0),
                "volume": info.get("volume", 0),
                "market_cap": info.get("marketCap", 0),
                "pe_ratio": info.get("trailingPE", 0),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            print(f"Error fetching quote for {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}

    def get_multiple_quotes(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """并行获取多个股票报价"""
        quotes = {}

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(self.get_realtime_quote, symbol): symbol
                      for symbol in symbols}

            for future in futures:
                symbol = futures[future]
                try:
                    quote = future.result(timeout=10)
                    quotes[symbol] = quote
                except Exception as e:
                    print(f"Error getting quote for {symbol}: {e}")
                    quotes[symbol] = {"symbol": symbol, "error": str(e)}

        return quotes

    def get_company_info(self, symbol: str) -> dict[str, Any]:
        """获取公司信息"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            return {
                "symbol": symbol,
                "name": info.get("longName", ""),
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
                "description": info.get("longBusinessSummary", ""),
                "website": info.get("website", ""),
                "employees": info.get("fullTimeEmployees", 0),
                "market_cap": info.get("marketCap", 0),
                "pe_ratio": info.get("trailingPE", 0),
                "forward_pe": info.get("forwardPE", 0),
                "pb_ratio": info.get("priceToBook", 0),
                "dividend_yield": info.get("dividendYield", 0),
                "beta": info.get("beta", 0),
            }

        except Exception as e:
            print(f"Error fetching company info for {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}


class AlpacaProvider(DataProvider):
    """Alpaca数据提供者"""

    def __init__(self, api_key: str, secret_key: str, base_url: str = "https://paper-api.alpaca.markets"):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        self.headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key
        }

    async def _make_request(self, endpoint: str, params: dict | None = None) -> dict:
        """发起异步HTTP请求"""
        url = f"{self.base_url}/{endpoint}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers, params=params) as response:
                return await response.json()

    def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1Day"
    ) -> pd.DataFrame:
        """获取历史数据"""
        endpoint = f"v2/stocks/{symbol}/bars"
        params = {
            "start": start_date,
            "end": end_date,
            "timeframe": interval
        }

        try:
            result = asyncio.run(self._make_request(endpoint, params))

            if "bars" not in result:
                return pd.DataFrame()

            df = pd.DataFrame(result["bars"])
            df = df.rename(columns={"t": "timestamp", "o": "open", "h": "high",
                                   "l": "low", "c": "close", "v": "volume"})
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)
            df["symbol"] = symbol

            return df

        except Exception as e:
            print(f"Error fetching Alpaca data for {symbol}: {e}")
            return pd.DataFrame()

    def get_realtime_quote(self, symbol: str) -> dict[str, Any]:
        """获取实时报价"""
        endpoint = f"v2/stocks/{symbol}/quotes/latest"

        try:
            result = asyncio.run(self._make_request(endpoint))

            if "quote" not in result:
                return {"symbol": symbol, "error": "No quote data"}

            quote = result["quote"]
            return {
                "symbol": symbol,
                "bid": quote.get("bp", 0),
                "ask": quote.get("ap", 0),
                "bid_size": quote.get("bs", 0),
                "ask_size": quote.get("as", 0),
                "timestamp": quote.get("t", "")
            }

        except Exception as e:
            print(f"Error fetching Alpaca quote for {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}

    def get_multiple_quotes(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """获取多个股票报价"""
        quotes = {}

        for symbol in symbols:
            quote = self.get_realtime_quote(symbol)
            quotes[symbol] = quote
            time.sleep(0.1)  # 避免超过API限制

        return quotes


class PolygonProvider(DataProvider):
    """Polygon.io数据提供者"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"

    async def _make_request(self, endpoint: str, params: dict | None = None) -> dict:
        """发起异步HTTP请求"""
        url = f"{self.base_url}/{endpoint}"
        params = params or {}
        params["apiKey"] = self.api_key

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                return await response.json()

    def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "day"
    ) -> pd.DataFrame:
        """获取历史数据"""
        # 转换日期格式
        start = datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d").strftime("%Y-%m-%d")

        endpoint = f"v2/aggs/ticker/{symbol}/range/1/{interval}/{start}/{end}"
        params = {"adjusted": "true", "sort": "asc", "limit": 50000}

        try:
            result = asyncio.run(self._make_request(endpoint, params))

            if "results" not in result:
                return pd.DataFrame()

            df = pd.DataFrame(result["results"])
            df = df.rename(columns={"t": "timestamp", "o": "open", "h": "high",
                                   "l": "low", "c": "close", "v": "volume"})
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            df["symbol"] = symbol

            return df

        except Exception as e:
            print(f"Error fetching Polygon data for {symbol}: {e}")
            return pd.DataFrame()

    def get_realtime_quote(self, symbol: str) -> dict[str, Any]:
        """获取实时报价"""
        endpoint = f"v2/last/trade/{symbol}"

        try:
            result = asyncio.run(self._make_request(endpoint))

            if "results" not in result:
                return {"symbol": symbol, "error": "No quote data"}

            quote = result["results"]
            return {
                "symbol": symbol,
                "price": quote.get("p", 0),
                "size": quote.get("s", 0),
                "exchange": quote.get("x", ""),
                "timestamp": datetime.fromtimestamp(quote.get("t", 0) / 1000).isoformat()
            }

        except Exception as e:
            print(f"Error fetching Polygon quote for {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}

    def get_multiple_quotes(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """获取多个股票报价"""
        endpoint = "v2/snapshot/locale/us/markets/stocks/tickers"
        params = {"tickers": ",".join(symbols)}

        try:
            result = asyncio.run(self._make_request(endpoint, params))

            if "tickers" not in result:
                return {}

            quotes = {}
            for ticker_data in result["tickers"]:
                symbol = ticker_data["ticker"]
                day = ticker_data.get("day", {})
                last_quote = ticker_data.get("lastQuote", {})

                quotes[symbol] = {
                    "symbol": symbol,
                    "price": day.get("c", 0),
                    "open": day.get("o", 0),
                    "high": day.get("h", 0),
                    "low": day.get("l", 0),
                    "volume": day.get("v", 0),
                    "bid": last_quote.get("p", 0),
                    "ask": last_quote.get("P", 0),
                }

            return quotes

        except Exception as e:
            print(f"Error fetching Polygon quotes: {e}")
            return {}


class MultiSourceProvider(DataProvider):
    """多源数据提供者 - 自动故障转移"""

    def __init__(self, providers: dict[str, DataProvider], priority: list[str] | None = None):
        """
        Args:
            providers: {name: provider} 提供者字典
            priority: 优先级列表
        """
        self.providers = providers
        self.priority = priority or list(providers.keys())
        self.stats = {name: {"success": 0, "failure": 0} for name in providers}

    def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1d"
    ) -> pd.DataFrame:
        """尝试从多个源获取历史数据"""
        for provider_name in self.priority:
            if provider_name not in self.providers:
                continue

            provider = self.providers[provider_name]

            try:
                df = provider.get_historical_data(symbol, start_date, end_date, interval)

                if not df.empty:
                    self.stats[provider_name]["success"] += 1
                    return df

            except Exception as e:
                print(f"Provider {provider_name} failed: {e}")
                self.stats[provider_name]["failure"] += 1
                continue

        print(f"All providers failed to fetch data for {symbol}")
        return pd.DataFrame()

    def get_realtime_quote(self, symbol: str) -> dict[str, Any]:
        """尝试从多个源获取实时报价"""
        for provider_name in self.priority:
            if provider_name not in self.providers:
                continue

            provider = self.providers[provider_name]

            try:
                quote = provider.get_realtime_quote(symbol)

                if "error" not in quote:
                    self.stats[provider_name]["success"] += 1
                    return quote

            except Exception as e:
                print(f"Provider {provider_name} failed: {e}")
                self.stats[provider_name]["failure"] += 1
                continue

        print(f"All providers failed to fetch quote for {symbol}")
        return {"symbol": symbol, "error": "All providers failed"}

    def get_multiple_quotes(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """尝试从多个源获取多个报价"""
        for provider_name in self.priority:
            if provider_name not in self.providers:
                continue

            provider = self.providers[provider_name]

            try:
                quotes = provider.get_multiple_quotes(symbols)

                if quotes:
                    self.stats[provider_name]["success"] += 1
                    return quotes

            except Exception as e:
                print(f"Provider {provider_name} failed: {e}")
                self.stats[provider_name]["failure"] += 1
                continue

        print("All providers failed to fetch quotes")
        return {}

    def get_stats(self) -> dict[str, dict[str, int]]:
        """获取统计信息"""
        return self.stats.copy()

    def update_priority(self):
        """根据成功率更新优先级"""
        scores = []

        for name, stats in self.stats.items():
            total = stats["success"] + stats["failure"]
            success_rate = stats["success"] / total if total > 0 else 0
            scores.append((name, success_rate))

        # 按成功率排序
        scores.sort(key=lambda x: x[1], reverse=True)
        self.priority = [name for name, _ in scores]

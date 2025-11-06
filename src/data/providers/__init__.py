"""
Data providers package.

Multi-source data providers for robustness and completeness.
"""

from src.data.providers.base import (
    DataProvider,
    DataProviderError,
    DataProviderType,
    PriceData,
    FundamentalData,
)
from src.data.providers.yahoo import YahooFinanceProvider
from src.data.providers.polygon import PolygonProvider
from src.data.providers.alpaca import AlpacaProvider
from src.data.providers.aggregator import MultiSourceAggregator

__all__ = [
    "DataProvider",
    "DataProviderError",
    "DataProviderType",
    "PriceData",
    "FundamentalData",
    "YahooFinanceProvider",
    "PolygonProvider",
    "AlpacaProvider",
    "MultiSourceAggregator",
]

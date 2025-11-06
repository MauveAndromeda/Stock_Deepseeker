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
from src.data.providers.aggregator import MultiSourceAggregator

# TODO: Polygon and Alpaca providers not yet implemented
# from src.data.providers.polygon import PolygonProvider
# from src.data.providers.alpaca import AlpacaProvider

__all__ = [
    "DataProvider",
    "DataProviderError",
    "DataProviderType",
    "PriceData",
    "FundamentalData",
    "YahooFinanceProvider",
    "MultiSourceAggregator",
    # "PolygonProvider",
    # "AlpacaProvider",
]

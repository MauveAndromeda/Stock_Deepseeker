"""
数据层
多源数据获取、清洗、特征工程
"""

from src.data.providers import (
    DataProvider,
    YahooFinanceProvider,
    MultiSourceAggregator,
)

# TODO: Additional providers not yet implemented
# from src.data.providers import AlpacaProvider, PolygonProvider

# TODO: Preprocessing modules not yet implemented
# from src.data.preprocessing import DataPreprocessor, FeatureEngineer, DataValidator

# TODO: Storage modules not yet implemented
# from src.data.storage import DataStorage, TimeSeriesDB, CacheLayer

__all__ = [
    "DataProvider",
    "YahooFinanceProvider",
    "MultiSourceAggregator",
]

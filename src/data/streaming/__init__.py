"""
Real-time market data streaming module.

Provides real-time data feeds from multiple sources:
- Alpaca (stocks, crypto)
- Interactive Brokers
- WebSocket-based custom feeds
- Mock streaming for testing
"""

from src.data.streaming.aggregator import OHLCV, DataAggregator
from src.data.streaming.alpaca_stream import AlpacaStreamingProvider
from src.data.streaming.base import (
    MessageType,
    StreamingDataProvider,
    StreamingMessage,
    Subscription,
)
from src.data.streaming.cache import MarketDataCache
from src.data.streaming.websocket_feed import WebSocketFeed

__all__ = [
    # Base classes
    "StreamingDataProvider",
    "StreamingMessage",
    "MessageType",
    "Subscription",

    # Providers
    "AlpacaStreamingProvider",
    "WebSocketFeed",

    # Utilities
    "DataAggregator",
    "OHLCV",
    "MarketDataCache",
]

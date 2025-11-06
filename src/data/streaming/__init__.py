"""
Real-time market data streaming module.

Provides real-time data feeds from multiple sources:
- Alpaca (stocks, crypto)
- Interactive Brokers
- WebSocket-based custom feeds
- Mock streaming for testing
"""

from src.data.streaming.base import (
    StreamingDataProvider,
    StreamingMessage,
    MessageType,
    Subscription
)
from src.data.streaming.alpaca_stream import AlpacaStreamingProvider
from src.data.streaming.websocket_feed import WebSocketFeed
from src.data.streaming.aggregator import DataAggregator, OHLCV
from src.data.streaming.cache import MarketDataCache

__all__ = [
    # Base classes
    'StreamingDataProvider',
    'StreamingMessage',
    'MessageType',
    'Subscription',

    # Providers
    'AlpacaStreamingProvider',
    'WebSocketFeed',

    # Utilities
    'DataAggregator',
    'OHLCV',
    'MarketDataCache',
]

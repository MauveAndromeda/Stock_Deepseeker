"""
Market data caching for fast access to recent data.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque, defaultdict
import threading

from src.data.streaming.base import StreamingMessage, MessageType
from src.data.streaming.aggregator import OHLCV


@dataclass
class Quote:
    """Latest quote data."""
    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    mid: float = field(init=False)
    spread: float = field(init=False)

    def __post_init__(self):
        self.mid = (self.bid + self.ask) / 2
        self.spread = self.ask - self.bid


@dataclass
class Trade:
    """Trade data."""
    symbol: str
    timestamp: datetime
    price: float
    size: int
    exchange: str = ""


class MarketDataCache:
    """
    Thread-safe cache for real-time market data.

    Stores:
    - Latest quotes (bid/ask)
    - Recent trades
    - Recent bars
    - Best bid/ask across exchanges
    - Market depth (optional)
    """

    def __init__(
        self,
        max_trade_history: int = 1000,
        max_bar_history: int = 1000,
        quote_expiry: timedelta = timedelta(seconds=30)
    ):
        """
        Initialize market data cache.

        Args:
            max_trade_history: Max trades to store per symbol
            max_bar_history: Max bars to store per symbol
            quote_expiry: Time before quote is considered stale
        """
        self.max_trade_history = max_trade_history
        self.max_bar_history = max_bar_history
        self.quote_expiry = quote_expiry

        # Latest quotes
        self._quotes: Dict[str, Quote] = {}

        # Trade history
        self._trades: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_trade_history)
        )

        # Bar history
        self._bars: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_bar_history)
        )

        # Latest prices
        self._last_prices: Dict[str, float] = {}
        self._last_trade_times: Dict[str, datetime] = {}

        # Thread safety
        self._lock = threading.RLock()

        # Stats
        self._quote_updates = 0
        self._trade_updates = 0
        self._bar_updates = 0

    def update_from_message(self, message: StreamingMessage) -> None:
        """
        Update cache from streaming message.

        Args:
            message: Streaming message to process
        """
        if message.message_type == MessageType.QUOTE:
            self.update_quote(message)
        elif message.message_type == MessageType.TRADE:
            self.update_trade(message)
        elif message.message_type == MessageType.BAR:
            self.update_bar(message)

    def update_quote(self, message: StreamingMessage) -> None:
        """Update quote from message."""
        data = message.data

        quote = Quote(
            symbol=message.symbol,
            timestamp=message.timestamp,
            bid=data.get('bid_price', 0.0),
            ask=data.get('ask_price', 0.0),
            bid_size=data.get('bid_size', 0),
            ask_size=data.get('ask_size', 0)
        )

        with self._lock:
            self._quotes[message.symbol] = quote
            self._quote_updates += 1

    def update_trade(self, message: StreamingMessage) -> None:
        """Update trade from message."""
        data = message.data

        trade = Trade(
            symbol=message.symbol,
            timestamp=message.timestamp,
            price=data.get('price', 0.0),
            size=data.get('size', 0),
            exchange=data.get('exchange', '')
        )

        with self._lock:
            self._trades[message.symbol].append(trade)
            self._last_prices[message.symbol] = trade.price
            self._last_trade_times[message.symbol] = trade.timestamp
            self._trade_updates += 1

    def update_bar(self, message: StreamingMessage) -> None:
        """Update bar from message."""
        data = message.data

        bar = OHLCV(
            symbol=message.symbol,
            timestamp=message.timestamp,
            open=data.get('open', 0.0),
            high=data.get('high', 0.0),
            low=data.get('low', 0.0),
            close=data.get('close', 0.0),
            volume=data.get('volume', 0),
            vwap=data.get('vwap'),
            trade_count=data.get('trade_count', 0)
        )

        with self._lock:
            self._bars[message.symbol].append(bar)
            self._last_prices[message.symbol] = bar.close
            self._last_trade_times[message.symbol] = bar.timestamp
            self._bar_updates += 1

    def add_bar(self, bar: OHLCV) -> None:
        """Add OHLCV bar directly."""
        with self._lock:
            self._bars[bar.symbol].append(bar)
            self._last_prices[bar.symbol] = bar.close
            self._last_trade_times[bar.symbol] = bar.timestamp
            self._bar_updates += 1

    def get_quote(self, symbol: str) -> Optional[Quote]:
        """
        Get latest quote for symbol.

        Args:
            symbol: Symbol to query

        Returns:
            Latest Quote or None
        """
        with self._lock:
            quote = self._quotes.get(symbol)

            if quote:
                # Check if quote is stale
                age = datetime.utcnow() - quote.timestamp
                if age > self.quote_expiry:
                    return None

            return quote

    def get_last_price(self, symbol: str) -> Optional[float]:
        """Get last trade price for symbol."""
        with self._lock:
            return self._last_prices.get(symbol)

    def get_mid_price(self, symbol: str) -> Optional[float]:
        """Get mid price (average of bid/ask)."""
        quote = self.get_quote(symbol)
        if quote:
            return quote.mid
        return None

    def get_spread(self, symbol: str) -> Optional[float]:
        """Get bid-ask spread."""
        quote = self.get_quote(symbol)
        if quote:
            return quote.spread
        return None

    def get_recent_trades(self, symbol: str, n: Optional[int] = None) -> List[Trade]:
        """
        Get recent trades for symbol.

        Args:
            symbol: Symbol to query
            n: Number of recent trades (None = all)

        Returns:
            List of Trade objects
        """
        with self._lock:
            trades = list(self._trades.get(symbol, []))

            if n:
                return trades[-n:]
            return trades

    def get_recent_bars(self, symbol: str, n: Optional[int] = None) -> List[OHLCV]:
        """
        Get recent bars for symbol.

        Args:
            symbol: Symbol to query
            n: Number of recent bars (None = all)

        Returns:
            List of OHLCV bars
        """
        with self._lock:
            bars = list(self._bars.get(symbol, []))

            if n:
                return bars[-n:]
            return bars

    def get_vwap(self, symbol: str, lookback_bars: int = 20) -> Optional[float]:
        """
        Calculate VWAP over recent bars.

        Args:
            symbol: Symbol to query
            lookback_bars: Number of bars for calculation

        Returns:
            VWAP or None
        """
        bars = self.get_recent_bars(symbol, lookback_bars)

        if not bars:
            return None

        total_pv = sum(bar.close * bar.volume for bar in bars)
        total_volume = sum(bar.volume for bar in bars)

        if total_volume == 0:
            return None

        return total_pv / total_volume

    def get_volume_profile(
        self,
        symbol: str,
        lookback_bars: int = 20
    ) -> Dict[float, int]:
        """
        Get volume profile (volume at each price level).

        Args:
            symbol: Symbol to query
            lookback_bars: Number of bars for calculation

        Returns:
            Dictionary mapping price to volume
        """
        trades = self.get_recent_trades(symbol)

        if not trades:
            return {}

        # Limit to recent trades
        recent_trades = trades[-lookback_bars * 100:]  # Approximate

        # Build profile
        profile = defaultdict(int)
        for trade in recent_trades:
            # Round price to 2 decimals
            price_level = round(trade.price, 2)
            profile[price_level] += trade.size

        return dict(profile)

    def get_symbols(self) -> List[str]:
        """Get all symbols in cache."""
        with self._lock:
            symbols = set()
            symbols.update(self._quotes.keys())
            symbols.update(self._trades.keys())
            symbols.update(self._bars.keys())
            return sorted(symbols)

    def clear_symbol(self, symbol: str) -> None:
        """Clear all data for a symbol."""
        with self._lock:
            self._quotes.pop(symbol, None)
            self._trades.pop(symbol, None)
            self._bars.pop(symbol, None)
            self._last_prices.pop(symbol, None)
            self._last_trade_times.pop(symbol, None)

    def clear_all(self) -> None:
        """Clear all cached data."""
        with self._lock:
            self._quotes.clear()
            self._trades.clear()
            self._bars.clear()
            self._last_prices.clear()
            self._last_trade_times.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                'symbols': len(self.get_symbols()),
                'quotes': len(self._quotes),
                'quote_updates': self._quote_updates,
                'trade_updates': self._trade_updates,
                'bar_updates': self._bar_updates,
                'total_trades': sum(len(t) for t in self._trades.values()),
                'total_bars': sum(len(b) for b in self._bars.values())
            }

"""
Data aggregation for converting ticks to bars.
"""

from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from src.data.streaming.base import MessageType, StreamingMessage


@dataclass
class OHLCV:
    """OHLCV bar data."""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float | None = None
    trade_count: int = 0

    def __repr__(self) -> str:
        return (
            f"OHLCV({self.symbol}, {self.timestamp}, "
            f"O={self.open:.2f}, H={self.high:.2f}, "
            f"L={self.low:.2f}, C={self.close:.2f}, V={self.volume})"
        )


class DataAggregator:
    """
    Aggregates tick data into time-based bars.

    Supports:
    - Time-based bars (1s, 1min, 5min, etc.)
    - Volume-based bars
    - Tick-based bars
    - Dollar-based bars
    """

    def __init__(
        self,
        bar_size: timedelta = timedelta(minutes=1),
        aggregation_type: str = "time",  # "time", "volume", "tick", "dollar"
        callback: Callable[[OHLCV], None] | None = None
    ):
        """
        Initialize data aggregator.

        Args:
            bar_size: Size of bars for time-based aggregation
            aggregation_type: Type of aggregation
            callback: Function to call when bar is complete
        """
        self.bar_size = bar_size
        self.aggregation_type = aggregation_type
        self.callback = callback

        # Current bars being built
        self._current_bars: dict[str, OHLCV] = {}
        self._current_bar_start: dict[str, datetime] = {}

        # Trade data for current bar
        self._bar_prices: dict[str, list[float]] = defaultdict(list)
        self._bar_volumes: dict[str, list[int]] = defaultdict(list)
        self._bar_trade_counts: dict[str, int] = defaultdict(int)

        # Completed bars history
        self._bar_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))

        # Stats
        self._bars_completed = 0
        self._ticks_processed = 0

    def process_message(self, message: StreamingMessage) -> OHLCV | None:
        """
        Process streaming message and update bars.

        Args:
            message: Streaming message (trade or bar)

        Returns:
            Completed bar if one was finalized, None otherwise
        """
        if message.message_type == MessageType.TRADE:
            return self._process_trade(message)
        if message.message_type == MessageType.BAR:
            return self._process_bar(message)
        return None

    def _process_trade(self, message: StreamingMessage) -> OHLCV | None:
        """Process a trade message."""
        symbol = message.symbol
        timestamp = message.timestamp
        price = message.data.get("price", 0.0)
        size = message.data.get("size", 0)

        self._ticks_processed += 1

        # Determine if we need to start a new bar
        if self.aggregation_type == "time":
            return self._process_time_bar(symbol, timestamp, price, size)
        if self.aggregation_type == "volume":
            return self._process_volume_bar(symbol, timestamp, price, size)
        if self.aggregation_type == "tick":
            return self._process_tick_bar(symbol, timestamp, price, size)
        if self.aggregation_type == "dollar":
            return self._process_dollar_bar(symbol, timestamp, price, size)
        return None

    def _process_time_bar(
        self,
        symbol: str,
        timestamp: datetime,
        price: float,
        size: int
    ) -> OHLCV | None:
        """Process time-based bar aggregation."""
        completed_bar = None

        # Get current bar start time (aligned to bar_size)
        bar_start = self._align_timestamp(timestamp)

        # Check if we need to complete the previous bar
        if symbol in self._current_bar_start:
            current_start = self._current_bar_start[symbol]

            if bar_start > current_start:
                # Complete the previous bar
                completed_bar = self._finalize_bar(symbol)

        # Initialize new bar if needed
        if symbol not in self._current_bars or completed_bar:
            self._init_bar(symbol, bar_start, price)
            self._current_bar_start[symbol] = bar_start

        # Update current bar
        self._update_bar(symbol, price, size)

        return completed_bar

    def _process_volume_bar(
        self,
        symbol: str,
        timestamp: datetime,
        price: float,
        size: int
    ) -> OHLCV | None:
        """Process volume-based bar aggregation."""
        # Define volume threshold (e.g., 10,000 shares)
        volume_threshold = 10000

        completed_bar = None

        # Initialize bar if needed
        if symbol not in self._current_bars:
            self._init_bar(symbol, timestamp, price)

        # Update bar
        self._update_bar(symbol, price, size)

        # Check if volume threshold reached
        if self._current_bars[symbol].volume >= volume_threshold:
            completed_bar = self._finalize_bar(symbol)
            # Start new bar
            self._init_bar(symbol, timestamp, price)

        return completed_bar

    def _process_tick_bar(
        self,
        symbol: str,
        timestamp: datetime,
        price: float,
        size: int
    ) -> OHLCV | None:
        """Process tick-based bar aggregation."""
        # Define tick threshold (e.g., 100 ticks)
        tick_threshold = 100

        completed_bar = None

        # Initialize bar if needed
        if symbol not in self._current_bars:
            self._init_bar(symbol, timestamp, price)

        # Update bar
        self._update_bar(symbol, price, size)

        # Check if tick threshold reached
        if self._bar_trade_counts[symbol] >= tick_threshold:
            completed_bar = self._finalize_bar(symbol)
            # Start new bar
            self._init_bar(symbol, timestamp, price)

        return completed_bar

    def _process_dollar_bar(
        self,
        symbol: str,
        timestamp: datetime,
        price: float,
        size: int
    ) -> OHLCV | None:
        """Process dollar volume-based bar aggregation."""
        # Define dollar threshold (e.g., $1 million)
        dollar_threshold = 1_000_000

        completed_bar = None

        # Initialize bar if needed
        if symbol not in self._current_bars:
            self._init_bar(symbol, timestamp, price)

        # Update bar
        self._update_bar(symbol, price, size)

        # Calculate dollar volume
        dollar_volume = sum(
            p * v for p, v in zip(
                self._bar_prices[symbol],
                self._bar_volumes[symbol]
            )
        )

        # Check if dollar threshold reached
        if dollar_volume >= dollar_threshold:
            completed_bar = self._finalize_bar(symbol)
            # Start new bar
            self._init_bar(symbol, timestamp, price)

        return completed_bar

    def _process_bar(self, message: StreamingMessage) -> OHLCV | None:
        """Process a pre-aggregated bar message."""
        data = message.data

        bar = OHLCV(
            symbol=message.symbol,
            timestamp=message.timestamp,
            open=data.get("open", 0.0),
            high=data.get("high", 0.0),
            low=data.get("low", 0.0),
            close=data.get("close", 0.0),
            volume=data.get("volume", 0),
            vwap=data.get("vwap"),
            trade_count=data.get("trade_count", 0)
        )

        # Store in history
        self._bar_history[message.symbol].append(bar)
        self._bars_completed += 1

        # Call callback
        if self.callback:
            self.callback(bar)

        return bar

    def _init_bar(self, symbol: str, timestamp: datetime, price: float) -> None:
        """Initialize a new bar."""
        self._current_bars[symbol] = OHLCV(
            symbol=symbol,
            timestamp=timestamp,
            open=price,
            high=price,
            low=price,
            close=price,
            volume=0,
            trade_count=0
        )

        # Clear bar data
        self._bar_prices[symbol] = []
        self._bar_volumes[symbol] = []
        self._bar_trade_counts[symbol] = 0

    def _update_bar(self, symbol: str, price: float, size: int) -> None:
        """Update current bar with new trade."""
        bar = self._current_bars[symbol]

        bar.high = max(bar.high, price)
        bar.low = min(bar.low, price)
        bar.close = price
        bar.volume += size
        bar.trade_count += 1

        # Store for VWAP calculation
        self._bar_prices[symbol].append(price)
        self._bar_volumes[symbol].append(size)
        self._bar_trade_counts[symbol] += 1

    def _finalize_bar(self, symbol: str) -> OHLCV:
        """Finalize and return completed bar."""
        bar = self._current_bars[symbol]

        # Calculate VWAP
        if len(self._bar_prices[symbol]) > 0 and bar.volume > 0:
            prices = np.array(self._bar_prices[symbol])
            volumes = np.array(self._bar_volumes[symbol])
            bar.vwap = np.sum(prices * volumes) / bar.volume
        else:
            bar.vwap = bar.close

        # Store in history
        self._bar_history[symbol].append(bar)
        self._bars_completed += 1

        # Call callback
        if self.callback:
            self.callback(bar)

        return bar

    def _align_timestamp(self, timestamp: datetime) -> datetime:
        """Align timestamp to bar size."""
        # Calculate seconds since epoch
        epoch = datetime(1970, 1, 1, tzinfo=timestamp.tzinfo)
        seconds_since_epoch = (timestamp - epoch).total_seconds()

        # Round down to nearest bar_size
        bar_size_seconds = self.bar_size.total_seconds()
        aligned_seconds = int(seconds_since_epoch // bar_size_seconds) * bar_size_seconds

        # Convert back to datetime
        aligned = epoch + timedelta(seconds=aligned_seconds)

        return aligned

    def get_bar_history(self, symbol: str, n_bars: int | None = None) -> list[OHLCV]:
        """
        Get historical bars for a symbol.

        Args:
            symbol: Symbol to query
            n_bars: Number of recent bars (None = all)

        Returns:
            List of OHLCV bars
        """
        history = list(self._bar_history.get(symbol, []))

        if n_bars:
            return history[-n_bars:]
        return history

    def get_current_bar(self, symbol: str) -> OHLCV | None:
        """Get the current incomplete bar for a symbol."""
        return self._current_bars.get(symbol)

    def get_stats(self) -> dict:
        """Get aggregator statistics."""
        return {
            "aggregation_type": self.aggregation_type,
            "bar_size": str(self.bar_size),
            "ticks_processed": self._ticks_processed,
            "bars_completed": self._bars_completed,
            "symbols_tracked": len(self._current_bars),
            "bars_in_history": sum(len(h) for h in self._bar_history.values())
        }

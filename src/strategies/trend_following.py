"""
Trend following strategy using multiple trend indicators.
"""

from typing import Dict, List, Optional, Tuple
from enum import Enum
import numpy as np
from collections import deque

from src.strategies.base import BaseStrategy, Signal, SignalType


class TrendState(Enum):
    """Trend state classification."""
    STRONG_UPTREND = "strong_uptrend"
    WEAK_UPTREND = "weak_uptrend"
    SIDEWAYS = "sideways"
    WEAK_DOWNTREND = "weak_downtrend"
    STRONG_DOWNTREND = "strong_downtrend"


class TrendFollowingStrategy(BaseStrategy):
    """
    Trend following strategy using multiple indicators and timeframes.

    Combines:
    - Moving average crossovers (fast/slow)
    - ADX (Average Directional Index) for trend strength
    - Parabolic SAR for entry/exit signals
    - ATR (Average True Range) for position sizing

    The strategy:
    1. Identifies trends using multiple indicators
    2. Enters on trend confirmation across timeframes
    3. Scales position size based on trend strength
    4. Uses trailing stops based on ATR

    Parameters:
        fast_ma: Fast moving average period
        slow_ma: Slow moving average period
        adx_period: ADX calculation period
        adx_threshold: Minimum ADX for trend confirmation
        atr_period: ATR calculation period
        atr_multiplier: ATR multiplier for stops
        use_multiple_timeframes: Use multiple timeframe confirmation
        max_positions: Maximum concurrent positions
    """

    def __init__(
        self,
        fast_ma: int = 20,
        slow_ma: int = 50,
        adx_period: int = 14,
        adx_threshold: float = 25,
        atr_period: int = 14,
        atr_multiplier: float = 2.0,
        use_multiple_timeframes: bool = True,
        max_positions: int = 10,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.fast_ma = fast_ma
        self.slow_ma = slow_ma
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.use_multiple_timeframes = use_multiple_timeframes
        self.max_positions = max_positions

        # State
        self.price_history: Dict[str, deque] = {}
        self.high_history: Dict[str, deque] = {}
        self.low_history: Dict[str, deque] = {}
        self.trend_states: Dict[str, TrendState] = {}
        self.entry_prices: Dict[str, float] = {}
        self.trailing_stops: Dict[str, float] = {}

    def on_start(self) -> None:
        """Initialize strategy."""
        self.logger.info(
            f"Starting TrendFollowingStrategy with {self.max_positions} max positions"
        )
        self.logger.info(
            f"MA periods: {self.fast_ma}/{self.slow_ma}, "
            f"ADX threshold: {self.adx_threshold}"
        )

    def on_data(self, data: Dict) -> List[Signal]:
        """
        Generate trend following signals.

        Args:
            data: Market data containing prices, highs, lows

        Returns:
            List of trading signals
        """
        self.days_elapsed += 1

        # Update price data
        if 'prices' in data:
            for symbol, price in data['prices'].items():
                if symbol not in self.price_history:
                    self.price_history[symbol] = deque(maxlen=max(self.slow_ma * 3, 252))
                self.price_history[symbol].append(price)

        if 'highs' in data:
            for symbol, high in data['highs'].items():
                if symbol not in self.high_history:
                    self.high_history[symbol] = deque(maxlen=max(self.slow_ma * 3, 252))
                self.high_history[symbol].append(high)

        if 'lows' in data:
            for symbol, low in data['lows'].items():
                if symbol not in self.low_history:
                    self.low_history[symbol] = deque(maxlen=max(self.slow_ma * 3, 252))
                self.low_history[symbol].append(low)

        signals = []

        # Update trend states and generate signals
        for symbol in self.price_history.keys():
            if len(self.price_history[symbol]) < self.slow_ma:
                continue

            # Calculate indicators
            trend_signal = self._analyze_trend(symbol)

            if trend_signal:
                signals.append(trend_signal)

        # Update trailing stops for existing positions
        self._update_trailing_stops()

        # Check stop losses
        stop_signals = self._check_stops()
        signals.extend(stop_signals)

        return signals

    def _analyze_trend(self, symbol: str) -> Optional[Signal]:
        """Analyze trend and generate signal if appropriate."""
        prices = np.array(self.price_history[symbol])
        highs = np.array(self.high_history.get(symbol, prices))
        lows = np.array(self.low_history.get(symbol, prices))

        # Calculate moving averages
        ma_fast = np.mean(prices[-self.fast_ma:])
        ma_slow = np.mean(prices[-self.slow_ma:])

        # Calculate ADX
        adx = self._calculate_adx(prices, highs, lows)

        # Calculate ATR
        atr = self._calculate_atr(highs, lows, prices)

        # Determine trend state
        trend_state = self._classify_trend(ma_fast, ma_slow, adx)
        self.trend_states[symbol] = trend_state

        current_price = prices[-1]
        in_position = symbol in self.positions

        # Generate signals
        # Entry signals
        if not in_position and len(self.positions) < self.max_positions:
            # Strong uptrend entry
            if trend_state in [TrendState.STRONG_UPTREND, TrendState.WEAK_UPTREND]:
                # Additional confirmation: price above both MAs
                if current_price > ma_fast and current_price > ma_slow:
                    # Check for multiple timeframe confirmation if enabled
                    if self.use_multiple_timeframes:
                        if not self._check_multiple_timeframes(prices):
                            return None

                    # Calculate position strength based on trend strength
                    strength = min(1.0, adx / 50.0)  # Normalize ADX to strength

                    # Set initial stop loss
                    stop_loss = current_price - (self.atr_multiplier * atr)
                    self.entry_prices[symbol] = current_price
                    self.trailing_stops[symbol] = stop_loss

                    return Signal(
                        symbol=symbol,
                        signal_type=SignalType.BUY,
                        strength=strength,
                        metadata={
                            'strategy': 'trend_following',
                            'trend_state': trend_state.value,
                            'adx': adx,
                            'ma_fast': ma_fast,
                            'ma_slow': ma_slow,
                            'atr': atr,
                            'stop_loss': stop_loss
                        }
                    )

        # Exit signals
        elif in_position:
            # Exit on trend reversal
            if trend_state in [TrendState.WEAK_DOWNTREND, TrendState.STRONG_DOWNTREND]:
                return Signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    strength=1.0,
                    metadata={
                        'strategy': 'trend_following_exit',
                        'reason': 'trend_reversal',
                        'trend_state': trend_state.value
                    }
                )

            # Exit on MA crossover (fast crosses below slow)
            if ma_fast < ma_slow:
                return Signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    strength=1.0,
                    metadata={
                        'strategy': 'trend_following_exit',
                        'reason': 'ma_crossover',
                        'ma_fast': ma_fast,
                        'ma_slow': ma_slow
                    }
                )

        return None

    def _calculate_adx(self, prices: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> float:
        """
        Calculate Average Directional Index (ADX).

        ADX measures trend strength (0-100):
        - 0-25: Weak/no trend
        - 25-50: Strong trend
        - 50+: Very strong trend
        """
        period = self.adx_period

        if len(prices) < period + 1:
            return 0.0

        # Calculate True Range
        tr = np.maximum(
            highs[-period:] - lows[-period:],
            np.maximum(
                np.abs(highs[-period:] - prices[-period-1:-1]),
                np.abs(lows[-period:] - prices[-period-1:-1])
            )
        )

        # Calculate Directional Movement
        high_diff = np.diff(highs[-period-1:])
        low_diff = -np.diff(lows[-period-1:])

        plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
        minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)

        # Smooth using Wilder's method (EMA with alpha = 1/period)
        atr = np.mean(tr)
        plus_di = 100 * np.mean(plus_dm) / atr if atr > 0 else 0
        minus_di = 100 * np.mean(minus_dm) / atr if atr > 0 else 0

        # Calculate DX
        di_sum = plus_di + minus_di
        dx = 100 * abs(plus_di - minus_di) / di_sum if di_sum > 0 else 0

        # ADX is smoothed DX (simplified here)
        adx = dx

        return adx

    def _calculate_atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> float:
        """Calculate Average True Range (ATR)."""
        period = self.atr_period

        if len(closes) < period + 1:
            return 0.0

        # Calculate True Range
        tr = np.maximum(
            highs[-period:] - lows[-period:],
            np.maximum(
                np.abs(highs[-period:] - closes[-period-1:-1]),
                np.abs(lows[-period:] - closes[-period-1:-1])
            )
        )

        atr = np.mean(tr)

        return atr

    def _classify_trend(self, ma_fast: float, ma_slow: float, adx: float) -> TrendState:
        """Classify the current trend state."""
        # No trend
        if adx < self.adx_threshold:
            return TrendState.SIDEWAYS

        # Uptrend
        if ma_fast > ma_slow:
            if adx > 40:
                return TrendState.STRONG_UPTREND
            else:
                return TrendState.WEAK_UPTREND

        # Downtrend
        else:
            if adx > 40:
                return TrendState.STRONG_DOWNTREND
            else:
                return TrendState.WEAK_DOWNTREND

    def _check_multiple_timeframes(self, prices: np.ndarray) -> bool:
        """
        Check if trend is confirmed across multiple timeframes.

        Uses longer-term MAs to confirm trend direction.
        """
        if len(prices) < 200:
            return True  # Insufficient data, pass by default

        # Check longer timeframe (e.g., 50/200 day MAs)
        ma_50 = np.mean(prices[-50:])
        ma_200 = np.mean(prices[-200:])

        # Long-term trend should align
        return ma_50 > ma_200

    def _update_trailing_stops(self) -> None:
        """Update trailing stops for existing positions."""
        for symbol in list(self.positions.keys()):
            if symbol not in self.price_history or symbol not in self.trailing_stops:
                continue

            prices = np.array(self.price_history[symbol])
            highs = np.array(self.high_history.get(symbol, prices))
            lows = np.array(self.low_history.get(symbol, prices))

            current_price = prices[-1]
            current_stop = self.trailing_stops[symbol]
            entry_price = self.entry_prices.get(symbol, current_price)

            # Calculate current ATR
            atr = self._calculate_atr(highs, lows, prices)

            # New trailing stop (ATR-based)
            new_stop = current_price - (self.atr_multiplier * atr)

            # Only raise the stop, never lower it
            if new_stop > current_stop:
                self.trailing_stops[symbol] = new_stop

                # Log if stop moved to breakeven or better
                if new_stop >= entry_price and current_stop < entry_price:
                    self.logger.info(
                        f"Trailing stop moved to breakeven for {symbol}: {new_stop:.2f}"
                    )

    def _check_stops(self) -> List[Signal]:
        """Check if any positions hit their trailing stops."""
        signals = []

        for symbol in list(self.positions.keys()):
            if symbol not in self.price_history or symbol not in self.trailing_stops:
                continue

            current_price = self.price_history[symbol][-1]
            stop_price = self.trailing_stops[symbol]

            if current_price <= stop_price:
                signals.append(Signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    strength=1.0,
                    metadata={
                        'strategy': 'trend_following_exit',
                        'reason': 'trailing_stop',
                        'stop_price': stop_price,
                        'exit_price': current_price
                    }
                ))

                # Clean up
                del self.trailing_stops[symbol]
                if symbol in self.entry_prices:
                    del self.entry_prices[symbol]

        return signals

    def on_signal(self, signal: Signal) -> None:
        """Handle generated signal."""
        metadata = signal.metadata

        if signal.signal_type == SignalType.BUY:
            self.logger.info(
                f"Trend entry: BUY {signal.symbol} "
                f"[state={metadata['trend_state']}, ADX={metadata['adx']:.1f}, "
                f"stop={metadata['stop_loss']:.2f}]"
            )
        else:
            self.logger.info(
                f"Trend exit: SELL {signal.symbol} "
                f"[reason={metadata['reason']}]"
            )

    def on_fill(self, symbol: str, quantity: float, price: float) -> None:
        """Handle order fill."""
        if quantity > 0:
            self.positions[symbol] = self.positions.get(symbol, 0) + quantity
        else:
            self.positions[symbol] = self.positions.get(symbol, 0) + quantity
            if abs(self.positions[symbol]) < 1e-6:
                del self.positions[symbol]

    def on_stop(self) -> None:
        """Cleanup on strategy stop."""
        self.logger.info("Stopping TrendFollowingStrategy")
        self.logger.info(f"Open positions: {len(self.positions)}")

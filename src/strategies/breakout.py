"""
Breakout trading strategy based on technical patterns and volume.
"""

from collections import deque
from enum import Enum

import numpy as np

from src.strategies.base import BaseStrategy, Signal, SignalType


class BreakoutType(Enum):
    """Types of breakout patterns."""
    RESISTANCE_BREAK = "resistance_break"
    RANGE_BREAK = "range_break"
    CHANNEL_BREAK = "channel_break"
    CONSOLIDATION_BREAK = "consolidation_break"


class BreakoutStrategy(BaseStrategy):
    """
    Breakout strategy that identifies and trades technical breakouts.

    The strategy detects:
    - Resistance level breakouts
    - Trading range breakouts
    - Channel breakouts
    - Consolidation pattern breakouts

    Filters breakouts using:
    - Volume confirmation
    - Momentum confirmation
    - Volatility expansion

    Parameters:
        lookback_support_resistance: Period to identify S/R levels
        lookback_consolidation: Period to detect consolidation
        breakout_threshold: Minimum breakout size (percentage)
        volume_multiplier: Volume must be X times average
        min_consolidation_days: Minimum consolidation period
        stop_loss_pct: Stop loss percentage below entry
        take_profit_pct: Take profit percentage above entry
        max_positions: Maximum concurrent positions
    """

    def __init__(
        self,
        lookback_support_resistance: int = 60,
        lookback_consolidation: int = 20,
        breakout_threshold: float = 0.02,  # 2%
        volume_multiplier: float = 1.5,
        min_consolidation_days: int = 10,
        stop_loss_pct: float = 0.05,  # 5%
        take_profit_pct: float = 0.15,  # 15%
        max_positions: int = 10,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.lookback_sr = lookback_support_resistance
        self.lookback_consolidation = lookback_consolidation
        self.breakout_threshold = breakout_threshold
        self.volume_multiplier = volume_multiplier
        self.min_consolidation_days = min_consolidation_days
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_positions = max_positions

        # State
        self.price_history: dict[str, deque] = {}
        self.volume_history: dict[str, deque] = {}
        self.high_history: dict[str, deque] = {}
        self.low_history: dict[str, deque] = {}
        self.breakout_positions: dict[str, tuple[float, float, float]] = {}  # symbol -> (entry, stop, target)

    def on_start(self) -> None:
        """Initialize strategy."""
        self.logger.info(
            f"Starting BreakoutStrategy with {self.max_positions} max positions"
        )
        self.logger.info(
            f"Breakout threshold: {self.breakout_threshold:.1%}, "
            f"Volume multiplier: {self.volume_multiplier}x"
        )

    def on_data(self, data: dict) -> list[Signal]:
        """
        Generate breakout trading signals.

        Args:
            data: Market data containing:
                - prices: Dict[symbol, close_price]
                - highs: Dict[symbol, high_price]
                - lows: Dict[symbol, low_price]
                - volumes: Dict[symbol, volume]

        Returns:
            List of trading signals
        """
        self.days_elapsed += 1

        # Update price data
        if "prices" in data:
            for symbol, price in data["prices"].items():
                if symbol not in self.price_history:
                    self.price_history[symbol] = deque(maxlen=self.lookback_sr * 2)
                self.price_history[symbol].append(price)

        if "highs" in data:
            for symbol, high in data["highs"].items():
                if symbol not in self.high_history:
                    self.high_history[symbol] = deque(maxlen=self.lookback_sr * 2)
                self.high_history[symbol].append(high)

        if "lows" in data:
            for symbol, low in data["lows"].items():
                if symbol not in self.low_history:
                    self.low_history[symbol] = deque(maxlen=self.lookback_sr * 2)
                self.low_history[symbol].append(low)

        if "volumes" in data:
            for symbol, volume in data["volumes"].items():
                if symbol not in self.volume_history:
                    self.volume_history[symbol] = deque(maxlen=self.lookback_sr * 2)
                self.volume_history[symbol].append(volume)

        signals = []

        # Check for new breakouts
        if len(self.breakout_positions) < self.max_positions:
            breakout_signals = self._detect_breakouts()
            signals.extend(breakout_signals)

        # Check exit conditions for existing positions
        exit_signals = self._check_exits()
        signals.extend(exit_signals)

        return signals

    def _detect_breakouts(self) -> list[Signal]:
        """Detect breakout patterns across all symbols."""
        signals = []

        for symbol in self.price_history.keys():
            if symbol in self.breakout_positions:
                continue  # Already in position

            # Need sufficient history
            if len(self.price_history[symbol]) < self.lookback_sr:
                continue

            # Get data
            prices = np.array(self.price_history[symbol])
            highs = np.array(self.high_history.get(symbol, prices))
            lows = np.array(self.low_history.get(symbol, prices))
            volumes = np.array(self.volume_history.get(symbol, [0] * len(prices)))

            # Check different breakout types
            breakout = self._check_resistance_breakout(symbol, prices, highs, volumes)

            if breakout is None:
                breakout = self._check_range_breakout(symbol, prices, highs, lows, volumes)

            if breakout is None:
                breakout = self._check_consolidation_breakout(symbol, prices, highs, lows, volumes)

            if breakout:
                breakout_type, entry_price, stop_loss, take_profit, strength = breakout

                signals.append(Signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    strength=strength,
                    metadata={
                        "strategy": "breakout",
                        "breakout_type": breakout_type.value,
                        "entry": entry_price,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit
                    }
                ))

                # Track position
                self.breakout_positions[symbol] = (entry_price, stop_loss, take_profit)

                # Limit number of new positions per day
                if len(signals) >= 3:
                    break

        return signals

    def _check_resistance_breakout(
        self,
        symbol: str,
        prices: np.ndarray,
        highs: np.ndarray,
        volumes: np.ndarray
    ) -> tuple[BreakoutType, float, float, float, float] | None:
        """Check for resistance level breakout."""
        # Identify resistance level
        lookback = min(self.lookback_sr, len(prices))
        historical_highs = highs[-lookback-1:-1]  # Exclude current bar
        resistance = np.percentile(historical_highs, 95)  # Top 5% of highs

        # Current price
        current_price = prices[-1]
        current_high = highs[-1]

        # Check if breaking resistance
        if current_high <= resistance:
            return None

        breakout_size = (current_high - resistance) / resistance

        if breakout_size < self.breakout_threshold:
            return None

        # Volume confirmation
        if not self._check_volume_confirmation(volumes):
            return None

        # Calculate stops and targets
        entry = current_price
        stop_loss = entry * (1 - self.stop_loss_pct)
        take_profit = entry * (1 + self.take_profit_pct)

        # Strength based on breakout size
        strength = min(1.0, breakout_size / (self.breakout_threshold * 3))

        return (BreakoutType.RESISTANCE_BREAK, entry, stop_loss, take_profit, strength)

    def _check_range_breakout(
        self,
        symbol: str,
        prices: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        volumes: np.ndarray
    ) -> tuple[BreakoutType, float, float, float, float] | None:
        """Check for trading range breakout."""
        lookback = min(self.lookback_consolidation, len(prices))

        # Define range
        range_highs = highs[-lookback-1:-1]
        range_lows = lows[-lookback-1:-1]

        resistance = np.max(range_highs)
        support = np.min(range_lows)
        range_size = (resistance - support) / support

        # Check if price was consolidating (narrow range)
        if range_size > 0.15:  # Range too wide (>15%)
            return None

        # Current price
        current_high = highs[-1]

        # Check if breaking above range
        if current_high <= resistance:
            return None

        breakout_size = (current_high - resistance) / resistance

        if breakout_size < self.breakout_threshold:
            return None

        # Volume confirmation
        if not self._check_volume_confirmation(volumes):
            return None

        # Calculate stops and targets
        entry = prices[-1]
        stop_loss = support  # Use range low as stop
        take_profit = entry + (range_size * entry * 2)  # 2x range size target

        strength = min(1.0, breakout_size / (self.breakout_threshold * 2))

        return (BreakoutType.RANGE_BREAK, entry, stop_loss, take_profit, strength)

    def _check_consolidation_breakout(
        self,
        symbol: str,
        prices: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        volumes: np.ndarray
    ) -> tuple[BreakoutType, float, float, float, float] | None:
        """Check for consolidation pattern breakout."""
        lookback = min(self.lookback_consolidation, len(prices))

        if lookback < self.min_consolidation_days:
            return None

        # Calculate volatility during consolidation
        returns = np.diff(prices[-lookback-1:-1]) / prices[-lookback-2:-2]
        consolidation_vol = np.std(returns)

        # Calculate historical volatility
        if len(prices) >= self.lookback_sr:
            hist_returns = np.diff(prices[-self.lookback_sr:-lookback-1]) / prices[-self.lookback_sr-1:-lookback-2]
            historical_vol = np.std(hist_returns)
        else:
            return None

        # Check if volatility contracted (consolidation)
        vol_ratio = consolidation_vol / historical_vol

        if vol_ratio > 0.7:  # Volatility didn't contract enough
            return None

        # Check for expansion (breakout)
        current_return = (prices[-1] - prices[-2]) / prices[-2]
        recent_vol = np.std(returns[-5:]) if len(returns) >= 5 else consolidation_vol

        if recent_vol <= consolidation_vol * 1.5:  # No volatility expansion
            return None

        # Check price movement
        consolidation_high = np.max(highs[-lookback-1:-1])
        current_high = highs[-1]

        if current_high <= consolidation_high:
            return None

        breakout_size = (current_high - consolidation_high) / consolidation_high

        if breakout_size < self.breakout_threshold:
            return None

        # Volume confirmation
        if not self._check_volume_confirmation(volumes):
            return None

        # Calculate stops and targets
        entry = prices[-1]
        consolidation_low = np.min(lows[-lookback-1:-1])
        stop_loss = consolidation_low * 0.98  # 2% below consolidation low
        range_size = consolidation_high - consolidation_low
        take_profit = entry + (range_size * 2)  # 2x range size

        strength = min(1.0, (breakout_size * vol_ratio) / self.breakout_threshold)

        return (BreakoutType.CONSOLIDATION_BREAK, entry, stop_loss, take_profit, strength)

    def _check_volume_confirmation(self, volumes: np.ndarray) -> bool:
        """Check if current volume confirms the breakout."""
        if len(volumes) < 20:
            return True  # Insufficient data, pass by default

        avg_volume = np.mean(volumes[-20:-1])
        current_volume = volumes[-1]

        return current_volume >= (avg_volume * self.volume_multiplier)

    def _check_exits(self) -> list[Signal]:
        """Check exit conditions for existing breakout positions."""
        signals = []

        for symbol in list(self.breakout_positions.keys()):
            if symbol not in self.price_history:
                continue

            entry_price, stop_loss, take_profit = self.breakout_positions[symbol]
            current_price = self.price_history[symbol][-1]

            exit_signal = False
            reason = ""

            # Stop loss hit
            if current_price <= stop_loss:
                exit_signal = True
                reason = "stop_loss"

            # Take profit hit
            elif current_price >= take_profit:
                exit_signal = True
                reason = "take_profit"

            # Trailing stop (move stop to breakeven after 5% profit)
            elif current_price > entry_price * 1.05:
                new_stop = entry_price  # Breakeven
                if current_price < new_stop:
                    exit_signal = True
                    reason = "trailing_stop"

            if exit_signal:
                signals.append(Signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    strength=1.0,
                    metadata={
                        "strategy": "breakout_exit",
                        "reason": reason,
                        "entry": entry_price,
                        "exit": current_price,
                        "pnl_pct": (current_price - entry_price) / entry_price
                    }
                ))

                # Remove from tracking
                del self.breakout_positions[symbol]

        return signals

    def on_signal(self, signal: Signal) -> None:
        """Handle generated signal."""
        metadata = signal.metadata

        if signal.signal_type == SignalType.BUY:
            self.logger.info(
                f"Breakout entry: BUY {signal.symbol} @ {metadata['entry']:.2f} "
                f"[type={metadata['breakout_type']}, "
                f"stop={metadata['stop_loss']:.2f}, "
                f"target={metadata['take_profit']:.2f}]"
            )
        else:
            self.logger.info(
                f"Breakout exit: SELL {signal.symbol} @ {metadata['exit']:.2f} "
                f"[reason={metadata['reason']}, "
                f"P&L={metadata['pnl_pct']:.2%}]"
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
        self.logger.info("Stopping BreakoutStrategy")
        self.logger.info(f"Open breakout positions: {len(self.breakout_positions)}")

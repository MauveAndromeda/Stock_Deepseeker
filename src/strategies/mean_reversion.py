"""
Mean reversion trading strategy.

Buys oversold assets, sells overbought assets.
"""

from collections import deque
from datetime import datetime

import numpy as np

from src.strategies.base import BaseStrategy, Signal, SignalType


class MeanReversionStrategy(BaseStrategy):
    """
    Mean reversion strategy using Bollinger Bands.
    
    Parameters:
        window: Moving average window
        num_std: Number of standard deviations for bands
        entry_threshold: Z-score threshold for entry
        exit_threshold: Z-score threshold for exit
    """

    def __init__(
        self,
        window: int = 20,
        num_std: float = 2.0,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5
    ):
        """Initialize mean reversion strategy."""
        super().__init__(name="MeanReversionStrategy")

        self.window = window
        self.num_std = num_std
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold

        self.price_history = {}

    def on_data(self, data: dict) -> list[Signal]:
        """Generate mean reversion signals."""
        signals = []

        current_time = data.get("timestamp", datetime.now())

        for symbol, price in data.get("prices", {}).items():
            # Update history
            if symbol not in self.price_history:
                self.price_history[symbol] = deque(maxlen=self.window)

            self.price_history[symbol].append(price)

            # Need full window
            if len(self.price_history[symbol]) < self.window:
                continue

            # Calculate Bollinger Bands
            prices = list(self.price_history[symbol])
            mean = np.mean(prices)
            std = np.std(prices)

            # Calculate z-score
            z_score = (price - mean) / std if std > 0 else 0

            # Generate signals based on z-score
            if z_score < -self.entry_threshold:
                # Oversold - buy signal
                signal = Signal(
                    timestamp=current_time,
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    strength=min(abs(z_score) / self.entry_threshold, 1.0),
                    price=price,
                    metadata={
                        "z_score": z_score,
                        "mean": mean,
                        "std": std
                    }
                )
                signals.append(signal)

            elif z_score > self.entry_threshold:
                # Overbought - sell signal
                signal = Signal(
                    timestamp=current_time,
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    strength=min(abs(z_score) / self.entry_threshold, 1.0),
                    price=price,
                    metadata={
                        "z_score": z_score,
                        "mean": mean,
                        "std": std
                    }
                )
                signals.append(signal)

            elif abs(z_score) < self.exit_threshold and symbol in self.positions:
                # Close to mean - exit signal
                signal = Signal(
                    timestamp=current_time,
                    symbol=symbol,
                    signal_type=SignalType.SELL if self.positions[symbol] > 0 else SignalType.BUY,
                    strength=1.0,
                    price=price,
                    metadata={"z_score": z_score, "reason": "mean_reversion"}
                )
                signals.append(signal)

        return signals

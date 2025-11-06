"""
Basic Backtest Example

Simple example showing how to use the event-driven backtest engine.
This is a MINIMAL working example - not production code.
"""

from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from src.backtest import BacktestEngineV2, BacktestConfig
from src.backtest.events import SignalEvent, MarketEvent
from src.strategies.base import BaseStrategy, Signal, SignalType


class SimpleMovingAverageStrategy(BaseStrategy):
    """
    Simple moving average crossover strategy.

    Buy when fast MA crosses above slow MA.
    Sell when fast MA crosses below slow MA.
    """

    def __init__(self, fast_period: int = 10, slow_period: int = 20):
        super().__init__()
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.prices = []

    def on_data(self, data: dict) -> list:
        """Generate signals based on MA crossover."""
        if 'close' not in data:
            return []

        # Store prices
        self.prices.append(data['close'])

        # Need enough data for slow MA
        if len(self.prices) < self.slow_period:
            return []

        # Calculate MAs
        fast_ma = np.mean(self.prices[-self.fast_period:])
        slow_ma = np.mean(self.prices[-self.slow_period:])

        # Previous MAs
        prev_fast = np.mean(self.prices[-self.fast_period-1:-1])
        prev_slow = np.mean(self.prices[-self.slow_period-1:-1])

        signals = []

        # Bullish crossover
        if prev_fast <= prev_slow and fast_ma > slow_ma:
            signals.append(Signal(
                symbol='AAPL',
                signal_type=SignalType.BUY,
                strength=1.0
            ))

        # Bearish crossover
        elif prev_fast >= prev_slow and fast_ma < slow_ma:
            signals.append(Signal(
                symbol='AAPL',
                signal_type=SignalType.SELL,
                strength=1.0
            ))

        return signals


def generate_sample_data():
    """Generate sample price data for testing."""
    dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')

    # Generate random walk with trend
    np.random.seed(42)
    returns = np.random.randn(len(dates)) * 0.02 + 0.0005
    prices = 100 * (1 + returns).cumprod()

    data = pd.DataFrame({
        'date': dates,
        'open': prices * (1 + np.random.randn(len(dates)) * 0.005),
        'high': prices * (1 + np.abs(np.random.randn(len(dates))) * 0.01),
        'low': prices * (1 - np.abs(np.random.randn(len(dates))) * 0.01),
        'close': prices,
        'volume': np.random.randint(1000000, 10000000, len(dates))
    })

    return data


def main():
    """Run a basic backtest."""
    print("=" * 60)
    print("Basic Backtest Example")
    print("=" * 60)
    print()

    # Generate sample data
    print("Generating sample data...")
    data = generate_sample_data()
    print(f"Data: {len(data)} days from {data['date'].min()} to {data['date'].max()}")
    print()

    # Create strategy
    print("Creating strategy: Simple MA Crossover (10/20)")
    strategy = SimpleMovingAverageStrategy(fast_period=10, slow_period=20)
    print()

    # Configure backtest
    config = BacktestConfig(
        initial_capital=100000.0,
        commission=0.001,  # 0.1%
        slippage=0.0005,   # 0.05%
    )

    # Create backtest engine
    print("Running backtest...")
    engine = BacktestEngineV2(config)

    # NOTE: This is a simplified example
    # Full implementation would properly integrate data and strategy
    print()
    print("⚠️  NOTE: This is a SKELETON example")
    print("    Full backtest integration is still in development")
    print()

    print("Strategy created successfully")
    print(f"Config: Initial capital=${config.initial_capital:,.2f}")
    print(f"        Commission={config.commission:.2%}")
    print(f"        Slippage={config.slippage:.2%}")
    print()

    print("=" * 60)
    print("Example completed")
    print("=" * 60)


if __name__ == "__main__":
    main()

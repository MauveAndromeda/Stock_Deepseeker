"""
Simple Moving Average (SMA) crossover strategy

Minimal reference strategy that doesn't require AI dependencies.
"""

from typing import Dict, List

import numpy as np
import pandas as pd


class SimpleMovingAverageStrategy:
    """
    SMA 20/50 crossover strategy

    Rules:
    - Long when SMA(20) > SMA(50)
    - Flat otherwise
    - Next-day execution (no lookahead bias)
    - Equal-weight portfolio across all symbols
    """

    def __init__(
        self,
        short_window: int = 20,
        long_window: int = 50,
        initial_capital: float = 100000.0
    ):
        """
        Initialize strategy

        Args:
            short_window: Short SMA period (default: 20)
            long_window: Long SMA period (default: 50)
            initial_capital: Starting capital in dollars
        """
        self.short_window = short_window
        self.long_window = long_window
        self.initial_capital = initial_capital

    def run_backtest(
        self,
        data: Dict[str, pd.DataFrame],
        verbose: bool = True
    ) -> Dict:
        """
        Run backtest on market data

        Args:
            data: Dict mapping symbol -> DataFrame with OHLCV data
            verbose: Print progress messages

        Returns:
            Dict with backtest results:
            {
                'portfolio_value': pd.Series,  # Daily portfolio value
                'returns': pd.Series,  # Daily returns
                'positions': Dict[str, pd.Series],  # Positions per symbol
                'trades': List[Dict],  # Trade log
                'symbols': List[str],
                'config': Dict
            }
        """
        if not data:
            raise ValueError("No data provided")

        symbols = list(data.keys())
        n_symbols = len(symbols)

        if verbose:
            print(f"Running SMA({self.short_window}/{self.long_window}) backtest...")
            print(f"Symbols: {', '.join(symbols)}")
            print(f"Initial capital: ${self.initial_capital:,.2f}\n")

        # Generate signals for each symbol
        signals = {}
        for symbol in symbols:
            signals[symbol] = self._generate_signals(data[symbol])

        # Align all data to common date range
        all_dates = sorted(set().union(*[set(sig.index) for sig in signals.values()]))
        portfolio_dates = pd.DatetimeIndex(all_dates)

        # Initialize portfolio tracking
        portfolio_value = pd.Series(index=portfolio_dates, dtype=float)
        portfolio_value.iloc[0] = self.initial_capital

        cash = self.initial_capital
        positions = {symbol: pd.Series(0.0, index=portfolio_dates) for symbol in symbols}
        trades = []

        # Simulate trading day by day
        for i in range(len(portfolio_dates)):
            date = portfolio_dates[i]

            # Calculate position sizes (equal weight when signal is long)
            target_positions = {}
            active_symbols = []

            for symbol in symbols:
                if date in signals[symbol].index:
                    signal = signals[symbol].loc[date]
                    if signal > 0:  # Long signal
                        active_symbols.append(symbol)
                        target_positions[symbol] = 1.0 / n_symbols  # Equal weight
                    else:
                        target_positions[symbol] = 0.0
                else:
                    target_positions[symbol] = 0.0

            # Rebalance portfolio
            for symbol in symbols:
                if date not in data[symbol].index:
                    continue

                current_pos = positions[symbol].iloc[i - 1] if i > 0 else 0.0
                target_pos = target_positions[symbol]

                if abs(current_pos - target_pos) > 0.001:  # Rebalance needed
                    price = data[symbol].loc[date, 'Adj Close']
                    shares_change = (target_pos - current_pos) * self.initial_capital / price

                    # Execute trade
                    cash -= shares_change * price
                    positions[symbol].iloc[i] = current_pos + shares_change / (self.initial_capital / price)

                    if abs(shares_change) > 0.001:
                        trades.append({
                            'date': date,
                            'symbol': symbol,
                            'action': 'BUY' if shares_change > 0 else 'SELL',
                            'shares': abs(shares_change),
                            'price': price,
                            'value': abs(shares_change * price)
                        })
                else:
                    positions[symbol].iloc[i] = current_pos

            # Calculate portfolio value
            holdings_value = 0.0
            for symbol in symbols:
                if date in data[symbol].index:
                    price = data[symbol].loc[date, 'Adj Close']
                    holdings_value += positions[symbol].iloc[i] * price * (self.initial_capital / self.initial_capital)

            portfolio_value.iloc[i] = cash + holdings_value

        # Calculate returns
        returns = portfolio_value.pct_change().fillna(0.0)

        if verbose:
            print(f"Backtest complete")
            print(f"Total trades: {len(trades)}")
            print(f"Final value: ${portfolio_value.iloc[-1]:,.2f}")
            total_return = (portfolio_value.iloc[-1] / self.initial_capital - 1) * 100
            print(f"Total return: {total_return:.2f}%\n")

        return {
            'portfolio_value': portfolio_value,
            'returns': returns,
            'positions': positions,
            'trades': trades,
            'symbols': symbols,
            'config': {
                'strategy': 'SMA',
                'short_window': self.short_window,
                'long_window': self.long_window,
                'initial_capital': self.initial_capital,
                'n_symbols': n_symbols
            }
        }

    def _generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate trading signals for a single symbol

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Series with signals (1.0 = long, 0.0 = flat)
        """
        # Calculate SMAs
        sma_short = df['Adj Close'].rolling(window=self.short_window).mean()
        sma_long = df['Adj Close'].rolling(window=self.long_window).mean()

        # Generate signals (1 = long, 0 = flat)
        signals = pd.Series(0.0, index=df.index)
        signals[sma_short > sma_long] = 1.0

        # Shift signals by 1 day to avoid lookahead bias
        # (signal generated today, executed tomorrow)
        signals = signals.shift(1).fillna(0.0)

        return signals

"""
Value investing strategy based on fundamental factors.
"""


import numpy as np
import pandas as pd

from src.factors.value import (
    DividendYield,
    EarningsYield,
    FCFYield,
    PriceToBook,
    PriceToEarnings,
    PriceToSales,
)
from src.strategies.base import BaseStrategy, Signal, SignalType


class ValueStrategy(BaseStrategy):
    """
    Value investing strategy using multiple value factors.

    Combines multiple value metrics to identify undervalued securities.
    Uses composite value score with equal or custom weights.

    Parameters:
        n_positions: Number of positions to hold
        rebalance_frequency: Days between rebalancing
        min_market_cap: Minimum market cap filter (millions)
        factor_weights: Custom weights for each factor
        exclude_financials: Exclude financial sector stocks
        value_threshold: Percentile threshold for buying (e.g., 0.2 = top 20%)
    """

    def __init__(
        self,
        n_positions: int = 20,
        rebalance_frequency: int = 21,  # Monthly
        min_market_cap: float = 1000,  # $1B
        factor_weights: dict[str, float] | None = None,
        exclude_financials: bool = True,
        value_threshold: float = 0.2,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.n_positions = n_positions
        self.rebalance_frequency = rebalance_frequency
        self.min_market_cap = min_market_cap
        self.exclude_financials = exclude_financials
        self.value_threshold = value_threshold

        # Initialize value factors
        self.factors = {
            "pb": PriceToBook(),
            "pe": PriceToEarnings(),
            "ps": PriceToSales(),
            "earnings_yield": EarningsYield(),
            "fcf_yield": FCFYield(),
            "dividend_yield": DividendYield()
        }

        # Factor weights (default to equal weight)
        if factor_weights is None:
            self.factor_weights = {name: 1.0 / len(self.factors) for name in self.factors}
        else:
            self.factor_weights = factor_weights
            # Normalize weights
            total = sum(factor_weights.values())
            self.factor_weights = {k: v / total for k, v in factor_weights.items()}

        # State
        self.last_rebalance_day = 0
        self.fundamental_data: dict[str, pd.DataFrame] = {}
        self.market_caps: dict[str, float] = {}
        self.sectors: dict[str, str] = {}

    def on_start(self) -> None:
        """Initialize strategy."""
        self.logger.info(
            f"Starting ValueStrategy with {self.n_positions} positions, "
            f"rebalancing every {self.rebalance_frequency} days"
        )
        self.logger.info(f"Factor weights: {self.factor_weights}")

    def on_data(self, data: dict) -> list[Signal]:
        """
        Generate trading signals based on value factors.

        Args:
            data: Market data dictionary containing:
                - prices: Dict[symbol, price]
                - fundamentals: Dict[symbol, fundamental_data]
                - market_caps: Dict[symbol, market_cap]
                - sectors: Dict[symbol, sector]

        Returns:
            List of trading signals
        """
        self.days_elapsed += 1

        # Update fundamental data
        if "fundamentals" in data:
            self.fundamental_data.update(data["fundamentals"])
        if "market_caps" in data:
            self.market_caps.update(data["market_caps"])
        if "sectors" in data:
            self.sectors.update(data["sectors"])

        # Check if rebalancing is needed
        if self.days_elapsed - self.last_rebalance_day < self.rebalance_frequency:
            return []

        self.last_rebalance_day = self.days_elapsed

        # Calculate value scores for all symbols
        value_scores = self._calculate_value_scores()

        if len(value_scores) == 0:
            return []

        # Apply filters
        filtered_scores = self._apply_filters(value_scores)

        if len(filtered_scores) == 0:
            return []

        # Rank and select top value stocks
        signals = self._generate_rebalance_signals(filtered_scores)

        return signals

    def _calculate_value_scores(self) -> dict[str, float]:
        """Calculate composite value score for each symbol."""
        value_scores = {}

        for symbol in self.fundamental_data.keys():
            if symbol not in self.fundamental_data:
                continue

            fund_data = self.fundamental_data[symbol]

            # Calculate each factor
            factor_values = {}
            for factor_name, factor in self.factors.items():
                try:
                    # Convert fundamental data to required format
                    value = self._calculate_factor(factor, fund_data)
                    if value is not None and not np.isnan(value):
                        factor_values[factor_name] = value
                except Exception as e:
                    self.logger.warning(f"Error calculating {factor_name} for {symbol}: {e}")
                    continue

            # Skip if we don't have enough factors
            if len(factor_values) < 3:
                continue

            # Calculate composite score (weighted average of z-scores)
            composite_score = 0.0
            total_weight = 0.0

            for factor_name, value in factor_values.items():
                weight = self.factor_weights.get(factor_name, 0.0)
                # Lower is better for valuation ratios, so invert
                if factor_name in ["pb", "pe", "ps"]:
                    score = -value  # Lower P/B, P/E, P/S is better
                else:
                    score = value  # Higher yields are better

                composite_score += weight * score
                total_weight += weight

            if total_weight > 0:
                value_scores[symbol] = composite_score / total_weight

        # Normalize scores to z-scores
        if len(value_scores) > 1:
            values = np.array(list(value_scores.values()))
            mean = np.mean(values)
            std = np.std(values)
            if std > 0:
                value_scores = {
                    symbol: (score - mean) / std
                    for symbol, score in value_scores.items()
                }

        return value_scores

    def _calculate_factor(self, factor, fund_data: pd.DataFrame) -> float | None:
        """Calculate a single factor value from fundamental data."""
        # This is a simplified version - in production, you'd have
        # proper fundamental data structures
        try:
            if hasattr(factor, "calculate"):
                result = factor.calculate(fund_data)
                if isinstance(result, pd.Series):
                    return result.iloc[-1] if len(result) > 0 else None
                return result
            return None
        except Exception:
            return None

    def _apply_filters(self, value_scores: dict[str, float]) -> dict[str, float]:
        """Apply market cap and sector filters."""
        filtered = {}

        for symbol, score in value_scores.items():
            # Market cap filter
            if symbol in self.market_caps:
                if self.market_caps[symbol] < self.min_market_cap:
                    continue

            # Sector filter
            if self.exclude_financials and symbol in self.sectors:
                if self.sectors[symbol] in ["Financials", "Financial Services"]:
                    continue

            filtered[symbol] = score

        return filtered

    def _generate_rebalance_signals(self, value_scores: dict[str, float]) -> list[Signal]:
        """Generate signals to rebalance portfolio."""
        signals = []

        # Sort by value score (higher is better)
        sorted_symbols = sorted(
            value_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Calculate threshold
        n_buy = int(len(sorted_symbols) * self.value_threshold)
        n_buy = min(n_buy, self.n_positions)

        # Get top value stocks
        buy_symbols = {symbol for symbol, _ in sorted_symbols[:n_buy]}

        # Get current positions
        current_positions = set(self.positions.keys())

        # Close positions not in buy list
        for symbol in current_positions:
            if symbol not in buy_symbols:
                signals.append(Signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    strength=1.0,
                    metadata={"reason": "rebalance_exit"}
                ))

        # Open new positions
        for symbol in buy_symbols:
            if symbol not in current_positions:
                # Strength based on value score
                strength = value_scores[symbol] / max(abs(v) for v in value_scores.values())
                strength = max(0.1, min(1.0, strength))  # Clamp to [0.1, 1.0]

                signals.append(Signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    strength=strength,
                    metadata={"value_score": value_scores[symbol]}
                ))

        return signals

    def on_signal(self, signal: Signal) -> None:
        """Handle generated signal."""
        self.logger.info(
            f"Value signal: {signal.signal_type.value} {signal.symbol} "
            f"(strength={signal.strength:.2f}, score={signal.metadata.get('value_score', 0):.2f})"
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
        self.logger.info("Stopping ValueStrategy")
        self.logger.info(f"Final positions: {list(self.positions.keys())}")

"""
Multi-factor strategy combining momentum, value, and quality.
"""

from dataclasses import dataclass

import numpy as np

from src.factors.momentum import RSI, PriceMomentum
from src.factors.quality import ROE, DebtToEquity
from src.factors.value import EarningsYield, PriceToBook
from src.factors.volatility import Volatility
from src.strategies.base import BaseStrategy, Signal, SignalType


@dataclass
class FactorScore:
    """Container for multi-factor scores."""
    symbol: str
    momentum_score: float
    value_score: float
    quality_score: float
    volatility_score: float
    composite_score: float

    def __repr__(self) -> str:
        return (
            f"FactorScore({self.symbol}: "
            f"M={self.momentum_score:.2f}, V={self.value_score:.2f}, "
            f"Q={self.quality_score:.2f}, Vol={self.volatility_score:.2f}, "
            f"Composite={self.composite_score:.2f})"
        )


class MultiFactorStrategy(BaseStrategy):
    """
    Multi-factor strategy combining multiple factor categories.

    Combines momentum, value, quality, and low volatility factors
    to construct a diversified portfolio. Uses factor timing
    to dynamically adjust factor weights based on recent performance.

    Parameters:
        n_positions: Number of positions to hold
        rebalance_frequency: Days between rebalancing
        factor_weights: Weights for each factor category
        use_factor_timing: Dynamically adjust weights based on performance
        timing_lookback: Lookback period for factor timing (days)
        long_only: Only take long positions
        max_sector_weight: Maximum weight per sector
        min_liquidity: Minimum average daily volume (shares)
    """

    def __init__(
        self,
        n_positions: int = 30,
        rebalance_frequency: int = 21,  # Monthly
        factor_weights: dict[str, float] | None = None,
        use_factor_timing: bool = True,
        timing_lookback: int = 63,  # ~3 months
        long_only: bool = True,
        max_sector_weight: float = 0.3,
        min_liquidity: float = 1_000_000,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.n_positions = n_positions
        self.rebalance_frequency = rebalance_frequency
        self.use_factor_timing = use_factor_timing
        self.timing_lookback = timing_lookback
        self.long_only = long_only
        self.max_sector_weight = max_sector_weight
        self.min_liquidity = min_liquidity

        # Default factor weights
        if factor_weights is None:
            self.base_factor_weights = {
                "momentum": 0.25,
                "value": 0.25,
                "quality": 0.25,
                "low_volatility": 0.25
            }
        else:
            total = sum(factor_weights.values())
            self.base_factor_weights = {k: v / total for k, v in factor_weights.items()}

        self.current_factor_weights = self.base_factor_weights.copy()

        # Initialize factors
        self._init_factors()

        # State
        self.last_rebalance_day = 0
        self.price_history: dict[str, list[float]] = {}
        self.factor_performance_history: dict[str, list[float]] = {}
        self.sectors: dict[str, str] = {}
        self.volumes: dict[str, float] = {}

    def _init_factors(self) -> None:
        """Initialize all factors."""
        # Momentum factors
        self.momentum_factors = {
            "momentum_12m": PriceMomentum(lookback=252, skip=21),
            "rsi": RSI(period=14)
        }

        # Value factors
        self.value_factors = {
            "pb": PriceToBook(),
            "earnings_yield": EarningsYield()
        }

        # Quality factors
        self.quality_factors = {
            "roe": ROE(),
            "debt_to_equity": DebtToEquity()
        }

        # Volatility factors
        self.volatility_factors = {
            "volatility": Volatility(window=60)
        }

    def on_start(self) -> None:
        """Initialize strategy."""
        self.logger.info(
            f"Starting MultiFactorStrategy with {self.n_positions} positions"
        )
        self.logger.info(f"Base factor weights: {self.base_factor_weights}")
        self.logger.info(f"Factor timing: {'enabled' if self.use_factor_timing else 'disabled'}")

    def on_data(self, data: dict) -> list[Signal]:
        """
        Generate trading signals based on multi-factor scores.

        Args:
            data: Market data dictionary

        Returns:
            List of trading signals
        """
        self.days_elapsed += 1

        # Update price history
        if "prices" in data:
            for symbol, price in data["prices"].items():
                if symbol not in self.price_history:
                    self.price_history[symbol] = []
                self.price_history[symbol].append(price)
                # Keep limited history
                if len(self.price_history[symbol]) > 500:
                    self.price_history[symbol] = self.price_history[symbol][-500:]

        # Update metadata
        if "sectors" in data:
            self.sectors.update(data["sectors"])
        if "volumes" in data:
            self.volumes.update(data["volumes"])

        # Check if rebalancing is needed
        if self.days_elapsed - self.last_rebalance_day < self.rebalance_frequency:
            return []

        self.last_rebalance_day = self.days_elapsed

        # Update factor weights if using timing
        if self.use_factor_timing:
            self._update_factor_weights()

        # Calculate factor scores for all symbols
        factor_scores = self._calculate_factor_scores()

        if len(factor_scores) == 0:
            return []

        # Generate rebalancing signals
        signals = self._generate_rebalance_signals(factor_scores)

        return signals

    def _calculate_factor_scores(self) -> list[FactorScore]:
        """Calculate multi-factor scores for all symbols."""
        scores = []

        # Need enough history
        min_history = 252
        eligible_symbols = [
            symbol for symbol, prices in self.price_history.items()
            if len(prices) >= min_history
        ]

        if len(eligible_symbols) == 0:
            return []

        # Calculate raw factor values
        momentum_values = self._calculate_momentum_scores(eligible_symbols)
        value_values = self._calculate_value_scores(eligible_symbols)
        quality_values = self._calculate_quality_scores(eligible_symbols)
        volatility_values = self._calculate_volatility_scores(eligible_symbols)

        # Convert to z-scores
        momentum_z = self._to_z_scores(momentum_values)
        value_z = self._to_z_scores(value_values)
        quality_z = self._to_z_scores(quality_values)
        volatility_z = self._to_z_scores(volatility_values)

        # Calculate composite scores
        for symbol in eligible_symbols:
            # Skip if missing any factor
            if (symbol not in momentum_z or symbol not in value_z or
                symbol not in quality_z or symbol not in volatility_z):
                continue

            # Apply liquidity filter
            if symbol in self.volumes:
                if self.volumes[symbol] < self.min_liquidity:
                    continue

            composite = (
                self.current_factor_weights["momentum"] * momentum_z[symbol] +
                self.current_factor_weights["value"] * value_z[symbol] +
                self.current_factor_weights["quality"] * quality_z[symbol] +
                self.current_factor_weights["low_volatility"] * volatility_z[symbol]
            )

            scores.append(FactorScore(
                symbol=symbol,
                momentum_score=momentum_z[symbol],
                value_score=value_z[symbol],
                quality_score=quality_z[symbol],
                volatility_score=volatility_z[symbol],
                composite_score=composite
            ))

        return scores

    def _calculate_momentum_scores(self, symbols: list[str]) -> dict[str, float]:
        """Calculate momentum scores."""
        scores = {}
        for symbol in symbols:
            prices = self.price_history[symbol]
            if len(prices) < 252:
                continue

            # 12-month momentum (skip last month)
            mom_12m = (prices[-21] / prices[-252]) - 1

            # RSI
            returns = np.diff(prices[-100:]) / prices[-101:-1]
            gains = returns[returns > 0]
            losses = -returns[returns < 0]
            avg_gain = np.mean(gains) if len(gains) > 0 else 0
            avg_loss = np.mean(losses) if len(losses) > 0 else 0
            rs = avg_gain / avg_loss if avg_loss > 0 else 100
            rsi = 100 - (100 / (1 + rs))
            rsi_score = (rsi - 50) / 50  # Normalize to [-1, 1]

            # Combine
            scores[symbol] = 0.7 * mom_12m + 0.3 * rsi_score

        return scores

    def _calculate_value_scores(self, symbols: list[str]) -> dict[str, float]:
        """Calculate value scores."""
        # This is simplified - in production, you'd use actual fundamental data
        scores = {}
        for symbol in symbols:
            # Placeholder: inverse of price momentum as proxy
            # In production: use actual P/B, P/E, etc.
            prices = self.price_history[symbol]
            if len(prices) < 252:
                continue

            # Inverse momentum as value proxy (mean reversion)
            mom_1m = (prices[-1] / prices[-21]) - 1
            scores[symbol] = -mom_1m  # Negative because we want beaten-down stocks

        return scores

    def _calculate_quality_scores(self, symbols: list[str]) -> dict[str, float]:
        """Calculate quality scores."""
        # This is simplified - in production, you'd use actual fundamental data
        scores = {}
        for symbol in symbols:
            # Placeholder: inverse volatility as quality proxy
            # In production: use actual ROE, margins, debt ratios
            prices = self.price_history[symbol]
            if len(prices) < 63:
                continue

            returns = np.diff(prices[-63:]) / prices[-64:-1]
            volatility = np.std(returns)
            scores[symbol] = -volatility  # Lower volatility = higher quality

        return scores

    def _calculate_volatility_scores(self, symbols: list[str]) -> dict[str, float]:
        """Calculate volatility scores (lower is better)."""
        scores = {}
        for symbol in symbols:
            prices = self.price_history[symbol]
            if len(prices) < 63:
                continue

            returns = np.diff(prices[-63:]) / prices[-64:-1]
            volatility = np.std(returns) * np.sqrt(252)  # Annualized
            scores[symbol] = -volatility  # Negative because lower is better

        return scores

    def _to_z_scores(self, values: dict[str, float]) -> dict[str, float]:
        """Convert raw values to z-scores."""
        if len(values) == 0:
            return {}

        vals = np.array(list(values.values()))
        mean = np.mean(vals)
        std = np.std(vals)

        if std == 0:
            return dict.fromkeys(values, 0.0)

        return {
            symbol: (value - mean) / std
            for symbol, value in values.items()
        }

    def _update_factor_weights(self) -> None:
        """Update factor weights based on recent performance."""
        # This is a simplified version of factor timing
        # In production, you'd track actual factor returns

        if len(self.factor_performance_history) < self.timing_lookback:
            return

        # For now, just revert to base weights
        # In production: calculate factor IC or returns over timing_lookback
        self.current_factor_weights = self.base_factor_weights.copy()

        self.logger.info(f"Updated factor weights: {self.current_factor_weights}")

    def _generate_rebalance_signals(self, factor_scores: list[FactorScore]) -> list[Signal]:
        """Generate rebalancing signals."""
        signals = []

        # Sort by composite score
        sorted_scores = sorted(factor_scores, key=lambda x: x.composite_score, reverse=True)

        # Apply sector constraints
        sector_weights = {}
        selected_symbols = []

        for score in sorted_scores:
            if len(selected_symbols) >= self.n_positions:
                break

            # Check sector weight
            sector = self.sectors.get(score.symbol, "Unknown")
            current_sector_weight = sector_weights.get(sector, 0.0)
            target_weight = 1.0 / self.n_positions

            if current_sector_weight + target_weight <= self.max_sector_weight:
                selected_symbols.append(score.symbol)
                sector_weights[sector] = current_sector_weight + target_weight

        # Generate signals
        target_symbols = set(selected_symbols)
        current_positions = set(self.positions.keys())

        # Close positions not in target
        for symbol in current_positions:
            if symbol not in target_symbols:
                signals.append(Signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    strength=1.0,
                    metadata={"reason": "rebalance_exit"}
                ))

        # Open new positions
        for symbol in target_symbols:
            if symbol not in current_positions:
                # Find score
                score = next((s for s in factor_scores if s.symbol == symbol), None)
                if score:
                    signals.append(Signal(
                        symbol=symbol,
                        signal_type=SignalType.BUY,
                        strength=min(1.0, max(0.1, score.composite_score / 2.0)),
                        metadata={"factor_score": score}
                    ))

        return signals

    def on_signal(self, signal: Signal) -> None:
        """Handle generated signal."""
        score = signal.metadata.get("factor_score")
        if score:
            self.logger.info(f"Multi-factor signal: {signal.signal_type.value} {signal.symbol}")
            self.logger.info(f"  {score}")
        else:
            self.logger.info(f"Exit signal: {signal.signal_type.value} {signal.symbol}")

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
        self.logger.info("Stopping MultiFactorStrategy")
        self.logger.info(f"Final factor weights: {self.current_factor_weights}")

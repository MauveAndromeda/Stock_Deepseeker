"""
Market neutral strategy using long/short factor exposures.
"""

from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.strategies.base import BaseStrategy, Signal, SignalType


@dataclass
class SecurityScore:
    """Container for security scoring data."""
    symbol: str
    factor_scores: dict[str, float]
    composite_score: float
    beta: float
    sector: str
    market_cap: float

    def __repr__(self) -> str:
        return f"SecurityScore({self.symbol}: score={self.composite_score:.2f}, beta={self.beta:.2f})"


class MarketNeutralStrategy(BaseStrategy):
    """
    Market neutral long/short equity strategy.

    Constructs a dollar-neutral portfolio that is:
    - Long: High-factor-score stocks (undervalued, high quality, strong momentum)
    - Short: Low-factor-score stocks (overvalued, low quality, weak momentum)

    The strategy maintains:
    - Dollar neutrality (long value ≈ short value)
    - Beta neutrality (portfolio beta ≈ 0)
    - Sector neutrality (optional)

    Parameters:
        n_long: Number of long positions
        n_short: Number of short positions
        rebalance_frequency: Days between rebalancing
        target_leverage: Target gross leverage (e.g., 2.0 = 100% long + 100% short)
        maintain_beta_neutral: Adjust positions to maintain zero beta
        maintain_sector_neutral: Match long/short exposure by sector
        factor_weights: Weights for different factor categories
        max_single_position: Maximum position size as % of portfolio
        correlation_threshold: Maximum allowed correlation between longs and shorts
    """

    def __init__(
        self,
        n_long: int = 25,
        n_short: int = 25,
        rebalance_frequency: int = 21,
        target_leverage: float = 2.0,
        maintain_beta_neutral: bool = True,
        maintain_sector_neutral: bool = True,
        factor_weights: dict[str, float] | None = None,
        max_single_position: float = 0.05,
        correlation_threshold: float = 0.3,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.n_long = n_long
        self.n_short = n_short
        self.rebalance_frequency = rebalance_frequency
        self.target_leverage = target_leverage
        self.maintain_beta_neutral = maintain_beta_neutral
        self.maintain_sector_neutral = maintain_sector_neutral
        self.max_single_position = max_single_position
        self.correlation_threshold = correlation_threshold

        # Factor weights
        if factor_weights is None:
            self.factor_weights = {
                "momentum": 0.33,
                "value": 0.33,
                "quality": 0.34
            }
        else:
            total = sum(factor_weights.values())
            self.factor_weights = {k: v / total for k, v in factor_weights.items()}

        # State
        self.last_rebalance_day = 0
        self.price_history: dict[str, list[float]] = {}
        self.market_prices: list[float] = []
        self.fundamentals: dict[str, pd.DataFrame] = {}
        self.sectors: dict[str, str] = {}
        self.market_caps: dict[str, float] = {}
        self.long_positions: set[str] = set()
        self.short_positions: set[str] = set()

    def on_start(self) -> None:
        """Initialize strategy."""
        self.logger.info(
            f"Starting MarketNeutralStrategy: {self.n_long} long / {self.n_short} short"
        )
        self.logger.info(f"Target leverage: {self.target_leverage}x")
        self.logger.info(
            f"Beta neutral: {self.maintain_beta_neutral}, "
            f"Sector neutral: {self.maintain_sector_neutral}"
        )

    def on_data(self, data: dict) -> list[Signal]:
        """
        Generate market neutral signals.

        Args:
            data: Market data containing prices, fundamentals, sectors, etc.

        Returns:
            List of trading signals
        """
        self.days_elapsed += 1

        # Update data
        if "prices" in data:
            for symbol, price in data["prices"].items():
                if symbol not in self.price_history:
                    self.price_history[symbol] = []
                self.price_history[symbol].append(price)
                # Keep limited history
                if len(self.price_history[symbol]) > 252:
                    self.price_history[symbol] = self.price_history[symbol][-252:]

        if "market_price" in data:
            self.market_prices.append(data["market_price"])
            if len(self.market_prices) > 252:
                self.market_prices = self.market_prices[-252:]

        if "fundamentals" in data:
            self.fundamentals.update(data["fundamentals"])

        if "sectors" in data:
            self.sectors.update(data["sectors"])

        if "market_caps" in data:
            self.market_caps.update(data["market_caps"])

        # Check if rebalancing is needed
        if self.days_elapsed - self.last_rebalance_day < self.rebalance_frequency:
            return []

        self.last_rebalance_day = self.days_elapsed

        # Need sufficient data
        if len(self.market_prices) < 60:
            return []

        # Calculate security scores
        security_scores = self._calculate_security_scores()

        if len(security_scores) < (self.n_long + self.n_short):
            return []

        # Construct long/short portfolios
        long_symbols, short_symbols = self._construct_portfolios(security_scores)

        # Generate rebalancing signals
        signals = self._generate_rebalance_signals(long_symbols, short_symbols)

        # Log portfolio characteristics
        self._log_portfolio_stats(security_scores, long_symbols, short_symbols)

        return signals

    def _calculate_security_scores(self) -> list[SecurityScore]:
        """Calculate multi-factor scores for all securities."""
        scores = []

        # Need enough price history
        min_history = 126
        eligible_symbols = [
            symbol for symbol, prices in self.price_history.items()
            if len(prices) >= min_history
        ]

        if len(eligible_symbols) == 0:
            return []

        # Calculate factor scores
        momentum_scores = self._calculate_momentum_scores(eligible_symbols)
        value_scores = self._calculate_value_scores(eligible_symbols)
        quality_scores = self._calculate_quality_scores(eligible_symbols)
        betas = self._calculate_betas(eligible_symbols)

        # Combine scores
        for symbol in eligible_symbols:
            if symbol not in momentum_scores or symbol not in betas:
                continue

            factor_scores = {
                "momentum": momentum_scores.get(symbol, 0),
                "value": value_scores.get(symbol, 0),
                "quality": quality_scores.get(symbol, 0)
            }

            # Calculate composite score
            composite = sum(
                self.factor_weights[factor] * score
                for factor, score in factor_scores.items()
            )

            scores.append(SecurityScore(
                symbol=symbol,
                factor_scores=factor_scores,
                composite_score=composite,
                beta=betas[symbol],
                sector=self.sectors.get(symbol, "Unknown"),
                market_cap=self.market_caps.get(symbol, 0)
            ))

        return scores

    def _calculate_momentum_scores(self, symbols: list[str]) -> dict[str, float]:
        """Calculate momentum z-scores."""
        raw_scores = {}

        for symbol in symbols:
            prices = self.price_history[symbol]
            if len(prices) < 126:
                continue

            # 6-month momentum
            mom_6m = (prices[-1] / prices[-126]) - 1
            raw_scores[symbol] = mom_6m

        # Convert to z-scores
        return self._to_z_scores(raw_scores)

    def _calculate_value_scores(self, symbols: list[str]) -> dict[str, float]:
        """Calculate value z-scores."""
        # Simplified - in production use actual fundamentals
        raw_scores = {}

        for symbol in symbols:
            prices = self.price_history[symbol]
            if len(prices) < 63:
                continue

            # Use inverse of recent performance as value proxy
            # In production: use actual P/B, P/E, etc.
            recent_return = (prices[-1] / prices[-63]) - 1
            raw_scores[symbol] = -recent_return  # Beaten-down = value

        return self._to_z_scores(raw_scores)

    def _calculate_quality_scores(self, symbols: list[str]) -> dict[str, float]:
        """Calculate quality z-scores."""
        # Simplified - in production use actual quality metrics
        raw_scores = {}

        for symbol in symbols:
            prices = self.price_history[symbol]
            if len(prices) < 63:
                continue

            # Use stability (inverse volatility) as quality proxy
            # In production: use actual ROE, margins, etc.
            returns = np.diff(prices[-63:]) / prices[-64:-1]
            volatility = np.std(returns)
            raw_scores[symbol] = -volatility  # Lower vol = higher quality

        return self._to_z_scores(raw_scores)

    def _calculate_betas(self, symbols: list[str]) -> dict[str, float]:
        """Calculate market betas."""
        betas = {}

        if len(self.market_prices) < 60:
            return dict.fromkeys(symbols, 1.0)

        market_returns = np.diff(self.market_prices[-60:]) / self.market_prices[-61:-1]
        market_var = np.var(market_returns)

        if market_var == 0:
            return dict.fromkeys(symbols, 1.0)

        for symbol in symbols:
            prices = self.price_history[symbol]
            if len(prices) < 60:
                continue

            stock_returns = np.diff(prices[-60:]) / prices[-61:-1]
            covariance = np.cov(stock_returns, market_returns)[0, 1]
            beta = covariance / market_var

            betas[symbol] = beta

        return betas

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

    def _construct_portfolios(
        self,
        security_scores: list[SecurityScore]
    ) -> tuple[list[str], list[str]]:
        """Construct long and short portfolios."""
        # Sort by composite score
        sorted_scores = sorted(security_scores, key=lambda x: x.composite_score, reverse=True)

        long_candidates = []
        short_candidates = []

        # Apply sector constraints if needed
        if self.maintain_sector_neutral:
            long_candidates, short_candidates = self._apply_sector_constraints(sorted_scores)
        else:
            # Simple: top N long, bottom N short
            long_candidates = [s.symbol for s in sorted_scores[:self.n_long * 2]]  # Take extras
            short_candidates = [s.symbol for s in sorted_scores[-self.n_short * 2:]]

        # Apply beta constraints if needed
        if self.maintain_beta_neutral:
            long_candidates, short_candidates = self._apply_beta_constraints(
                security_scores, long_candidates, short_candidates
            )

        # Select final portfolios
        long_symbols = long_candidates[:self.n_long]
        short_symbols = short_candidates[:self.n_short]

        return long_symbols, short_symbols

    def _apply_sector_constraints(
        self,
        sorted_scores: list[SecurityScore]
    ) -> tuple[list[str], list[str]]:
        """Apply sector neutrality constraints."""
        # Group by sector
        sector_longs: dict[str, list[str]] = defaultdict(list)
        sector_shorts: dict[str, list[str]] = defaultdict(list)

        # Top half = long candidates
        for score in sorted_scores[:len(sorted_scores) // 2]:
            sector_longs[score.sector].append(score.symbol)

        # Bottom half = short candidates
        for score in sorted_scores[len(sorted_scores) // 2:]:
            sector_shorts[score.sector].append(score.symbol)

        # Select balanced positions from each sector
        all_sectors = set(sector_longs.keys()) | set(sector_shorts.keys())
        n_per_sector = max(1, self.n_long // len(all_sectors))

        long_symbols = []
        short_symbols = []

        for sector in all_sectors:
            # Add longs from this sector
            long_symbols.extend(sector_longs[sector][:n_per_sector])
            # Add shorts from this sector
            short_symbols.extend(sector_shorts[sector][:n_per_sector])

        return long_symbols, short_symbols

    def _apply_beta_constraints(
        self,
        security_scores: list[SecurityScore],
        long_candidates: list[str],
        short_candidates: list[str]
    ) -> tuple[list[str], list[str]]:
        """
        Adjust portfolios to maintain beta neutrality.

        Target: Long portfolio beta * Long value = Short portfolio beta * Short value
        """
        # Get betas
        score_map = {s.symbol: s for s in security_scores}

        # Calculate current betas
        long_betas = [score_map[sym].beta for sym in long_candidates if sym in score_map]
        short_betas = [score_map[sym].beta for sym in short_candidates if sym in score_map]

        if len(long_betas) == 0 or len(short_betas) == 0:
            return long_candidates, short_candidates

        avg_long_beta = np.mean(long_betas)
        avg_short_beta = np.mean(short_betas)

        # If significantly imbalanced, adjust
        beta_diff = abs(avg_long_beta - avg_short_beta)

        if beta_diff > 0.2:  # Threshold for adjustment
            # Prefer lower beta longs if long beta is high
            if avg_long_beta > avg_short_beta:
                long_candidates = sorted(
                    long_candidates,
                    key=lambda sym: score_map[sym].beta if sym in score_map else 1.0
                )

            # Prefer higher beta shorts if short beta is low
            else:
                short_candidates = sorted(
                    short_candidates,
                    key=lambda sym: -score_map[sym].beta if sym in score_map else 1.0
                )

        return long_candidates, short_candidates

    def _generate_rebalance_signals(
        self,
        long_symbols: list[str],
        short_symbols: list[str]
    ) -> list[Signal]:
        """Generate rebalancing signals."""
        signals = []

        target_longs = set(long_symbols)
        target_shorts = set(short_symbols)

        current_longs = self.long_positions
        current_shorts = self.short_positions

        # Close positions no longer in target
        for symbol in current_longs:
            if symbol not in target_longs:
                signals.append(Signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    strength=1.0,
                    metadata={"side": "long_exit", "reason": "rebalance"}
                ))

        for symbol in current_shorts:
            if symbol not in target_shorts:
                signals.append(Signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,  # Cover short
                    strength=1.0,
                    metadata={"side": "short_cover", "reason": "rebalance"}
                ))

        # Open new long positions
        for symbol in target_longs:
            if symbol not in current_longs:
                weight = 1.0 / self.n_long  # Equal weight
                signals.append(Signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    strength=weight,
                    metadata={"side": "long_entry", "weight": weight}
                ))

        # Open new short positions
        for symbol in target_shorts:
            if symbol not in current_shorts:
                weight = 1.0 / self.n_short  # Equal weight
                signals.append(Signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    strength=weight,
                    metadata={"side": "short_entry", "weight": weight}
                ))

        # Update position tracking
        self.long_positions = target_longs
        self.short_positions = target_shorts

        return signals

    def _log_portfolio_stats(
        self,
        security_scores: list[SecurityScore],
        long_symbols: list[str],
        short_symbols: list[str]
    ) -> None:
        """Log portfolio characteristics."""
        score_map = {s.symbol: s for s in security_scores}

        # Calculate portfolio betas
        long_betas = [score_map[sym].beta for sym in long_symbols if sym in score_map]
        short_betas = [score_map[sym].beta for sym in short_symbols if sym in score_map]

        long_beta = np.mean(long_betas) if long_betas else 0
        short_beta = np.mean(short_betas) if short_betas else 0
        net_beta = (long_beta - short_beta) / 2  # Assuming equal dollar amounts

        self.logger.info("Portfolio rebalance:")
        self.logger.info(f"  Long: {len(long_symbols)} positions, avg beta={long_beta:.2f}")
        self.logger.info(f"  Short: {len(short_symbols)} positions, avg beta={short_beta:.2f}")
        self.logger.info(f"  Net beta: {net_beta:.2f}")

    def on_signal(self, signal: Signal) -> None:
        """Handle generated signal."""
        metadata = signal.metadata
        side = metadata.get("side", "unknown")

        self.logger.info(
            f"Market neutral: {side} {signal.signal_type.value} {signal.symbol}"
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
        self.logger.info("Stopping MarketNeutralStrategy")
        self.logger.info(f"Long positions: {len(self.long_positions)}")
        self.logger.info(f"Short positions: {len(self.short_positions)}")

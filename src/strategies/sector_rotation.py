"""
Sector rotation strategy based on macroeconomic indicators and momentum.
"""

from typing import Dict, List, Optional, Tuple
from enum import Enum
import numpy as np
import pandas as pd
from datetime import datetime
from collections import deque

from src.strategies.base import BaseStrategy, Signal, SignalType


class MarketRegime(Enum):
    """Market regime classification."""
    EARLY_BULL = "early_bull"
    LATE_BULL = "late_bull"
    EARLY_BEAR = "early_bear"
    LATE_BEAR = "late_bear"
    RECOVERY = "recovery"


class SectorRotationStrategy(BaseStrategy):
    """
    Sector rotation strategy that allocates capital across sectors
    based on business cycle position, momentum, and relative strength.

    The strategy identifies the current market regime and overweights
    sectors that historically outperform in that regime.

    Sector performance by regime (typical patterns):
    - Early Bull: Technology, Financials, Industrials
    - Late Bull: Energy, Materials, Consumer Discretionary
    - Early Bear: Utilities, Healthcare, Consumer Staples
    - Late Bear: Financials (distressed), Technology (cheap)
    - Recovery: Financials, Consumer Discretionary

    Parameters:
        sectors: List of sector ETFs or sector classifications
        lookback_momentum: Lookback period for sector momentum
        lookback_strength: Lookback period for relative strength
        rebalance_frequency: Days between rebalancing
        n_sectors: Number of sectors to overweight
        use_regime_detection: Use market regime detection
        equal_weight: Use equal weight vs momentum-weighted
    """

    def __init__(
        self,
        sectors: Optional[List[str]] = None,
        lookback_momentum: int = 126,  # ~6 months
        lookback_strength: int = 21,   # ~1 month
        rebalance_frequency: int = 21,
        n_sectors: int = 3,
        use_regime_detection: bool = True,
        equal_weight: bool = False,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.lookback_momentum = lookback_momentum
        self.lookback_strength = lookback_strength
        self.rebalance_frequency = rebalance_frequency
        self.n_sectors = n_sectors
        self.use_regime_detection = use_regime_detection
        self.equal_weight = equal_weight

        # Define sectors (using SPDR sector ETFs as default)
        if sectors is None:
            self.sectors = {
                'XLK': 'Technology',
                'XLF': 'Financials',
                'XLV': 'Healthcare',
                'XLE': 'Energy',
                'XLI': 'Industrials',
                'XLY': 'Consumer Discretionary',
                'XLP': 'Consumer Staples',
                'XLB': 'Materials',
                'XLU': 'Utilities',
                'XLRE': 'Real Estate',
                'XLC': 'Communication Services'
            }
        else:
            self.sectors = {sector: sector for sector in sectors}

        # Regime-based sector preferences (scores 0-1)
        self.regime_preferences = {
            MarketRegime.EARLY_BULL: {
                'Technology': 1.0,
                'Financials': 0.9,
                'Industrials': 0.8,
                'Consumer Discretionary': 0.7,
                'Communication Services': 0.7,
                'Materials': 0.5,
                'Energy': 0.4,
                'Healthcare': 0.4,
                'Real Estate': 0.3,
                'Consumer Staples': 0.2,
                'Utilities': 0.1
            },
            MarketRegime.LATE_BULL: {
                'Energy': 1.0,
                'Materials': 0.9,
                'Consumer Discretionary': 0.8,
                'Technology': 0.7,
                'Industrials': 0.6,
                'Financials': 0.5,
                'Communication Services': 0.5,
                'Healthcare': 0.4,
                'Real Estate': 0.3,
                'Consumer Staples': 0.3,
                'Utilities': 0.2
            },
            MarketRegime.EARLY_BEAR: {
                'Utilities': 1.0,
                'Healthcare': 0.9,
                'Consumer Staples': 0.9,
                'Real Estate': 0.5,
                'Communication Services': 0.4,
                'Technology': 0.3,
                'Financials': 0.3,
                'Industrials': 0.2,
                'Energy': 0.2,
                'Materials': 0.1,
                'Consumer Discretionary': 0.1
            },
            MarketRegime.LATE_BEAR: {
                'Consumer Staples': 1.0,
                'Healthcare': 0.9,
                'Utilities': 0.8,
                'Technology': 0.6,  # Quality tech at discount
                'Financials': 0.5,
                'Communication Services': 0.4,
                'Real Estate': 0.3,
                'Consumer Discretionary': 0.3,
                'Industrials': 0.2,
                'Materials': 0.2,
                'Energy': 0.2
            },
            MarketRegime.RECOVERY: {
                'Financials': 1.0,
                'Consumer Discretionary': 0.9,
                'Technology': 0.8,
                'Industrials': 0.8,
                'Materials': 0.7,
                'Energy': 0.6,
                'Communication Services': 0.6,
                'Real Estate': 0.5,
                'Healthcare': 0.4,
                'Consumer Staples': 0.3,
                'Utilities': 0.2
            }
        }

        # State
        self.last_rebalance_day = 0
        self.sector_prices: Dict[str, deque] = {}
        self.market_prices: deque = deque(maxlen=252)
        self.current_regime: Optional[MarketRegime] = None
        self.sector_momentum: Dict[str, float] = {}
        self.sector_strength: Dict[str, float] = {}

    def on_start(self) -> None:
        """Initialize strategy."""
        self.logger.info(
            f"Starting SectorRotationStrategy with {self.n_sectors} sectors"
        )
        self.logger.info(f"Tracking {len(self.sectors)} sector ETFs")
        self.logger.info(
            f"Regime detection: {'enabled' if self.use_regime_detection else 'disabled'}"
        )

    def on_data(self, data: Dict) -> List[Signal]:
        """
        Generate sector rotation signals.

        Args:
            data: Market data containing:
                - sector_prices: Dict[sector_symbol, price]
                - market_price: Overall market price (e.g., SPY)

        Returns:
            List of trading signals
        """
        self.days_elapsed += 1

        # Update sector prices
        if 'sector_prices' in data:
            for sector, price in data['sector_prices'].items():
                if sector in self.sectors:
                    if sector not in self.sector_prices:
                        self.sector_prices[sector] = deque(maxlen=252)
                    self.sector_prices[sector].append(price)

        # Update market prices
        if 'market_price' in data:
            self.market_prices.append(data['market_price'])

        # Check if rebalancing is needed
        if self.days_elapsed - self.last_rebalance_day < self.rebalance_frequency:
            return []

        self.last_rebalance_day = self.days_elapsed

        # Need enough history
        if len(self.market_prices) < self.lookback_momentum:
            return []

        # Detect market regime
        if self.use_regime_detection:
            self.current_regime = self._detect_market_regime()
            self.logger.info(f"Current market regime: {self.current_regime.value}")

        # Calculate sector scores
        sector_scores = self._calculate_sector_scores()

        if len(sector_scores) == 0:
            return []

        # Generate rebalancing signals
        signals = self._generate_rebalance_signals(sector_scores)

        return signals

    def _detect_market_regime(self) -> MarketRegime:
        """
        Detect current market regime using technical and fundamental indicators.

        Uses:
        - Trend (SMA slopes)
        - Momentum (ROC)
        - Volatility (realized vol)
        - Breadth (advance/decline)
        """
        market_prices = np.array(self.market_prices)

        # Calculate indicators
        returns = np.diff(market_prices) / market_prices[:-1]

        # Trend: SMA slopes
        sma_50 = np.mean(market_prices[-50:])
        sma_200 = np.mean(market_prices[-200:])
        trend_short = market_prices[-1] / sma_50 - 1
        trend_long = sma_50 / sma_200 - 1

        # Momentum
        momentum_3m = market_prices[-1] / market_prices[-63] - 1
        momentum_6m = market_prices[-1] / market_prices[-126] - 1

        # Volatility
        volatility_21d = np.std(returns[-21:]) * np.sqrt(252)
        volatility_63d = np.std(returns[-63:]) * np.sqrt(252)

        # Classify regime
        # Early Bull: Rising trend, positive momentum, declining volatility
        if trend_long > 0 and trend_short > 0.02 and momentum_3m > 0 and volatility_21d < volatility_63d:
            return MarketRegime.EARLY_BULL

        # Late Bull: Rising trend, slowing momentum, rising volatility
        elif trend_long > 0 and momentum_3m > 0 and momentum_6m > momentum_3m and volatility_21d > volatility_63d:
            return MarketRegime.LATE_BULL

        # Early Bear: Declining trend, negative momentum, rising volatility
        elif trend_short < 0 and momentum_3m < 0 and volatility_21d > 0.2:
            return MarketRegime.EARLY_BEAR

        # Late Bear: Declining trend, negative momentum, declining volatility
        elif trend_long < 0 and momentum_3m < 0 and volatility_21d < volatility_63d:
            return MarketRegime.LATE_BEAR

        # Recovery: Bottoming out, early positive signals
        elif trend_long < 0 and trend_short > 0 and momentum_3m > -0.05:
            return MarketRegime.RECOVERY

        # Default to late bull if unclear
        else:
            return MarketRegime.LATE_BULL

    def _calculate_sector_scores(self) -> Dict[str, float]:
        """Calculate composite scores for each sector."""
        scores = {}

        for sector_symbol, sector_name in self.sectors.items():
            if sector_symbol not in self.sector_prices:
                continue

            prices = np.array(self.sector_prices[sector_symbol])

            if len(prices) < self.lookback_momentum:
                continue

            # 1. Momentum score
            momentum_score = self._calculate_momentum(prices)
            self.sector_momentum[sector_symbol] = momentum_score

            # 2. Relative strength score
            strength_score = self._calculate_relative_strength(sector_symbol, prices)
            self.sector_strength[sector_symbol] = strength_score

            # 3. Regime preference score
            regime_score = 0.5  # Default neutral
            if self.use_regime_detection and self.current_regime:
                regime_score = self.regime_preferences[self.current_regime].get(sector_name, 0.5)

            # Composite score (weighted average)
            composite = (
                0.4 * momentum_score +
                0.3 * strength_score +
                0.3 * regime_score
            )

            scores[sector_symbol] = composite

        return scores

    def _calculate_momentum(self, prices: np.ndarray) -> float:
        """Calculate momentum score (0 to 1)."""
        # Multiple timeframe momentum
        mom_1m = (prices[-1] / prices[-21] - 1) if len(prices) >= 21 else 0
        mom_3m = (prices[-1] / prices[-63] - 1) if len(prices) >= 63 else 0
        mom_6m = (prices[-1] / prices[-126] - 1) if len(prices) >= 126 else 0

        # Weighted average
        momentum = 0.2 * mom_1m + 0.3 * mom_3m + 0.5 * mom_6m

        # Normalize to [0, 1] (assume +/- 50% range)
        normalized = (momentum + 0.5) / 1.0
        return np.clip(normalized, 0, 1)

    def _calculate_relative_strength(self, sector_symbol: str, sector_prices: np.ndarray) -> float:
        """Calculate relative strength vs market."""
        if len(self.market_prices) < self.lookback_strength:
            return 0.5

        market_prices = np.array(self.market_prices)

        # Calculate returns
        sector_returns = np.diff(sector_prices[-self.lookback_strength:]) / sector_prices[-self.lookback_strength-1:-1]
        market_returns = np.diff(market_prices[-self.lookback_strength:]) / market_prices[-self.lookback_strength-1:-1]

        # Relative strength = cumulative sector return / cumulative market return
        sector_cum = np.prod(1 + sector_returns)
        market_cum = np.prod(1 + market_returns)

        if market_cum == 0:
            return 0.5

        rel_strength = sector_cum / market_cum

        # Normalize to [0, 1] (assume 0.8 to 1.2 range)
        normalized = (rel_strength - 0.8) / 0.4
        return np.clip(normalized, 0, 1)

    def _generate_rebalance_signals(self, sector_scores: Dict[str, float]) -> List[Signal]:
        """Generate rebalancing signals."""
        signals = []

        # Sort sectors by score
        sorted_sectors = sorted(sector_scores.items(), key=lambda x: x[1], reverse=True)

        # Select top N sectors
        target_sectors = {sector for sector, _ in sorted_sectors[:self.n_sectors]}
        current_sectors = set(self.positions.keys())

        # Calculate target weights
        if self.equal_weight:
            target_weight = 1.0 / self.n_sectors
            sector_weights = {sector: target_weight for sector in target_sectors}
        else:
            # Momentum-weighted
            total_score = sum(score for sector, score in sorted_sectors[:self.n_sectors])
            sector_weights = {
                sector: score / total_score
                for sector, score in sorted_sectors[:self.n_sectors]
            }

        # Exit sectors no longer in target
        for sector in current_sectors:
            if sector not in target_sectors:
                signals.append(Signal(
                    symbol=sector,
                    signal_type=SignalType.SELL,
                    strength=1.0,
                    metadata={
                        'reason': 'sector_rotation',
                        'old_score': sector_scores.get(sector, 0)
                    }
                ))

        # Enter new sectors or rebalance existing
        for sector in target_sectors:
            target_weight = sector_weights[sector]

            if sector not in current_sectors:
                # New entry
                signals.append(Signal(
                    symbol=sector,
                    signal_type=SignalType.BUY,
                    strength=target_weight,
                    metadata={
                        'reason': 'sector_entry',
                        'score': sector_scores[sector],
                        'momentum': self.sector_momentum.get(sector, 0),
                        'rel_strength': self.sector_strength.get(sector, 0),
                        'target_weight': target_weight
                    }
                ))
            # Note: Rebalancing existing positions would go here

        return signals

    def on_signal(self, signal: Signal) -> None:
        """Handle generated signal."""
        sector_name = self.sectors.get(signal.symbol, signal.symbol)
        metadata = signal.metadata

        if signal.signal_type == SignalType.BUY:
            self.logger.info(
                f"Sector rotation: BUY {sector_name} ({signal.symbol}) "
                f"[score={metadata.get('score', 0):.3f}, "
                f"mom={metadata.get('momentum', 0):.3f}, "
                f"weight={metadata.get('target_weight', 0):.2%}]"
            )
        else:
            self.logger.info(
                f"Sector rotation: SELL {sector_name} ({signal.symbol}) "
                f"[old_score={metadata.get('old_score', 0):.3f}]"
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
        self.logger.info("Stopping SectorRotationStrategy")
        self.logger.info(f"Final regime: {self.current_regime.value if self.current_regime else 'unknown'}")
        self.logger.info(f"Active sectors: {list(self.positions.keys())}")

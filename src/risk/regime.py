"""
Market regime detection system.

Identifies market regimes (bull, bear, high vol, etc.) for dynamic risk management.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from loguru import logger
import numpy as np
import pandas as pd


class MarketRegime(Enum):
    """Market regime types."""
    BULL = "bull"  # Trending up, low vol
    BEAR = "bear"  # Trending down, rising vol
    HIGH_VOLATILITY = "high_volatility"  # Sideways, high vol
    LOW_VOLATILITY = "low_volatility"  # Sideways, low vol
    CRISIS = "crisis"  # Sharp decline, extreme vol
    RECOVERY = "recovery"  # Bouncing from lows


@dataclass
class RegimeState:
    """Current market regime state."""
    regime: MarketRegime
    confidence: float  # 0-1
    duration_days: int
    indicators: dict[str, float]
    timestamp: datetime


class RegimeDetector:
    """
    Detects market regimes using multiple indicators.
    
    Uses:
    - Trend (SMA crossovers)
    - Volatility (realized vol)
    - Momentum (rate of change)
    - Drawdown
    """

    def __init__(
        self,
        short_window: int = 50,
        long_window: int = 200,
        vol_window: int = 20,
        high_vol_threshold: float = 0.25,  # 25% annual vol
        low_vol_threshold: float = 0.12,  # 12% annual vol
        crisis_threshold: float = -0.15  # 15% drawdown
    ):
        """Initialize regime detector."""
        self.short_window = short_window
        self.long_window = long_window
        self.vol_window = vol_window
        self.high_vol_threshold = high_vol_threshold
        self.low_vol_threshold = low_vol_threshold
        self.crisis_threshold = crisis_threshold

        # State tracking
        self.current_regime: RegimeState | None = None
        self.regime_history: list[RegimeState] = []

        logger.info("Initialized RegimeDetector")

    def detect(
        self,
        prices: pd.Series,  # Price series
        returns: pd.Series | None = None
    ) -> RegimeState:
        """
        Detect current market regime.
        
        Args:
            prices: Price series (e.g., S&P 500)
            returns: Optional returns series
            
        Returns:
            RegimeState
        """
        if returns is None:
            returns = prices.pct_change()

        # Calculate indicators
        indicators = self._calculate_indicators(prices, returns)

        # Determine regime
        regime, confidence = self._classify_regime(indicators)

        # Calculate duration
        if self.current_regime and self.current_regime.regime == regime:
            duration = self.current_regime.duration_days + 1
        else:
            duration = 1

        state = RegimeState(
            regime=regime,
            confidence=confidence,
            duration_days=duration,
            indicators=indicators,
            timestamp=datetime.now()
        )

        self.current_regime = state
        self.regime_history.append(state)

        logger.info(
            f"Market regime: {regime.value.upper()} "
            f"(confidence={confidence:.2f}, duration={duration}D)"
        )

        return state

    def _calculate_indicators(
        self,
        prices: pd.Series,
        returns: pd.Series
    ) -> dict[str, float]:
        """Calculate regime indicators."""
        indicators = {}

        # 1. Trend (SMA crossover)
        sma_short = prices.rolling(self.short_window).mean()
        sma_long = prices.rolling(self.long_window).mean()

        if len(sma_short) > 0 and len(sma_long) > 0:
            indicators["sma_ratio"] = sma_short.iloc[-1] / sma_long.iloc[-1]
            indicators["price_vs_sma200"] = prices.iloc[-1] / sma_long.iloc[-1]
        else:
            indicators["sma_ratio"] = 1.0
            indicators["price_vs_sma200"] = 1.0

        # 2. Volatility
        if len(returns) >= self.vol_window:
            realized_vol = returns.tail(self.vol_window).std() * np.sqrt(252)
            indicators["realized_volatility"] = realized_vol
        else:
            indicators["realized_volatility"] = 0.15

        # 3. Momentum
        if len(returns) >= 20:
            mom_1m = prices.iloc[-1] / prices.iloc[-21] - 1
            mom_3m = prices.iloc[-1] / prices.iloc[-63] - 1 if len(prices) >= 63 else 0
            indicators["momentum_1m"] = mom_1m
            indicators["momentum_3m"] = mom_3m
        else:
            indicators["momentum_1m"] = 0
            indicators["momentum_3m"] = 0

        # 4. Drawdown
        running_max = prices.cummax()
        drawdown = (prices - running_max) / running_max
        indicators["current_drawdown"] = drawdown.iloc[-1]
        indicators["max_drawdown_60d"] = drawdown.tail(60).min() if len(drawdown) >= 60 else 0

        # 5. Volatility regime (vol of vol)
        if len(returns) >= 60:
            rolling_vol = returns.rolling(self.vol_window).std()
            vol_of_vol = rolling_vol.tail(60).std()
            indicators["vol_of_vol"] = vol_of_vol
        else:
            indicators["vol_of_vol"] = 0

        return indicators

    def _classify_regime(
        self,
        indicators: dict[str, float]
    ) -> tuple[MarketRegime, float]:
        """
        Classify regime based on indicators.
        
        Returns:
            (regime, confidence)
        """
        # Extract indicators
        sma_ratio = indicators.get("sma_ratio", 1.0)
        vol = indicators.get("realized_volatility", 0.15)
        mom_1m = indicators.get("momentum_1m", 0)
        drawdown = indicators.get("current_drawdown", 0)

        # Crisis detection (highest priority)
        if drawdown < self.crisis_threshold or vol > 0.40:
            return MarketRegime.CRISIS, 0.9

        # Recovery detection
        if drawdown < -0.10 and mom_1m > 0.05:  # Rebounding from drawdown
            return MarketRegime.RECOVERY, 0.8

        # High/low volatility
        if vol > self.high_vol_threshold:
            # High vol + uptrend = still bull but choppy
            if sma_ratio > 1.02:
                return MarketRegime.BULL, 0.6
            # High vol + downtrend = bear
            if sma_ratio < 0.98:
                return MarketRegime.BEAR, 0.8
            return MarketRegime.HIGH_VOLATILITY, 0.85

        if vol < self.low_vol_threshold:
            # Low vol + uptrend = bull
            if sma_ratio > 1.02:
                return MarketRegime.BULL, 0.9
            # Low vol + downtrend = bear
            if sma_ratio < 0.98:
                return MarketRegime.BEAR, 0.7
            return MarketRegime.LOW_VOLATILITY, 0.85

        # Medium volatility - use trend
        if sma_ratio > 1.02 and mom_1m > 0:
            return MarketRegime.BULL, 0.75
        if sma_ratio < 0.98 and mom_1m < 0:
            return MarketRegime.BEAR, 0.75
        # Default to low vol if uncertain
        return MarketRegime.LOW_VOLATILITY, 0.5

    def get_risk_adjustment(
        self,
        regime: MarketRegime | None = None
    ) -> float:
        """
        Get risk scaling factor for current regime.
        
        Args:
            regime: Optional regime (uses current if None)
            
        Returns:
            Risk scaling factor (1.0 = normal)
        """
        if regime is None:
            if self.current_regime is None:
                return 1.0
            regime = self.current_regime.regime

        # Risk adjustments by regime
        adjustments = {
            MarketRegime.BULL: 1.0,  # Normal risk
            MarketRegime.BEAR: 0.7,  # Reduce risk by 30%
            MarketRegime.HIGH_VOLATILITY: 0.6,  # Reduce risk by 40%
            MarketRegime.LOW_VOLATILITY: 1.2,  # Can increase risk by 20%
            MarketRegime.CRISIS: 0.3,  # Reduce risk by 70%
            MarketRegime.RECOVERY: 0.8,  # Cautiously increase
        }

        return adjustments.get(regime, 1.0)

    def get_regime_transitions(
        self
    ) -> pd.DataFrame:
        """Get regime transition history."""
        if len(self.regime_history) == 0:
            return pd.DataFrame()

        transitions = []
        prev_regime = None

        for state in self.regime_history:
            if prev_regime is None or state.regime != prev_regime:
                transitions.append({
                    "timestamp": state.timestamp,
                    "from_regime": prev_regime.value if prev_regime else None,
                    "to_regime": state.regime.value,
                    "confidence": state.confidence,
                    "volatility": state.indicators.get("realized_volatility", 0),
                })
                prev_regime = state.regime

        return pd.DataFrame(transitions)

    def get_regime_statistics(
        self
    ) -> dict[MarketRegime, dict]:
        """Get statistics for each regime."""
        if len(self.regime_history) == 0:
            return {}

        stats = {}

        for regime in MarketRegime:
            regime_states = [s for s in self.regime_history if s.regime == regime]

            if len(regime_states) == 0:
                continue

            # Calculate duration statistics
            durations = [s.duration_days for s in regime_states]

            stats[regime] = {
                "occurrences": len(regime_states),
                "total_days": sum(durations),
                "avg_duration": np.mean(durations),
                "max_duration": max(durations),
                "avg_confidence": np.mean([s.confidence for s in regime_states]),
            }

        return stats


class HiddenMarkovRegime:
    """
    Hidden Markov Model for regime detection.
    
    More sophisticated than rule-based detector.
    Uses statistical methods to infer hidden states.
    """

    def __init__(self, n_states: int = 3):
        """Initialize HMM regime detector."""
        self.n_states = n_states
        self.model = None
        logger.info(f"Initialized HMM with {n_states} states")

    def fit(self, returns: pd.Series) -> None:
        """
        Fit HMM to historical returns.
        
        Args:
            returns: Historical returns
        """
        try:
            from hmmlearn import hmm

            # Prepare data
            X = returns.values.reshape(-1, 1)

            # Fit Gaussian HMM
            model = hmm.GaussianHMM(
                n_components=self.n_states,
                covariance_type="full",
                n_iter=100,
                random_state=42
            )

            model.fit(X)
            self.model = model

            logger.info("HMM fitted successfully")

        except ImportError:
            logger.warning("hmmlearn not installed, HMM not available")
            self.model = None

    def predict(self, returns: pd.Series) -> np.ndarray:
        """
        Predict regime states.
        
        Args:
            returns: Returns series
            
        Returns:
            Array of predicted states
        """
        if self.model is None:
            return np.zeros(len(returns))

        X = returns.values.reshape(-1, 1)
        states = self.model.predict(X)

        return states

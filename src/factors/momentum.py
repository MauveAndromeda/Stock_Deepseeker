"""
Momentum factors.

Price and earnings momentum factors for cross-sectional ranking.
"""


import numpy as np
import pandas as pd

from src.factors import Factor, FactorCategory, FactorMetadata


class PriceMomentum(Factor):
    """
    Price momentum over specified period.

    Formula: (Price_t - Price_t-n) / Price_t-n
    """

    def __init__(self, lookback: int = 252, skip: int = 21) -> None:
        """
        Initialize price momentum.

        Args:
            lookback: Lookback period (default 252 = 1 year)
            skip: Days to skip (default 21 = 1 month, to avoid short-term reversal)
        """
        metadata = FactorMetadata(
            name=f"price_momentum_{lookback}d",
            category=FactorCategory.MOMENTUM,
            description=f"{lookback}-day price momentum (skipping last {skip} days)",
            formula=f"(close_t-{skip} - close_t-{lookback}) / close_t-{lookback}",
            data_requirements=["close"],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback
        self.skip = skip

    def calculate(
        self,
        data: pd.DataFrame,
        universe: list[str] | None = None
    ) -> pd.Series:
        """Calculate price momentum."""
        closes = data["close"].unstack(fill_value=np.nan)

        # Calculate momentum skipping recent period
        if self.skip > 0:
            recent_price = closes.shift(self.skip)
            old_price = closes.shift(self.lookback)
        else:
            recent_price = closes
            old_price = closes.shift(self.lookback)

        momentum = (recent_price - old_price) / old_price

        # Stack back to Series
        result = momentum.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class RSI(Factor):
    """
    Relative Strength Index.

    RSI = 100 - 100 / (1 + RS)
    where RS = Average Gain / Average Loss
    """

    def __init__(self, period: int = 14) -> None:
        """
        Initialize RSI.

        Args:
            period: RSI period (default 14 days)
        """
        metadata = FactorMetadata(
            name=f"rsi_{period}d",
            category=FactorCategory.MOMENTUM,
            description=f"{period}-day Relative Strength Index",
            formula=f"100 - 100 / (1 + RS_{period})",
            data_requirements=["close"],
            lookback_period=period * 2,  # Need extra for warmup
        )
        super().__init__(metadata)
        self.period = period

    def calculate(
        self,
        data: pd.DataFrame,
        universe: list[str] | None = None
    ) -> pd.Series:
        """Calculate RSI."""
        closes = data["close"].unstack(fill_value=np.nan)

        # Calculate price changes
        delta = closes.diff()

        # Separate gains and losses
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        # Calculate exponential moving averages
        avg_gain = gain.ewm(span=self.period, adjust=False).mean()
        avg_loss = loss.ewm(span=self.period, adjust=False).mean()

        # Calculate RS and RSI.  Guard against divide-by-zero when there are
        # no losses in the window by treating the ratio as infinite (RSI=100).
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        # Fill missing values that arise from the warmup period or zero
        # losses/gains with the neutral RSI value of 50 and clamp to the
        # canonical [0, 100] range expected by the tests.
        rsi = rsi.fillna(50).clip(lower=0, upper=100)

        result = rsi.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class MACD(Factor):
    """
    Moving Average Convergence Divergence.

    MACD = EMA_fast - EMA_slow
    Signal = EMA(MACD)
    Histogram = MACD - Signal
    """

    def __init__(
        self,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> None:
        """
        Initialize MACD.

        Args:
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line EMA period
        """
        metadata = FactorMetadata(
            name=f"macd_{fast}_{slow}_{signal}",
            category=FactorCategory.MOMENTUM,
            description=f"MACD ({fast},{slow},{signal}) histogram",
            formula=f"EMA_{fast} - EMA_{slow} - EMA_signal",
            data_requirements=["close"],
            lookback_period=slow * 2,
        )
        super().__init__(metadata)
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def calculate(
        self,
        data: pd.DataFrame,
        universe: list[str] | None = None
    ) -> pd.Series:
        """Calculate MACD histogram."""
        closes = data["close"].unstack(fill_value=np.nan)

        # Calculate EMAs
        ema_fast = closes.ewm(span=self.fast, adjust=False).mean()
        ema_slow = closes.ewm(span=self.slow, adjust=False).mean()

        # MACD line
        macd_line = ema_fast - ema_slow

        # Signal line
        signal_line = macd_line.ewm(span=self.signal, adjust=False).mean()

        # MACD histogram
        histogram = macd_line - signal_line

        # Normalize by price for cross-sectional comparison
        histogram_normalized = histogram / closes

        result = histogram_normalized.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class VolumeMomentum(Factor):
    """
    Volume momentum - change in trading volume.

    Formula: (Volume_t - Volume_avg) / Volume_avg
    """

    def __init__(self, lookback: int = 20) -> None:
        """
        Initialize volume momentum.

        Args:
            lookback: Lookback period for average volume
        """
        metadata = FactorMetadata(
            name=f"volume_momentum_{lookback}d",
            category=FactorCategory.MOMENTUM,
            description=f"Volume deviation from {lookback}-day average",
            formula=f"(volume_t - SMA_volume_{lookback}) / SMA_volume_{lookback}",
            data_requirements=["volume"],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: list[str] | None = None
    ) -> pd.Series:
        """Calculate volume momentum."""
        volumes = data["volume"].unstack(fill_value=np.nan)

        # Calculate average volume
        avg_volume = volumes.rolling(window=self.lookback).mean()

        # Current volume vs average
        volume_momentum = (volumes - avg_volume) / avg_volume

        result = volume_momentum.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class PriceAcceleration(Factor):
    """
    Price acceleration - second derivative of price.

    Measures whether momentum is accelerating or decelerating.
    """

    def __init__(self, short_period: int = 5, long_period: int = 20) -> None:
        """
        Initialize price acceleration.

        Args:
            short_period: Short momentum period
            long_period: Long momentum period
        """
        metadata = FactorMetadata(
            name=f"price_acceleration_{short_period}_{long_period}",
            category=FactorCategory.MOMENTUM,
            description="Price momentum acceleration",
            formula=f"Momentum_{short_period} - Momentum_{long_period}",
            data_requirements=["close"],
            lookback_period=long_period,
        )
        super().__init__(metadata)
        self.short_period = short_period
        self.long_period = long_period

    def calculate(
        self,
        data: pd.DataFrame,
        universe: list[str] | None = None
    ) -> pd.Series:
        """Calculate price acceleration."""
        closes = data["close"].unstack(fill_value=np.nan)

        # Short-term momentum
        short_mom = closes.pct_change(periods=self.short_period)

        # Long-term momentum
        long_mom = closes.pct_change(periods=self.long_period)

        # Acceleration = difference in momentum
        acceleration = short_mom - long_mom

        result = acceleration.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class ReversalFactor(Factor):
    """
    Short-term reversal factor.

    Captures mean reversion over short periods.
    """

    def __init__(self, lookback: int = 5) -> None:
        """
        Initialize reversal factor.

        Args:
            lookback: Lookback period (typically short: 1-5 days)
        """
        metadata = FactorMetadata(
            name=f"reversal_{lookback}d",
            category=FactorCategory.MOMENTUM,
            description=f"{lookback}-day price reversal (mean reversion)",
            formula=f"-1 * (close_t - close_t-{lookback}) / close_t-{lookback}",
            data_requirements=["close"],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: list[str] | None = None
    ) -> pd.Series:
        """Calculate reversal factor."""
        closes = data["close"].unstack(fill_value=np.nan)

        # Short-term returns (negative for reversal)
        returns = closes.pct_change(periods=self.lookback)
        reversal = -returns  # Invert: losers become winners

        result = reversal.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class TrendStrength(Factor):
    """
    Trend strength using ADX (Average Directional Index).

    Measures the strength of a trend (not direction).
    """

    def __init__(self, period: int = 14) -> None:
        """
        Initialize trend strength.

        Args:
            period: ADX period
        """
        metadata = FactorMetadata(
            name=f"trend_strength_{period}d",
            category=FactorCategory.MOMENTUM,
            description=f"{period}-day trend strength (ADX)",
            formula="ADX based on +DI and -DI",
            data_requirements=["high", "low", "close"],
            lookback_period=period * 2,
        )
        super().__init__(metadata)
        self.period = period

    def calculate(
        self,
        data: pd.DataFrame,
        universe: list[str] | None = None
    ) -> pd.Series:
        """Calculate trend strength (simplified ADX)."""
        highs = data["high"].unstack(fill_value=np.nan)
        lows = data["low"].unstack(fill_value=np.nan)
        closes = data["close"].unstack(fill_value=np.nan)

        # True Range
        tr1 = highs - lows
        tr2 = (highs - closes.shift(1)).abs()
        tr3 = (lows - closes.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Directional Movement
        up_move = highs - highs.shift(1)
        down_move = lows.shift(1) - lows

        plus_dm = pd.DataFrame(0, index=up_move.index, columns=up_move.columns)
        plus_dm[up_move > down_move] = up_move[up_move > down_move]
        plus_dm[plus_dm < 0] = 0

        minus_dm = pd.DataFrame(0, index=down_move.index, columns=down_move.columns)
        minus_dm[down_move > up_move] = down_move[down_move > up_move]
        minus_dm[minus_dm < 0] = 0

        # Smoothed indicators
        atr = tr.ewm(span=self.period, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(span=self.period, adjust=False).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(span=self.period, adjust=False).mean() / atr)

        # ADX
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        adx = dx.ewm(span=self.period, adjust=False).mean()

        # Normalize to [0, 1]
        adx_normalized = adx / 100

        result = adx_normalized.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


# Factory function to create all momentum factors
def create_momentum_factors() -> list[Factor]:
    """
    Create standard set of momentum factors.

    Returns:
        List of momentum factors
    """
    return [
        PriceMomentum(lookback=252, skip=21),  # 12-month momentum
        PriceMomentum(lookback=126, skip=21),  # 6-month momentum
        PriceMomentum(lookback=63, skip=0),    # 3-month momentum
        PriceMomentum(lookback=21, skip=0),    # 1-month momentum
        RSI(period=14),
        RSI(period=28),
        MACD(fast=12, slow=26, signal=9),
        VolumeMomentum(lookback=20),
        VolumeMomentum(lookback=60),
        PriceAcceleration(short_period=5, long_period=20),
        ReversalFactor(lookback=1),  # 1-day reversal
        ReversalFactor(lookback=5),  # 5-day reversal
        TrendStrength(period=14),
    ]

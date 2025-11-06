"""
Liquidity factors.

Trading liquidity and market microstructure factors.
"""

from typing import Optional, List
import pandas as pd
import numpy as np
from loguru import logger

from src.factors import Factor, FactorMetadata, FactorCategory


class AverageDollarVolume(Factor):
    """
    Average dollar volume traded.

    Formula: Average(Price * Volume) over period
    Higher volume = better liquidity
    """

    def __init__(self, lookback: int = 20) -> None:
        """
        Initialize average dollar volume factor.

        Args:
            lookback: Lookback period
        """
        metadata = FactorMetadata(
            name=f"avg_dollar_volume_{lookback}d",
            category=FactorCategory.LIQUIDITY,
            description=f"{lookback}-day average dollar volume",
            formula=f"Average(Price * Volume) over {lookback} days",
            data_requirements=['close', 'volume'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate average dollar volume."""
        closes = data['close'].unstack(fill_value=np.nan)
        volumes = data['volume'].unstack(fill_value=np.nan)

        # Calculate dollar volume
        dollar_volume = closes * volumes

        # Calculate average
        avg_dollar_volume = dollar_volume.rolling(window=self.lookback).mean()

        result = avg_dollar_volume.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class ShareTurnover(Factor):
    """
    Share turnover ratio.

    Formula: Volume / Shares Outstanding
    Higher turnover = better liquidity
    """

    def __init__(self, lookback: int = 20) -> None:
        """
        Initialize share turnover factor.

        Args:
            lookback: Lookback period for averaging
        """
        metadata = FactorMetadata(
            name=f"share_turnover_{lookback}d",
            category=FactorCategory.LIQUIDITY,
            description=f"{lookback}-day average share turnover",
            formula=f"Average(Volume / Shares Outstanding) over {lookback} days",
            data_requirements=['volume', 'shares_outstanding'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate share turnover."""
        volumes = data['volume'].unstack(fill_value=np.nan)

        if 'shares_outstanding' not in data.columns:
            logger.warning("Missing shares outstanding data for turnover calculation")
            return pd.Series(dtype=float)

        shares = data['shares_outstanding'].unstack(fill_value=np.nan)

        # Calculate daily turnover
        daily_turnover = volumes / shares

        # Calculate average turnover
        avg_turnover = daily_turnover.rolling(window=self.lookback).mean()

        result = avg_turnover.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class AmihudIlliquidity(Factor):
    """
    Amihud illiquidity measure.

    Formula: Average(|Return| / Dollar Volume)
    Lower value = better liquidity (inverted for quality signal)
    """

    def __init__(self, lookback: int = 20) -> None:
        """
        Initialize Amihud illiquidity factor.

        Args:
            lookback: Lookback period
        """
        metadata = FactorMetadata(
            name=f"amihud_illiquidity_{lookback}d",
            category=FactorCategory.LIQUIDITY,
            description=f"{lookback}-day Amihud illiquidity (inverted)",
            formula=f"-1 * Average(|Return| / Dollar Volume) over {lookback} days",
            data_requirements=['close', 'volume'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate inverted Amihud illiquidity."""
        closes = data['close'].unstack(fill_value=np.nan)
        volumes = data['volume'].unstack(fill_value=np.nan)

        # Calculate returns
        returns = closes.pct_change().abs()

        # Calculate dollar volume
        dollar_volume = closes * volumes

        # Calculate daily illiquidity
        daily_illiq = returns / dollar_volume

        # Calculate average illiquidity
        avg_illiq = daily_illiq.rolling(window=self.lookback).mean()

        # Invert for liquidity signal (lower illiquidity = higher score)
        result = (-avg_illiq).stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class BidAskSpread(Factor):
    """
    Bid-ask spread factor.

    Formula: (Ask - Bid) / Mid Price
    Lower spread = better liquidity (inverted for quality signal)
    """

    def __init__(self, lookback: int = 20) -> None:
        """
        Initialize bid-ask spread factor.

        Args:
            lookback: Lookback period for averaging
        """
        metadata = FactorMetadata(
            name=f"bid_ask_spread_{lookback}d",
            category=FactorCategory.LIQUIDITY,
            description=f"{lookback}-day average bid-ask spread (inverted)",
            formula="-1 * Average((Ask - Bid) / Mid)",
            data_requirements=['bid', 'ask'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate inverted bid-ask spread."""
        if 'bid' not in data.columns or 'ask' not in data.columns:
            logger.warning("Missing bid/ask data for spread calculation")
            # Estimate from high-low spread
            if 'high' in data.columns and 'low' in data.columns:
                highs = data['high'].unstack(fill_value=np.nan)
                lows = data['low'].unstack(fill_value=np.nan)
                closes = data['close'].unstack(fill_value=np.nan)
                spread = (highs - lows) / closes
                avg_spread = spread.rolling(window=self.lookback).mean()
                result = (-avg_spread).stack()
            else:
                return pd.Series(dtype=float)
        else:
            bids = data['bid'].unstack(fill_value=np.nan)
            asks = data['ask'].unstack(fill_value=np.nan)

            # Calculate mid price
            mid = (bids + asks) / 2

            # Calculate spread
            spread = (asks - bids) / mid

            # Calculate average spread
            avg_spread = spread.rolling(window=self.lookback).mean()

            # Invert for liquidity signal
            result = (-avg_spread).stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class VolumeVolatility(Factor):
    """
    Volume volatility (consistency of trading activity).

    Formula: StdDev(Volume) / Mean(Volume)
    Lower volatility = more consistent liquidity
    """

    def __init__(self, lookback: int = 20) -> None:
        """
        Initialize volume volatility factor.

        Args:
            lookback: Lookback period
        """
        metadata = FactorMetadata(
            name=f"volume_volatility_{lookback}d",
            category=FactorCategory.LIQUIDITY,
            description=f"{lookback}-day volume volatility (inverted)",
            formula="-1 * StdDev(Volume) / Mean(Volume)",
            data_requirements=['volume'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate inverted volume volatility."""
        volumes = data['volume'].unstack(fill_value=np.nan)

        # Calculate coefficient of variation
        vol_mean = volumes.rolling(window=self.lookback).mean()
        vol_std = volumes.rolling(window=self.lookback).std()
        vol_cv = vol_std / vol_mean

        # Invert for consistency signal
        result = (-vol_cv).stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class RollMeasure(Factor):
    """
    Roll's bid-ask spread estimator.

    Estimates spread from serial covariance of price changes.
    Lower Roll measure = better liquidity
    """

    def __init__(self, lookback: int = 20) -> None:
        """
        Initialize Roll measure factor.

        Args:
            lookback: Lookback period
        """
        metadata = FactorMetadata(
            name=f"roll_measure_{lookback}d",
            category=FactorCategory.LIQUIDITY,
            description=f"{lookback}-day Roll spread estimate (inverted)",
            formula="2 * sqrt(-Cov(ΔP_t, ΔP_t-1))",
            data_requirements=['close'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate inverted Roll measure."""
        closes = data['close'].unstack(fill_value=np.nan)

        # Calculate price changes
        price_changes = closes.diff()

        # Calculate rolling covariance with lagged price changes
        def rolling_roll(col):
            roll_values = []
            for i in range(len(col)):
                if i < self.lookback:
                    roll_values.append(np.nan)
                else:
                    window = col.iloc[i-self.lookback:i]
                    lagged = window.shift(1)
                    cov = window.cov(lagged)
                    # Roll measure: 2 * sqrt(max(-cov, 0))
                    roll = 2 * np.sqrt(max(-cov, 0)) if not np.isnan(cov) else np.nan
                    roll_values.append(roll)
            return pd.Series(roll_values, index=col.index)

        roll_measure = price_changes.apply(rolling_roll)

        # Invert for liquidity signal
        result = (-roll_measure).stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class ZeroReturnDays(Factor):
    """
    Proportion of zero return days (liquidity proxy).

    Higher proportion = less liquidity (inverted for quality signal)
    """

    def __init__(self, lookback: int = 60) -> None:
        """
        Initialize zero return days factor.

        Args:
            lookback: Lookback period
        """
        metadata = FactorMetadata(
            name=f"zero_return_days_{lookback}d",
            category=FactorCategory.LIQUIDITY,
            description=f"{lookback}-day proportion of zero return days (inverted)",
            formula="-1 * Count(|Return| < threshold) / N",
            data_requirements=['close'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate inverted zero return days proportion."""
        closes = data['close'].unstack(fill_value=np.nan)

        # Calculate returns
        returns = closes.pct_change()

        # Count zero return days (using small threshold)
        threshold = 0.0001
        zero_days = (returns.abs() < threshold).astype(int)

        # Calculate rolling proportion
        zero_proportion = zero_days.rolling(window=self.lookback).mean()

        # Invert for liquidity signal
        result = (-zero_proportion).stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class PriceImpact(Factor):
    """
    Price impact factor.

    Measures how much volume moves prices.
    Lower impact = better liquidity
    """

    def __init__(self, lookback: int = 20) -> None:
        """
        Initialize price impact factor.

        Args:
            lookback: Lookback period
        """
        metadata = FactorMetadata(
            name=f"price_impact_{lookback}d",
            category=FactorCategory.LIQUIDITY,
            description=f"{lookback}-day price impact (inverted)",
            formula="-1 * Average(|Return| / Volume^0.5)",
            data_requirements=['close', 'volume'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate inverted price impact."""
        closes = data['close'].unstack(fill_value=np.nan)
        volumes = data['volume'].unstack(fill_value=np.nan)

        # Calculate returns
        returns = closes.pct_change().abs()

        # Calculate price impact (Kyle's lambda approximation)
        impact = returns / np.sqrt(volumes)

        # Calculate average impact
        avg_impact = impact.rolling(window=self.lookback).mean()

        # Invert for liquidity signal
        result = (-avg_impact).stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class LiquidityRatio(Factor):
    """
    Liquidity ratio (composite measure).

    Combines volume and volatility for overall liquidity score.
    Higher ratio = better liquidity
    """

    def __init__(self, lookback: int = 20) -> None:
        """
        Initialize liquidity ratio factor.

        Args:
            lookback: Lookback period
        """
        metadata = FactorMetadata(
            name=f"liquidity_ratio_{lookback}d",
            category=FactorCategory.LIQUIDITY,
            description=f"{lookback}-day liquidity ratio",
            formula="Volume / Volatility",
            data_requirements=['close', 'volume'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate liquidity ratio."""
        closes = data['close'].unstack(fill_value=np.nan)
        volumes = data['volume'].unstack(fill_value=np.nan)

        # Calculate average volume
        avg_volume = volumes.rolling(window=self.lookback).mean()

        # Calculate volatility
        returns = closes.pct_change()
        volatility = returns.rolling(window=self.lookback).std()

        # Calculate liquidity ratio
        liq_ratio = avg_volume / volatility

        result = liq_ratio.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class MarketCapitalization(Factor):
    """
    Market capitalization (size factor).

    Formula: Price * Shares Outstanding
    Larger cap = generally better liquidity
    """

    def __init__(self) -> None:
        """Initialize market cap factor."""
        metadata = FactorMetadata(
            name="market_cap",
            category=FactorCategory.LIQUIDITY,
            description="Market capitalization (size factor)",
            formula="Price * Shares Outstanding",
            data_requirements=['close', 'shares_outstanding'],
            lookback_period=1,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate market cap."""
        if 'market_cap' in data.columns:
            market_cap = data['market_cap'].unstack(fill_value=np.nan)
        else:
            closes = data['close'].unstack(fill_value=np.nan)

            if 'shares_outstanding' not in data.columns:
                logger.warning("Missing shares outstanding data for market cap calculation")
                return pd.Series(dtype=float)

            shares = data['shares_outstanding'].unstack(fill_value=np.nan)
            market_cap = closes * shares

        # Use log scale for better distribution
        log_market_cap = np.log(market_cap)

        result = log_market_cap.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


# Factory function to create all liquidity factors
def create_liquidity_factors() -> List[Factor]:
    """
    Create standard set of liquidity factors.

    Returns:
        List of liquidity factors
    """
    return [
        # Volume-based
        AverageDollarVolume(lookback=20),
        AverageDollarVolume(lookback=60),
        ShareTurnover(lookback=20),

        # Price impact
        AmihudIlliquidity(lookback=20),
        PriceImpact(lookback=20),

        # Spread measures
        BidAskSpread(lookback=20),
        RollMeasure(lookback=20),

        # Consistency
        VolumeVolatility(lookback=20),
        ZeroReturnDays(lookback=60),

        # Composite
        LiquidityRatio(lookback=20),

        # Size
        MarketCapitalization(),
    ]


# Alias for backward compatibility
DollarVolume = AverageDollarVolume


# Additional alias
MarketCapFactor = MarketCapitalization

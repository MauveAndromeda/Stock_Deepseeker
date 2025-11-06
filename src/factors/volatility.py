"""
Volatility factors.

Risk and volatility metrics for cross-sectional ranking.
"""

from typing import Optional, List
import pandas as pd
import numpy as np
from loguru import logger

from src.factors import Factor, FactorMetadata, FactorCategory


class HistoricalVolatility(Factor):
    """
    Historical volatility (standard deviation of returns).

    Formula: StdDev(returns) * sqrt(252)
    Lower volatility = less risk (inverted for quality signal)
    """

    def __init__(self, lookback: int = 20) -> None:
        """
        Initialize historical volatility factor.

        Args:
            lookback: Lookback period for volatility calculation
        """
        metadata = FactorMetadata(
            name=f"historical_volatility_{lookback}d",
            category=FactorCategory.VOLATILITY,
            description=f"{lookback}-day annualized volatility (inverted)",
            formula=f"-1 * StdDev(returns_{lookback}d) * sqrt(252)",
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
        """Calculate inverted historical volatility."""
        closes = data['close'].unstack(fill_value=np.nan)

        # Calculate returns
        returns = closes.pct_change()

        # Calculate rolling volatility
        volatility = returns.rolling(window=self.lookback).std()

        # Annualize
        volatility_annual = volatility * np.sqrt(252)

        # Invert for quality signal (lower vol = higher score)
        result = (-volatility_annual).stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class DownsideVolatility(Factor):
    """
    Downside volatility (semi-deviation).

    Only measures volatility of negative returns.
    Lower downside vol = better risk profile
    """

    def __init__(self, lookback: int = 20) -> None:
        """
        Initialize downside volatility factor.

        Args:
            lookback: Lookback period
        """
        metadata = FactorMetadata(
            name=f"downside_volatility_{lookback}d",
            category=FactorCategory.VOLATILITY,
            description=f"{lookback}-day downside semi-deviation (inverted)",
            formula=f"-1 * StdDev(negative_returns_{lookback}d) * sqrt(252)",
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
        """Calculate inverted downside volatility."""
        closes = data['close'].unstack(fill_value=np.nan)

        # Calculate returns
        returns = closes.pct_change()

        # Only keep negative returns
        downside_returns = returns.copy()
        downside_returns[downside_returns > 0] = 0

        # Calculate rolling downside volatility
        downside_vol = downside_returns.rolling(window=self.lookback).std()

        # Annualize
        downside_vol_annual = downside_vol * np.sqrt(252)

        # Invert for quality signal
        result = (-downside_vol_annual).stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class BetaFactor(Factor):
    """
    Market Beta factor.

    Formula: Cov(stock, market) / Var(market)
    Lower beta = less systematic risk (inverted for low-beta anomaly)
    """

    def __init__(self, lookback: int = 252, market_symbol: str = 'SPY') -> None:
        """
        Initialize beta factor.

        Args:
            lookback: Lookback period for beta calculation
            market_symbol: Symbol to use as market proxy
        """
        metadata = FactorMetadata(
            name=f"beta_{lookback}d",
            category=FactorCategory.VOLATILITY,
            description=f"{lookback}-day market beta (inverted for low-beta anomaly)",
            formula=f"-1 * Cov(stock, {market_symbol}) / Var({market_symbol})",
            data_requirements=['close'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback
        self.market_symbol = market_symbol

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate inverted beta."""
        closes = data['close'].unstack(fill_value=np.nan)

        # Get market returns
        if self.market_symbol not in closes.columns:
            logger.warning(f"Market symbol {self.market_symbol} not in data, using mean returns")
            market_returns = closes.pct_change().mean(axis=1)
        else:
            market_returns = closes[self.market_symbol].pct_change()

        # Calculate stock returns
        stock_returns = closes.pct_change()

        # Calculate rolling beta
        def rolling_beta(stock_rets):
            covariance = stock_rets.rolling(window=self.lookback).cov(market_returns)
            market_variance = market_returns.rolling(window=self.lookback).var()
            return covariance / market_variance

        beta = stock_returns.apply(rolling_beta)

        # Invert for low-beta anomaly
        result = (-beta).stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class IdiosyncraticVolatility(Factor):
    """
    Idiosyncratic volatility (stock-specific risk).

    Volatility of residuals from market model.
    Lower idiosyncratic vol = better
    """

    def __init__(self, lookback: int = 60, market_symbol: str = 'SPY') -> None:
        """
        Initialize idiosyncratic volatility factor.

        Args:
            lookback: Lookback period
            market_symbol: Market proxy symbol
        """
        metadata = FactorMetadata(
            name=f"idiosyncratic_volatility_{lookback}d",
            category=FactorCategory.VOLATILITY,
            description=f"{lookback}-day idiosyncratic volatility (inverted)",
            formula="StdDev(stock_returns - beta * market_returns)",
            data_requirements=['close'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback
        self.market_symbol = market_symbol

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate inverted idiosyncratic volatility."""
        closes = data['close'].unstack(fill_value=np.nan)

        # Get market returns
        if self.market_symbol not in closes.columns:
            logger.warning(f"Market symbol {self.market_symbol} not in data")
            market_returns = closes.pct_change().mean(axis=1)
        else:
            market_returns = closes[self.market_symbol].pct_change()

        # Calculate stock returns
        stock_returns = closes.pct_change()

        # Calculate rolling beta and residuals
        def rolling_idio_vol(stock_rets):
            # Calculate beta
            covariance = stock_rets.rolling(window=self.lookback).cov(market_returns)
            market_variance = market_returns.rolling(window=self.lookback).var()
            beta = covariance / market_variance

            # Calculate residuals
            residuals = stock_rets - beta * market_returns

            # Calculate volatility of residuals
            idio_vol = residuals.rolling(window=self.lookback).std()
            return idio_vol * np.sqrt(252)

        idio_volatility = stock_returns.apply(rolling_idio_vol)

        # Invert for quality signal
        result = (-idio_volatility).stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class MaxDrawdown(Factor):
    """
    Maximum drawdown factor.

    Largest peak-to-trough decline over period.
    Lower drawdown = better risk profile
    """

    def __init__(self, lookback: int = 252) -> None:
        """
        Initialize max drawdown factor.

        Args:
            lookback: Lookback period
        """
        metadata = FactorMetadata(
            name=f"max_drawdown_{lookback}d",
            category=FactorCategory.VOLATILITY,
            description=f"{lookback}-day maximum drawdown (inverted)",
            formula="Max peak-to-trough decline",
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
        """Calculate inverted max drawdown."""
        closes = data['close'].unstack(fill_value=np.nan)

        # Calculate rolling max drawdown
        def calc_max_dd(prices):
            rolling_max = prices.rolling(window=self.lookback, min_periods=1).max()
            drawdown = (prices - rolling_max) / rolling_max
            return drawdown.rolling(window=self.lookback).min()

        max_dd = closes.apply(calc_max_dd)

        # Invert for quality signal (less negative = better)
        result = (-max_dd).stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class VolatilityOfVolatility(Factor):
    """
    Volatility of volatility (vol-of-vol).

    Measures consistency of volatility.
    Lower vol-of-vol = more stable risk profile
    """

    def __init__(self, short_period: int = 20, long_period: int = 60) -> None:
        """
        Initialize vol-of-vol factor.

        Args:
            short_period: Period for calculating volatility
            long_period: Period for calculating vol-of-vol
        """
        metadata = FactorMetadata(
            name=f"vol_of_vol_{short_period}_{long_period}d",
            category=FactorCategory.VOLATILITY,
            description="Volatility of volatility (inverted)",
            formula=f"StdDev(rolling_vol_{short_period}d) over {long_period}d",
            data_requirements=['close'],
            lookback_period=long_period,
        )
        super().__init__(metadata)
        self.short_period = short_period
        self.long_period = long_period

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate inverted vol-of-vol."""
        closes = data['close'].unstack(fill_value=np.nan)

        # Calculate returns
        returns = closes.pct_change()

        # Calculate rolling volatility
        volatility = returns.rolling(window=self.short_period).std()

        # Calculate volatility of volatility
        vol_of_vol = volatility.rolling(window=self.long_period).std()

        # Invert for quality signal
        result = (-vol_of_vol).stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class SharpeRatio(Factor):
    """
    Sharpe ratio (risk-adjusted return).

    Formula: (Return - Risk Free Rate) / Volatility
    Higher Sharpe = better risk-adjusted performance
    """

    def __init__(self, lookback: int = 252, risk_free_rate: float = 0.02) -> None:
        """
        Initialize Sharpe ratio factor.

        Args:
            lookback: Lookback period
            risk_free_rate: Annual risk-free rate
        """
        metadata = FactorMetadata(
            name=f"sharpe_ratio_{lookback}d",
            category=FactorCategory.VOLATILITY,
            description=f"{lookback}-day Sharpe ratio",
            formula="(Annualized Return - Risk Free Rate) / Annualized Volatility",
            data_requirements=['close'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback
        self.risk_free_rate = risk_free_rate

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate Sharpe ratio."""
        closes = data['close'].unstack(fill_value=np.nan)

        # Calculate returns
        returns = closes.pct_change()

        # Calculate rolling mean return
        mean_return = returns.rolling(window=self.lookback).mean() * 252

        # Calculate rolling volatility
        volatility = returns.rolling(window=self.lookback).std() * np.sqrt(252)

        # Calculate Sharpe ratio
        sharpe = (mean_return - self.risk_free_rate) / volatility

        result = sharpe.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class SortinoRatio(Factor):
    """
    Sortino ratio (downside risk-adjusted return).

    Uses downside deviation instead of total volatility.
    Higher Sortino = better downside risk-adjusted performance
    """

    def __init__(self, lookback: int = 252, risk_free_rate: float = 0.02) -> None:
        """
        Initialize Sortino ratio factor.

        Args:
            lookback: Lookback period
            risk_free_rate: Annual risk-free rate
        """
        metadata = FactorMetadata(
            name=f"sortino_ratio_{lookback}d",
            category=FactorCategory.VOLATILITY,
            description=f"{lookback}-day Sortino ratio",
            formula="(Return - Risk Free Rate) / Downside Deviation",
            data_requirements=['close'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback
        self.risk_free_rate = risk_free_rate

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate Sortino ratio."""
        closes = data['close'].unstack(fill_value=np.nan)

        # Calculate returns
        returns = closes.pct_change()

        # Calculate rolling mean return
        mean_return = returns.rolling(window=self.lookback).mean() * 252

        # Calculate downside deviation
        downside_returns = returns.copy()
        downside_returns[downside_returns > 0] = 0
        downside_dev = downside_returns.rolling(window=self.lookback).std() * np.sqrt(252)

        # Calculate Sortino ratio
        sortino = (mean_return - self.risk_free_rate) / downside_dev

        result = sortino.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class CalmarRatio(Factor):
    """
    Calmar ratio (return / max drawdown).

    Higher Calmar = better drawdown-adjusted performance
    """

    def __init__(self, lookback: int = 252) -> None:
        """
        Initialize Calmar ratio factor.

        Args:
            lookback: Lookback period
        """
        metadata = FactorMetadata(
            name=f"calmar_ratio_{lookback}d",
            category=FactorCategory.VOLATILITY,
            description=f"{lookback}-day Calmar ratio",
            formula="Annualized Return / Abs(Max Drawdown)",
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
        """Calculate Calmar ratio."""
        closes = data['close'].unstack(fill_value=np.nan)

        # Calculate annualized returns
        returns = closes.pct_change()
        annual_return = returns.rolling(window=self.lookback).mean() * 252

        # Calculate max drawdown
        def calc_max_dd(prices):
            rolling_max = prices.rolling(window=self.lookback, min_periods=1).max()
            drawdown = (prices - rolling_max) / rolling_max
            return drawdown.rolling(window=self.lookback).min()

        max_dd = closes.apply(calc_max_dd)

        # Calculate Calmar ratio
        calmar = annual_return / abs(max_dd)

        result = calmar.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class UpVolatility(Factor):
    """
    Upside volatility (volatility of positive returns).

    Higher upside vol = more explosive upside potential
    """

    def __init__(self, lookback: int = 20) -> None:
        """
        Initialize upside volatility factor.

        Args:
            lookback: Lookback period
        """
        metadata = FactorMetadata(
            name=f"upside_volatility_{lookback}d",
            category=FactorCategory.VOLATILITY,
            description=f"{lookback}-day upside semi-deviation",
            formula=f"StdDev(positive_returns_{lookback}d) * sqrt(252)",
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
        """Calculate upside volatility."""
        closes = data['close'].unstack(fill_value=np.nan)

        # Calculate returns
        returns = closes.pct_change()

        # Only keep positive returns
        upside_returns = returns.copy()
        upside_returns[upside_returns < 0] = 0

        # Calculate rolling upside volatility
        upside_vol = upside_returns.rolling(window=self.lookback).std()

        # Annualize
        upside_vol_annual = upside_vol * np.sqrt(252)

        result = upside_vol_annual.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


# Factory function to create all volatility factors
def create_volatility_factors() -> List[Factor]:
    """
    Create standard set of volatility factors.

    Returns:
        List of volatility factors
    """
    return [
        # Basic volatility
        HistoricalVolatility(lookback=20),
        HistoricalVolatility(lookback=60),
        DownsideVolatility(lookback=20),
        DownsideVolatility(lookback=60),

        # Market-relative
        BetaFactor(lookback=252),
        IdiosyncraticVolatility(lookback=60),

        # Drawdown
        MaxDrawdown(lookback=252),

        # Volatility dynamics
        VolatilityOfVolatility(short_period=20, long_period=60),

        # Risk-adjusted metrics
        SharpeRatio(lookback=252),
        SortinoRatio(lookback=252),
        CalmarRatio(lookback=252),

        # Upside potential
        UpVolatility(lookback=20),
    ]


# Aliases for backward compatibility
Beta = BetaFactor
Volatility = HistoricalVolatility

"""
Factor backtesting framework.

Tests individual factors by ranking stocks and measuring forward returns.
"""

from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger
import numpy as np
import pandas as pd

from src.factors import Factor


@dataclass
class FactorBacktestResult:
    """
    Results from factor backtest.

    Attributes:
        factor_name: Name of factor tested
        start_date: Backtest start date
        end_date: Backtest end date
        total_periods: Number of rebalancing periods
        quantile_returns: Returns by factor quantile
        long_short_returns: Long-short portfolio returns
        cumulative_returns: Cumulative returns over time
        sharpe_ratio: Sharpe ratio of long-short portfolio
        information_ratio: Information ratio
        win_rate: Proportion of periods with positive returns
        max_drawdown: Maximum drawdown
        turnover: Average portfolio turnover
        ic_mean: Mean Information Coefficient
        ic_std: IC standard deviation
        ic_ir: IC Information Ratio
        metadata: Additional metrics
    """
    factor_name: str
    start_date: datetime
    end_date: datetime
    total_periods: int
    quantile_returns: pd.DataFrame
    long_short_returns: pd.Series
    cumulative_returns: pd.Series
    sharpe_ratio: float
    information_ratio: float
    win_rate: float
    max_drawdown: float
    turnover: float
    ic_mean: float
    ic_std: float
    ic_ir: float
    metadata: dict = field(default_factory=dict)

    def summary(self) -> str:
        """Generate summary report."""
        return f"""
Factor Backtest Summary: {self.factor_name}
{'=' * 60}
Period: {self.start_date.date()} to {self.end_date.date()}
Total Periods: {self.total_periods}

Performance Metrics:
- Sharpe Ratio: {self.sharpe_ratio:.3f}
- Information Ratio: {self.information_ratio:.3f}
- Win Rate: {self.win_rate:.1%}
- Max Drawdown: {self.max_drawdown:.2%}
- Average Turnover: {self.turnover:.1%}

Information Coefficient:
- Mean IC: {self.ic_mean:.4f}
- IC Std: {self.ic_std:.4f}
- IC IR: {self.ic_ir:.3f}

Quantile Returns (annualized):
{self.quantile_returns.mean() * 252}
"""


class FactorBacktester:
    """
    Backtests individual factors using quantile portfolios.

    Tests factor predictive power by:
    1. Ranking stocks by factor values
    2. Forming quintile portfolios
    3. Measuring forward returns
    4. Calculating performance metrics
    """

    def __init__(
        self,
        holding_period: int = 21,  # Days to hold position
        quantiles: int = 5,  # Number of quantiles
        long_quantile: int = 5,  # Top quantile for long
        short_quantile: int = 1,  # Bottom quantile for short
        rebalance_frequency: str = "monthly",  # 'daily', 'weekly', 'monthly'
        min_stocks_per_quantile: int = 5,
        transaction_cost: float = 0.001,  # 10 bps per trade
    ) -> None:
        """
        Initialize factor backtester.

        Args:
            holding_period: Days to hold each position
            quantiles: Number of quantiles to form
            long_quantile: Which quantile to long (highest = best)
            short_quantile: Which quantile to short
            rebalance_frequency: How often to rebalance
            min_stocks_per_quantile: Minimum stocks per quantile
            transaction_cost: Transaction cost per trade
        """
        self.holding_period = holding_period
        self.quantiles = quantiles
        self.long_quantile = long_quantile
        self.short_quantile = short_quantile
        self.rebalance_frequency = rebalance_frequency
        self.min_stocks_per_quantile = min_stocks_per_quantile
        self.transaction_cost = transaction_cost

        logger.info(f"Initialized FactorBacktester with {quantiles} quantiles")

    def backtest(
        self,
        factor: Factor,
        price_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
        universe: list[str] | None = None
    ) -> FactorBacktestResult:
        """
        Run backtest for a factor.

        Args:
            factor: Factor to test
            price_data: Price data (multi-index: date, symbol)
            start_date: Backtest start
            end_date: Backtest end
            universe: Optional list of symbols to test on

        Returns:
            FactorBacktestResult with performance metrics
        """
        logger.info(f"Backtesting factor: {factor.metadata.name}")

        # Filter data to backtest period
        mask = (price_data.index.get_level_values(0) >= start_date) & \
               (price_data.index.get_level_values(0) <= end_date)
        data = price_data[mask].copy()

        # Calculate factor values
        factor_values = factor.calculate(data, universe)

        # Get rebalancing dates
        rebalance_dates = self._get_rebalance_dates(data, start_date, end_date)

        # Run backtest across rebalancing periods
        quantile_returns_list = []
        long_short_returns_list = []
        ic_list = []
        turnover_list = []
        previous_holdings = None

        for i, rebal_date in enumerate(rebalance_dates[:-1]):
            # Get factor values at rebalance date
            if rebal_date not in factor_values.index.get_level_values(0):
                continue

            factor_at_date = factor_values.loc[rebal_date]

            # Form quantile portfolios
            portfolios = self._form_quantile_portfolios(factor_at_date)

            # Calculate forward returns
            next_rebal_date = rebalance_dates[i + 1]
            quantile_rets = self._calculate_forward_returns(
                portfolios, data, rebal_date, next_rebal_date
            )

            if quantile_rets is None:
                continue

            quantile_returns_list.append(quantile_rets)

            # Long-short return
            long_ret = quantile_rets.iloc[self.long_quantile - 1]
            short_ret = quantile_rets.iloc[self.short_quantile - 1]
            ls_ret = long_ret - short_ret - 2 * self.transaction_cost
            long_short_returns_list.append((rebal_date, ls_ret))

            # Information Coefficient
            ic = self._calculate_ic(factor_at_date, data, rebal_date, next_rebal_date)
            if ic is not None:
                ic_list.append(ic)

            # Turnover
            if previous_holdings is not None:
                turnover = self._calculate_turnover(
                    previous_holdings,
                    portfolios[self.long_quantile]
                )
                turnover_list.append(turnover)

            previous_holdings = portfolios[self.long_quantile]

        # Aggregate results
        quantile_returns = pd.DataFrame(quantile_returns_list)
        long_short_returns = pd.Series(
            [ret for _, ret in long_short_returns_list],
            index=[date for date, _ in long_short_returns_list]
        )

        # Calculate cumulative returns
        cumulative_returns = (1 + long_short_returns).cumprod()

        # Calculate metrics
        sharpe = self._calculate_sharpe_ratio(long_short_returns)
        ir = self._calculate_information_ratio(long_short_returns)
        win_rate = (long_short_returns > 0).mean()
        max_dd = self._calculate_max_drawdown(cumulative_returns)
        avg_turnover = np.mean(turnover_list) if turnover_list else 0

        ic_series = pd.Series(ic_list)
        ic_mean = ic_series.mean()
        ic_std = ic_series.std()
        ic_ir = ic_mean / ic_std if ic_std > 0 else 0

        result = FactorBacktestResult(
            factor_name=factor.metadata.name,
            start_date=start_date,
            end_date=end_date,
            total_periods=len(rebalance_dates) - 1,
            quantile_returns=quantile_returns,
            long_short_returns=long_short_returns,
            cumulative_returns=cumulative_returns,
            sharpe_ratio=sharpe,
            information_ratio=ir,
            win_rate=win_rate,
            max_drawdown=max_dd,
            turnover=avg_turnover,
            ic_mean=ic_mean,
            ic_std=ic_std,
            ic_ir=ic_ir,
        )

        logger.info(f"Backtest completed: Sharpe={sharpe:.3f}, IC={ic_mean:.4f}")

        return result

    def _get_rebalance_dates(
        self,
        data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime
    ) -> list[datetime]:
        """Get list of rebalancing dates."""
        all_dates = sorted(data.index.get_level_values(0).unique())
        dates_in_range = [d for d in all_dates if start_date <= d <= end_date]

        if self.rebalance_frequency == "daily":
            return dates_in_range
        if self.rebalance_frequency == "weekly":
            # First trading day of each week
            rebal_dates = []
            current_week = None
            for date in dates_in_range:
                week = date.isocalendar()[1]
                if week != current_week:
                    rebal_dates.append(date)
                    current_week = week
            return rebal_dates
        if self.rebalance_frequency == "monthly":
            # First trading day of each month
            rebal_dates = []
            current_month = None
            for date in dates_in_range:
                month = date.month
                if month != current_month:
                    rebal_dates.append(date)
                    current_month = month
            return rebal_dates
        raise ValueError(f"Unknown rebalance frequency: {self.rebalance_frequency}")

    def _form_quantile_portfolios(
        self,
        factor_values: pd.Series
    ) -> dict[int, list[str]]:
        """
        Form quantile portfolios based on factor values.

        Args:
            factor_values: Factor values for stocks

        Returns:
            Dict mapping quantile number to list of symbols
        """
        # Remove NaN values
        factor_values = factor_values.dropna()

        if len(factor_values) < self.quantiles * self.min_stocks_per_quantile:
            logger.warning(
                f"Insufficient stocks ({len(factor_values)}) for {self.quantiles} quantiles"
            )
            return {}

        # Rank into quantiles
        factor_values = factor_values.sort_values()
        quantile_size = len(factor_values) // self.quantiles

        portfolios = {}
        for q in range(1, self.quantiles + 1):
            start_idx = (q - 1) * quantile_size
            if q == self.quantiles:
                # Last quantile gets remainder
                end_idx = len(factor_values)
            else:
                end_idx = q * quantile_size

            portfolios[q] = factor_values.iloc[start_idx:end_idx].index.tolist()

        return portfolios

    def _calculate_forward_returns(
        self,
        portfolios: dict[int, list[str]],
        data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime
    ) -> pd.Series | None:
        """
        Calculate forward returns for each quantile portfolio.

        Args:
            portfolios: Quantile portfolios
            data: Price data
            start_date: Portfolio formation date
            end_date: Portfolio liquidation date

        Returns:
            Series of returns by quantile
        """
        quantile_returns = []

        for q in range(1, self.quantiles + 1):
            if q not in portfolios or len(portfolios[q]) == 0:
                quantile_returns.append(np.nan)
                continue

            symbols = portfolios[q]

            # Get prices at start and end
            returns = []
            for symbol in symbols:
                try:
                    start_price = data.loc[(start_date, symbol), "close"]
                    end_price = data.loc[(end_date, symbol), "close"]
                    ret = (end_price - start_price) / start_price
                    returns.append(ret)
                except (KeyError, ZeroDivisionError):
                    continue

            if len(returns) == 0:
                quantile_returns.append(np.nan)
            else:
                # Equal-weighted portfolio return
                quantile_returns.append(np.mean(returns))

        if all(np.isnan(quantile_returns)):
            return None

        return pd.Series(quantile_returns, index=range(1, self.quantiles + 1))

    def _calculate_ic(
        self,
        factor_values: pd.Series,
        data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime
    ) -> float | None:
        """
        Calculate Information Coefficient (Spearman correlation).

        Args:
            factor_values: Factor values at start_date
            data: Price data
            start_date: Start date
            end_date: End date

        Returns:
            IC value
        """
        # Calculate forward returns for all stocks
        forward_returns = []
        factor_vals = []

        for symbol in factor_values.index:
            try:
                start_price = data.loc[(start_date, symbol), "close"]
                end_price = data.loc[(end_date, symbol), "close"]
                ret = (end_price - start_price) / start_price
                forward_returns.append(ret)
                factor_vals.append(factor_values[symbol])
            except (KeyError, ZeroDivisionError):
                continue

        if len(forward_returns) < 10:  # Need minimum stocks
            return None

        # Calculate Spearman correlation
        try:
            from scipy.stats import spearmanr
            ic, _ = spearmanr(factor_vals, forward_returns)
            return ic
        except Exception as e:
            logger.warning(f"Failed to calculate IC: {e}")
            return None

    def _calculate_turnover(
        self,
        old_holdings: list[str],
        new_holdings: list[str]
    ) -> float:
        """
        Calculate portfolio turnover.

        Args:
            old_holdings: Previous period holdings
            new_holdings: Current period holdings

        Returns:
            Turnover ratio [0, 1]
        """
        old_set = set(old_holdings)
        new_set = set(new_holdings)

        # Turnover = (additions + deletions) / 2
        additions = len(new_set - old_set)
        deletions = len(old_set - new_set)

        turnover = (additions + deletions) / (2 * len(old_set)) if len(old_set) > 0 else 1.0

        return turnover

    def _calculate_sharpe_ratio(self, returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """Calculate annualized Sharpe ratio."""
        if len(returns) == 0 or returns.std() == 0:
            return 0.0

        excess_returns = returns - risk_free_rate / 252
        sharpe = np.sqrt(252) * excess_returns.mean() / returns.std()
        return sharpe

    def _calculate_information_ratio(self, returns: pd.Series) -> float:
        """Calculate Information Ratio (Sharpe with 0 benchmark)."""
        if len(returns) == 0 or returns.std() == 0:
            return 0.0

        ir = np.sqrt(252) * returns.mean() / returns.std()
        return ir

    def _calculate_max_drawdown(self, cumulative_returns: pd.Series) -> float:
        """Calculate maximum drawdown."""
        if len(cumulative_returns) == 0:
            return 0.0

        running_max = cumulative_returns.cummax()
        drawdown = (cumulative_returns - running_max) / running_max
        return drawdown.min()

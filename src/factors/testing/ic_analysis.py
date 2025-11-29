"""
Information Coefficient (IC) analysis.

Analyzes the predictive power of factors using IC metrics.
"""

from dataclasses import dataclass
from datetime import datetime

from loguru import logger
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr


@dataclass
class ICMetrics:
    """
    Information Coefficient metrics.

    Attributes:
        mean_ic: Mean IC
        median_ic: Median IC
        std_ic: Standard deviation of IC
        ic_ir: IC Information Ratio (mean / std)
        positive_ic_ratio: Proportion of periods with positive IC
        ic_skewness: Skewness of IC distribution
        ic_kurtosis: Kurtosis of IC distribution
        ic_series: Time series of IC values
        rank_ic_mean: Mean Rank IC (Spearman)
        rank_ic_ir: Rank IC Information Ratio
    """
    mean_ic: float
    median_ic: float
    std_ic: float
    ic_ir: float
    positive_ic_ratio: float
    ic_skewness: float
    ic_kurtosis: float
    ic_series: pd.Series
    rank_ic_mean: float
    rank_ic_ir: float

    def summary(self) -> str:
        """Generate summary report."""
        return f"""
Information Coefficient Analysis
{'=' * 60}
Mean IC: {self.mean_ic:.4f}
Median IC: {self.median_ic:.4f}
IC Std Dev: {self.std_ic:.4f}
IC IR: {self.ic_ir:.3f}
Positive IC %: {self.positive_ic_ratio:.1%}
IC Skewness: {self.ic_skewness:.3f}
IC Kurtosis: {self.ic_kurtosis:.3f}

Rank IC (Spearman):
Mean: {self.rank_ic_mean:.4f}
IR: {self.rank_ic_ir:.3f}
"""


class ICAnalyzer:
    """
    Analyzes Information Coefficient of factors.

    IC measures the correlation between factor values and forward returns,
    indicating the factor's predictive power.
    """

    def __init__(
        self,
        forward_periods: list[int] = None,
        ic_type: str = "both",  # 'pearson', 'spearman', 'both'
        min_stocks: int = 20,
    ) -> None:
        """
        Initialize IC analyzer.

        Args:
            forward_periods: List of forward return periods to test
            ic_type: Type of correlation to calculate
            min_stocks: Minimum stocks required for IC calculation
        """
        self.forward_periods = forward_periods or [1, 5, 10, 21]
        self.ic_type = ic_type
        self.min_stocks = min_stocks

        logger.info(f"Initialized ICAnalyzer with periods: {self.forward_periods}")

    def analyze(
        self,
        factor_values: pd.Series,
        price_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime
    ) -> dict[int, ICMetrics]:
        """
        Analyze IC for different forward periods.

        Args:
            factor_values: Factor values (multi-index: date, symbol)
            price_data: Price data
            start_date: Analysis start date
            end_date: Analysis end date

        Returns:
            Dict mapping forward period to ICMetrics
        """
        logger.info(f"Analyzing IC from {start_date.date()} to {end_date.date()}")

        results = {}

        for period in self.forward_periods:
            ic_metrics = self._calculate_period_ic(
                factor_values,
                price_data,
                period,
                start_date,
                end_date
            )

            if ic_metrics is not None:
                results[period] = ic_metrics
                logger.info(
                    f"{period}D IC: Mean={ic_metrics.mean_ic:.4f}, "
                    f"IR={ic_metrics.ic_ir:.3f}"
                )

        return results

    def _calculate_period_ic(
        self,
        factor_values: pd.Series,
        price_data: pd.DataFrame,
        forward_period: int,
        start_date: datetime,
        end_date: datetime
    ) -> ICMetrics | None:
        """Calculate IC for a specific forward period."""
        # Get unique dates
        dates = sorted(factor_values.index.get_level_values(0).unique())
        dates = [d for d in dates if start_date <= d <= end_date]

        pearson_ics = []
        spearman_ics = []

        for date in dates:
            # Get factor values at this date
            if date not in factor_values.index.get_level_values(0):
                continue

            factor_at_date = factor_values.loc[date]

            # Calculate forward returns
            forward_returns = self._calculate_forward_returns(
                factor_at_date.index.tolist(),
                price_data,
                date,
                forward_period
            )

            if len(forward_returns) < self.min_stocks:
                continue

            # Align factor values and returns
            common_symbols = list(set(factor_at_date.index) & set(forward_returns.keys()))
            if len(common_symbols) < self.min_stocks:
                continue

            factor_vals = [factor_at_date[s] for s in common_symbols]
            returns = [forward_returns[s] for s in common_symbols]

            # Calculate IC
            if self.ic_type in ["pearson", "both"]:
                try:
                    ic_p, _ = pearsonr(factor_vals, returns)
                    if not np.isnan(ic_p):
                        pearson_ics.append((date, ic_p))
                except (ValueError, TypeError):
                    pass

            if self.ic_type in ["spearman", "both"]:
                try:
                    ic_s, _ = spearmanr(factor_vals, returns)
                    if not np.isnan(ic_s):
                        spearman_ics.append((date, ic_s))
                except (ValueError, TypeError):
                    pass

        if len(pearson_ics) == 0 and len(spearman_ics) == 0:
            return None

        # Use Pearson by default, Spearman for rank IC
        if len(pearson_ics) > 0:
            ic_series = pd.Series(
                [ic for _, ic in pearson_ics],
                index=[date for date, _ in pearson_ics]
            )
        else:
            ic_series = pd.Series(
                [ic for _, ic in spearman_ics],
                index=[date for date, _ in spearman_ics]
            )

        if len(spearman_ics) > 0:
            rank_ic_series = pd.Series(
                [ic for _, ic in spearman_ics],
                index=[date for date, _ in spearman_ics]
            )
        else:
            rank_ic_series = ic_series

        # Calculate metrics
        mean_ic = ic_series.mean()
        median_ic = ic_series.median()
        std_ic = ic_series.std()
        ic_ir = mean_ic / std_ic if std_ic > 0 else 0
        positive_ic_ratio = (ic_series > 0).mean()
        ic_skewness = ic_series.skew()
        ic_kurtosis = ic_series.kurtosis()

        rank_ic_mean = rank_ic_series.mean()
        rank_ic_std = rank_ic_series.std()
        rank_ic_ir = rank_ic_mean / rank_ic_std if rank_ic_std > 0 else 0

        return ICMetrics(
            mean_ic=mean_ic,
            median_ic=median_ic,
            std_ic=std_ic,
            ic_ir=ic_ir,
            positive_ic_ratio=positive_ic_ratio,
            ic_skewness=ic_skewness,
            ic_kurtosis=ic_kurtosis,
            ic_series=ic_series,
            rank_ic_mean=rank_ic_mean,
            rank_ic_ir=rank_ic_ir,
        )

    def _calculate_forward_returns(
        self,
        symbols: list[str],
        price_data: pd.DataFrame,
        start_date: datetime,
        forward_period: int
    ) -> dict[str, float]:
        """
        Calculate forward returns for symbols.

        Args:
            symbols: List of symbols
            price_data: Price data
            start_date: Starting date
            forward_period: Number of days forward

        Returns:
            Dict mapping symbol to forward return
        """
        forward_returns = {}

        # Get all dates
        all_dates = sorted(price_data.index.get_level_values(0).unique())

        # Find end date
        try:
            start_idx = all_dates.index(start_date)
            end_idx = min(start_idx + forward_period, len(all_dates) - 1)
            end_date = all_dates[end_idx]
        except (ValueError, IndexError):
            return {}

        for symbol in symbols:
            try:
                start_price = price_data.loc[(start_date, symbol), "close"]
                end_price = price_data.loc[(end_date, symbol), "close"]

                if start_price > 0:
                    ret = (end_price - start_price) / start_price
                    forward_returns[symbol] = ret
            except (KeyError, ZeroDivisionError):
                continue

        return forward_returns

    def rolling_ic_analysis(
        self,
        factor_values: pd.Series,
        price_data: pd.DataFrame,
        window: int = 252,  # 1 year rolling window
        forward_period: int = 21
    ) -> pd.DataFrame:
        """
        Calculate rolling IC over time.

        Args:
            factor_values: Factor values
            price_data: Price data
            window: Rolling window size
            forward_period: Forward return period

        Returns:
            DataFrame with rolling IC metrics
        """
        logger.info(f"Calculating {window}D rolling IC")

        dates = sorted(factor_values.index.get_level_values(0).unique())

        rolling_results = []

        for i in range(window, len(dates)):
            end_date = dates[i]
            start_date = dates[i - window]

            ic_metrics = self._calculate_period_ic(
                factor_values,
                price_data,
                forward_period,
                start_date,
                end_date
            )

            if ic_metrics is not None:
                rolling_results.append({
                    "date": end_date,
                    "mean_ic": ic_metrics.mean_ic,
                    "ic_ir": ic_metrics.ic_ir,
                    "positive_ratio": ic_metrics.positive_ic_ratio,
                })

        return pd.DataFrame(rolling_results).set_index("date")

    def ic_decay_analysis(
        self,
        factor_values: pd.Series,
        price_data: pd.DataFrame,
        max_period: int = 63,  # 3 months
        start_date: datetime | None = None,
        end_date: datetime | None = None
    ) -> pd.DataFrame:
        """
        Analyze how IC decays over time.

        Args:
            factor_values: Factor values
            price_data: Price data
            max_period: Maximum forward period to test
            start_date: Analysis start
            end_date: Analysis end

        Returns:
            DataFrame with IC at different horizons
        """
        logger.info(f"Analyzing IC decay up to {max_period} days")

        if start_date is None:
            start_date = factor_values.index.get_level_values(0).min()
        if end_date is None:
            end_date = factor_values.index.get_level_values(0).max()

        decay_results = []

        for period in range(1, max_period + 1, 5):  # Every 5 days
            ic_metrics = self._calculate_period_ic(
                factor_values,
                price_data,
                period,
                start_date,
                end_date
            )

            if ic_metrics is not None:
                decay_results.append({
                    "forward_period": period,
                    "mean_ic": ic_metrics.mean_ic,
                    "ic_ir": ic_metrics.ic_ir,
                    "positive_ratio": ic_metrics.positive_ic_ratio,
                })

        return pd.DataFrame(decay_results).set_index("forward_period")

    def cross_sectional_ic_distribution(
        self,
        factor_values: pd.Series,
        price_data: pd.DataFrame,
        forward_period: int = 21,
        bins: int = 20
    ) -> pd.Series:
        """
        Get distribution of cross-sectional IC values.

        Args:
            factor_values: Factor values
            price_data: Price data
            forward_period: Forward return period
            bins: Number of bins for histogram

        Returns:
            Series with IC distribution
        """
        dates = sorted(factor_values.index.get_level_values(0).unique())

        ic_values = []

        for date in dates:
            if date not in factor_values.index.get_level_values(0):
                continue

            factor_at_date = factor_values.loc[date]
            forward_returns = self._calculate_forward_returns(
                factor_at_date.index.tolist(),
                price_data,
                date,
                forward_period
            )

            if len(forward_returns) < self.min_stocks:
                continue

            common_symbols = list(set(factor_at_date.index) & set(forward_returns.keys()))
            if len(common_symbols) < self.min_stocks:
                continue

            factor_vals = [factor_at_date[s] for s in common_symbols]
            returns = [forward_returns[s] for s in common_symbols]

            try:
                ic, _ = spearmanr(factor_vals, returns)
                if not np.isnan(ic):
                    ic_values.append(ic)
            except (ValueError, TypeError):
                continue

        if len(ic_values) == 0:
            return pd.Series()

        # Create histogram
        hist, bin_edges = np.histogram(ic_values, bins=bins)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        return pd.Series(hist, index=bin_centers)

"""
Factor decay analysis.

Analyzes how factor signals decay over time.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from loguru import logger
from scipy.stats import spearmanr


@dataclass
class DecayAnalysis:
    """
    Factor decay analysis result.

    Attributes:
        factor_name: Name of factor
        ic_by_period: IC at different forward periods
        returns_by_period: Average returns at different periods
        cumulative_returns: Cumulative returns over time
        half_life: Estimated half-life of signal (days)
        optimal_holding_period: Optimal holding period
        decay_rate: Rate of decay per day
        periods_tested: List of periods tested
    """
    factor_name: str
    ic_by_period: pd.Series
    returns_by_period: pd.Series
    cumulative_returns: pd.Series
    half_life: float
    optimal_holding_period: int
    decay_rate: float
    periods_tested: List[int]
    metadata: Dict = field(default_factory=dict)

    def summary(self) -> str:
        """Generate summary report."""
        return f"""
Factor Decay Analysis: {self.factor_name}
{'=' * 60}
Half-Life: {self.half_life:.1f} days
Optimal Holding Period: {self.optimal_holding_period} days
Decay Rate: {self.decay_rate:.4f} per day

IC by Forward Period:
{self.ic_by_period}

Returns by Period (annualized):
{self.returns_by_period * 252}
"""


class FactorDecayAnalyzer:
    """
    Analyzes how factor signals decay over time.

    Tests factor predictive power at various forward horizons
    to determine optimal holding period and signal persistence.
    """

    def __init__(
        self,
        max_period: int = 126,  # Maximum forward period (6 months)
        step: int = 5,  # Step between periods
        min_stocks: int = 20,
    ) -> None:
        """
        Initialize decay analyzer.

        Args:
            max_period: Maximum forward period to test
            step: Step size between periods
            min_stocks: Minimum stocks for analysis
        """
        self.max_period = max_period
        self.step = step
        self.min_stocks = min_stocks

        logger.info(
            f"Initialized FactorDecayAnalyzer: testing up to {max_period} days"
        )

    def analyze_decay(
        self,
        factor_values: pd.Series,  # (date, symbol) multi-index
        price_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime
    ) -> DecayAnalysis:
        """
        Analyze factor decay pattern.

        Args:
            factor_values: Factor values
            price_data: Price data
            start_date: Analysis start
            end_date: Analysis end

        Returns:
            DecayAnalysis with decay metrics
        """
        factor_name = "factor"  # Can be extracted from metadata if available
        logger.info(f"Analyzing decay for {factor_name}")

        # Test IC at different forward periods
        periods = list(range(1, self.max_period + 1, self.step))

        ic_results = []
        return_results = []
        cumulative_returns = []

        for period in periods:
            # Calculate IC for this period
            ic, avg_return = self._calculate_period_metrics(
                factor_values,
                price_data,
                period,
                start_date,
                end_date
            )

            if ic is not None:
                ic_results.append((period, ic))
                return_results.append((period, avg_return))

                # Cumulative return approximation
                cumulative_returns.append((period, avg_return * period))

        if len(ic_results) < 3:
            logger.warning("Insufficient data for decay analysis")
            return self._empty_result(factor_name, periods)

        # Convert to Series
        ic_series = pd.Series([ic for _, ic in ic_results],
                             index=[p for p, _ in ic_results])
        return_series = pd.Series([r for _, r in return_results],
                                  index=[p for p, _ in return_results])
        cumulative_series = pd.Series([r for _, r in cumulative_returns],
                                       index=[p for p, _ in cumulative_returns])

        # Calculate decay metrics
        half_life = self._calculate_half_life(ic_series)
        optimal_period = self._find_optimal_period(return_series)
        decay_rate = self._calculate_decay_rate(ic_series)

        result = DecayAnalysis(
            factor_name=factor_name,
            ic_by_period=ic_series,
            returns_by_period=return_series,
            cumulative_returns=cumulative_series,
            half_life=half_life,
            optimal_holding_period=optimal_period,
            decay_rate=decay_rate,
            periods_tested=periods,
        )

        logger.info(
            f"Decay analysis complete: Half-life={half_life:.1f}D, "
            f"Optimal={optimal_period}D"
        )

        return result

    def compare_factors(
        self,
        factor_values_dict: Dict[str, pd.Series],
        price_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Compare decay patterns across multiple factors.

        Args:
            factor_values_dict: Dict of factor name -> values
            price_data: Price data
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame comparing decay metrics
        """
        logger.info(f"Comparing decay for {len(factor_values_dict)} factors")

        comparison_results = []

        for factor_name, factor_values in factor_values_dict.items():
            decay = self.analyze_decay(
                factor_values, price_data, start_date, end_date
            )

            comparison_results.append({
                'factor': factor_name,
                'half_life': decay.half_life,
                'optimal_period': decay.optimal_holding_period,
                'decay_rate': decay.decay_rate,
                'max_ic': decay.ic_by_period.max(),
                'max_return': decay.returns_by_period.max(),
            })

        df = pd.DataFrame(comparison_results)
        return df.sort_values('half_life', ascending=False)

    def _calculate_period_metrics(
        self,
        factor_values: pd.Series,
        price_data: pd.DataFrame,
        forward_period: int,
        start_date: datetime,
        end_date: datetime
    ) -> tuple[Optional[float], Optional[float]]:
        """Calculate IC and returns for a specific forward period."""
        dates = sorted(factor_values.index.get_level_values(0).unique())
        dates = [d for d in dates if start_date <= d <= end_date]

        all_factors = []
        all_returns = []

        for date in dates:
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

            # Align
            common_symbols = list(
                set(factor_at_date.index) & set(forward_returns.keys())
            )

            if len(common_symbols) < self.min_stocks:
                continue

            for symbol in common_symbols:
                all_factors.append(factor_at_date[symbol])
                all_returns.append(forward_returns[symbol])

        if len(all_factors) < self.min_stocks:
            return None, None

        # Calculate IC
        try:
            ic, _ = spearmanr(all_factors, all_returns)
        except Exception:
            ic = 0.0

        # Calculate average return (for top quintile)
        combined = pd.DataFrame({
            'factor': all_factors,
            'return': all_returns
        })
        combined = combined.sort_values('factor', ascending=False)
        top_quintile = combined.head(len(combined) // 5)
        avg_return = top_quintile['return'].mean()

        return ic, avg_return

    def _calculate_forward_returns(
        self,
        symbols: List[str],
        price_data: pd.DataFrame,
        start_date: datetime,
        forward_period: int
    ) -> Dict[str, float]:
        """Calculate forward returns for symbols."""
        all_dates = sorted(price_data.index.get_level_values(0).unique())

        try:
            start_idx = all_dates.index(start_date)
            end_idx = min(start_idx + forward_period, len(all_dates) - 1)
            end_date = all_dates[end_idx]
        except (ValueError, IndexError):
            return {}

        forward_returns = {}

        for symbol in symbols:
            try:
                start_price = price_data.loc[(start_date, symbol), 'close']
                end_price = price_data.loc[(end_date, symbol), 'close']

                if start_price > 0:
                    ret = (end_price - start_price) / start_price
                    forward_returns[symbol] = ret
            except (KeyError, ZeroDivisionError):
                continue

        return forward_returns

    def _calculate_half_life(self, ic_series: pd.Series) -> float:
        """
        Calculate half-life of signal decay.

        Fits exponential decay: IC(t) = IC(0) * exp(-λt)
        Half-life = ln(2) / λ
        """
        if len(ic_series) < 3:
            return np.nan

        # Fit exponential decay
        periods = ic_series.index.values
        ic_values = ic_series.values

        # Handle negative IC by using absolute value
        ic_abs = np.abs(ic_values)

        # Log transform
        log_ic = np.log(ic_abs + 1e-9)  # Add small value to avoid log(0)

        # Linear regression on log values
        try:
            from scipy.optimize import curve_fit

            def exp_decay(t, ic0, decay_rate):
                return ic0 * np.exp(-decay_rate * t)

            params, _ = curve_fit(
                exp_decay,
                periods,
                ic_abs,
                p0=[ic_abs[0], 0.01],
                maxfev=10000
            )

            decay_rate = params[1]
            half_life = np.log(2) / decay_rate if decay_rate > 0 else np.inf

            return half_life

        except Exception:
            # Fallback: simple linear regression on log values
            try:
                slope, _ = np.polyfit(periods, log_ic, 1)
                decay_rate = -slope
                half_life = np.log(2) / decay_rate if decay_rate > 0 else np.inf
                return half_life
            except Exception:
                return np.nan

    def _find_optimal_period(self, return_series: pd.Series) -> int:
        """Find optimal holding period (max risk-adjusted return)."""
        if len(return_series) == 0:
            return 1

        # Find period with maximum IC/Sharpe-like metric
        # Adjust returns by holding period to get per-period return
        adjusted_returns = return_series / np.sqrt(return_series.index.values)

        optimal_period = adjusted_returns.idxmax()

        return int(optimal_period)

    def _calculate_decay_rate(self, ic_series: pd.Series) -> float:
        """Calculate decay rate per day."""
        if len(ic_series) < 2:
            return 0.0

        # Simple: (IC_end - IC_start) / periods
        ic_start = ic_series.iloc[0]
        ic_end = ic_series.iloc[-1]
        periods = ic_series.index[-1] - ic_series.index[0]

        if periods > 0:
            decay_rate = (ic_end - ic_start) / periods
        else:
            decay_rate = 0.0

        return decay_rate

    def _empty_result(
        self,
        factor_name: str,
        periods: List[int]
    ) -> DecayAnalysis:
        """Return empty decay result."""
        return DecayAnalysis(
            factor_name=factor_name,
            ic_by_period=pd.Series(),
            returns_by_period=pd.Series(),
            cumulative_returns=pd.Series(),
            half_life=np.nan,
            optimal_holding_period=21,
            decay_rate=0.0,
            periods_tested=periods,
        )

    def autocorrelation_analysis(
        self,
        factor_values: pd.Series,
        max_lag: int = 21
    ) -> pd.Series:
        """
        Analyze autocorrelation of factor values.

        High autocorrelation suggests slow-moving factors.

        Args:
            factor_values: Factor values
            max_lag: Maximum lag to test

        Returns:
            Series of autocorrelations by lag
        """
        logger.info(f"Calculating autocorrelation up to {max_lag} lags")

        # Get factor values for a single stock over time
        # (as a proxy for factor autocorrelation)
        symbols = factor_values.index.get_level_values(1).unique()

        if len(symbols) == 0:
            return pd.Series()

        # Use first stock with sufficient data
        autocorrs = []

        for lag in range(1, max_lag + 1):
            lagged_corrs = []

            for symbol in symbols[:10]:  # Sample first 10 stocks
                try:
                    series = factor_values.xs(symbol, level=1)
                    if len(series) < lag + 20:
                        continue

                    # Calculate autocorrelation
                    series_lagged = series.shift(lag)
                    corr = series.corr(series_lagged)

                    if not np.isnan(corr):
                        lagged_corrs.append(corr)
                except Exception:
                    continue

            if len(lagged_corrs) > 0:
                autocorrs.append((lag, np.mean(lagged_corrs)))

        return pd.Series([ac for _, ac in autocorrs],
                        index=[lag for lag, _ in autocorrs])

    def turnover_analysis(
        self,
        factor_values: pd.Series,
        quantile: int = 5,  # Top quintile
        periods: List[int] = None
    ) -> pd.DataFrame:
        """
        Analyze portfolio turnover at different rebalancing frequencies.

        Args:
            factor_values: Factor values
            quantile: Which quantile to form portfolio from
            periods: List of rebalancing periods to test

        Returns:
            DataFrame with turnover metrics
        """
        if periods is None:
            periods = [1, 5, 10, 21, 63]

        logger.info(f"Analyzing turnover for periods: {periods}")

        dates = sorted(factor_values.index.get_level_values(0).unique())

        turnover_results = []

        for period in periods:
            turnovers = []
            previous_holdings = None

            for i in range(0, len(dates) - period, period):
                date = dates[i]

                if date not in factor_values.index.get_level_values(0):
                    continue

                # Form portfolio (top quintile)
                factor_at_date = factor_values.loc[date].sort_values(ascending=False)
                portfolio_size = len(factor_at_date) // quantile
                current_holdings = set(factor_at_date.head(portfolio_size).index)

                if previous_holdings is not None:
                    # Calculate turnover
                    additions = len(current_holdings - previous_holdings)
                    deletions = len(previous_holdings - current_holdings)
                    turnover = (additions + deletions) / (2 * len(previous_holdings))
                    turnovers.append(turnover)

                previous_holdings = current_holdings

            if len(turnovers) > 0:
                turnover_results.append({
                    'period': period,
                    'mean_turnover': np.mean(turnovers),
                    'std_turnover': np.std(turnovers),
                    'max_turnover': np.max(turnovers),
                })

        return pd.DataFrame(turnover_results)

"""
Cross-sectional regression analysis.

Tests factor significance using Fama-MacBeth regressions.
"""

from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger
import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class RegressionResult:
    """
    Cross-sectional regression result.

    Attributes:
        factor_coefficients: Mean coefficients for each factor
        t_statistics: T-statistics for coefficients
        p_values: P-values for coefficients
        r_squared: Mean R-squared across periods
        adjusted_r_squared: Mean adjusted R-squared
        num_periods: Number of regression periods
        coefficients_series: Time series of coefficients
        std_errors: Standard errors of coefficients
        newey_west_t_stats: Newey-West corrected t-stats
    """
    factor_coefficients: dict[str, float]
    t_statistics: dict[str, float]
    p_values: dict[str, float]
    r_squared: float
    adjusted_r_squared: float
    num_periods: int
    coefficients_series: pd.DataFrame
    std_errors: dict[str, float]
    newey_west_t_stats: dict[str, float] | None = None
    metadata: dict = field(default_factory=dict)

    def summary(self) -> str:
        """Generate summary report."""
        results_str = "\n".join([
            f"  {name:30s}: Coef={self.factor_coefficients[name]:8.4f}, "
            f"t-stat={self.t_statistics[name]:6.2f}, "
            f"p-val={self.p_values[name]:6.4f}"
            for name in self.factor_coefficients.keys()
        ])

        return f"""
Cross-Sectional Regression Results
{'=' * 80}
Number of Periods: {self.num_periods}
Mean R-Squared: {self.r_squared:.4f}
Adjusted R-Squared: {self.adjusted_r_squared:.4f}

Factor Coefficients:
{results_str}
"""


class CrossSectionalRegression:
    """
    Performs Fama-MacBeth style cross-sectional regressions.

    Tests which factors predict future returns by:
    1. Running cross-sectional regression each period
    2. Averaging coefficients across periods
    3. Testing significance with time-series of coefficients
    """

    def __init__(
        self,
        forward_period: int = 21,  # Forward return period
        min_stocks: int = 30,  # Minimum stocks per regression
        winsorize: float = 0.01,  # Winsorize extreme values
        standardize: bool = True,  # Standardize factors
        newey_west_lags: int = 3,  # Lags for Newey-West correction
    ) -> None:
        """
        Initialize cross-sectional regression.

        Args:
            forward_period: Forward return period for dependent variable
            min_stocks: Minimum stocks required per period
            winsorize: Winsorization threshold (e.g., 0.01 = 1% and 99%)
            standardize: Whether to standardize factors
            newey_west_lags: Number of lags for Newey-West HAC correction
        """
        self.forward_period = forward_period
        self.min_stocks = min_stocks
        self.winsorize = winsorize
        self.standardize = standardize
        self.newey_west_lags = newey_west_lags

        logger.info(
            f"Initialized CrossSectionalRegression with {forward_period}D forward returns"
        )

    def run_fama_macbeth(
        self,
        factor_values: dict[str, pd.Series],  # factor_name -> (date, symbol) values
        price_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
        control_factors: list[str] | None = None
    ) -> RegressionResult:
        """
        Run Fama-MacBeth cross-sectional regression.

        Args:
            factor_values: Dict of factor values
            price_data: Price data for calculating returns
            start_date: Regression start date
            end_date: Regression end date
            control_factors: Optional list of control factors (always included)

        Returns:
            RegressionResult with coefficients and statistics
        """
        logger.info(
            f"Running Fama-MacBeth regression from {start_date.date()} to {end_date.date()}"
        )

        # Get common dates across all factors
        common_dates = self._get_common_dates(factor_values, start_date, end_date)

        if len(common_dates) < 10:
            logger.warning(f"Insufficient dates ({len(common_dates)}) for regression")
            return self._empty_result()

        # Run cross-sectional regression for each date
        period_results = []

        for date in common_dates:
            # Get forward returns
            forward_returns = self._calculate_forward_returns(
                price_data, date, self.forward_period
            )

            if len(forward_returns) < self.min_stocks:
                continue

            # Align factor values
            period_data = self._align_factor_data(
                factor_values, date, forward_returns.index.tolist()
            )

            if len(period_data) < self.min_stocks:
                continue

            # Add forward returns as dependent variable
            period_data["forward_return"] = forward_returns

            # Drop any rows with NaN
            period_data = period_data.dropna()

            if len(period_data) < self.min_stocks:
                continue

            # Preprocess factors
            X, y = self._preprocess_data(period_data)

            # Run regression
            coeffs, r2, adj_r2 = self._run_ols(X, y)

            if coeffs is not None:
                result = {
                    "date": date,
                    "r_squared": r2,
                    "adj_r_squared": adj_r2,
                    "n_stocks": len(y),
                    **coeffs
                }
                period_results.append(result)

        if len(period_results) < 10:
            logger.warning(f"Insufficient periods ({len(period_results)}) for Fama-MacBeth")
            return self._empty_result()

        # Convert to DataFrame
        coeffs_df = pd.DataFrame(period_results).set_index("date")

        # Calculate time-series statistics
        factor_names = [col for col in coeffs_df.columns
                       if col not in ["r_squared", "adj_r_squared", "n_stocks"]]

        mean_coeffs = {}
        t_stats = {}
        p_values = {}
        std_errors = {}

        for factor in factor_names:
            coeff_series = coeffs_df[factor]

            # Mean coefficient
            mean_coeff = coeff_series.mean()
            mean_coeffs[factor] = mean_coeff

            # Standard error
            std_error = coeff_series.std() / np.sqrt(len(coeff_series))
            std_errors[factor] = std_error

            # T-statistic
            t_stat = mean_coeff / std_error if std_error > 0 else 0
            t_stats[factor] = t_stat

            # P-value (two-tailed)
            p_val = 2 * (1 - stats.t.cdf(abs(t_stat), len(coeff_series) - 1))
            p_values[factor] = p_val

        # Newey-West correction
        nw_t_stats = None
        if self.newey_west_lags > 0:
            nw_t_stats = self._calculate_newey_west_t_stats(
                coeffs_df[factor_names]
            )

        result = RegressionResult(
            factor_coefficients=mean_coeffs,
            t_statistics=t_stats,
            p_values=p_values,
            r_squared=coeffs_df["r_squared"].mean(),
            adjusted_r_squared=coeffs_df["adj_r_squared"].mean(),
            num_periods=len(period_results),
            coefficients_series=coeffs_df[factor_names],
            std_errors=std_errors,
            newey_west_t_stats=nw_t_stats,
        )

        logger.info(
            f"Fama-MacBeth complete: {len(period_results)} periods, "
            f"R²={result.r_squared:.4f}"
        )

        return result

    def rolling_regression(
        self,
        factor_values: dict[str, pd.Series],
        price_data: pd.DataFrame,
        window: int = 252,
        step: int = 21
    ) -> pd.DataFrame:
        """
        Run rolling Fama-MacBeth regressions.

        Args:
            factor_values: Factor values
            price_data: Price data
            window: Rolling window size
            step: Step size between windows

        Returns:
            DataFrame with rolling coefficients
        """
        logger.info(f"Running rolling regressions with {window}D window")

        dates = sorted(factor_values[list(factor_values.keys())[0]].index.get_level_values(0).unique())

        rolling_results = []

        for i in range(window, len(dates), step):
            end_date = dates[i]
            start_date = dates[i - window]

            result = self.run_fama_macbeth(
                factor_values, price_data, start_date, end_date
            )

            if result.num_periods > 0:
                result_row = {
                    "date": end_date,
                    "r_squared": result.r_squared,
                    "n_periods": result.num_periods,
                    **result.factor_coefficients
                }
                rolling_results.append(result_row)

        return pd.DataFrame(rolling_results).set_index("date")

    def factor_significance_test(
        self,
        factor_values: dict[str, pd.Series],
        price_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
        significance_level: float = 0.05
    ) -> pd.DataFrame:
        """
        Test significance of factors.

        Args:
            factor_values: Factor values
            price_data: Price data
            start_date: Start date
            end_date: End date
            significance_level: Significance level for testing

        Returns:
            DataFrame with significance test results
        """
        result = self.run_fama_macbeth(
            factor_values, price_data, start_date, end_date
        )

        significance_results = []

        for factor in result.factor_coefficients.keys():
            significance_results.append({
                "factor": factor,
                "coefficient": result.factor_coefficients[factor],
                "t_statistic": result.t_statistics[factor],
                "p_value": result.p_values[factor],
                "significant": result.p_values[factor] < significance_level,
                "std_error": result.std_errors[factor],
            })

        df = pd.DataFrame(significance_results)
        return df.sort_values("t_statistic", key=abs, ascending=False)

    def _get_common_dates(
        self,
        factor_values: dict[str, pd.Series],
        start_date: datetime,
        end_date: datetime
    ) -> list[datetime]:
        """Get dates common to all factors."""
        if len(factor_values) == 0:
            return []

        # Get dates from first factor
        all_date_sets = []

        for factor_vals in factor_values.values():
            dates = factor_vals.index.get_level_values(0).unique()
            dates = [d for d in dates if start_date <= d <= end_date]
            all_date_sets.append(set(dates))

        # Find intersection
        common_dates = set.intersection(*all_date_sets)

        return sorted(list(common_dates))

    def _calculate_forward_returns(
        self,
        price_data: pd.DataFrame,
        start_date: datetime,
        forward_period: int
    ) -> pd.Series:
        """Calculate forward returns for all stocks."""
        all_dates = sorted(price_data.index.get_level_values(0).unique())

        try:
            start_idx = all_dates.index(start_date)
            end_idx = min(start_idx + forward_period, len(all_dates) - 1)
            end_date = all_dates[end_idx]
        except (ValueError, IndexError):
            return pd.Series()

        # Get prices at both dates
        start_prices = price_data.loc[start_date, "close"]
        end_prices = price_data.loc[end_date, "close"]

        # Calculate returns
        forward_returns = (end_prices - start_prices) / start_prices

        return forward_returns.dropna()

    def _align_factor_data(
        self,
        factor_values: dict[str, pd.Series],
        date: datetime,
        symbols: list[str]
    ) -> pd.DataFrame:
        """Align factor values for given date and symbols."""
        data = pd.DataFrame(index=symbols)

        for factor_name, factor_vals in factor_values.items():
            if date in factor_vals.index.get_level_values(0):
                factor_at_date = factor_vals.loc[date]
                # Align with symbols
                data[factor_name] = factor_at_date.reindex(symbols)

        return data

    def _preprocess_data(
        self,
        data: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.Series]:
        """Preprocess data for regression."""
        # Separate X and y
        y = data["forward_return"]
        X = data.drop("forward_return", axis=1)

        # Winsorize
        if self.winsorize > 0:
            X = self._winsorize_dataframe(X, self.winsorize)

        # Standardize
        if self.standardize:
            X = (X - X.mean()) / X.std()

        return X, y

    def _winsorize_dataframe(
        self,
        df: pd.DataFrame,
        threshold: float
    ) -> pd.DataFrame:
        """Winsorize DataFrame columns."""
        df_winsorized = df.copy()

        for col in df.columns:
            lower = df[col].quantile(threshold)
            upper = df[col].quantile(1 - threshold)
            df_winsorized[col] = df[col].clip(lower, upper)

        return df_winsorized

    def _run_ols(
        self,
        X: pd.DataFrame,
        y: pd.Series
    ) -> tuple[dict | None, float, float]:
        """Run OLS regression."""
        try:
            from sklearn.linear_model import LinearRegression

            model = LinearRegression(fit_intercept=True)
            model.fit(X, y)

            # Coefficients
            coeffs = dict(zip(X.columns, model.coef_))

            # R-squared
            r2 = model.score(X, y)

            # Adjusted R-squared
            n = len(y)
            p = X.shape[1]
            adj_r2 = 1 - (1 - r2) * (n - 1) / (n - p - 1)

            return coeffs, r2, adj_r2

        except Exception as e:
            logger.warning(f"OLS regression failed: {e}")
            return None, 0.0, 0.0

    def _calculate_newey_west_t_stats(
        self,
        coeffs_df: pd.DataFrame
    ) -> dict[str, float]:
        """Calculate Newey-West corrected t-statistics."""
        nw_t_stats = {}

        for factor in coeffs_df.columns:
            coeff_series = coeffs_df[factor].values
            mean_coeff = np.mean(coeff_series)

            # Calculate Newey-West standard error
            nw_se = self._newey_west_se(coeff_series, self.newey_west_lags)

            # T-statistic
            t_stat = mean_coeff / nw_se if nw_se > 0 else 0
            nw_t_stats[factor] = t_stat

        return nw_t_stats

    def _newey_west_se(
        self,
        series: np.ndarray,
        lags: int
    ) -> float:
        """Calculate Newey-West standard error."""
        n = len(series)
        mean = np.mean(series)

        # Variance
        var = np.sum((series - mean) ** 2) / n

        # Autocovariances
        for lag in range(1, lags + 1):
            weight = 1 - lag / (lags + 1)  # Bartlett kernel

            cov = 0
            for t in range(lag, n):
                cov += (series[t] - mean) * (series[t - lag] - mean)

            cov = cov / n
            var += 2 * weight * cov

        se = np.sqrt(var / n)
        return se

    def _empty_result(self) -> RegressionResult:
        """Return empty regression result."""
        return RegressionResult(
            factor_coefficients={},
            t_statistics={},
            p_values={},
            r_squared=0.0,
            adjusted_r_squared=0.0,
            num_periods=0,
            coefficients_series=pd.DataFrame(),
            std_errors={},
        )

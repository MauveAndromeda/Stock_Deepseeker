"""
Performance attribution framework.

Decomposes portfolio returns into factor contributions.
"""

from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger
import numpy as np
import pandas as pd

from src.factors import Factor


@dataclass
class AttributionResult:
    """
    Performance attribution result.

    Attributes:
        total_return: Total portfolio return
        factor_contributions: Dict of factor contributions
        residual_return: Unexplained return (alpha)
        factor_exposures: Average factor exposures
        factor_returns: Factor returns over period
        r_squared: Proportion of variance explained
        active_risk: Tracking error
        information_ratio: IR of residual returns
        start_date: Attribution start date
        end_date: Attribution end date
    """
    total_return: float
    factor_contributions: dict[str, float]
    residual_return: float
    factor_exposures: dict[str, float]
    factor_returns: dict[str, float]
    r_squared: float
    active_risk: float
    information_ratio: float
    start_date: datetime
    end_date: datetime
    metadata: dict = field(default_factory=dict)

    def summary(self) -> str:
        """Generate summary report."""
        factor_contrib_str = "\n".join(
            [f"  {name}: {contrib:.2%}" for name, contrib in self.factor_contributions.items()]
        )

        return f"""
Performance Attribution Report
{'=' * 60}
Period: {self.start_date.date()} to {self.end_date.date()}

Total Return: {self.total_return:.2%}
Residual (Alpha): {self.residual_return:.2%}
R-Squared: {self.r_squared:.3f}

Factor Contributions:
{factor_contrib_str}

Risk Metrics:
- Active Risk: {self.active_risk:.2%}
- Information Ratio: {self.information_ratio:.3f}
"""


class PerformanceAttributor:
    """
    Attributes portfolio performance to factor exposures.

    Uses regression-based attribution to decompose returns into:
    1. Factor contributions (beta * factor return)
    2. Residual return (alpha)
    """

    def __init__(
        self,
        factors: list[Factor],
        attribution_frequency: str = "monthly",  # 'daily', 'weekly', 'monthly'
        min_periods: int = 20,  # Minimum periods for regression
    ) -> None:
        """
        Initialize performance attributor.

        Args:
            factors: List of factors to use in attribution
            attribution_frequency: How often to run attribution
            min_periods: Minimum periods for regression
        """
        self.factors = factors
        self.attribution_frequency = attribution_frequency
        self.min_periods = min_periods

        logger.info(
            f"Initialized PerformanceAttributor with {len(factors)} factors"
        )

    def attribute(
        self,
        portfolio_returns: pd.Series,
        holdings: pd.DataFrame,  # date x symbol
        factor_values: dict[str, pd.Series],  # factor_name -> (date, symbol) values
        start_date: datetime,
        end_date: datetime
    ) -> AttributionResult:
        """
        Attribute portfolio returns to factors.

        Args:
            portfolio_returns: Time series of portfolio returns
            holdings: Portfolio holdings (weights) over time
            factor_values: Dict of factor values
            start_date: Attribution start
            end_date: Attribution end

        Returns:
            AttributionResult with factor contributions
        """
        logger.info(f"Attributing performance from {start_date.date()} to {end_date.date()}")

        # Filter to date range
        mask = (portfolio_returns.index >= start_date) & (portfolio_returns.index <= end_date)
        returns = portfolio_returns[mask]

        # Calculate portfolio factor exposures
        exposures = self._calculate_portfolio_exposures(
            holdings, factor_values, start_date, end_date
        )

        # Calculate factor returns
        factor_rets = self._calculate_factor_returns(
            factor_values, start_date, end_date
        )

        # Run attribution regression
        attribution = self._run_attribution_regression(
            returns, exposures, factor_rets
        )

        # Calculate metrics
        total_return = returns.sum()
        factor_contributions = attribution["factor_contributions"]
        residual_return = attribution["alpha"]
        r_squared = attribution["r_squared"]

        # Calculate risk metrics
        residual_returns = attribution["residual_returns"]
        active_risk = residual_returns.std() * np.sqrt(252)
        information_ratio = (
            residual_return / active_risk if active_risk > 0 else 0
        )

        result = AttributionResult(
            total_return=total_return,
            factor_contributions=factor_contributions,
            residual_return=residual_return,
            factor_exposures=attribution["factor_exposures"],
            factor_returns=factor_rets,
            r_squared=r_squared,
            active_risk=active_risk,
            information_ratio=information_ratio,
            start_date=start_date,
            end_date=end_date,
        )

        logger.info(f"Attribution complete: Alpha={residual_return:.2%}, R²={r_squared:.3f}")

        return result

    def _calculate_portfolio_exposures(
        self,
        holdings: pd.DataFrame,
        factor_values: dict[str, pd.Series],
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Calculate portfolio factor exposures over time.

        Args:
            holdings: Portfolio weights
            factor_values: Factor values
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with factor exposures (date x factor)
        """
        # Filter holdings to date range
        mask = (holdings.index >= start_date) & (holdings.index <= end_date)
        holdings_period = holdings[mask]

        exposures_list = []

        for date in holdings_period.index:
            date_holdings = holdings_period.loc[date]
            date_holdings = date_holdings[date_holdings > 0]  # Non-zero holdings

            if len(date_holdings) == 0:
                continue

            # Calculate exposure to each factor
            date_exposures = {}

            for factor_name, factor_vals in factor_values.items():
                if date not in factor_vals.index.get_level_values(0):
                    date_exposures[factor_name] = np.nan
                    continue

                factor_at_date = factor_vals.loc[date]

                # Weight-average factor values
                exposure = 0.0
                total_weight = 0.0

                for symbol, weight in date_holdings.items():
                    if symbol in factor_at_date.index:
                        exposure += weight * factor_at_date[symbol]
                        total_weight += weight

                if total_weight > 0:
                    date_exposures[factor_name] = exposure / total_weight
                else:
                    date_exposures[factor_name] = np.nan

            exposures_list.append({
                "date": date,
                **date_exposures
            })

        return pd.DataFrame(exposures_list).set_index("date")

    def _calculate_factor_returns(
        self,
        factor_values: dict[str, pd.Series],
        start_date: datetime,
        end_date: datetime
    ) -> dict[str, float]:
        """
        Calculate factor returns (long top quintile, short bottom).

        Args:
            factor_values: Factor values
            start_date: Start date
            end_date: End date

        Returns:
            Dict of factor returns
        """
        factor_returns = {}

        for factor_name, factor_vals in factor_values.items():
            # This is a simplified version
            # In practice, you'd want to use the factor backtester
            # For now, just calculate correlation with equal-weighted returns
            dates = sorted(factor_vals.index.get_level_values(0).unique())
            dates = [d for d in dates if start_date <= d <= end_date]

            if len(dates) == 0:
                factor_returns[factor_name] = 0.0
                continue

            # Average factor value change as proxy for factor return
            first_date = dates[0]
            last_date = dates[-1]

            first_vals = factor_vals.loc[first_date].mean()
            last_vals = factor_vals.loc[last_date].mean()

            if abs(first_vals) > 1e-9:
                factor_ret = (last_vals - first_vals) / abs(first_vals)
            else:
                factor_ret = 0.0

            factor_returns[factor_name] = factor_ret

        return factor_returns

    def _run_attribution_regression(
        self,
        returns: pd.Series,
        exposures: pd.DataFrame,
        factor_returns: dict[str, float]
    ) -> dict:
        """
        Run attribution regression.

        Return = α + β₁·F₁ + β₂·F₂ + ... + ε

        Args:
            returns: Portfolio returns
            exposures: Factor exposures
            factor_returns: Factor returns

        Returns:
            Dict with attribution results
        """
        # Align data
        common_dates = returns.index.intersection(exposures.index)

        if len(common_dates) < self.min_periods:
            logger.warning(
                f"Insufficient periods ({len(common_dates)}) for attribution"
            )
            return self._empty_attribution()

        returns_aligned = returns.loc[common_dates]
        exposures_aligned = exposures.loc[common_dates]

        # Drop any NaN columns
        exposures_aligned = exposures_aligned.dropna(axis=1, how="all")

        if exposures_aligned.shape[1] == 0:
            return self._empty_attribution()

        # Run regression: R = α + Σ(β_i * exposure_i) + ε
        from sklearn.linear_model import LinearRegression

        X = exposures_aligned.values
        y = returns_aligned.values

        model = LinearRegression(fit_intercept=True)
        model.fit(X, y)

        # Extract results
        alpha = model.intercept_
        betas = dict(zip(exposures_aligned.columns, model.coef_))

        # Calculate factor contributions
        avg_exposures = exposures_aligned.mean()
        factor_contributions = {}

        for factor_name in exposures_aligned.columns:
            beta = betas[factor_name]
            exposure = avg_exposures[factor_name]
            factor_ret = factor_returns.get(factor_name, 0.0)

            # Contribution = beta * exposure * factor_return
            contribution = beta * exposure * factor_ret
            factor_contributions[factor_name] = contribution

        # Calculate residuals
        y_pred = model.predict(X)
        residuals = y - y_pred
        residual_returns = pd.Series(residuals, index=common_dates)

        # R-squared
        r_squared = model.score(X, y)

        return {
            "alpha": alpha,
            "factor_contributions": factor_contributions,
            "factor_exposures": avg_exposures.to_dict(),
            "residual_returns": residual_returns,
            "r_squared": r_squared,
        }

    def _empty_attribution(self) -> dict:
        """Return empty attribution result."""
        return {
            "alpha": 0.0,
            "factor_contributions": {},
            "factor_exposures": {},
            "residual_returns": pd.Series(),
            "r_squared": 0.0,
        }

    def rolling_attribution(
        self,
        portfolio_returns: pd.Series,
        holdings: pd.DataFrame,
        factor_values: dict[str, pd.Series],
        window: int = 252
    ) -> pd.DataFrame:
        """
        Calculate rolling attribution over time.

        Args:
            portfolio_returns: Portfolio returns
            holdings: Holdings over time
            factor_values: Factor values
            window: Rolling window size

        Returns:
            DataFrame with rolling attribution results
        """
        logger.info(f"Calculating {window}D rolling attribution")

        dates = sorted(portfolio_returns.index)
        results = []

        for i in range(window, len(dates)):
            end_date = dates[i]
            start_date = dates[i - window]

            attribution = self.attribute(
                portfolio_returns,
                holdings,
                factor_values,
                start_date,
                end_date
            )

            result_row = {
                "date": end_date,
                "total_return": attribution.total_return,
                "alpha": attribution.residual_return,
                "r_squared": attribution.r_squared,
                "information_ratio": attribution.information_ratio,
                **attribution.factor_contributions
            }

            results.append(result_row)

        return pd.DataFrame(results).set_index("date")

    def factor_timing_analysis(
        self,
        portfolio_returns: pd.Series,
        holdings: pd.DataFrame,
        factor_values: dict[str, pd.Series],
        periods: list[int] = None
    ) -> pd.DataFrame:
        """
        Analyze factor timing ability across periods.

        Args:
            portfolio_returns: Portfolio returns
            holdings: Holdings
            factor_values: Factor values
            periods: List of periods to analyze

        Returns:
            DataFrame with timing metrics
        """
        if periods is None:
            periods = [63, 126, 252]  # 3M, 6M, 1Y

        timing_results = []

        for period in periods:
            dates = sorted(portfolio_returns.index)

            period_alphas = []
            period_irs = []

            for i in range(period, len(dates), period // 2):  # 50% overlap
                end_date = dates[i]
                start_date = dates[max(0, i - period)]

                attribution = self.attribute(
                    portfolio_returns,
                    holdings,
                    factor_values,
                    start_date,
                    end_date
                )

                period_alphas.append(attribution.residual_return)
                period_irs.append(attribution.information_ratio)

            timing_results.append({
                "period": period,
                "mean_alpha": np.mean(period_alphas),
                "alpha_volatility": np.std(period_alphas),
                "mean_ir": np.mean(period_irs),
                "positive_alpha_ratio": (np.array(period_alphas) > 0).mean(),
            })

        return pd.DataFrame(timing_results)

    def marginal_contribution_analysis(
        self,
        portfolio_returns: pd.Series,
        holdings: pd.DataFrame,
        factor_values: dict[str, pd.Series],
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Calculate marginal contribution of each factor.

        Remove each factor one at a time and measure impact.

        Args:
            portfolio_returns: Portfolio returns
            holdings: Holdings
            factor_values: Factor values
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with marginal contributions
        """
        logger.info("Calculating marginal factor contributions")

        # Baseline attribution with all factors
        baseline = self.attribute(
            portfolio_returns, holdings, factor_values,
            start_date, end_date
        )

        marginal_results = []

        for factor_to_remove in factor_values:
            # Create reduced factor set
            reduced_factors = {
                k: v for k, v in factor_values.items()
                if k != factor_to_remove
            }

            # Re-run attribution
            reduced_attribution = self.attribute(
                portfolio_returns, holdings, reduced_factors,
                start_date, end_date
            )

            # Marginal contribution = change in R²
            marginal_r2 = baseline.r_squared - reduced_attribution.r_squared
            marginal_alpha = baseline.residual_return - reduced_attribution.residual_return

            marginal_results.append({
                "factor": factor_to_remove,
                "marginal_r_squared": marginal_r2,
                "marginal_alpha": marginal_alpha,
                "baseline_contribution": baseline.factor_contributions.get(factor_to_remove, 0),
            })

        return pd.DataFrame(marginal_results)

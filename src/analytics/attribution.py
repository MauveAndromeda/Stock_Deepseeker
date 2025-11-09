"""
Performance attribution analysis.
"""

from collections import defaultdict
from dataclasses import dataclass

import pandas as pd


@dataclass
class AttributionResult:
    """Container for attribution analysis results."""
    total_return: float
    factor_returns: dict[str, float]
    factor_contributions: dict[str, float]
    residual_return: float
    explained_variance: float

    def to_dict(self) -> dict:
        """Convert to dictionary for reporting."""
        return {
            "Total Return": f"{self.total_return:.2%}",
            "Factor Contributions": {
                k: f"{v:.2%}" for k, v in self.factor_contributions.items()
            },
            "Residual Return": f"{self.residual_return:.2%}",
            "Explained Variance": f"{self.explained_variance:.2%}"
        }


class AttributionAnalyzer:
    """
    Perform return attribution analysis.

    Decomposes portfolio returns into:
    - Factor contributions (momentum, value, quality, etc.)
    - Sector contributions
    - Security selection
    - Allocation effects
    - Residual/alpha
    """

    def __init__(self):
        """Initialize attribution analyzer."""

    def factor_attribution(
        self,
        returns: pd.Series,
        factor_exposures: pd.DataFrame,
        factor_returns: pd.DataFrame
    ) -> AttributionResult:
        """
        Perform factor-based attribution.

        Args:
            returns: Portfolio returns
            factor_exposures: Factor exposures (columns = factors)
            factor_returns: Factor returns (columns = factors)

        Returns:
            Attribution results
        """
        # Align data
        aligned_data = pd.concat(
            [returns, factor_exposures, factor_returns],
            axis=1,
            join="inner"
        )

        if len(aligned_data) == 0:
            return self._empty_attribution()

        # Calculate factor contributions
        factor_names = factor_exposures.columns

        factor_contributions = {}
        for factor in factor_names:
            # Contribution = exposure * factor_return
            contribution = (
                aligned_data[f"{factor}_exposure"] *
                aligned_data[f"{factor}_return"]
            ).mean()
            factor_contributions[factor] = contribution

        # Calculate residual (unexplained return)
        total_return = returns.mean()
        explained_return = sum(factor_contributions.values())
        residual_return = total_return - explained_return

        # R-squared (explained variance)
        explained_variance = self._calculate_r_squared(
            returns,
            factor_exposures,
            factor_returns
        )

        # Factor returns (average)
        factor_rets = {
            factor: factor_returns[factor].mean()
            for factor in factor_names
        }

        return AttributionResult(
            total_return=total_return,
            factor_returns=factor_rets,
            factor_contributions=factor_contributions,
            residual_return=residual_return,
            explained_variance=explained_variance
        )

    def sector_attribution(
        self,
        portfolio_returns: pd.Series,
        portfolio_weights: pd.DataFrame,  # columns = sectors
        sector_returns: pd.DataFrame      # columns = sectors
    ) -> dict[str, dict[str, float]]:
        """
        Perform sector attribution (allocation and selection effects).

        Uses Brinson attribution:
        - Allocation effect: Over/under-weighting sectors
        - Selection effect: Security selection within sectors
        - Interaction effect: Combined effect

        Args:
            portfolio_returns: Portfolio returns
            portfolio_weights: Portfolio sector weights
            sector_returns: Sector benchmark returns

        Returns:
            Dictionary with allocation, selection, and interaction effects
        """
        sectors = portfolio_weights.columns

        allocation_effects = {}
        selection_effects = {}
        interaction_effects = {}

        for sector in sectors:
            # Allocation effect: (portfolio_weight - benchmark_weight) * benchmark_return
            # Simplified: assume equal benchmark weights
            benchmark_weight = 1.0 / len(sectors)
            portfolio_weight = portfolio_weights[sector].mean()

            weight_diff = portfolio_weight - benchmark_weight
            sector_return = sector_returns[sector].mean()

            allocation_effects[sector] = weight_diff * sector_return

            # Selection effect would require individual security data
            # Placeholder for now
            selection_effects[sector] = 0.0
            interaction_effects[sector] = 0.0

        return {
            "allocation": allocation_effects,
            "selection": selection_effects,
            "interaction": interaction_effects,
            "total_allocation": sum(allocation_effects.values()),
            "total_selection": sum(selection_effects.values()),
            "total_interaction": sum(interaction_effects.values())
        }

    def security_attribution(
        self,
        portfolio_returns: pd.DataFrame,  # columns = securities
        portfolio_weights: pd.DataFrame,  # columns = securities
        benchmark_returns: pd.DataFrame | None = None
    ) -> dict[str, float]:
        """
        Calculate contribution of each security to portfolio return.

        Args:
            portfolio_returns: Returns for each security
            portfolio_weights: Weights for each security
            benchmark_returns: Benchmark returns (optional)

        Returns:
            Dictionary mapping security to contribution
        """
        securities = portfolio_returns.columns

        contributions = {}

        for security in securities:
            # Contribution = weight * return
            contribution = (
                portfolio_weights[security] *
                portfolio_returns[security]
            ).mean()

            contributions[security] = contribution

        return contributions

    def rolling_attribution(
        self,
        returns: pd.Series,
        factor_exposures: pd.DataFrame,
        factor_returns: pd.DataFrame,
        window: int = 60
    ) -> pd.DataFrame:
        """
        Calculate rolling factor attribution.

        Args:
            returns: Portfolio returns
            factor_exposures: Factor exposures
            factor_returns: Factor returns
            window: Rolling window size

        Returns:
            DataFrame with rolling factor contributions
        """
        factor_names = factor_exposures.columns

        rolling_contributions = defaultdict(list)
        dates = []

        for i in range(window, len(returns)):
            window_returns = returns.iloc[i-window:i]
            window_exposures = factor_exposures.iloc[i-window:i]
            window_factor_returns = factor_returns.iloc[i-window:i]

            # Calculate contributions for this window
            for factor in factor_names:
                contribution = (
                    window_exposures[factor] *
                    window_factor_returns[factor]
                ).mean()

                rolling_contributions[factor].append(contribution)

            dates.append(returns.index[i])

        # Create DataFrame
        df = pd.DataFrame(rolling_contributions, index=dates)

        # Add total and residual
        df["total_return"] = returns.iloc[window:]
        df["explained"] = df[list(factor_names)].sum(axis=1)
        df["residual"] = df["total_return"] - df["explained"]

        return df

    def _calculate_r_squared(
        self,
        returns: pd.Series,
        factor_exposures: pd.DataFrame,
        factor_returns: pd.DataFrame
    ) -> float:
        """Calculate R-squared (explained variance)."""
        # Simple calculation: variance of explained returns / variance of total returns
        factor_names = factor_exposures.columns

        # Calculate explained returns
        explained_returns = pd.Series(0.0, index=returns.index)

        for factor in factor_names:
            explained_returns += (
                factor_exposures[factor] *
                factor_returns[factor]
            )

        # R-squared
        ss_res = ((returns - explained_returns) ** 2).sum()
        ss_tot = ((returns - returns.mean()) ** 2).sum()

        if ss_tot == 0:
            return 0.0

        r_squared = 1 - (ss_res / ss_tot)

        return max(0.0, min(1.0, r_squared))  # Clamp to [0, 1]

    def _empty_attribution(self) -> AttributionResult:
        """Return empty attribution result."""
        return AttributionResult(
            total_return=0.0,
            factor_returns={},
            factor_contributions={},
            residual_return=0.0,
            explained_variance=0.0
        )

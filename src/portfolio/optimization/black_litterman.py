"""
Black-Litterman Model

This module implements the Black-Litterman model for incorporating investor views
into portfolio optimization. The model combines market equilibrium (CAPM) with
subjective views to produce posterior expected returns.

Key Features:
- Market equilibrium return estimation
- View incorporation with confidence levels
- Posterior distribution calculation
- Integration with Markowitz optimization
"""

import logging
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd
from scipy.linalg import inv

logger = logging.getLogger(__name__)


class ViewConfidence(Enum):
    """Predefined confidence levels for views"""
    VERY_LOW = 0.1
    LOW = 0.25
    MEDIUM = 0.5
    HIGH = 0.75
    VERY_HIGH = 0.95


@dataclass
class MarketView:
    """
    Represents an investor's view on asset returns.

    Types of views:
    - Absolute: "Asset A will return X%"
    - Relative: "Asset A will outperform Asset B by X%"

    Attributes:
        assets: List of assets involved in the view
        view_return: Expected return according to the view
        confidence: Confidence level (0-1)
        pick_vector: Pick vector (P matrix row) for the view
        view_type: Type of view ('absolute' or 'relative')
    """
    assets: List[str]
    view_return: float
    confidence: float
    pick_vector: Optional[np.ndarray] = None
    view_type: str = 'absolute'

    def __post_init__(self):
        """Validate view parameters"""
        if not 0 <= self.confidence <= 1:
            raise ValueError("Confidence must be between 0 and 1")
        if self.view_type not in ['absolute', 'relative']:
            raise ValueError("view_type must be 'absolute' or 'relative'")


class BlackLittermanModel:
    """
    Black-Litterman Model for portfolio optimization with views.

    The Black-Litterman model provides a framework for incorporating investor
    views into the portfolio optimization process. It starts with a prior
    (market equilibrium returns) and updates it with investor views to produce
    posterior expected returns.

    Mathematical Framework:
    - Prior: π ~ N(Π, τΣ) where Π are market-implied returns
    - Views: Q = Pμ + ε, ε ~ N(0, Ω)
    - Posterior: E[R] = [(τΣ)^-1 + P'Ω^-1P]^-1 [(τΣ)^-1Π + P'Ω^-1Q]
    """

    def __init__(
        self,
        assets: List[str],
        prior_returns: Optional[Union[pd.Series, np.ndarray, Dict[str, float]]] = None,
        prior_covariance: Optional[Union[pd.DataFrame, np.ndarray]] = None,
        market_caps: Optional[Dict[str, float]] = None,
        risk_aversion: float = 2.5,
        risk_free_rate: float = 0.02,
        tau: float = 0.05,
    ):
        """
        Initialize Black-Litterman model.

        Args:
            assets: List of asset symbols
            prior_returns: Prior expected returns (if None, calculated from market equilibrium)
            prior_covariance: Prior covariance matrix
            market_caps: Market capitalizations for equilibrium calculation
            risk_aversion: Market risk aversion coefficient (typically 2-4)
            risk_free_rate: Risk-free rate
            tau: Uncertainty scaling parameter (typically 0.01-0.05)
        """
        self.assets = assets
        self.n_assets = len(assets)
        self.risk_aversion = risk_aversion
        self.risk_free_rate = risk_free_rate
        self.tau = tau

        # Market capitalizations
        self.market_caps = market_caps

        # Handle prior returns
        if prior_returns is not None:
            self.prior_returns = self._process_returns(prior_returns)
        elif market_caps is not None:
            # Calculate equilibrium returns if market caps provided
            self.prior_covariance = self._process_covariance(prior_covariance)
            self.prior_returns = self._calculate_equilibrium_returns()
        else:
            raise ValueError(
                "Must provide either prior_returns or market_caps for equilibrium calculation"
            )

        # Handle prior covariance
        if prior_covariance is not None:
            self.prior_covariance = self._process_covariance(prior_covariance)
        else:
            raise ValueError("Must provide prior_covariance matrix")

        # Views
        self.views: List[MarketView] = []
        self.P: Optional[np.ndarray] = None  # Pick matrix
        self.Q: Optional[np.ndarray] = None  # View returns
        self.Omega: Optional[np.ndarray] = None  # View uncertainty matrix

        # Posterior estimates
        self.posterior_returns: Optional[np.ndarray] = None
        self.posterior_covariance: Optional[np.ndarray] = None

        logger.info(
            f"Initialized Black-Litterman model with {self.n_assets} assets, "
            f"tau={tau:.4f}, risk_aversion={risk_aversion:.2f}"
        )

    def _process_returns(
        self,
        returns: Union[pd.Series, np.ndarray, Dict[str, float]]
    ) -> np.ndarray:
        """Process returns into numpy array"""
        if isinstance(returns, pd.Series):
            return returns.reindex(self.assets).values
        elif isinstance(returns, dict):
            return np.array([returns[asset] for asset in self.assets])
        else:
            return np.asarray(returns)

    def _process_covariance(
        self,
        covariance: Union[pd.DataFrame, np.ndarray]
    ) -> np.ndarray:
        """Process covariance into numpy array"""
        if isinstance(covariance, pd.DataFrame):
            return covariance.loc[self.assets, self.assets].values
        else:
            return np.asarray(covariance)

    def _calculate_equilibrium_returns(self) -> np.ndarray:
        """
        Calculate market equilibrium returns using reverse optimization.

        Market equilibrium returns (Π) are calculated as:
        Π = λ * Σ * w_mkt

        where:
        - λ is the risk aversion coefficient
        - Σ is the covariance matrix
        - w_mkt are market-cap weighted portfolio weights
        """
        if self.market_caps is None:
            raise ValueError("Market caps required for equilibrium calculation")

        # Calculate market weights
        total_market_cap = sum(self.market_caps.values())
        market_weights = np.array([
            self.market_caps.get(asset, 0) / total_market_cap
            for asset in self.assets
        ])

        # Calculate equilibrium returns: Π = λΣw
        equilibrium_returns = (
            self.risk_aversion * self.prior_covariance @ market_weights
        )

        logger.info(
            f"Calculated equilibrium returns. "
            f"Mean: {equilibrium_returns.mean():.4f}, "
            f"Std: {equilibrium_returns.std():.4f}"
        )

        return equilibrium_returns

    def add_view(
        self,
        assets: Union[str, List[str]],
        view_return: float,
        confidence: Union[float, ViewConfidence] = ViewConfidence.MEDIUM,
        view_type: str = 'absolute',
    ) -> None:
        """
        Add an investment view.

        Args:
            assets: Asset(s) involved in the view
            view_return: Expected return for the view
            confidence: Confidence level (0-1 or ViewConfidence enum)
            view_type: 'absolute' for single asset, 'relative' for relative views
        """
        # Handle single asset
        if isinstance(assets, str):
            assets = [assets]

        # Handle confidence enum
        if isinstance(confidence, ViewConfidence):
            confidence = confidence.value

        # Validate assets
        for asset in assets:
            if asset not in self.assets:
                raise ValueError(f"Asset {asset} not in portfolio")

        # Create pick vector
        pick_vector = self._create_pick_vector(assets, view_type)

        # Create view
        view = MarketView(
            assets=assets,
            view_return=view_return,
            confidence=confidence,
            pick_vector=pick_vector,
            view_type=view_type,
        )

        self.views.append(view)
        logger.info(
            f"Added {view_type} view: {assets} -> {view_return:.4f} "
            f"(confidence: {confidence:.2f})"
        )

        # Rebuild view matrices
        self._build_view_matrices()

    def add_relative_view(
        self,
        asset_long: str,
        asset_short: str,
        outperformance: float,
        confidence: Union[float, ViewConfidence] = ViewConfidence.MEDIUM,
    ) -> None:
        """
        Add a relative view: asset_long will outperform asset_short by outperformance.

        Args:
            asset_long: Asset expected to outperform
            asset_short: Asset expected to underperform
            outperformance: Expected outperformance
            confidence: Confidence level
        """
        if isinstance(confidence, ViewConfidence):
            confidence = confidence.value

        # Create pick vector for relative view
        pick_vector = np.zeros(self.n_assets)
        long_idx = self.assets.index(asset_long)
        short_idx = self.assets.index(asset_short)
        pick_vector[long_idx] = 1.0
        pick_vector[short_idx] = -1.0

        view = MarketView(
            assets=[asset_long, asset_short],
            view_return=outperformance,
            confidence=confidence,
            pick_vector=pick_vector,
            view_type='relative',
        )

        self.views.append(view)
        logger.info(
            f"Added relative view: {asset_long} vs {asset_short} -> "
            f"{outperformance:.4f} (confidence: {confidence:.2f})"
        )

        self._build_view_matrices()

    def _create_pick_vector(self, assets: List[str], view_type: str) -> np.ndarray:
        """
        Create pick vector for a view.

        For absolute views: P[i] = 1 if asset i is in the view, 0 otherwise
        For relative views: User should use add_relative_view instead
        """
        pick_vector = np.zeros(self.n_assets)

        if view_type == 'absolute':
            if len(assets) == 1:
                idx = self.assets.index(assets[0])
                pick_vector[idx] = 1.0
            else:
                # Equal weight combination
                for asset in assets:
                    idx = self.assets.index(asset)
                    pick_vector[idx] = 1.0 / len(assets)
        else:
            raise ValueError("Use add_relative_view for relative views")

        return pick_vector

    def _build_view_matrices(self) -> None:
        """Build P, Q, and Omega matrices from views"""
        if not self.views:
            self.P = None
            self.Q = None
            self.Omega = None
            return

        n_views = len(self.views)

        # Build P matrix (pick matrix)
        self.P = np.vstack([view.pick_vector for view in self.views])

        # Build Q vector (view returns)
        self.Q = np.array([view.view_return for view in self.views])

        # Build Omega matrix (view uncertainty)
        # Omega = diag(confidence^-1 * P * Σ * P')
        self.Omega = np.zeros((n_views, n_views))

        for i, view in enumerate(self.views):
            # View uncertainty inversely proportional to confidence
            view_variance = (
                view.pick_vector @
                self.prior_covariance @
                view.pick_vector
            )
            # Scale by confidence: higher confidence = lower uncertainty
            self.Omega[i, i] = view_variance / view.confidence

        logger.debug(
            f"Built view matrices: P={self.P.shape}, Q={self.Q.shape}, "
            f"Omega={self.Omega.shape}"
        )

    def calculate_posterior(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate posterior expected returns and covariance.

        The posterior distribution combines the prior (market equilibrium)
        with investor views using Bayesian updating.

        Returns:
            Tuple of (posterior_returns, posterior_covariance)
        """
        if not self.views:
            logger.warning("No views specified, returning prior estimates")
            return self.prior_returns, self.prior_covariance

        try:
            # Scale prior covariance by tau
            tau_sigma = self.tau * self.prior_covariance

            # Posterior precision: (τΣ)^-1 + P'Ω^-1P
            tau_sigma_inv = inv(tau_sigma)
            omega_inv = inv(self.Omega)

            posterior_precision = tau_sigma_inv + self.P.T @ omega_inv @ self.P

            # Posterior covariance
            self.posterior_covariance = inv(posterior_precision)

            # Posterior mean: M * [(τΣ)^-1 * Π + P'Ω^-1 * Q]
            posterior_mean_term = (
                tau_sigma_inv @ self.prior_returns +
                self.P.T @ omega_inv @ self.Q
            )
            self.posterior_returns = self.posterior_covariance @ posterior_mean_term

            logger.info(
                f"Calculated posterior with {len(self.views)} views. "
                f"Mean return: {self.posterior_returns.mean():.4f}"
            )

            return self.posterior_returns, self.posterior_covariance

        except np.linalg.LinAlgError as e:
            logger.error(f"Singular matrix in posterior calculation: {e}")
            raise

    def get_posterior(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get posterior estimates, calculating if necessary.

        Returns:
            Tuple of (posterior_returns, posterior_covariance)
        """
        if self.posterior_returns is None or self.posterior_covariance is None:
            return self.calculate_posterior()
        return self.posterior_returns, self.posterior_covariance

    def get_posterior_returns_series(self) -> pd.Series:
        """Get posterior returns as pandas Series"""
        posterior_returns, _ = self.get_posterior()
        return pd.Series(posterior_returns, index=self.assets)

    def get_posterior_covariance_df(self) -> pd.DataFrame:
        """Get posterior covariance as pandas DataFrame"""
        _, posterior_cov = self.get_posterior()
        return pd.DataFrame(
            posterior_cov,
            index=self.assets,
            columns=self.assets
        )

    def clear_views(self) -> None:
        """Clear all views and reset to prior"""
        self.views = []
        self.P = None
        self.Q = None
        self.Omega = None
        self.posterior_returns = None
        self.posterior_covariance = None
        logger.info("Cleared all views")

    def remove_view(self, index: int) -> None:
        """
        Remove a view by index.

        Args:
            index: Index of view to remove
        """
        if 0 <= index < len(self.views):
            removed_view = self.views.pop(index)
            logger.info(f"Removed view: {removed_view.assets}")
            self._build_view_matrices()
            self.posterior_returns = None
            self.posterior_covariance = None
        else:
            raise ValueError(f"Invalid view index: {index}")

    def get_view_summary(self) -> pd.DataFrame:
        """
        Get summary of all views.

        Returns:
            DataFrame with view information
        """
        if not self.views:
            return pd.DataFrame()

        data = []
        for i, view in enumerate(self.views):
            data.append({
                'index': i,
                'assets': ', '.join(view.assets),
                'type': view.view_type,
                'return': view.view_return,
                'confidence': view.confidence,
            })

        return pd.DataFrame(data)

    def compute_implied_returns(
        self,
        weights: Union[np.ndarray, Dict[str, float]]
    ) -> np.ndarray:
        """
        Compute implied returns for a given portfolio (reverse optimization).

        Args:
            weights: Portfolio weights

        Returns:
            Implied expected returns
        """
        if isinstance(weights, dict):
            w = np.array([weights.get(asset, 0) for asset in self.assets])
        else:
            w = np.asarray(weights)

        # Implied returns: Π = λΣw
        implied_returns = self.risk_aversion * self.prior_covariance @ w

        return implied_returns

    def sensitivity_analysis(
        self,
        confidence_range: Tuple[float, float] = (0.1, 1.0),
        n_steps: int = 10,
    ) -> pd.DataFrame:
        """
        Perform sensitivity analysis on view confidence levels.

        Args:
            confidence_range: Range of confidence values to test
            n_steps: Number of steps in the range

        Returns:
            DataFrame with sensitivity results
        """
        if not self.views:
            raise ValueError("No views to analyze")

        results = []
        original_confidences = [view.confidence for view in self.views]

        confidence_values = np.linspace(
            confidence_range[0],
            confidence_range[1],
            n_steps
        )

        for conf in confidence_values:
            # Set all views to this confidence
            for view in self.views:
                view.confidence = conf

            self._build_view_matrices()
            posterior_returns, posterior_cov = self.calculate_posterior()

            results.append({
                'confidence': conf,
                'mean_return': posterior_returns.mean(),
                'std_return': posterior_returns.std(),
                'portfolio_risk': np.sqrt(np.diag(posterior_cov).mean()),
            })

        # Restore original confidences
        for view, orig_conf in zip(self.views, original_confidences):
            view.confidence = orig_conf
        self._build_view_matrices()
        self.posterior_returns = None
        self.posterior_covariance = None

        return pd.DataFrame(results)

    def compare_prior_posterior(self) -> pd.DataFrame:
        """
        Compare prior and posterior expected returns.

        Returns:
            DataFrame comparing prior and posterior returns
        """
        posterior_returns, _ = self.get_posterior()

        comparison = pd.DataFrame({
            'asset': self.assets,
            'prior_return': self.prior_returns,
            'posterior_return': posterior_returns,
            'difference': posterior_returns - self.prior_returns,
            'pct_change': (
                (posterior_returns - self.prior_returns) /
                np.abs(self.prior_returns) * 100
            ),
        })

        return comparison.sort_values('difference', ascending=False)

    def idzorek_method(
        self,
        view_idx: int,
        confidence_level: float,
    ) -> Dict[str, float]:
        """
        Use Idzorek's method to determine view returns from confidence levels.

        Idzorek's method calibrates view returns based on how much the optimal
        portfolio should tilt toward the view given a confidence level.

        Args:
            view_idx: Index of the view
            confidence_level: Desired confidence level (0-1)

        Returns:
            Dictionary with calibrated view parameters
        """
        # This is a simplified implementation
        # Full Idzorek method requires iterative solving

        if view_idx >= len(self.views):
            raise ValueError(f"Invalid view index: {view_idx}")

        view = self.views[view_idx]

        # Estimate view return that would give desired confidence
        # This is an approximation - full implementation would solve iteratively
        view_uncertainty = np.sqrt(self.Omega[view_idx, view_idx])

        # Higher confidence -> view return further from prior
        prior_return = view.pick_vector @ self.prior_returns
        adjustment = view_uncertainty * (confidence_level - 0.5) * 2

        calibrated_return = prior_return + adjustment

        return {
            'view_index': view_idx,
            'assets': view.assets,
            'prior_return': float(prior_return),
            'calibrated_return': float(calibrated_return),
            'confidence': confidence_level,
            'uncertainty': float(view_uncertainty),
        }

    def __repr__(self) -> str:
        return (
            f"BlackLittermanModel(n_assets={self.n_assets}, "
            f"n_views={len(self.views)}, tau={self.tau:.4f})"
        )

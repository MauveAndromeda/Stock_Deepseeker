"""
Markowitz Mean-Variance Optimization

This module implements the classic Markowitz portfolio optimization framework:
- Mean-Variance Optimization
- Efficient Frontier calculation
- Capital Market Line
- Risk-Return tradeoff analysis
- Integration with Black-Litterman for posterior estimates
"""

import logging
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy.optimize import minimize, Bounds
import cvxpy as cp
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


@dataclass
class PortfolioPoint:
    """
    A point on the efficient frontier.

    Attributes:
        weights: Asset weights
        expected_return: Portfolio expected return
        volatility: Portfolio volatility
        sharpe_ratio: Sharpe ratio
    """
    weights: Dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float

    def __repr__(self) -> str:
        return (
            f"PortfolioPoint(return={self.expected_return:.4f}, "
            f"vol={self.volatility:.4f}, sharpe={self.sharpe_ratio:.4f})"
        )


class EfficientFrontier:
    """
    Represents the efficient frontier of optimal portfolios.

    The efficient frontier shows the set of optimal portfolios that offer
    the highest expected return for a given level of risk.
    """

    def __init__(self):
        """Initialize efficient frontier"""
        self.points: List[PortfolioPoint] = []
        self.min_variance_point: Optional[PortfolioPoint] = None
        self.max_sharpe_point: Optional[PortfolioPoint] = None

    def add_point(self, point: PortfolioPoint) -> None:
        """Add a portfolio point to the frontier"""
        self.points.append(point)

    def sort_points(self) -> None:
        """Sort points by volatility"""
        self.points.sort(key=lambda p: p.volatility)

    def get_returns(self) -> np.ndarray:
        """Get array of returns"""
        return np.array([p.expected_return for p in self.points])

    def get_volatilities(self) -> np.ndarray:
        """Get array of volatilities"""
        return np.array([p.volatility for p in self.points])

    def get_sharpe_ratios(self) -> np.ndarray:
        """Get array of Sharpe ratios"""
        return np.array([p.sharpe_ratio for p in self.points])

    def find_minimum_variance(self) -> PortfolioPoint:
        """Find the minimum variance portfolio on the frontier"""
        if not self.points:
            raise ValueError("Efficient frontier is empty")
        self.min_variance_point = min(self.points, key=lambda p: p.volatility)
        return self.min_variance_point

    def find_maximum_sharpe(self) -> PortfolioPoint:
        """Find the maximum Sharpe ratio portfolio"""
        if not self.points:
            raise ValueError("Efficient frontier is empty")
        self.max_sharpe_point = max(self.points, key=lambda p: p.sharpe_ratio)
        return self.max_sharpe_point

    def to_dataframe(self) -> pd.DataFrame:
        """Convert frontier to DataFrame"""
        data = {
            'expected_return': self.get_returns(),
            'volatility': self.get_volatilities(),
            'sharpe_ratio': self.get_sharpe_ratios(),
        }
        return pd.DataFrame(data)


class MarkowitzOptimizer:
    """
    Markowitz Mean-Variance Optimizer.

    This class implements the classic Markowitz portfolio optimization framework
    with multiple objective functions and constraint handling.
    """

    def __init__(
        self,
        expected_returns: Union[pd.Series, np.ndarray, Dict[str, float]],
        covariance_matrix: Union[pd.DataFrame, np.ndarray],
        risk_free_rate: float = 0.02,
        assets: Optional[List[str]] = None,
    ):
        """
        Initialize Markowitz optimizer.

        Args:
            expected_returns: Expected returns for each asset
            covariance_matrix: Covariance matrix of returns
            risk_free_rate: Risk-free rate for Sharpe ratio calculation
            assets: List of asset names (if not provided in Series/DataFrame)
        """
        # Handle different input types
        if isinstance(expected_returns, pd.Series):
            self.assets = expected_returns.index.tolist()
            self.expected_returns = expected_returns.values
        elif isinstance(expected_returns, dict):
            self.assets = list(expected_returns.keys())
            self.expected_returns = np.array([expected_returns[a] for a in self.assets])
        else:
            if assets is None:
                raise ValueError("Must provide asset names when using numpy arrays")
            self.assets = assets
            self.expected_returns = np.asarray(expected_returns)

        if isinstance(covariance_matrix, pd.DataFrame):
            self.covariance_matrix = covariance_matrix.values
        else:
            self.covariance_matrix = np.asarray(covariance_matrix)

        self.risk_free_rate = risk_free_rate
        self.n_assets = len(self.assets)

        # Validate inputs
        self._validate_inputs()

        logger.info(f"Initialized MarkowitzOptimizer with {self.n_assets} assets")

    def _validate_inputs(self) -> None:
        """Validate input data"""
        if len(self.expected_returns) != self.n_assets:
            raise ValueError("Expected returns length must match number of assets")

        if self.covariance_matrix.shape != (self.n_assets, self.n_assets):
            raise ValueError(
                f"Covariance matrix shape {self.covariance_matrix.shape} must be "
                f"({self.n_assets}, {self.n_assets})"
            )

        # Check if covariance matrix is positive semi-definite
        eigenvalues = np.linalg.eigvalsh(self.covariance_matrix)
        if np.any(eigenvalues < -1e-8):
            logger.warning("Covariance matrix is not positive semi-definite")

    def minimum_variance_portfolio(
        self,
        long_only: bool = True,
        min_weight: float = 0.0,
        max_weight: float = 1.0,
    ) -> PortfolioPoint:
        """
        Calculate the minimum variance portfolio.

        Args:
            long_only: If True, constrain weights to be non-negative
            min_weight: Minimum weight per asset
            max_weight: Maximum weight per asset

        Returns:
            PortfolioPoint representing the minimum variance portfolio
        """
        try:
            w = cp.Variable(self.n_assets)

            # Objective: minimize variance
            portfolio_variance = cp.quad_form(w, self.covariance_matrix)
            objective = cp.Minimize(portfolio_variance)

            # Constraints
            constraints = [cp.sum(w) == 1.0]
            if long_only:
                constraints.append(w >= 0)
            constraints.append(w >= min_weight)
            constraints.append(w <= max_weight)

            # Solve
            problem = cp.Problem(objective, constraints)
            problem.solve(solver=cp.OSQP, verbose=False)

            if w.value is None:
                raise ValueError("Optimization failed to converge")

            weights = self._clean_weights(w.value)
            return self._create_portfolio_point(weights)

        except Exception as e:
            logger.error(f"Minimum variance optimization failed: {e}")
            raise

    def maximum_sharpe_portfolio(
        self,
        long_only: bool = True,
        min_weight: float = 0.0,
        max_weight: float = 1.0,
    ) -> PortfolioPoint:
        """
        Calculate the maximum Sharpe ratio portfolio (tangency portfolio).

        Args:
            long_only: If True, constrain weights to be non-negative
            min_weight: Minimum weight per asset
            max_weight: Maximum weight per asset

        Returns:
            PortfolioPoint representing the maximum Sharpe portfolio
        """
        try:
            # Use convex reformulation: optimize y = w/kappa
            y = cp.Variable(self.n_assets)
            kappa = cp.Variable()

            # Objective: minimize risk
            portfolio_variance = cp.quad_form(y, self.covariance_matrix)
            objective = cp.Minimize(portfolio_variance)

            # Constraints
            excess_returns = self.expected_returns - self.risk_free_rate
            constraints = [
                excess_returns @ y == 1.0,  # Normalized excess return
                cp.sum(y) == kappa,
                kappa >= 0,
            ]

            if long_only:
                constraints.append(y >= 0)

            # Solve
            problem = cp.Problem(objective, constraints)
            problem.solve(solver=cp.OSQP, verbose=False)

            if y.value is None or kappa.value is None:
                raise ValueError("Maximum Sharpe optimization failed")

            # Convert back to weights
            weights = y.value / kappa.value
            weights = self._clean_weights(weights)

            # Apply weight bounds through projection
            weights = np.clip(weights, min_weight, max_weight)
            weights = weights / np.sum(weights)

            return self._create_portfolio_point(weights)

        except Exception as e:
            logger.error(f"Maximum Sharpe optimization failed: {e}")
            raise

    def efficient_return_portfolio(
        self,
        target_return: float,
        long_only: bool = True,
        min_weight: float = 0.0,
        max_weight: float = 1.0,
    ) -> PortfolioPoint:
        """
        Find the minimum variance portfolio for a target return.

        Args:
            target_return: Target portfolio return
            long_only: If True, constrain weights to be non-negative
            min_weight: Minimum weight per asset
            max_weight: Maximum weight per asset

        Returns:
            PortfolioPoint with target return and minimum variance
        """
        try:
            w = cp.Variable(self.n_assets)

            # Objective: minimize variance
            portfolio_variance = cp.quad_form(w, self.covariance_matrix)
            objective = cp.Minimize(portfolio_variance)

            # Constraints
            portfolio_return = self.expected_returns @ w
            constraints = [
                cp.sum(w) == 1.0,
                portfolio_return >= target_return,
                w >= min_weight,
                w <= max_weight,
            ]

            if long_only:
                constraints.append(w >= 0)

            # Solve
            problem = cp.Problem(objective, constraints)
            problem.solve(solver=cp.OSQP, verbose=False)

            if w.value is None:
                raise ValueError(
                    f"Could not find portfolio with return {target_return:.4f}"
                )

            weights = self._clean_weights(w.value)
            return self._create_portfolio_point(weights)

        except Exception as e:
            logger.error(f"Efficient return optimization failed: {e}")
            raise

    def efficient_risk_portfolio(
        self,
        target_risk: float,
        long_only: bool = True,
        min_weight: float = 0.0,
        max_weight: float = 1.0,
    ) -> PortfolioPoint:
        """
        Find the maximum return portfolio for a target risk level.

        Args:
            target_risk: Target portfolio volatility
            long_only: If True, constrain weights to be non-negative
            min_weight: Minimum weight per asset
            max_weight: Maximum weight per asset

        Returns:
            PortfolioPoint with target risk and maximum return
        """
        try:
            w = cp.Variable(self.n_assets)

            # Objective: maximize return
            portfolio_return = self.expected_returns @ w
            objective = cp.Maximize(portfolio_return)

            # Constraints
            portfolio_variance = cp.quad_form(w, self.covariance_matrix)
            constraints = [
                cp.sum(w) == 1.0,
                portfolio_variance <= target_risk ** 2,
                w >= min_weight,
                w <= max_weight,
            ]

            if long_only:
                constraints.append(w >= 0)

            # Solve
            problem = cp.Problem(objective, constraints)
            problem.solve(solver=cp.OSQP, verbose=False)

            if w.value is None:
                raise ValueError(
                    f"Could not find portfolio with risk {target_risk:.4f}"
                )

            weights = self._clean_weights(w.value)
            return self._create_portfolio_point(weights)

        except Exception as e:
            logger.error(f"Efficient risk optimization failed: {e}")
            raise

    def calculate_efficient_frontier(
        self,
        n_points: int = 50,
        long_only: bool = True,
        min_weight: float = 0.0,
        max_weight: float = 1.0,
    ) -> EfficientFrontier:
        """
        Calculate the efficient frontier.

        Args:
            n_points: Number of points to calculate
            long_only: If True, constrain weights to be non-negative
            min_weight: Minimum weight per asset
            max_weight: Maximum weight per asset

        Returns:
            EfficientFrontier object with portfolio points
        """
        logger.info(f"Calculating efficient frontier with {n_points} points")

        frontier = EfficientFrontier()

        # Get minimum variance portfolio
        min_var_portfolio = self.minimum_variance_portfolio(
            long_only=long_only,
            min_weight=min_weight,
            max_weight=max_weight,
        )
        frontier.add_point(min_var_portfolio)

        # Get maximum return portfolio (unconstrained by risk)
        max_return = np.max(self.expected_returns)

        # Generate target returns
        min_return = min_var_portfolio.expected_return
        target_returns = np.linspace(min_return, max_return, n_points)

        # Calculate efficient portfolios for each target return
        for target_return in target_returns[1:]:
            try:
                portfolio = self.efficient_return_portfolio(
                    target_return=target_return,
                    long_only=long_only,
                    min_weight=min_weight,
                    max_weight=max_weight,
                )
                frontier.add_point(portfolio)
            except Exception as e:
                logger.debug(f"Could not find portfolio for return {target_return:.4f}: {e}")
                break

        frontier.sort_points()
        frontier.find_minimum_variance()
        frontier.find_maximum_sharpe()

        logger.info(
            f"Efficient frontier calculated with {len(frontier.points)} points. "
            f"Max Sharpe: {frontier.max_sharpe_point.sharpe_ratio:.4f}"
        )

        return frontier

    def optimize_with_views(
        self,
        prior_returns: Optional[np.ndarray] = None,
        prior_covariance: Optional[np.ndarray] = None,
        views: Optional[Dict] = None,
        view_confidences: Optional[np.ndarray] = None,
    ) -> PortfolioPoint:
        """
        Optimize portfolio using Black-Litterman posterior estimates.

        This method integrates Black-Litterman views into the Markowitz framework.

        Args:
            prior_returns: Prior expected returns (if different from current)
            prior_covariance: Prior covariance matrix (if different from current)
            views: Dictionary of views (see BlackLittermanModel)
            view_confidences: Confidence levels for views

        Returns:
            PortfolioPoint with optimal weights
        """
        try:
            from .black_litterman import BlackLittermanModel

            # Use current estimates as priors if not provided
            if prior_returns is None:
                prior_returns = self.expected_returns
            if prior_covariance is None:
                prior_covariance = self.covariance_matrix

            # Create Black-Litterman model
            bl_model = BlackLittermanModel(
                assets=self.assets,
                prior_returns=prior_returns,
                prior_covariance=prior_covariance,
                risk_free_rate=self.risk_free_rate,
            )

            # Add views if provided
            if views:
                for view_name, view_data in views.items():
                    bl_model.add_view(
                        assets=view_data['assets'],
                        view_return=view_data['return'],
                        confidence=view_data.get('confidence', 1.0),
                    )

            # Get posterior estimates
            posterior_returns, posterior_cov = bl_model.get_posterior()

            # Create temporary optimizer with posterior estimates
            temp_optimizer = MarkowitzOptimizer(
                expected_returns=posterior_returns,
                covariance_matrix=posterior_cov,
                risk_free_rate=self.risk_free_rate,
                assets=self.assets,
            )

            # Optimize with posterior estimates
            return temp_optimizer.maximum_sharpe_portfolio()

        except Exception as e:
            logger.error(f"Optimization with views failed: {e}")
            raise

    def portfolio_metrics(self, weights: Union[np.ndarray, Dict[str, float]]) -> Dict[str, float]:
        """
        Calculate portfolio metrics for given weights.

        Args:
            weights: Portfolio weights (array or dict)

        Returns:
            Dictionary with portfolio metrics
        """
        if isinstance(weights, dict):
            w = np.array([weights.get(asset, 0.0) for asset in self.assets])
        else:
            w = np.asarray(weights)

        expected_return = float(self.expected_returns @ w)
        variance = float(w @ self.covariance_matrix @ w)
        volatility = float(np.sqrt(variance))
        sharpe_ratio = (expected_return - self.risk_free_rate) / volatility if volatility > 0 else 0.0

        return {
            'expected_return': expected_return,
            'volatility': volatility,
            'variance': variance,
            'sharpe_ratio': sharpe_ratio,
        }

    def plot_efficient_frontier(
        self,
        frontier: EfficientFrontier,
        show_assets: bool = True,
        show_cml: bool = True,
        figsize: Tuple[int, int] = (12, 8),
    ) -> plt.Figure:
        """
        Plot the efficient frontier.

        Args:
            frontier: EfficientFrontier to plot
            show_assets: If True, show individual assets
            show_cml: If True, show Capital Market Line
            figsize: Figure size

        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=figsize)

        # Plot frontier
        vols = frontier.get_volatilities()
        rets = frontier.get_returns()
        ax.plot(vols, rets, 'b-', linewidth=2, label='Efficient Frontier')

        # Plot individual assets
        if show_assets:
            asset_vols = np.sqrt(np.diag(self.covariance_matrix))
            ax.scatter(
                asset_vols,
                self.expected_returns,
                c='red',
                marker='o',
                s=100,
                alpha=0.6,
                label='Individual Assets'
            )

            # Label assets
            for i, asset in enumerate(self.assets):
                ax.annotate(
                    asset,
                    (asset_vols[i], self.expected_returns[i]),
                    xytext=(5, 5),
                    textcoords='offset points',
                    fontsize=8,
                )

        # Highlight special portfolios
        if frontier.min_variance_point:
            ax.scatter(
                frontier.min_variance_point.volatility,
                frontier.min_variance_point.expected_return,
                c='green',
                marker='*',
                s=500,
                label='Min Variance',
                zorder=5,
            )

        if frontier.max_sharpe_point:
            ax.scatter(
                frontier.max_sharpe_point.volatility,
                frontier.max_sharpe_point.expected_return,
                c='gold',
                marker='*',
                s=500,
                label='Max Sharpe',
                zorder=5,
            )

            # Plot Capital Market Line
            if show_cml:
                max_vol = vols.max() * 1.2
                cml_vols = np.linspace(0, max_vol, 100)
                sharpe = frontier.max_sharpe_point.sharpe_ratio
                cml_rets = self.risk_free_rate + sharpe * cml_vols
                ax.plot(
                    cml_vols,
                    cml_rets,
                    'r--',
                    linewidth=2,
                    label='Capital Market Line',
                    alpha=0.7,
                )

        ax.set_xlabel('Volatility (Risk)', fontsize=12)
        ax.set_ylabel('Expected Return', fontsize=12)
        ax.set_title('Efficient Frontier', fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=10)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        return fig

    def _create_portfolio_point(self, weights: np.ndarray) -> PortfolioPoint:
        """Create PortfolioPoint from weight array"""
        weights_dict = {
            asset: float(w)
            for asset, w in zip(self.assets, weights)
            if abs(w) > 1e-6
        }

        metrics = self.portfolio_metrics(weights)

        return PortfolioPoint(
            weights=weights_dict,
            expected_return=metrics['expected_return'],
            volatility=metrics['volatility'],
            sharpe_ratio=metrics['sharpe_ratio'],
        )

    def _clean_weights(self, weights: np.ndarray, threshold: float = 1e-6) -> np.ndarray:
        """Clean up weights by removing tiny positions and renormalizing"""
        weights = np.asarray(weights)
        weights[np.abs(weights) < threshold] = 0
        weight_sum = np.sum(weights)
        if weight_sum > 0:
            weights = weights / weight_sum
        return weights

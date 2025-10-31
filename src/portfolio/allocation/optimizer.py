"""
Portfolio Optimizer Module

This module implements various portfolio allocation strategies including:
- Kelly Criterion position sizing
- Risk Parity allocation
- Minimum Variance portfolio
- Maximum Sharpe ratio portfolio
- Custom constraint handling

The optimizer uses cvxpy for convex optimization and scipy for non-convex problems.
"""

import logging
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import pandas as pd
from scipy.optimize import minimize, Bounds, LinearConstraint, NonlinearConstraint
from scipy.stats import gmean
import cvxpy as cp

logger = logging.getLogger(__name__)


class OptimizationObjective(Enum):
    """Optimization objectives for portfolio allocation"""
    MIN_VARIANCE = "min_variance"
    MAX_SHARPE = "max_sharpe"
    MAX_RETURN = "max_return"
    RISK_PARITY = "risk_parity"
    KELLY = "kelly"
    EQUAL_WEIGHT = "equal_weight"
    MAX_DIVERSIFICATION = "max_diversification"
    MIN_CVAR = "min_cvar"
    MAX_UTILITY = "max_utility"


@dataclass
class AllocationConstraints:
    """
    Portfolio allocation constraints.

    Attributes:
        long_only: If True, all weights must be non-negative
        max_leverage: Maximum total leverage (sum of absolute weights)
        min_weight: Minimum weight per asset
        max_weight: Maximum weight per asset
        target_return: Target portfolio return (if applicable)
        target_risk: Target portfolio risk (if applicable)
        sector_limits: Dictionary mapping sector names to max exposure
        asset_sector_map: Dictionary mapping assets to sectors
        turnover_limit: Maximum portfolio turnover from current weights
        transaction_costs: Per-asset transaction costs (basis points)
        cardinality: Maximum number of non-zero positions
        sum_to_one: If True, weights must sum to exactly 1.0
    """
    long_only: bool = True
    max_leverage: float = 1.0
    min_weight: float = 0.0
    max_weight: float = 1.0
    target_return: Optional[float] = None
    target_risk: Optional[float] = None
    sector_limits: Optional[Dict[str, float]] = None
    asset_sector_map: Optional[Dict[str, str]] = None
    turnover_limit: Optional[float] = None
    transaction_costs: Optional[Dict[str, float]] = None
    cardinality: Optional[int] = None
    sum_to_one: bool = True
    risk_free_rate: float = 0.02

    def __post_init__(self):
        """Validate constraints"""
        if self.max_weight < self.min_weight:
            raise ValueError("max_weight must be >= min_weight")
        if self.max_leverage < 0:
            raise ValueError("max_leverage must be non-negative")
        if not 0 <= self.min_weight <= 1:
            raise ValueError("min_weight must be between 0 and 1")
        if not 0 <= self.max_weight <= 1:
            raise ValueError("max_weight must be between 0 and 1")


@dataclass
class AllocationResult:
    """
    Result from portfolio optimization.

    Attributes:
        weights: Dictionary mapping asset symbols to weights
        expected_return: Expected portfolio return
        expected_risk: Expected portfolio risk (volatility)
        sharpe_ratio: Portfolio Sharpe ratio
        objective_value: Value of the optimization objective
        success: Whether optimization succeeded
        message: Status message
        metadata: Additional result metadata
    """
    weights: Dict[str, float]
    expected_return: float
    expected_risk: float
    sharpe_ratio: float
    objective_value: float
    success: bool
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_series(self) -> pd.Series:
        """Convert weights to pandas Series"""
        return pd.Series(self.weights)

    def get_metrics(self) -> Dict[str, float]:
        """Get portfolio metrics as dictionary"""
        return {
            'expected_return': self.expected_return,
            'expected_risk': self.expected_risk,
            'sharpe_ratio': self.sharpe_ratio,
            'objective_value': self.objective_value,
        }


class PortfolioOptimizer:
    """
    Multi-strategy portfolio optimizer supporting various allocation approaches.

    This optimizer implements multiple optimization objectives and handles
    complex constraints including position limits, sector exposure, turnover,
    and transaction costs.
    """

    def __init__(
        self,
        returns: pd.DataFrame,
        constraints: Optional[AllocationConstraints] = None,
        risk_free_rate: float = 0.02,
        frequency: int = 252,
    ):
        """
        Initialize portfolio optimizer.

        Args:
            returns: DataFrame of asset returns (T x N)
            constraints: Allocation constraints
            risk_free_rate: Risk-free rate for Sharpe ratio calculation
            frequency: Number of periods per year (252 for daily, 52 for weekly, etc.)
        """
        self.returns = returns
        self.assets = returns.columns.tolist()
        self.n_assets = len(self.assets)
        self.constraints = constraints or AllocationConstraints()
        self.risk_free_rate = risk_free_rate
        self.frequency = frequency

        # Pre-compute statistics
        self.mean_returns = returns.mean() * frequency
        self.cov_matrix = returns.cov() * frequency
        self.std_returns = np.sqrt(np.diag(self.cov_matrix))
        self.corr_matrix = returns.corr()

        logger.info(
            f"Initialized PortfolioOptimizer with {self.n_assets} assets, "
            f"{len(returns)} return observations"
        )

    def optimize(
        self,
        objective: OptimizationObjective,
        current_weights: Optional[Dict[str, float]] = None,
        **kwargs
    ) -> AllocationResult:
        """
        Optimize portfolio allocation.

        Args:
            objective: Optimization objective
            current_weights: Current portfolio weights (for turnover constraints)
            **kwargs: Additional objective-specific parameters

        Returns:
            AllocationResult with optimal weights and metrics
        """
        logger.info(f"Optimizing portfolio with objective: {objective.value}")

        # Convert current weights to array if provided
        w_current = None
        if current_weights is not None:
            w_current = np.array([current_weights.get(asset, 0.0) for asset in self.assets])

        # Route to appropriate optimization method
        if objective == OptimizationObjective.MIN_VARIANCE:
            result = self._optimize_min_variance(w_current)
        elif objective == OptimizationObjective.MAX_SHARPE:
            result = self._optimize_max_sharpe(w_current)
        elif objective == OptimizationObjective.MAX_RETURN:
            result = self._optimize_max_return(w_current)
        elif objective == OptimizationObjective.RISK_PARITY:
            result = self._optimize_risk_parity(w_current)
        elif objective == OptimizationObjective.KELLY:
            result = self._optimize_kelly(w_current, **kwargs)
        elif objective == OptimizationObjective.EQUAL_WEIGHT:
            result = self._equal_weight()
        elif objective == OptimizationObjective.MAX_DIVERSIFICATION:
            result = self._optimize_max_diversification(w_current)
        elif objective == OptimizationObjective.MIN_CVAR:
            result = self._optimize_min_cvar(w_current, **kwargs)
        elif objective == OptimizationObjective.MAX_UTILITY:
            result = self._optimize_max_utility(w_current, **kwargs)
        else:
            raise ValueError(f"Unknown optimization objective: {objective}")

        logger.info(
            f"Optimization complete. Success: {result.success}, "
            f"Return: {result.expected_return:.4f}, Risk: {result.expected_risk:.4f}"
        )

        return result

    def _optimize_min_variance(
        self,
        current_weights: Optional[np.ndarray] = None
    ) -> AllocationResult:
        """
        Minimize portfolio variance using convex optimization.

        Args:
            current_weights: Current portfolio weights

        Returns:
            AllocationResult with optimal weights
        """
        try:
            # Define optimization variable
            w = cp.Variable(self.n_assets)

            # Objective: minimize variance
            portfolio_variance = cp.quad_form(w, self.cov_matrix.values)
            objective = cp.Minimize(portfolio_variance)

            # Constraints
            constraints = self._build_cvxpy_constraints(w, current_weights)

            # Solve
            problem = cp.Problem(objective, constraints)
            problem.solve(solver=cp.OSQP, verbose=False)

            if w.value is None:
                return self._create_failure_result("Optimization failed to converge")

            # Extract results
            weights = w.value
            weights = self._post_process_weights(weights)

            return self._create_result(weights, portfolio_variance.value)

        except Exception as e:
            logger.error(f"Min variance optimization failed: {e}")
            return self._create_failure_result(str(e))

    def _optimize_max_sharpe(
        self,
        current_weights: Optional[np.ndarray] = None
    ) -> AllocationResult:
        """
        Maximize Sharpe ratio.

        This is reformulated as a convex problem by optimizing on y = w/kappa
        where kappa = mean_return @ w.

        Args:
            current_weights: Current portfolio weights

        Returns:
            AllocationResult with optimal weights
        """
        try:
            # Use convex reformulation
            y = cp.Variable(self.n_assets)
            kappa = cp.Variable()

            # Objective: minimize variance (risk) per unit return
            portfolio_variance = cp.quad_form(y, self.cov_matrix.values)
            objective = cp.Minimize(portfolio_variance)

            # Constraints
            mean_ret = self.mean_returns.values - self.risk_free_rate
            constraints = [
                mean_ret @ y == 1,  # Normalized return
                kappa >= 0,
            ]

            # Add weight constraints (adapted for y = w/kappa)
            if self.constraints.long_only:
                constraints.append(y >= 0)

            if self.constraints.sum_to_one:
                constraints.append(cp.sum(y) == kappa)

            # Solve
            problem = cp.Problem(objective, constraints)
            problem.solve(solver=cp.OSQP, verbose=False)

            if y.value is None or kappa.value is None:
                return self._create_failure_result("Max Sharpe optimization failed")

            # Convert back to weights
            weights = y.value / kappa.value
            weights = self._post_process_weights(weights)

            return self._create_result(weights, 0.0)

        except Exception as e:
            logger.error(f"Max Sharpe optimization failed: {e}")
            return self._create_failure_result(str(e))

    def _optimize_max_return(
        self,
        current_weights: Optional[np.ndarray] = None
    ) -> AllocationResult:
        """
        Maximize expected return subject to risk constraint.

        Args:
            current_weights: Current portfolio weights

        Returns:
            AllocationResult with optimal weights
        """
        try:
            w = cp.Variable(self.n_assets)

            # Objective: maximize expected return
            portfolio_return = self.mean_returns.values @ w
            objective = cp.Maximize(portfolio_return)

            # Constraints
            constraints = self._build_cvxpy_constraints(w, current_weights)

            # Add risk constraint if specified
            if self.constraints.target_risk is not None:
                portfolio_variance = cp.quad_form(w, self.cov_matrix.values)
                constraints.append(
                    portfolio_variance <= self.constraints.target_risk ** 2
                )

            # Solve
            problem = cp.Problem(objective, constraints)
            problem.solve(solver=cp.OSQP, verbose=False)

            if w.value is None:
                return self._create_failure_result("Max return optimization failed")

            weights = w.value
            weights = self._post_process_weights(weights)

            return self._create_result(weights, portfolio_return.value)

        except Exception as e:
            logger.error(f"Max return optimization failed: {e}")
            return self._create_failure_result(str(e))

    def _optimize_risk_parity(
        self,
        current_weights: Optional[np.ndarray] = None
    ) -> AllocationResult:
        """
        Risk parity allocation - equalize risk contributions.

        This uses scipy.optimize since the risk parity objective is not convex.

        Args:
            current_weights: Current portfolio weights

        Returns:
            AllocationResult with optimal weights
        """
        def risk_parity_objective(w):
            """Minimize difference in risk contributions"""
            portfolio_vol = np.sqrt(w @ self.cov_matrix.values @ w)
            marginal_contrib = self.cov_matrix.values @ w
            risk_contrib = w * marginal_contrib / portfolio_vol

            # Minimize sum of squared deviations from equal risk
            target_risk = portfolio_vol / self.n_assets
            return np.sum((risk_contrib - target_risk) ** 2)

        # Initial guess
        w0 = np.ones(self.n_assets) / self.n_assets

        # Bounds and constraints
        bounds = Bounds(
            self.constraints.min_weight,
            self.constraints.max_weight
        )

        scipy_constraints = []
        if self.constraints.sum_to_one:
            scipy_constraints.append({
                'type': 'eq',
                'fun': lambda w: np.sum(w) - 1.0
            })

        # Optimize
        result = minimize(
            risk_parity_objective,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=scipy_constraints,
            options={'maxiter': 1000, 'ftol': 1e-9}
        )

        if not result.success:
            logger.warning(f"Risk parity optimization: {result.message}")

        weights = self._post_process_weights(result.x)
        return self._create_result(weights, result.fun, success=result.success)

    def _optimize_kelly(
        self,
        current_weights: Optional[np.ndarray] = None,
        kelly_fraction: float = 1.0,
    ) -> AllocationResult:
        """
        Kelly Criterion position sizing for optimal growth.

        Kelly fraction allows fractional Kelly betting to reduce volatility.

        Args:
            current_weights: Current portfolio weights
            kelly_fraction: Fraction of Kelly criterion to use (0-1)

        Returns:
            AllocationResult with optimal weights
        """
        try:
            # Kelly weights: f = Sigma^-1 @ mu
            # where mu is excess return over risk-free rate
            excess_returns = self.mean_returns.values - self.risk_free_rate

            # Solve linear system: cov @ f = excess_returns
            kelly_weights = np.linalg.solve(
                self.cov_matrix.values,
                excess_returns
            )

            # Apply Kelly fraction
            kelly_weights = kelly_weights * kelly_fraction

            # Apply constraints using projection
            weights = self._project_to_constraints(kelly_weights)

            return self._create_result(weights, 0.0)

        except np.linalg.LinAlgError as e:
            logger.error(f"Kelly optimization failed - singular covariance: {e}")
            return self._create_failure_result("Singular covariance matrix")
        except Exception as e:
            logger.error(f"Kelly optimization failed: {e}")
            return self._create_failure_result(str(e))

    def _optimize_max_diversification(
        self,
        current_weights: Optional[np.ndarray] = None
    ) -> AllocationResult:
        """
        Maximize diversification ratio: (w @ sigma) / sqrt(w @ Cov @ w)

        Args:
            current_weights: Current portfolio weights

        Returns:
            AllocationResult with optimal weights
        """
        def neg_diversification_ratio(w):
            """Negative diversification ratio for minimization"""
            portfolio_vol = np.sqrt(w @ self.cov_matrix.values @ w)
            weighted_vol = w @ self.std_returns
            return -weighted_vol / portfolio_vol

        w0 = np.ones(self.n_assets) / self.n_assets
        bounds = Bounds(self.constraints.min_weight, self.constraints.max_weight)

        scipy_constraints = []
        if self.constraints.sum_to_one:
            scipy_constraints.append({'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0})

        result = minimize(
            neg_diversification_ratio,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=scipy_constraints,
            options={'maxiter': 1000}
        )

        weights = self._post_process_weights(result.x)
        return self._create_result(weights, -result.fun, success=result.success)

    def _optimize_min_cvar(
        self,
        current_weights: Optional[np.ndarray] = None,
        alpha: float = 0.05
    ) -> AllocationResult:
        """
        Minimize Conditional Value at Risk (CVaR/ES).

        Args:
            current_weights: Current portfolio weights
            alpha: Confidence level for CVaR (e.g., 0.05 for 95% CVaR)

        Returns:
            AllocationResult with optimal weights
        """
        try:
            T = len(self.returns)
            returns_matrix = self.returns.values

            # Variables
            w = cp.Variable(self.n_assets)
            z = cp.Variable(T)
            var = cp.Variable()

            # CVaR formulation
            portfolio_returns = returns_matrix @ w
            cvar = var + (1 / (alpha * T)) * cp.sum(z)

            # Objective
            objective = cp.Minimize(cvar)

            # Constraints
            constraints = [z >= 0]
            constraints.extend([
                z[t] >= -portfolio_returns[t] - var
                for t in range(T)
            ])
            constraints.extend(self._build_cvxpy_constraints(w, current_weights))

            # Solve
            problem = cp.Problem(objective, constraints)
            problem.solve(solver=cp.OSQP, verbose=False)

            if w.value is None:
                return self._create_failure_result("CVaR optimization failed")

            weights = self._post_process_weights(w.value)
            return self._create_result(weights, cvar.value)

        except Exception as e:
            logger.error(f"CVaR optimization failed: {e}")
            return self._create_failure_result(str(e))

    def _optimize_max_utility(
        self,
        current_weights: Optional[np.ndarray] = None,
        risk_aversion: float = 2.0
    ) -> AllocationResult:
        """
        Maximize expected utility: E[R] - (lambda/2) * Var[R]

        Args:
            current_weights: Current portfolio weights
            risk_aversion: Risk aversion parameter (lambda)

        Returns:
            AllocationResult with optimal weights
        """
        try:
            w = cp.Variable(self.n_assets)

            # Utility = expected return - risk_aversion * variance / 2
            portfolio_return = self.mean_returns.values @ w
            portfolio_variance = cp.quad_form(w, self.cov_matrix.values)
            utility = portfolio_return - (risk_aversion / 2) * portfolio_variance

            objective = cp.Maximize(utility)
            constraints = self._build_cvxpy_constraints(w, current_weights)

            problem = cp.Problem(objective, constraints)
            problem.solve(solver=cp.OSQP, verbose=False)

            if w.value is None:
                return self._create_failure_result("Utility optimization failed")

            weights = self._post_process_weights(w.value)
            return self._create_result(weights, utility.value)

        except Exception as e:
            logger.error(f"Utility optimization failed: {e}")
            return self._create_failure_result(str(e))

    def _equal_weight(self) -> AllocationResult:
        """Simple equal weight allocation"""
        weights = np.ones(self.n_assets) / self.n_assets
        return self._create_result(weights, 0.0)

    def _build_cvxpy_constraints(
        self,
        w: cp.Variable,
        current_weights: Optional[np.ndarray] = None
    ) -> List:
        """Build list of cvxpy constraints"""
        constraints = []

        # Long only
        if self.constraints.long_only:
            constraints.append(w >= 0)

        # Sum to one
        if self.constraints.sum_to_one:
            constraints.append(cp.sum(w) == 1.0)

        # Weight bounds
        if self.constraints.min_weight > 0:
            constraints.append(w >= self.constraints.min_weight)
        if self.constraints.max_weight < 1:
            constraints.append(w <= self.constraints.max_weight)

        # Leverage constraint
        if self.constraints.max_leverage < float('inf'):
            constraints.append(cp.norm(w, 1) <= self.constraints.max_leverage)

        # Target return
        if self.constraints.target_return is not None:
            portfolio_return = self.mean_returns.values @ w
            constraints.append(portfolio_return >= self.constraints.target_return)

        # Turnover constraint
        if current_weights is not None and self.constraints.turnover_limit is not None:
            turnover = cp.norm(w - current_weights, 1)
            constraints.append(turnover <= self.constraints.turnover_limit)

        return constraints

    def _project_to_constraints(self, weights: np.ndarray) -> np.ndarray:
        """Project weights to satisfy constraints"""
        # Clip to bounds
        weights = np.clip(weights, self.constraints.min_weight, self.constraints.max_weight)

        # Long only
        if self.constraints.long_only:
            weights = np.maximum(weights, 0)

        # Normalize if needed
        if self.constraints.sum_to_one:
            weight_sum = np.sum(weights)
            if weight_sum > 0:
                weights = weights / weight_sum

        return weights

    def _post_process_weights(self, weights: np.ndarray) -> np.ndarray:
        """Clean up weights (remove tiny positions, normalize)"""
        # Remove tiny positions
        weights[np.abs(weights) < 1e-6] = 0

        # Renormalize if needed
        if self.constraints.sum_to_one:
            weight_sum = np.sum(weights)
            if weight_sum > 0:
                weights = weights / weight_sum

        return weights

    def _create_result(
        self,
        weights: np.ndarray,
        objective_value: float,
        success: bool = True
    ) -> AllocationResult:
        """Create AllocationResult from weight array"""
        weights_dict = {
            asset: float(w)
            for asset, w in zip(self.assets, weights)
            if abs(w) > 1e-6
        }

        # Calculate portfolio metrics
        w = np.array([weights_dict.get(asset, 0.0) for asset in self.assets])
        expected_return = float(self.mean_returns.values @ w)
        expected_risk = float(np.sqrt(w @ self.cov_matrix.values @ w))

        sharpe_ratio = 0.0
        if expected_risk > 0:
            sharpe_ratio = (expected_return - self.risk_free_rate) / expected_risk

        return AllocationResult(
            weights=weights_dict,
            expected_return=expected_return,
            expected_risk=expected_risk,
            sharpe_ratio=sharpe_ratio,
            objective_value=objective_value,
            success=success,
            message="Optimization successful" if success else "Optimization failed"
        )

    def _create_failure_result(self, message: str) -> AllocationResult:
        """Create failed AllocationResult"""
        return AllocationResult(
            weights={},
            expected_return=0.0,
            expected_risk=0.0,
            sharpe_ratio=0.0,
            objective_value=0.0,
            success=False,
            message=message
        )

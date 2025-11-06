"""
Portfolio optimization.

Implements Markowitz Mean-Variance, Black-Litterman, and other optimization methods.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum
import pandas as pd
import numpy as np
from scipy.optimize import minimize
from loguru import logger


class OptimizationMethod(Enum):
    """Portfolio optimization methods."""
    MEAN_VARIANCE = "mean_variance"  # Markowitz
    MIN_VARIANCE = "min_variance"
    MAX_SHARPE = "max_sharpe"
    RISK_PARITY = "risk_parity"
    BLACK_LITTERMAN = "black_litterman"
    MAX_DIVERSIFICATION = "max_diversification"


@dataclass
class OptimizationResult:
    """Portfolio optimization result."""
    weights: pd.Series  # Optimal weights
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    method: OptimizationMethod
    timestamp: datetime
    metadata: Dict = None


class PortfolioOptimizer:
    """
    Portfolio optimization engine.
    
    Supports multiple optimization methods:
    - Mean-Variance (Markowitz)
    - Minimum Variance
    - Maximum Sharpe
    - Risk Parity
    - Black-Litterman
    - Maximum Diversification
    """
    
    def __init__(
        self,
        risk_free_rate: float = 0.02,
        target_return: Optional[float] = None,
        target_volatility: Optional[float] = None
    ):
        """Initialize portfolio optimizer."""
        self.risk_free_rate = risk_free_rate
        self.target_return = target_return
        self.target_volatility = target_volatility
        
        logger.info("Initialized PortfolioOptimizer")
    
    def optimize(
        self,
        returns: pd.DataFrame,  # Historical returns
        method: OptimizationMethod = OptimizationMethod.MAX_SHARPE,
        constraints: Optional[Dict] = None,
        views: Optional[Dict] = None  # For Black-Litterman
    ) -> OptimizationResult:
        """
        Optimize portfolio weights.
        
        Args:
            returns: Historical returns DataFrame (dates x assets)
            method: Optimization method
            constraints: Optional constraints dict
            views: Optional views for Black-Litterman
            
        Returns:
            OptimizationResult
        """
        # Calculate covariance matrix
        cov_matrix = returns.cov() * 252  # Annualized
        
        # Calculate expected returns
        expected_returns = returns.mean() * 252  # Annualized
        
        # Optimize
        if method == OptimizationMethod.MEAN_VARIANCE:
            weights = self._mean_variance_optimization(
                expected_returns, cov_matrix, constraints
            )
        elif method == OptimizationMethod.MIN_VARIANCE:
            weights = self._min_variance_optimization(cov_matrix, constraints)
        elif method == OptimizationMethod.MAX_SHARPE:
            weights = self._max_sharpe_optimization(
                expected_returns, cov_matrix, constraints
            )
        elif method == OptimizationMethod.RISK_PARITY:
            weights = self._risk_parity_optimization(cov_matrix, constraints)
        elif method == OptimizationMethod.BLACK_LITTERMAN:
            weights = self._black_litterman_optimization(
                expected_returns, cov_matrix, views, constraints
            )
        elif method == OptimizationMethod.MAX_DIVERSIFICATION:
            weights = self._max_diversification_optimization(cov_matrix, constraints)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Calculate portfolio metrics
        port_return = np.dot(weights, expected_returns)
        port_vol = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))
        sharpe = (port_return - self.risk_free_rate) / port_vol if port_vol > 0 else 0
        
        result = OptimizationResult(
            weights=pd.Series(weights, index=returns.columns),
            expected_return=port_return,
            expected_volatility=port_vol,
            sharpe_ratio=sharpe,
            method=method,
            timestamp=datetime.now()
        )
        
        logger.info(
            f"Optimization complete: method={method.value}, "
            f"return={port_return:.2%}, vol={port_vol:.2%}, sharpe={sharpe:.3f}"
        )
        
        return result
    
    def _mean_variance_optimization(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        constraints: Optional[Dict]
    ) -> np.ndarray:
        """Markowitz mean-variance optimization."""
        n_assets = len(expected_returns)
        
        # Objective: minimize variance for target return
        def objective(weights):
            return np.dot(weights, np.dot(cov_matrix, weights))
        
        # Constraints
        cons = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]  # Weights sum to 1
        
        if self.target_return is not None:
            cons.append({
                'type': 'eq',
                'fun': lambda w: np.dot(w, expected_returns) - self.target_return
            })
        
        # Bounds
        bounds = tuple((0, 1) for _ in range(n_assets))  # Long only
        
        if constraints and 'bounds' in constraints:
            bounds = constraints['bounds']
        
        # Initial guess
        x0 = np.array([1.0 / n_assets] * n_assets)
        
        # Optimize
        result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=cons)
        
        return result.x
    
    def _min_variance_optimization(
        self,
        cov_matrix: pd.DataFrame,
        constraints: Optional[Dict]
    ) -> np.ndarray:
        """Minimum variance optimization."""
        n_assets = len(cov_matrix)
        
        def objective(weights):
            return np.dot(weights, np.dot(cov_matrix, weights))
        
        cons = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        bounds = tuple((0, 1) for _ in range(n_assets))
        x0 = np.array([1.0 / n_assets] * n_assets)
        
        result = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=cons)
        
        return result.x
    
    def _max_sharpe_optimization(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        constraints: Optional[Dict]
    ) -> np.ndarray:
        """Maximum Sharpe ratio optimization."""
        n_assets = len(expected_returns)
        
        def neg_sharpe(weights):
            port_return = np.dot(weights, expected_returns)
            port_vol = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))
            return -(port_return - self.risk_free_rate) / port_vol if port_vol > 0 else 0
        
        cons = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        bounds = tuple((0, 1) for _ in range(n_assets))
        x0 = np.array([1.0 / n_assets] * n_assets)
        
        result = minimize(neg_sharpe, x0, method='SLSQP', bounds=bounds, constraints=cons)
        
        return result.x
    
    def _risk_parity_optimization(
        self,
        cov_matrix: pd.DataFrame,
        constraints: Optional[Dict]
    ) -> np.ndarray:
        """Risk parity optimization."""
        n_assets = len(cov_matrix)
        
        def risk_budget_objective(weights):
            port_vol = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))
            marginal_contrib = np.dot(cov_matrix, weights) / port_vol
            risk_contrib = weights * marginal_contrib
            target_risk = port_vol / n_assets
            return np.sum((risk_contrib - target_risk) ** 2)
        
        cons = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        bounds = tuple((0.001, 1) for _ in range(n_assets))  # Min 0.1%
        x0 = np.array([1.0 / n_assets] * n_assets)
        
        result = minimize(risk_budget_objective, x0, method='SLSQP', bounds=bounds, constraints=cons)
        
        return result.x
    
    def _black_litterman_optimization(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        views: Optional[Dict],
        constraints: Optional[Dict]
    ) -> np.ndarray:
        """Black-Litterman optimization with investor views."""
        # Simplified Black-Litterman
        # In production, would implement full model with view uncertainty
        
        if views is None or len(views) == 0:
            # No views, fall back to mean-variance
            return self._mean_variance_optimization(expected_returns, cov_matrix, constraints)
        
        # Adjust expected returns based on views
        adjusted_returns = expected_returns.copy()
        
        for asset, view_return in views.items():
            if asset in adjusted_returns.index:
                # Simple blend: 50% view, 50% historical
                adjusted_returns[asset] = 0.5 * view_return + 0.5 * adjusted_returns[asset]
        
        # Optimize with adjusted returns
        return self._max_sharpe_optimization(adjusted_returns, cov_matrix, constraints)
    
    def _max_diversification_optimization(
        self,
        cov_matrix: pd.DataFrame,
        constraints: Optional[Dict]
    ) -> np.ndarray:
        """Maximum diversification ratio optimization."""
        n_assets = len(cov_matrix)
        
        # Individual volatilities
        vols = np.sqrt(np.diag(cov_matrix))
        
        def neg_diversification_ratio(weights):
            weighted_avg_vol = np.dot(weights, vols)
            port_vol = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))
            return -weighted_avg_vol / port_vol if port_vol > 0 else 0
        
        cons = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        bounds = tuple((0, 1) for _ in range(n_assets))
        x0 = np.array([1.0 / n_assets] * n_assets)
        
        result = minimize(neg_diversification_ratio, x0, method='SLSQP', bounds=bounds, constraints=cons)
        
        return result.x
    
    def efficient_frontier(
        self,
        returns: pd.DataFrame,
        n_points: int = 50
    ) -> pd.DataFrame:
        """
        Calculate efficient frontier.
        
        Args:
            returns: Historical returns
            n_points: Number of points on frontier
            
        Returns:
            DataFrame with frontier points
        """
        expected_returns = returns.mean() * 252
        cov_matrix = returns.cov() * 252
        
        # Range of target returns
        min_ret = expected_returns.min()
        max_ret = expected_returns.max()
        target_returns = np.linspace(min_ret, max_ret, n_points)
        
        frontier_points = []
        
        for target_ret in target_returns:
            self.target_return = target_ret
            
            try:
                result = self.optimize(
                    returns,
                    method=OptimizationMethod.MEAN_VARIANCE
                )
                
                frontier_points.append({
                    'return': result.expected_return,
                    'volatility': result.expected_volatility,
                    'sharpe': result.sharpe_ratio
                })
            except Exception as e:
                logger.warning(f"Failed to optimize for target return {target_ret:.2%}: {e}")
                continue
        
        self.target_return = None  # Reset
        
        return pd.DataFrame(frontier_points)

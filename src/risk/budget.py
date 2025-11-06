"""
Dynamic risk budgeting system.

Allocates risk budget across strategies and positions based on market conditions.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from loguru import logger


@dataclass
class RiskBudget:
    """Risk budget allocation."""
    total_budget: float  # Total risk budget (e.g., 15% vol target)
    strategy_budgets: Dict[str, float]  # Strategy -> budget
    position_budgets: Dict[str, float]  # Position -> budget
    timestamp: datetime
    utilization: float  # Current risk / budget


class RiskBudgetManager:
    """
    Dynamic risk budgeting system.
    
    Allocates risk budget across:
    1. Strategies (factor, momentum, mean-reversion, etc.)
    2. Individual positions
    3. Time periods
    
    Adjusts based on:
    - Market regime
    - Recent performance
    - Risk utilization
    """
    
    def __init__(
        self,
        base_vol_target: float = 0.15,  # 15% annual vol target
        max_vol_target: float = 0.25,  # 25% max
        min_vol_target: float = 0.05,  # 5% min
        rebalance_threshold: float = 0.20  # 20% deviation triggers rebalance
    ):
        """Initialize risk budget manager."""
        self.base_vol_target = base_vol_target
        self.max_vol_target = max_vol_target
        self.min_vol_target = min_vol_target
        self.rebalance_threshold = rebalance_threshold
        
        # Current budget
        self.current_budget: Optional[RiskBudget] = None
        self.budget_history: List[RiskBudget] = []
        
        logger.info(f"Initialized RiskBudgetManager: target={base_vol_target:.1%}")
    
    def calculate_budget(
        self,
        market_regime: str,  # Current market regime
        current_volatility: float,  # Realized portfolio vol
        strategies: Dict[str, Dict],  # Strategy -> {vol, sharpe, allocation}
        regime_adjustment: float = 1.0  # From regime detector
    ) -> RiskBudget:
        """
        Calculate dynamic risk budget.
        
        Args:
            market_regime: Current market regime
            current_volatility: Current portfolio volatility
            strategies: Strategy metrics
            regime_adjustment: Risk scaling from regime detector
            
        Returns:
            RiskBudget
        """
        # Adjust base target based on regime
        adjusted_target = self.base_vol_target * regime_adjustment
        
        # Ensure within bounds
        adjusted_target = np.clip(
            adjusted_target,
            self.min_vol_target,
            self.max_vol_target
        )
        
        # Allocate budget across strategies
        strategy_budgets = self._allocate_strategy_budgets(
            strategies,
            adjusted_target
        )
        
        # Allocate budget across positions (if strategies provide positions)
        position_budgets = self._allocate_position_budgets(
            strategies,
            strategy_budgets
        )
        
        # Calculate utilization
        utilization = current_volatility / adjusted_target if adjusted_target > 0 else 0
        
        budget = RiskBudget(
            total_budget=adjusted_target,
            strategy_budgets=strategy_budgets,
            position_budgets=position_budgets,
            timestamp=datetime.now(),
            utilization=utilization
        )
        
        self.current_budget = budget
        self.budget_history.append(budget)
        
        logger.info(
            f"Risk budget: Target={adjusted_target:.2%}, "
            f"Realized={current_volatility:.2%}, "
            f"Utilization={utilization:.1%}"
        )
        
        return budget
    
    def _allocate_strategy_budgets(
        self,
        strategies: Dict[str, Dict],
        total_budget: float
    ) -> Dict[str, float]:
        """
        Allocate risk budget across strategies.
        
        Uses risk parity approach weighted by Sharpe ratio.
        """
        if len(strategies) == 0:
            return {}
        
        # Calculate risk-adjusted weights
        weights = {}
        total_weight = 0
        
        for name, metrics in strategies.items():
            vol = metrics.get('volatility', 0.15)
            sharpe = metrics.get('sharpe', 0)
            
            # Weight = Sharpe / Vol (risk-adjusted return)
            if vol > 0:
                weight = max(sharpe, 0.1) / vol  # Min weight for stability
            else:
                weight = 0
            
            weights[name] = weight
            total_weight += weight
        
        # Normalize and allocate budget
        budgets = {}
        for name, weight in weights.items():
            if total_weight > 0:
                allocation = weight / total_weight
                budgets[name] = total_budget * allocation
            else:
                budgets[name] = total_budget / len(strategies)
        
        return budgets
    
    def _allocate_position_budgets(
        self,
        strategies: Dict[str, Dict],
        strategy_budgets: Dict[str, float]
    ) -> Dict[str, float]:
        """Allocate budget to individual positions."""
        position_budgets = {}
        
        for strategy_name, metrics in strategies.items():
            strategy_budget = strategy_budgets.get(strategy_name, 0)
            positions = metrics.get('positions', {})
            
            if len(positions) == 0:
                continue
            
            # Equal risk allocation within strategy
            position_budget = strategy_budget / len(positions)
            
            for symbol in positions:
                if symbol not in position_budgets:
                    position_budgets[symbol] = 0
                position_budgets[symbol] += position_budget
        
        return position_budgets
    
    def check_rebalance_needed(
        self
    ) -> bool:
        """Check if rebalancing is needed."""
        if self.current_budget is None:
            return False
        
        utilization = self.current_budget.utilization
        
        # Rebalance if significantly over/under budget
        if abs(utilization - 1.0) > self.rebalance_threshold:
            logger.info(
                f"Rebalance needed: utilization={utilization:.1%} "
                f"(threshold={self.rebalance_threshold:.0%})"
            )
            return True
        
        return False
    
    def get_scaling_factor(
        self,
        strategy_name: str
    ) -> float:
        """
        Get position scaling factor for strategy.
        
        Used to scale positions to meet risk budget.
        
        Args:
            strategy_name: Strategy name
            
        Returns:
            Scaling factor (1.0 = no change)
        """
        if self.current_budget is None:
            return 1.0
        
        strategy_budget = self.current_budget.strategy_budgets.get(strategy_name, 0)
        
        # Simple approach: scale linearly with budget
        # More sophisticated: use optimization
        base_budget = self.base_vol_target / len(self.current_budget.strategy_budgets)
        
        if base_budget > 0:
            scaling = strategy_budget / base_budget
        else:
            scaling = 1.0
        
        return scaling
    
    def get_position_limits(
        self,
        symbol: str,
        portfolio_value: float
    ) -> Dict[str, float]:
        """
        Get position size limits based on risk budget.
        
        Args:
            symbol: Symbol
            portfolio_value: Total portfolio value
            
        Returns:
            Dict with max_position_value, max_position_pct
        """
        if self.current_budget is None:
            return {
                'max_position_value': portfolio_value * 0.10,
                'max_position_pct': 0.10
            }
        
        position_budget = self.current_budget.position_budgets.get(symbol, 0)
        
        # Assume volatility of 30% for position
        # position_vol * position_weight = position_budget
        # position_weight = position_budget / position_vol
        assumed_vol = 0.30
        max_position_pct = position_budget / assumed_vol
        
        # Cap at 20% of portfolio
        max_position_pct = min(max_position_pct, 0.20)
        
        return {
            'max_position_value': portfolio_value * max_position_pct,
            'max_position_pct': max_position_pct
        }
    
    def get_budget_history(
        self
    ) -> pd.DataFrame:
        """Get budget history as DataFrame."""
        if len(self.budget_history) == 0:
            return pd.DataFrame()
        
        data = []
        for budget in self.budget_history:
            data.append({
                'timestamp': budget.timestamp,
                'total_budget': budget.total_budget,
                'utilization': budget.utilization,
                'n_strategies': len(budget.strategy_budgets),
                'n_positions': len(budget.position_budgets),
            })
        
        return pd.DataFrame(data).set_index('timestamp')
    
    def get_utilization_report(
        self
    ) -> Dict:
        """Get detailed utilization report."""
        if self.current_budget is None:
            return {}
        
        budget = self.current_budget
        
        return {
            'total_budget': budget.total_budget,
            'utilization': budget.utilization,
            'over_budget': budget.utilization > 1.0,
            'rebalance_needed': self.check_rebalance_needed(),
            'strategy_budgets': budget.strategy_budgets,
            'largest_position_budget': max(budget.position_budgets.values()) if budget.position_budgets else 0,
            'smallest_position_budget': min(budget.position_budgets.values()) if budget.position_budgets else 0,
        }


class RiskParityAllocator:
    """
    Risk parity allocation.
    
    Allocates capital to equalize risk contribution across assets.
    """
    
    def __init__(self):
        """Initialize risk parity allocator."""
        logger.info("Initialized RiskParityAllocator")
    
    def calculate_weights(
        self,
        covariance_matrix: pd.DataFrame,
        target_vol: float = 0.15
    ) -> pd.Series:
        """
        Calculate risk parity weights.
        
        Args:
            covariance_matrix: Covariance matrix
            target_vol: Target portfolio volatility
            
        Returns:
            Series of weights
        """
        n_assets = len(covariance_matrix)
        
        # Start with equal weights
        weights = np.ones(n_assets) / n_assets
        
        # Iterative optimization (simple approach)
        for _ in range(100):
            # Calculate marginal risk contributions
            portfolio_var = np.dot(weights, np.dot(covariance_matrix.values, weights))
            portfolio_vol = np.sqrt(portfolio_var)
            
            if portfolio_vol == 0:
                break
            
            marginal_contrib = np.dot(covariance_matrix.values, weights) / portfolio_vol
            risk_contrib = marginal_contrib * weights
            
            # Target risk contribution (equal for all)
            target_contrib = portfolio_vol / n_assets
            
            # Adjust weights
            adjustment = target_contrib / (risk_contrib + 1e-9)
            weights = weights * adjustment
            
            # Normalize
            weights = weights / weights.sum()
        
        # Scale to target volatility
        portfolio_vol = np.sqrt(np.dot(weights, np.dot(covariance_matrix.values, weights)))
        if portfolio_vol > 0:
            scale = target_vol / portfolio_vol
            weights = weights * scale
        
        return pd.Series(weights, index=covariance_matrix.index)

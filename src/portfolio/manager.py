"""
Portfolio Management System
Manages positions, allocation, and rebalancing
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger
import cvxpy as cp

class PortfolioManager:
    """Portfolio management and optimization"""

    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions = {}
        self.cash = initial_capital
        self.equity_curve = [initial_capital]
        self.trades = []
        logger.info(f"Portfolio Manager initialized with ${initial_capital:,.2f}")

    def optimize_allocation(self, candidates: List[Dict]) -> Dict:
        """Optimize portfolio allocation using mean-variance optimization"""
        if not candidates:
            return {}
        
        n = len(candidates)
        symbols = [c['symbol'] for c in candidates]
        
        # Expected returns (simplified)
        expected_returns = np.array([c.get('score', 0.5) for c in candidates])
        
        # Covariance matrix (simplified - in production, use historical data)
        cov_matrix = np.eye(n) * 0.02  # 2% variance, uncorrelated
        
        # Optimization variables
        weights = cp.Variable(n)
        
        # Objective: maximize return - risk
        risk_aversion = 2.0
        portfolio_return = expected_returns @ weights
        portfolio_risk = cp.quad_form(weights, cov_matrix)
        objective = cp.Maximize(portfolio_return - risk_aversion * portfolio_risk)
        
        # Constraints
        constraints = [
            cp.sum(weights) == 1,
            weights >= 0,
            weights <= 0.2  # Max 20% per position
        ]
        
        # Solve
        problem = cp.Problem(objective, constraints)
        try:
            problem.solve()
            
            if problem.status == 'optimal':
                allocation = {}
                for i, symbol in enumerate(symbols):
                    if weights.value[i] > 0.01:  # Minimum 1% allocation
                        allocation[symbol] = {
                            'symbol': symbol,
                            'weight': weights.value[i],
                            'action': candidates[i]['action'],
                            'quantity': int(weights.value[i] * self.current_capital / 100)  # Placeholder
                        }
                return allocation
        except Exception as e:
            logger.error(f"Optimization failed: {e}")
        
        # Fallback: equal weight
        equal_weight = 1.0 / n
        allocation = {}
        for c in candidates:
            allocation[c['symbol']] = {
                'symbol': c['symbol'],
                'weight': equal_weight,
                'action': c['action'],
                'quantity': int(equal_weight * self.current_capital / 100)
            }
        return allocation

    def update_state(self, positions: Dict, account: Dict):
        """Update portfolio state"""
        self.positions = positions
        self.cash = account.get('cash', 0)
        self.current_capital = account.get('portfolio_value', 0)
        self.equity_curve.append(self.current_capital)

    def calculate_returns(self) -> np.ndarray:
        """Calculate portfolio returns"""
        if len(self.equity_curve) < 2:
            return np.array([])
        equity = np.array(self.equity_curve)
        returns = np.diff(equity) / equity[:-1]
        return returns

    def get_performance_metrics(self) -> Dict:
        """Calculate portfolio performance metrics"""
        returns = self.calculate_returns()
        
        if len(returns) == 0:
            return {
                'total_return': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'win_rate': 0.0
            }
        
        total_return = (self.current_capital / self.initial_capital - 1) * 100
        
        # Sharpe ratio
        if np.std(returns) > 0:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe = 0.0
        
        # Max drawdown
        equity = np.array(self.equity_curve)
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max
        max_dd = abs(np.min(drawdown))
        
        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd,
            'current_value': self.current_capital,
            'cash': self.cash,
            'num_positions': len(self.positions)
        }

    def rebalance(self, target_allocation: Dict) -> List:
        """Calculate rebalancing trades"""
        trades = []
        
        # Calculate current allocation
        current_allocation = {}
        for symbol, pos in self.positions.items():
            current_allocation[symbol] = pos.get('value', 0) / self.current_capital
        
        # Calculate trades needed
        for symbol, target in target_allocation.items():
            current_weight = current_allocation.get(symbol, 0)
            target_weight = target['weight']
            
            weight_diff = target_weight - current_weight
            
            if abs(weight_diff) > 0.02:  # 2% threshold
                trades.append({
                    'symbol': symbol,
                    'action': 'buy' if weight_diff > 0 else 'sell',
                    'amount': abs(weight_diff) * self.current_capital
                })
        
        return trades

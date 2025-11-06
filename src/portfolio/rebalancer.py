"""
Portfolio rebalancing engine.

Automatic rebalancing to maintain target weights with transaction cost optimization.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
import pandas as pd
import numpy as np
from loguru import logger


class RebalanceMethod(Enum):
    """Rebalancing methods."""
    PERIODIC = "periodic"  # Calendar-based
    THRESHOLD = "threshold"  # Deviation-based
    ADAPTIVE = "adaptive"  # Volatility-adjusted
    COST_OPTIMIZED = "cost_optimized"  # Minimize transaction costs


@dataclass
class RebalanceResult:
    """Rebalancing result."""
    timestamp: datetime
    trades: Dict[str, float]  # symbol -> trade size
    estimated_cost: float
    current_weights: Dict[str, float]
    target_weights: Dict[str, float]
    weight_deviations: Dict[str, float]
    reason: str


class Rebalancer:
    """
    Portfolio rebalancing engine.
    
    Determines when and how to rebalance portfolio to maintain target weights
    while minimizing transaction costs.
    """
    
    def __init__(
        self,
        method: RebalanceMethod = RebalanceMethod.THRESHOLD,
        threshold: float = 0.05,  # 5% deviation triggers rebalance
        min_trade_size: float = 100.0,  # Minimum trade size
        max_turnover: float = 0.50,  # Max 50% turnover per rebalance
        transaction_cost: float = 0.001,  # 10 bps per trade
    ):
        """
        Initialize rebalancer.
        
        Args:
            method: Rebalancing method
            threshold: Deviation threshold for rebalancing
            min_trade_size: Minimum trade size to execute
            max_turnover: Maximum portfolio turnover per rebalance
            transaction_cost: Transaction cost per trade
        """
        self.method = method
        self.threshold = threshold
        self.min_trade_size = min_trade_size
        self.max_turnover = max_turnover
        self.transaction_cost = transaction_cost
        
        self.rebalance_history: List[RebalanceResult] = []
        
        logger.info(
            f"Initialized Rebalancer: method={method.value}, "
            f"threshold={threshold:.1%}"
        )
    
    def check_rebalance_needed(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        volatilities: Optional[Dict[str, float]] = None
    ) -> bool:
        """
        Check if rebalancing is needed.
        
        Args:
            current_weights: Current portfolio weights
            target_weights: Target weights
            volatilities: Optional volatilities for adaptive method
            
        Returns:
            True if rebalancing needed
        """
        if self.method == RebalanceMethod.THRESHOLD:
            return self._threshold_check(current_weights, target_weights)
        
        elif self.method == RebalanceMethod.ADAPTIVE:
            return self._adaptive_check(current_weights, target_weights, volatilities)
        
        else:
            # PERIODIC and COST_OPTIMIZED require external trigger
            return False
    
    def _threshold_check(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float]
    ) -> bool:
        """Check if any position exceeds threshold deviation."""
        max_deviation = 0
        
        for symbol in set(current_weights.keys()) | set(target_weights.keys()):
            current = current_weights.get(symbol, 0)
            target = target_weights.get(symbol, 0)
            deviation = abs(current - target)
            max_deviation = max(max_deviation, deviation)
        
        return max_deviation > self.threshold
    
    def _adaptive_check(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        volatilities: Optional[Dict[str, float]]
    ) -> bool:
        """Adaptive threshold based on volatility."""
        if volatilities is None:
            return self._threshold_check(current_weights, target_weights)
        
        # Adjust threshold based on average portfolio volatility
        avg_vol = np.mean(list(volatilities.values()))
        
        # Higher vol -> wider threshold (less frequent rebalancing)
        adjusted_threshold = self.threshold * (1 + avg_vol)
        
        max_deviation = 0
        for symbol in set(current_weights.keys()) | set(target_weights.keys()):
            current = current_weights.get(symbol, 0)
            target = target_weights.get(symbol, 0)
            deviation = abs(current - target)
            max_deviation = max(max_deviation, deviation)
        
        return max_deviation > adjusted_threshold
    
    def calculate_rebalance(
        self,
        current_positions: Dict[str, float],  # symbol -> quantity
        current_prices: Dict[str, float],  # symbol -> price
        target_weights: Dict[str, float],  # symbol -> target weight
        portfolio_value: float
    ) -> RebalanceResult:
        """
        Calculate rebalancing trades.
        
        Args:
            current_positions: Current positions (shares)
            current_prices: Current prices
            target_weights: Target portfolio weights
            portfolio_value: Total portfolio value
            
        Returns:
            RebalanceResult with trades
        """
        # Calculate current weights
        current_weights = {}
        for symbol, quantity in current_positions.items():
            if symbol in current_prices:
                value = quantity * current_prices[symbol]
                current_weights[symbol] = value / portfolio_value if portfolio_value > 0 else 0
        
        # Calculate target positions
        target_positions = {}
        for symbol, weight in target_weights.items():
            target_value = weight * portfolio_value
            if symbol in current_prices and current_prices[symbol] > 0:
                target_positions[symbol] = target_value / current_prices[symbol]
            else:
                target_positions[symbol] = 0
        
        # Calculate trades
        trades = {}
        total_turnover = 0
        
        all_symbols = set(current_positions.keys()) | set(target_positions.keys())
        
        for symbol in all_symbols:
            current_qty = current_positions.get(symbol, 0)
            target_qty = target_positions.get(symbol, 0)
            trade_qty = target_qty - current_qty
            
            # Check minimum trade size
            if symbol in current_prices:
                trade_value = abs(trade_qty * current_prices[symbol])
                
                if trade_value >= self.min_trade_size:
                    trades[symbol] = trade_qty
                    total_turnover += trade_value
        
        # Check turnover limit
        turnover_pct = total_turnover / portfolio_value if portfolio_value > 0 else 0
        
        if turnover_pct > self.max_turnover:
            logger.warning(
                f"Turnover {turnover_pct:.1%} exceeds limit {self.max_turnover:.1%}, "
                "scaling down trades"
            )
            scale_factor = self.max_turnover / turnover_pct
            trades = {symbol: qty * scale_factor for symbol, qty in trades.items()}
            total_turnover *= scale_factor
        
        # Estimate transaction costs
        estimated_cost = total_turnover * self.transaction_cost
        
        # Calculate deviations
        weight_deviations = {}
        for symbol in set(current_weights.keys()) | set(target_weights.keys()):
            current = current_weights.get(symbol, 0)
            target = target_weights.get(symbol, 0)
            weight_deviations[symbol] = current - target
        
        # Determine reason
        max_deviation = max(abs(d) for d in weight_deviations.values()) if weight_deviations else 0
        reason = f"Weight deviation: {max_deviation:.2%}"
        
        result = RebalanceResult(
            timestamp=datetime.now(),
            trades=trades,
            estimated_cost=estimated_cost,
            current_weights=current_weights,
            target_weights=target_weights,
            weight_deviations=weight_deviations,
            reason=reason
        )
        
        self.rebalance_history.append(result)
        
        logger.info(
            f"Rebalance calculated: {len(trades)} trades, "
            f"cost=${estimated_cost:,.2f}, turnover={turnover_pct:.1%}"
        )
        
        return result
    
    def get_rebalance_schedule(
        self,
        frequency: str = 'monthly'  # 'daily', 'weekly', 'monthly', 'quarterly'
    ) -> List[datetime]:
        """
        Get periodic rebalancing schedule.
        
        Args:
            frequency: Rebalancing frequency
            
        Returns:
            List of rebalance dates
        """
        # Placeholder - would generate actual schedule
        return []
    
    def optimize_rebalance_timing(
        self,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        volatility_forecast: Optional[Dict[str, float]] = None
    ) -> Dict:
        """
        Optimize rebalancing timing to minimize costs.
        
        Args:
            current_weights: Current weights
            target_weights: Target weights
            volatility_forecast: Forecasted volatilities
            
        Returns:
            Dict with optimal timing recommendation
        """
        # Calculate urgency based on deviations
        deviations = {
            symbol: abs(current_weights.get(symbol, 0) - target_weights.get(symbol, 0))
            for symbol in set(current_weights.keys()) | set(target_weights.keys())
        }
        
        max_deviation = max(deviations.values()) if deviations else 0
        urgency_score = max_deviation / self.threshold
        
        # High urgency -> rebalance now
        # Low urgency -> can wait for lower vol/costs
        
        recommendation = {
            'urgency_score': urgency_score,
            'max_deviation': max_deviation,
            'threshold': self.threshold,
            'recommendation': 'immediate' if urgency_score > 1.5 else 'wait' if urgency_score < 0.5 else 'monitor'
        }
        
        return recommendation
    
    def get_rebalance_stats(self) -> pd.DataFrame:
        """Get rebalancing statistics."""
        if len(self.rebalance_history) == 0:
            return pd.DataFrame()
        
        stats_data = []
        for result in self.rebalance_history:
            stats_data.append({
                'timestamp': result.timestamp,
                'num_trades': len(result.trades),
                'estimated_cost': result.estimated_cost,
                'max_deviation': max(abs(d) for d in result.weight_deviations.values()),
                'reason': result.reason
            })
        
        return pd.DataFrame(stats_data)

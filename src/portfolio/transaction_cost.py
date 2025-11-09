"""
Transaction cost modeling and optimization.

Models various transaction costs and optimizes trade execution.
"""

from dataclasses import dataclass
from enum import Enum

from loguru import logger
import numpy as np
import pandas as pd


class CostModel(Enum):
    """Transaction cost models."""
    FIXED = "fixed"  # Fixed cost per trade
    LINEAR = "linear"  # Linear in trade size
    MARKET_IMPACT = "market_impact"  # Square root model
    COMPREHENSIVE = "comprehensive"  # All costs combined


@dataclass
class TransactionCostModel:
    """Transaction cost model parameters."""
    fixed_cost: float = 1.0  # Fixed cost per trade
    linear_cost: float = 0.001  # 10 bps commission
    market_impact_coef: float = 0.1  # Market impact coefficient
    spread_cost: float = 0.0005  # 5 bps spread

    def calculate_cost(
        self,
        trade_value: float,
        volume: float,
        volatility: float = 0.20
    ) -> float:
        """
        Calculate total transaction cost.
        
        Args:
            trade_value: Trade size in dollars
            volume: Daily trading volume in dollars
            volatility: Asset volatility
            
        Returns:
            Total transaction cost
        """
        # Fixed cost
        fixed = self.fixed_cost if trade_value > 0 else 0

        # Linear commission
        linear = abs(trade_value) * self.linear_cost

        # Market impact (square root model)
        if volume > 0:
            participation_rate = abs(trade_value) / volume
            impact = abs(trade_value) * self.market_impact_coef * volatility * np.sqrt(participation_rate)
        else:
            impact = 0

        # Spread cost
        spread = abs(trade_value) * self.spread_cost

        total_cost = fixed + linear + impact + spread

        return total_cost


class TradingCostOptimizer:
    """
    Optimizes trade execution to minimize transaction costs.
    
    Features:
    - Trade splitting (TWAP/VWAP)
    - Optimal execution horizon
    - Volume participation limits
    - Cost-benefit analysis
    """

    def __init__(
        self,
        cost_model: TransactionCostModel = None,
        max_participation_rate: float = 0.10,  # Max 10% of daily volume
        max_execution_days: int = 5  # Max days to execute
    ):
        """
        Initialize cost optimizer.
        
        Args:
            cost_model: Transaction cost model
            max_participation_rate: Max volume participation rate
            max_execution_days: Maximum days to execute large orders
        """
        self.cost_model = cost_model or TransactionCostModel()
        self.max_participation_rate = max_participation_rate
        self.max_execution_days = max_execution_days

        logger.info("Initialized TradingCostOptimizer")

    def optimize_execution(
        self,
        trade_value: float,
        daily_volume: float,
        volatility: float,
        urgency: str = "normal"  # 'low', 'normal', 'high'
    ) -> dict:
        """
        Optimize trade execution strategy.
        
        Args:
            trade_value: Desired trade size
            daily_volume: Average daily trading volume
            volatility: Asset volatility
            urgency: Execution urgency
            
        Returns:
            Dict with execution plan
        """
        # Calculate max trade size per day
        max_daily_trade = daily_volume * self.max_participation_rate

        # Determine execution horizon
        if abs(trade_value) <= max_daily_trade:
            # Can execute in one day
            execution_days = 1
            daily_trades = [trade_value]
        else:
            # Need to split across multiple days
            execution_days = min(
                int(np.ceil(abs(trade_value) / max_daily_trade)),
                self.max_execution_days
            )

            # Adjust based on urgency
            if urgency == "high":
                execution_days = max(1, execution_days // 2)
            elif urgency == "low":
                execution_days = min(execution_days * 2, self.max_execution_days)

            # Split trade equally across days (TWAP strategy)
            daily_trade_size = trade_value / execution_days
            daily_trades = [daily_trade_size] * execution_days

        # Calculate costs
        total_cost = sum(
            self.cost_model.calculate_cost(trade, daily_volume, volatility)
            for trade in daily_trades
        )

        # Cost as percentage of trade value
        cost_pct = total_cost / abs(trade_value) if trade_value != 0 else 0

        plan = {
            "execution_days": execution_days,
            "daily_trades": daily_trades,
            "total_cost": total_cost,
            "cost_percentage": cost_pct,
            "strategy": "TWAP",
            "urgency": urgency
        }

        logger.info(
            f"Execution plan: {execution_days} days, "
            f"cost={cost_pct:.3%}"
        )

        return plan

    def analyze_trade_timing(
        self,
        trade_value: float,
        volatility_forecast: pd.Series,  # Forecasted volatility
        volume_forecast: pd.Series  # Forecasted volume
    ) -> dict:
        """
        Analyze optimal timing for trade execution.
        
        Args:
            trade_value: Trade size
            volatility_forecast: Volatility forecast by day
            volume_forecast: Volume forecast by day
            
        Returns:
            Dict with timing recommendation
        """
        # Calculate expected cost for each day
        daily_costs = []

        for day, (vol, volume) in enumerate(zip(volatility_forecast, volume_forecast)):
            cost = self.cost_model.calculate_cost(trade_value, volume, vol)
            daily_costs.append({
                "day": day,
                "volatility": vol,
                "volume": volume,
                "cost": cost,
                "cost_pct": cost / abs(trade_value) if trade_value != 0 else 0
            })

        # Find optimal day (lowest cost)
        optimal_day = min(daily_costs, key=lambda x: x["cost"])

        return {
            "optimal_day": optimal_day["day"],
            "expected_cost": optimal_day["cost"],
            "daily_costs": pd.DataFrame(daily_costs)
        }

    def compare_execution_strategies(
        self,
        trade_value: float,
        daily_volume: float,
        volatility: float
    ) -> pd.DataFrame:
        """
        Compare different execution strategies.
        
        Args:
            trade_value: Trade size
            daily_volume: Daily volume
            volatility: Volatility
            
        Returns:
            DataFrame comparing strategies
        """
        strategies = []

        # 1. Immediate execution (1 day)
        immediate_cost = self.cost_model.calculate_cost(trade_value, daily_volume, volatility)
        strategies.append({
            "strategy": "Immediate",
            "days": 1,
            "cost": immediate_cost,
            "cost_pct": immediate_cost / abs(trade_value) if trade_value != 0 else 0
        })

        # 2. TWAP over 3 days
        twap_3d_cost = sum(
            self.cost_model.calculate_cost(trade_value / 3, daily_volume, volatility)
            for _ in range(3)
        )
        strategies.append({
            "strategy": "TWAP_3D",
            "days": 3,
            "cost": twap_3d_cost,
            "cost_pct": twap_3d_cost / abs(trade_value) if trade_value != 0 else 0
        })

        # 3. TWAP over 5 days
        twap_5d_cost = sum(
            self.cost_model.calculate_cost(trade_value / 5, daily_volume, volatility)
            for _ in range(5)
        )
        strategies.append({
            "strategy": "TWAP_5D",
            "days": 5,
            "cost": twap_5d_cost,
            "cost_pct": twap_5d_cost / abs(trade_value) if trade_value != 0 else 0
        })

        # 4. Volume participation (10% of daily volume)
        max_daily = daily_volume * self.max_participation_rate
        vp_days = int(np.ceil(abs(trade_value) / max_daily))
        vp_cost = sum(
            self.cost_model.calculate_cost(max_daily, daily_volume, volatility)
            for _ in range(vp_days)
        )
        strategies.append({
            "strategy": "Volume_Participation",
            "days": vp_days,
            "cost": vp_cost,
            "cost_pct": vp_cost / abs(trade_value) if trade_value != 0 else 0
        })

        df = pd.DataFrame(strategies)
        df = df.sort_values("cost")

        return df

    def estimate_slippage(
        self,
        trade_value: float,
        order_book_depth: dict[float, float]  # price -> quantity
    ) -> float:
        """
        Estimate slippage from order book.
        
        Args:
            trade_value: Trade size
            order_book_depth: Order book (price levels)
            
        Returns:
            Estimated slippage in basis points
        """
        # Simplified slippage estimation
        # In production, would use actual order book analysis

        if not order_book_depth:
            return 0

        # Get total liquidity
        total_liquidity = sum(order_book_depth.values())

        if total_liquidity == 0:
            return 100  # 100 bps slippage if no liquidity

        # Estimate slippage as proportion of trade to liquidity
        slippage_bps = (abs(trade_value) / total_liquidity) * 100

        # Cap at reasonable maximum
        slippage_bps = min(slippage_bps, 200)

        return slippage_bps

    def calculate_implementation_shortfall(
        self,
        decision_price: float,
        execution_prices: list[float],
        quantities: list[float]
    ) -> dict:
        """
        Calculate implementation shortfall.
        
        Args:
            decision_price: Price at decision time
            execution_prices: Actual execution prices
            quantities: Quantities executed at each price
            
        Returns:
            Dict with shortfall metrics
        """
        # Volume-weighted average execution price
        total_quantity = sum(quantities)

        if total_quantity == 0:
            return {"shortfall": 0, "shortfall_bps": 0}

        vwap = sum(p * q for p, q in zip(execution_prices, quantities)) / total_quantity

        # Implementation shortfall
        shortfall = abs(vwap - decision_price) * total_quantity
        shortfall_bps = abs(vwap - decision_price) / decision_price * 10000

        return {
            "decision_price": decision_price,
            "vwap": vwap,
            "shortfall": shortfall,
            "shortfall_bps": shortfall_bps,
            "total_quantity": total_quantity
        }

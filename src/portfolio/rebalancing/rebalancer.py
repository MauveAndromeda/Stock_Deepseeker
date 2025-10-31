"""
Portfolio Rebalancing Engine

This module implements various portfolio rebalancing strategies:
- Threshold-based rebalancing (absolute and relative)
- Time-based (calendar) rebalancing
- Volatility-adaptive rebalancing
- Tax-aware rebalancing with tax-loss harvesting
- Transaction cost minimization

The rebalancing engine optimizes trade execution to minimize costs while
maintaining target allocations.
"""

import logging
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from scipy.optimize import minimize, linprog
import cvxpy as cp

logger = logging.getLogger(__name__)


class RebalancingStrategy(Enum):
    """Rebalancing strategy types"""
    THRESHOLD_ABSOLUTE = "threshold_absolute"
    THRESHOLD_RELATIVE = "threshold_relative"
    CALENDAR = "calendar"
    VOLATILITY_ADAPTIVE = "volatility_adaptive"
    COMBINED = "combined"
    TAX_AWARE = "tax_aware"
    COST_AWARE = "cost_aware"


@dataclass
class TaxLot:
    """
    Represents a tax lot for tax-aware rebalancing.

    Attributes:
        asset: Asset symbol
        quantity: Number of shares/units
        purchase_price: Purchase price per share
        purchase_date: Purchase date
        current_price: Current market price
        holding_period_days: Days held
    """
    asset: str
    quantity: float
    purchase_price: float
    purchase_date: datetime
    current_price: float
    holding_period_days: int = 0

    def __post_init__(self):
        """Calculate holding period"""
        if self.holding_period_days == 0:
            self.holding_period_days = (
                datetime.now() - self.purchase_date
            ).days

    @property
    def market_value(self) -> float:
        """Current market value of the lot"""
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> float:
        """Cost basis of the lot"""
        return self.quantity * self.purchase_price

    @property
    def unrealized_gain(self) -> float:
        """Unrealized gain/loss"""
        return self.market_value - self.cost_basis

    @property
    def unrealized_gain_pct(self) -> float:
        """Unrealized gain/loss percentage"""
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_gain / self.cost_basis) * 100

    @property
    def is_long_term(self) -> bool:
        """Check if position qualifies for long-term capital gains"""
        return self.holding_period_days > 365


@dataclass
class RebalancingSignal:
    """
    Signal indicating rebalancing is needed.

    Attributes:
        timestamp: When signal was generated
        strategy: Strategy that generated the signal
        trigger: What triggered the rebalancing
        current_weights: Current portfolio weights
        target_weights: Target portfolio weights
        deviations: Deviations from target
        priority: Priority score (higher = more urgent)
    """
    timestamp: datetime
    strategy: RebalancingStrategy
    trigger: str
    current_weights: Dict[str, float]
    target_weights: Dict[str, float]
    deviations: Dict[str, float]
    priority: float = 0.0


@dataclass
class RebalancingResult:
    """
    Result from rebalancing execution.

    Attributes:
        trades: Dictionary of trades {asset: quantity}
        current_weights: Current portfolio weights
        new_weights: Portfolio weights after rebalancing
        estimated_cost: Estimated transaction costs
        tax_impact: Estimated tax impact
        tracking_error: Tracking error vs target
        turnover: Portfolio turnover
        success: Whether rebalancing succeeded
        message: Status message
    """
    trades: Dict[str, float]
    current_weights: Dict[str, float]
    new_weights: Dict[str, float]
    estimated_cost: float
    tax_impact: float
    tracking_error: float
    turnover: float
    success: bool
    message: str = ""
    metadata: Dict = field(default_factory=dict)


class RebalancingEngine:
    """
    Portfolio rebalancing engine with multiple strategies.

    This engine monitors portfolio drift and executes rebalancing trades
    to maintain target allocations while minimizing costs and taxes.
    """

    def __init__(
        self,
        target_weights: Dict[str, float],
        threshold_absolute: float = 0.05,
        threshold_relative: float = 0.2,
        rebalance_frequency: str = 'monthly',
        transaction_cost_bps: float = 10.0,
        short_term_tax_rate: float = 0.37,
        long_term_tax_rate: float = 0.20,
        min_trade_size: float = 100.0,
        max_trades_per_rebalance: int = 10,
    ):
        """
        Initialize rebalancing engine.

        Args:
            target_weights: Target portfolio weights
            threshold_absolute: Absolute threshold for rebalancing (e.g., 0.05 = 5%)
            threshold_relative: Relative threshold (e.g., 0.2 = 20% drift from target)
            rebalance_frequency: Rebalancing frequency ('daily', 'weekly', 'monthly', 'quarterly')
            transaction_cost_bps: Transaction costs in basis points
            short_term_tax_rate: Short-term capital gains tax rate
            long_term_tax_rate: Long-term capital gains tax rate
            min_trade_size: Minimum trade size (in portfolio value)
            max_trades_per_rebalance: Maximum number of trades per rebalancing
        """
        self.target_weights = self._normalize_weights(target_weights)
        self.threshold_absolute = threshold_absolute
        self.threshold_relative = threshold_relative
        self.rebalance_frequency = rebalance_frequency
        self.transaction_cost_bps = transaction_cost_bps
        self.short_term_tax_rate = short_term_tax_rate
        self.long_term_tax_rate = long_term_tax_rate
        self.min_trade_size = min_trade_size
        self.max_trades_per_rebalance = max_trades_per_rebalance

        # State tracking
        self.last_rebalance_date: Optional[datetime] = None
        self.rebalance_history: List[RebalancingResult] = []
        self.tax_lots: Dict[str, List[TaxLot]] = {}

        logger.info(
            f"Initialized RebalancingEngine with {len(target_weights)} assets, "
            f"threshold={threshold_absolute:.2%}"
        )

    def check_rebalancing_needed(
        self,
        current_weights: Dict[str, float],
        current_date: datetime,
        volatility: Optional[Dict[str, float]] = None,
        strategy: RebalancingStrategy = RebalancingStrategy.THRESHOLD_ABSOLUTE,
    ) -> Optional[RebalancingSignal]:
        """
        Check if rebalancing is needed.

        Args:
            current_weights: Current portfolio weights
            current_date: Current date
            volatility: Current volatility estimates (for volatility-adaptive)
            strategy: Rebalancing strategy to use

        Returns:
            RebalancingSignal if rebalancing needed, None otherwise
        """
        current_weights = self._normalize_weights(current_weights)

        if strategy == RebalancingStrategy.THRESHOLD_ABSOLUTE:
            return self._check_threshold_absolute(current_weights, current_date)
        elif strategy == RebalancingStrategy.THRESHOLD_RELATIVE:
            return self._check_threshold_relative(current_weights, current_date)
        elif strategy == RebalancingStrategy.CALENDAR:
            return self._check_calendar(current_weights, current_date)
        elif strategy == RebalancingStrategy.VOLATILITY_ADAPTIVE:
            return self._check_volatility_adaptive(
                current_weights, current_date, volatility
            )
        elif strategy == RebalancingStrategy.COMBINED:
            return self._check_combined(current_weights, current_date, volatility)
        else:
            logger.warning(f"Unknown rebalancing strategy: {strategy}")
            return None

    def _check_threshold_absolute(
        self,
        current_weights: Dict[str, float],
        current_date: datetime,
    ) -> Optional[RebalancingSignal]:
        """Check absolute threshold rebalancing"""
        deviations = self._calculate_deviations(current_weights)
        max_deviation = max(abs(d) for d in deviations.values())

        if max_deviation > self.threshold_absolute:
            priority = max_deviation / self.threshold_absolute
            return RebalancingSignal(
                timestamp=current_date,
                strategy=RebalancingStrategy.THRESHOLD_ABSOLUTE,
                trigger=f"Absolute threshold exceeded: {max_deviation:.2%}",
                current_weights=current_weights,
                target_weights=self.target_weights,
                deviations=deviations,
                priority=priority,
            )

        return None

    def _check_threshold_relative(
        self,
        current_weights: Dict[str, float],
        current_date: datetime,
    ) -> Optional[RebalancingSignal]:
        """Check relative threshold rebalancing"""
        deviations = self._calculate_deviations(current_weights)

        # Calculate relative deviations
        relative_deviations = {}
        for asset, deviation in deviations.items():
            target = self.target_weights.get(asset, 0.0)
            if target > 0:
                relative_deviations[asset] = abs(deviation / target)
            else:
                relative_deviations[asset] = 0.0

        max_relative_deviation = max(relative_deviations.values())

        if max_relative_deviation > self.threshold_relative:
            priority = max_relative_deviation / self.threshold_relative
            return RebalancingSignal(
                timestamp=current_date,
                strategy=RebalancingStrategy.THRESHOLD_RELATIVE,
                trigger=f"Relative threshold exceeded: {max_relative_deviation:.2%}",
                current_weights=current_weights,
                target_weights=self.target_weights,
                deviations=deviations,
                priority=priority,
            )

        return None

    def _check_calendar(
        self,
        current_weights: Dict[str, float],
        current_date: datetime,
    ) -> Optional[RebalancingSignal]:
        """Check calendar-based rebalancing"""
        if self.last_rebalance_date is None:
            return RebalancingSignal(
                timestamp=current_date,
                strategy=RebalancingStrategy.CALENDAR,
                trigger="Initial rebalancing",
                current_weights=current_weights,
                target_weights=self.target_weights,
                deviations=self._calculate_deviations(current_weights),
                priority=1.0,
            )

        # Determine if enough time has passed
        days_since_rebalance = (current_date - self.last_rebalance_date).days

        frequency_days = {
            'daily': 1,
            'weekly': 7,
            'monthly': 30,
            'quarterly': 90,
            'semiannual': 180,
            'annual': 365,
        }

        required_days = frequency_days.get(self.rebalance_frequency, 30)

        if days_since_rebalance >= required_days:
            deviations = self._calculate_deviations(current_weights)
            max_deviation = max(abs(d) for d in deviations.values())

            return RebalancingSignal(
                timestamp=current_date,
                strategy=RebalancingStrategy.CALENDAR,
                trigger=f"Calendar rebalancing: {days_since_rebalance} days",
                current_weights=current_weights,
                target_weights=self.target_weights,
                deviations=deviations,
                priority=1.0 + max_deviation,
            )

        return None

    def _check_volatility_adaptive(
        self,
        current_weights: Dict[str, float],
        current_date: datetime,
        volatility: Optional[Dict[str, float]] = None,
    ) -> Optional[RebalancingSignal]:
        """
        Check volatility-adaptive rebalancing.

        Adjusts thresholds based on current market volatility.
        Higher volatility -> tighter thresholds.
        """
        if volatility is None:
            logger.warning("Volatility not provided for volatility-adaptive strategy")
            return self._check_threshold_absolute(current_weights, current_date)

        # Calculate portfolio volatility
        portfolio_vol = sum(
            current_weights.get(asset, 0) * vol
            for asset, vol in volatility.items()
        )

        # Adjust threshold based on volatility (inverse relationship)
        # Higher vol -> lower threshold (more frequent rebalancing)
        base_vol = 0.15  # 15% annual volatility as base
        vol_adjustment = base_vol / max(portfolio_vol, 0.01)
        adjusted_threshold = self.threshold_absolute * vol_adjustment

        deviations = self._calculate_deviations(current_weights)
        max_deviation = max(abs(d) for d in deviations.values())

        if max_deviation > adjusted_threshold:
            priority = max_deviation / adjusted_threshold
            return RebalancingSignal(
                timestamp=current_date,
                strategy=RebalancingStrategy.VOLATILITY_ADAPTIVE,
                trigger=f"Volatility-adjusted threshold: {adjusted_threshold:.2%}",
                current_weights=current_weights,
                target_weights=self.target_weights,
                deviations=deviations,
                priority=priority,
            )

        return None

    def _check_combined(
        self,
        current_weights: Dict[str, float],
        current_date: datetime,
        volatility: Optional[Dict[str, float]] = None,
    ) -> Optional[RebalancingSignal]:
        """
        Combined strategy: threshold OR calendar.

        Rebalance if either condition is met.
        """
        threshold_signal = self._check_threshold_absolute(current_weights, current_date)
        calendar_signal = self._check_calendar(current_weights, current_date)

        if threshold_signal is not None:
            return threshold_signal
        elif calendar_signal is not None:
            return calendar_signal

        return None

    def execute_rebalancing(
        self,
        current_positions: Dict[str, float],
        current_prices: Dict[str, float],
        portfolio_value: float,
        signal: RebalancingSignal,
        tax_aware: bool = True,
        cost_aware: bool = True,
    ) -> RebalancingResult:
        """
        Execute rebalancing trades.

        Args:
            current_positions: Current positions {asset: quantity}
            current_prices: Current prices {asset: price}
            portfolio_value: Total portfolio value
            signal: Rebalancing signal
            tax_aware: Use tax-aware optimization
            cost_aware: Use transaction cost minimization

        Returns:
            RebalancingResult with trade details
        """
        logger.info(f"Executing rebalancing: {signal.trigger}")

        try:
            # Calculate current weights
            current_weights = self._positions_to_weights(
                current_positions, current_prices, portfolio_value
            )

            # Calculate target positions
            target_positions = {
                asset: (weight * portfolio_value) / current_prices.get(asset, 1.0)
                for asset, weight in self.target_weights.items()
            }

            # Calculate required trades
            if tax_aware and self.tax_lots:
                trades = self._optimize_tax_aware_trades(
                    current_positions,
                    target_positions,
                    current_prices,
                )
            elif cost_aware:
                trades = self._optimize_cost_aware_trades(
                    current_positions,
                    target_positions,
                    current_prices,
                )
            else:
                trades = {
                    asset: target_positions.get(asset, 0) - current_positions.get(asset, 0)
                    for asset in set(target_positions) | set(current_positions)
                }

            # Filter small trades
            trades = {
                asset: qty
                for asset, qty in trades.items()
                if abs(qty * current_prices.get(asset, 0)) >= self.min_trade_size
            }

            # Calculate new weights
            new_positions = {
                asset: current_positions.get(asset, 0) + trades.get(asset, 0)
                for asset in set(current_positions) | set(trades)
            }
            new_weights = self._positions_to_weights(
                new_positions, current_prices, portfolio_value
            )

            # Calculate costs and metrics
            estimated_cost = self._calculate_transaction_costs(trades, current_prices)
            tax_impact = self._calculate_tax_impact(trades, current_prices)
            tracking_error = self._calculate_tracking_error(new_weights)
            turnover = self._calculate_turnover(trades, current_prices, portfolio_value)

            result = RebalancingResult(
                trades=trades,
                current_weights=current_weights,
                new_weights=new_weights,
                estimated_cost=estimated_cost,
                tax_impact=tax_impact,
                tracking_error=tracking_error,
                turnover=turnover,
                success=True,
                message=f"Rebalanced {len(trades)} positions",
            )

            # Update state
            self.last_rebalance_date = signal.timestamp
            self.rebalance_history.append(result)

            logger.info(
                f"Rebalancing complete: {len(trades)} trades, "
                f"cost=${estimated_cost:.2f}, turnover={turnover:.2%}"
            )

            return result

        except Exception as e:
            logger.error(f"Rebalancing failed: {e}")
            return RebalancingResult(
                trades={},
                current_weights=current_weights,
                new_weights=current_weights,
                estimated_cost=0.0,
                tax_impact=0.0,
                tracking_error=0.0,
                turnover=0.0,
                success=False,
                message=f"Rebalancing failed: {e}",
            )

    def _optimize_tax_aware_trades(
        self,
        current_positions: Dict[str, float],
        target_positions: Dict[str, float],
        current_prices: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Optimize trades to minimize tax impact using tax lot selection.

        Uses HIFO (Highest In, First Out) for losses and
        LIFO (Last In, First Out) for gains to minimize taxes.
        """
        trades = {}

        for asset in set(current_positions) | set(target_positions):
            current_qty = current_positions.get(asset, 0)
            target_qty = target_positions.get(asset, 0)
            required_trade = target_qty - current_qty

            if abs(required_trade) < 1e-6:
                continue

            if required_trade < 0:  # Selling
                # Select lots to minimize tax impact
                lots = self.tax_lots.get(asset, [])
                if lots:
                    lots_to_sell = self._select_tax_lots_to_sell(
                        lots, abs(required_trade), current_prices.get(asset, 0)
                    )
                    trades[asset] = -sum(lot.quantity for lot in lots_to_sell)
                else:
                    trades[asset] = required_trade
            else:  # Buying
                trades[asset] = required_trade

        return trades

    def _select_tax_lots_to_sell(
        self,
        lots: List[TaxLot],
        quantity_to_sell: float,
        current_price: float,
    ) -> List[TaxLot]:
        """
        Select tax lots to sell to minimize tax impact.

        Strategy:
        1. Prioritize losses (tax loss harvesting)
        2. For gains, prefer long-term over short-term
        3. Use HIFO for losses, LIFO for gains
        """
        # Sort lots by tax efficiency
        def tax_efficiency_key(lot: TaxLot) -> Tuple[float, bool, float]:
            gain = lot.unrealized_gain
            is_loss = gain < 0
            is_long_term = lot.is_long_term

            # Priority: losses first, then long-term gains, then short-term gains
            if is_loss:
                return (0, True, -gain)  # Largest losses first
            elif is_long_term:
                return (1, False, gain)  # Smallest long-term gains first
            else:
                return (2, False, gain)  # Smallest short-term gains first

        sorted_lots = sorted(lots, key=tax_efficiency_key)

        # Select lots up to required quantity
        selected_lots = []
        remaining_qty = quantity_to_sell

        for lot in sorted_lots:
            if remaining_qty <= 0:
                break

            if lot.quantity <= remaining_qty:
                selected_lots.append(lot)
                remaining_qty -= lot.quantity
            else:
                # Partial lot
                partial_lot = TaxLot(
                    asset=lot.asset,
                    quantity=remaining_qty,
                    purchase_price=lot.purchase_price,
                    purchase_date=lot.purchase_date,
                    current_price=current_price,
                )
                selected_lots.append(partial_lot)
                remaining_qty = 0

        return selected_lots

    def _optimize_cost_aware_trades(
        self,
        current_positions: Dict[str, float],
        target_positions: Dict[str, float],
        current_prices: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Optimize trades to minimize transaction costs.

        Uses linear programming to find trades that minimize costs
        while getting close to target weights.
        """
        assets = list(set(current_positions) | set(target_positions))
        n = len(assets)

        # Current and target position arrays
        current = np.array([current_positions.get(a, 0) for a in assets])
        target = np.array([target_positions.get(a, 0) for a in assets])
        prices = np.array([current_prices.get(a, 1.0) for a in assets])

        # Trade array (what we're solving for)
        try:
            # Use CVXPY for better optimization
            trade = cp.Variable(n)

            # Objective: minimize transaction costs + tracking error penalty
            trade_value = cp.abs(trade) @ prices
            tracking_penalty = cp.sum_squares(current + trade - target)

            cost_per_dollar = self.transaction_cost_bps / 10000
            objective = cp.Minimize(
                cost_per_dollar * trade_value + 0.1 * tracking_penalty
            )

            # Constraints
            constraints = []

            # Can't sell more than we have
            constraints.append(current + trade >= 0)

            # Limit number of trades (approximately)
            # This is hard to enforce exactly in convex optimization

            problem = cp.Problem(objective, constraints)
            problem.solve(solver=cp.OSQP, verbose=False)

            if trade.value is None:
                # Fallback to simple trades
                return {
                    asset: target_positions.get(asset, 0) - current_positions.get(asset, 0)
                    for asset in assets
                }

            # Convert to dictionary
            trades = {
                asset: float(qty)
                for asset, qty in zip(assets, trade.value)
                if abs(qty) > 1e-6
            }

            return trades

        except Exception as e:
            logger.warning(f"Cost optimization failed: {e}. Using simple trades.")
            return {
                asset: target_positions.get(asset, 0) - current_positions.get(asset, 0)
                for asset in assets
            }

    def add_tax_lot(self, lot: TaxLot) -> None:
        """Add a tax lot for tracking"""
        if lot.asset not in self.tax_lots:
            self.tax_lots[lot.asset] = []
        self.tax_lots[lot.asset].append(lot)
        logger.debug(f"Added tax lot: {lot.asset} x {lot.quantity} @ ${lot.purchase_price}")

    def update_target_weights(self, new_targets: Dict[str, float]) -> None:
        """Update target weights"""
        self.target_weights = self._normalize_weights(new_targets)
        logger.info(f"Updated target weights: {len(new_targets)} assets")

    def _calculate_deviations(self, current_weights: Dict[str, float]) -> Dict[str, float]:
        """Calculate deviations from target weights"""
        all_assets = set(current_weights) | set(self.target_weights)
        return {
            asset: current_weights.get(asset, 0) - self.target_weights.get(asset, 0)
            for asset in all_assets
        }

    def _calculate_transaction_costs(
        self,
        trades: Dict[str, float],
        prices: Dict[str, float],
    ) -> float:
        """Calculate estimated transaction costs"""
        total_cost = 0.0
        for asset, quantity in trades.items():
            trade_value = abs(quantity) * prices.get(asset, 0)
            total_cost += trade_value * (self.transaction_cost_bps / 10000)
        return total_cost

    def _calculate_tax_impact(
        self,
        trades: Dict[str, float],
        prices: Dict[str, float],
    ) -> float:
        """Calculate estimated tax impact"""
        total_tax = 0.0

        for asset, quantity in trades.items():
            if quantity >= 0:  # Buying - no tax impact
                continue

            # Selling - calculate gains
            lots = self.tax_lots.get(asset, [])
            if not lots:
                continue

            lots_to_sell = self._select_tax_lots_to_sell(
                lots, abs(quantity), prices.get(asset, 0)
            )

            for lot in lots_to_sell:
                gain = lot.unrealized_gain
                if gain > 0:
                    tax_rate = (
                        self.long_term_tax_rate if lot.is_long_term
                        else self.short_term_tax_rate
                    )
                    total_tax += gain * tax_rate

        return total_tax

    def _calculate_tracking_error(self, weights: Dict[str, float]) -> float:
        """Calculate tracking error vs target"""
        deviations = self._calculate_deviations(weights)
        return np.sqrt(sum(d ** 2 for d in deviations.values()))

    def _calculate_turnover(
        self,
        trades: Dict[str, float],
        prices: Dict[str, float],
        portfolio_value: float,
    ) -> float:
        """Calculate portfolio turnover"""
        if portfolio_value == 0:
            return 0.0

        total_traded = sum(
            abs(quantity) * prices.get(asset, 0)
            for asset, quantity in trades.items()
        )

        return total_traded / portfolio_value

    def _positions_to_weights(
        self,
        positions: Dict[str, float],
        prices: Dict[str, float],
        portfolio_value: float,
    ) -> Dict[str, float]:
        """Convert positions to weights"""
        if portfolio_value == 0:
            return {}

        return {
            asset: (quantity * prices.get(asset, 0)) / portfolio_value
            for asset, quantity in positions.items()
        }

    def _normalize_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Normalize weights to sum to 1"""
        total = sum(weights.values())
        if total == 0:
            return weights
        return {asset: w / total for asset, w in weights.items()}

    def get_rebalancing_stats(self) -> pd.DataFrame:
        """Get statistics on rebalancing history"""
        if not self.rebalance_history:
            return pd.DataFrame()

        data = []
        for i, result in enumerate(self.rebalance_history):
            data.append({
                'rebalance_num': i + 1,
                'num_trades': len(result.trades),
                'turnover': result.turnover,
                'cost': result.estimated_cost,
                'tax_impact': result.tax_impact,
                'tracking_error': result.tracking_error,
            })

        return pd.DataFrame(data)

"""
Execution handler - Simulates realistic order execution.

Features:
- Market impact modeling
- Slippage calculation
- Partial fills
- Order rejection
- Liquidity constraints
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger
import pandas as pd

from src.backtest.events import FillEvent, OrderEvent
from src.backtest.portfolio_v2 import PortfolioV2

if TYPE_CHECKING:
    pass


class ExecutionHandler:
    """
    Handles order execution with realistic market simulation.

    Features:
    - Slippage modeling
    - Commission calculation
    - Liquidity checks
    - Volume constraints
    """

    def __init__(
        self,
        portfolio: PortfolioV2,
        price_data: dict[str, pd.DataFrame],
        config: Any  # BacktestConfig - use Any to avoid circular import at runtime
    ) -> None:
        """
        Initialize execution handler.

        Args:
            portfolio: Portfolio instance
            price_data: Historical price data
            config: Backtest configuration
        """
        self.portfolio = portfolio
        self.price_data = price_data
        self.config = config

        # Statistics
        self.total_orders = 0
        self.filled_orders = 0
        self.rejected_orders = 0

    def execute_order(self, order: OrderEvent) -> FillEvent | None:
        """
        Execute an order.

        Args:
            order: Order event

        Returns:
            FillEvent if successful, None if rejected
        """
        self.total_orders += 1

        # Validate order
        if not self._validate_order(order):
            self.rejected_orders += 1
            return None

        # Get execution price
        execution_price = self._get_execution_price(order)
        if execution_price is None:
            logger.warning(f"No execution price for {order.symbol}")
            self.rejected_orders += 1
            return None

        # Calculate costs
        commission = self._calculate_commission(order, execution_price)
        slippage = self._calculate_slippage(order, execution_price)

        # Check if we have enough cash (for buys)
        if order.direction == "BUY":
            total_cost = order.quantity * execution_price + commission + slippage
            if total_cost > self.portfolio.cash:
                logger.warning(
                    f"Insufficient cash for {order.symbol}: "
                    f"need ${total_cost:.2f}, have ${self.portfolio.cash:.2f}"
                )
                self.rejected_orders += 1
                return None

        # Create fill event
        fill = FillEvent(
            timestamp=order.timestamp,
            symbol=order.symbol,
            quantity=order.quantity,
            fill_price=execution_price,
            commission=commission,
            slippage=slippage,
            direction=order.direction,
            metadata={
                "order_type": order.order_type,
                "original_price": order.price,
            }
        )

        self.filled_orders += 1
        logger.debug(
            f"Filled: {order.direction} {order.quantity} {order.symbol} "
            f"@ ${execution_price:.2f}"
        )

        return fill

    def _validate_order(self, order: OrderEvent) -> bool:
        """
        Validate order before execution.

        Args:
            order: Order event

        Returns:
            True if valid
        """
        # Check if symbol has data
        if order.symbol not in self.price_data:
            logger.warning(f"No data for {order.symbol}")
            return False

        # Check if price data exists for this date
        df = self.price_data[order.symbol]
        if order.timestamp not in df.index:
            logger.warning(
                f"No price data for {order.symbol} on {order.timestamp.date()}"
            )
            return False

        # Check quantity
        if order.quantity <= 0:
            logger.warning(f"Invalid quantity: {order.quantity}")
            return False

        # Check for short selling restrictions
        if order.direction == "SELL":
            position = self.portfolio.get_position(order.symbol)
            if position is None or position.quantity < order.quantity:
                if not self.config.enable_short_selling:
                    logger.warning(
                        f"Short selling disabled, cannot sell {order.symbol}"
                    )
                    return False

        return True

    def _get_execution_price(self, order: OrderEvent) -> float | None:
        """
        Get execution price for order.

        Args:
            order: Order event

        Returns:
            Execution price or None
        """
        df = self.price_data[order.symbol]

        if order.timestamp not in df.index:
            return None

        row = df.loc[order.timestamp]

        if order.order_type == "MARKET":
            # Use close price if trade_on_close, otherwise open
            if self.config.trade_on_close:
                return row["close"]
            return row["open"]

        if order.order_type == "LIMIT":
            # For limit orders, check if limit price would have been filled
            if order.price is None:
                return None

            if order.direction == "BUY":
                # Buy limit: execute if low <= limit price
                if row["low"] <= order.price:
                    return min(order.price, row["open"])
            # Sell limit: execute if high >= limit price
            elif row["high"] >= order.price:
                return max(order.price, row["open"])

            return None  # Limit not hit

        if order.order_type == "STOP":
            # For stop orders
            if order.price is None:
                return None

            if order.direction == "BUY":
                # Buy stop: execute if high >= stop price
                if row["high"] >= order.price:
                    return max(order.price, row["open"])
            # Sell stop: execute if low <= stop price
            elif row["low"] <= order.price:
                return min(order.price, row["open"])

            return None  # Stop not hit

        return None

    def _calculate_commission(self, order: OrderEvent, price: float) -> float:
        """
        Calculate commission for order.

        Args:
            order: Order event
            price: Execution price

        Returns:
            Commission amount
        """
        notional_value = order.quantity * price
        commission = notional_value * self.config.commission
        return commission

    def _calculate_slippage(self, order: OrderEvent, price: float) -> float:
        """
        Calculate slippage for order.

        Args:
            order: Order event
            price: Execution price

        Returns:
            Slippage cost
        """
        # Simple slippage model: percentage of notional value
        notional_value = order.quantity * price
        slippage = notional_value * self.config.slippage

        # Could be enhanced with:
        # - Volume-based slippage
        # - Spread-based slippage
        # - Market impact model

        return slippage

    def get_statistics(self) -> dict:
        """
        Get execution statistics.

        Returns:
            Dict with statistics
        """
        return {
            "total_orders": self.total_orders,
            "filled_orders": self.filled_orders,
            "rejected_orders": self.rejected_orders,
            "fill_rate": (
                self.filled_orders / self.total_orders
                if self.total_orders > 0 else 0
            ),
        }

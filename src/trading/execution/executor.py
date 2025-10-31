"""
Order Executor
Handles order placement and execution
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
import asyncio
from loguru import logger

class OrderType(Enum):
    """Order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class OrderStatus(Enum):
    """Order status"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

@dataclass
class Order:
    """Order object"""
    id: str
    symbol: str
    action: str  # buy or sell
    quantity: int
    order_type: OrderType
    status: OrderStatus
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    created_at: datetime = None
    filled_at: Optional[datetime] = None

class OrderExecutor:
    """Executes trading orders"""

    def __init__(self):
        self.orders = []
        self.positions = {}
        self.account = {'cash': 100000, 'portfolio_value': 100000}
        logger.info("Order Executor initialized")

    async def buy(self, symbol: str, quantity: int, 
                  limit_price: Optional[float] = None,
                  order_type: OrderType = OrderType.MARKET) -> Order:
        """Place buy order"""
        order = Order(
            id=f"ORD_{len(self.orders)}",
            symbol=symbol,
            action="buy",
            quantity=quantity,
            order_type=order_type,
            status=OrderStatus.PENDING,
            limit_price=limit_price,
            created_at=datetime.now()
        )
        
        self.orders.append(order)
        logger.info(f"Buy order placed: {symbol} x {quantity}")
        
        # Simulate execution
        await self._execute_order(order)
        
        return order

    async def sell(self, symbol: str, quantity: int,
                   limit_price: Optional[float] = None,
                   order_type: OrderType = OrderType.MARKET) -> Order:
        """Place sell order"""
        order = Order(
            id=f"ORD_{len(self.orders)}",
            symbol=symbol,
            action="sell",
            quantity=quantity,
            order_type=order_type,
            status=OrderStatus.PENDING,
            limit_price=limit_price,
            created_at=datetime.now()
        )
        
        self.orders.append(order)
        logger.info(f"Sell order placed: {symbol} x {quantity}")
        
        await self._execute_order(order)
        
        return order

    async def _execute_order(self, order: Order):
        """Simulate order execution"""
        await asyncio.sleep(0.1)  # Simulate network delay
        
        # In production, this would submit to broker API
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.avg_fill_price = order.limit_price or 100.0  # Placeholder
        order.filled_at = datetime.now()
        
        logger.info(f"Order filled: {order.id}")

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        for order in self.orders:
            if order.id == order_id and order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
                order.status = OrderStatus.CANCELLED
                logger.info(f"Order cancelled: {order_id}")
                return True
        return False

    async def cancel_all_orders(self):
        """Cancel all open orders"""
        for order in self.orders:
            if order.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
                await self.cancel_order(order.id)

    async def get_positions(self) -> Dict:
        """Get current positions"""
        return self.positions

    async def get_account(self) -> Dict:
        """Get account information"""
        return self.account

    async def close_position(self, symbol: str, reason: str = "user"):
        """Close a position"""
        if symbol in self.positions:
            pos = self.positions[symbol]
            await self.sell(symbol, pos['quantity'])
            del self.positions[symbol]
            logger.info(f"Closed position: {symbol}, reason: {reason}")

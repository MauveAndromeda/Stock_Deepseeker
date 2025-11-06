"""
Order Management System (OMS).

Central system for managing orders throughout their lifecycle.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Callable
from collections import defaultdict
import threading
from loguru import logger


class OrderStatus(Enum):
    """Order status enumeration."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    PARTIAL_FILL = "partial_fill"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderType(Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderSide(Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class TimeInForce(Enum):
    """Time in force options."""
    DAY = "day"
    GTC = "gtc"  # Good till cancelled
    IOC = "ioc"  # Immediate or cancel
    FOK = "fok"  # Fill or kill


@dataclass
class Order:
    """Order object."""
    order_id: str
    client_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    status: OrderStatus = OrderStatus.PENDING
    
    # Optional fields
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    
    # Execution details
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    
    # Metadata
    strategy_id: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    
    @property
    def is_complete(self) -> bool:
        """Check if order is complete."""
        return self.status in [
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED
        ]
    
    @property
    def remaining_quantity(self) -> float:
        """Get remaining unfilled quantity."""
        return self.quantity - self.filled_quantity
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'order_id': self.order_id,
            'client_order_id': self.client_order_id,
            'symbol': self.symbol,
            'side': self.side.value,
            'order_type': self.order_type.value,
            'quantity': self.quantity,
            'status': self.status.value,
            'filled_quantity': self.filled_quantity,
            'avg_fill_price': self.avg_fill_price,
            'created_at': self.created_at.isoformat(),
            'strategy_id': self.strategy_id
        }


@dataclass
class Fill:
    """Order fill event."""
    fill_id: str
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    commission: float
    timestamp: datetime
    execution_id: str = ""


class OrderManager:
    """
    Order Management System.
    
    Features:
    - Order lifecycle management
    - Fill processing
    - Order status tracking
    - Order book maintenance
    - Callbacks for order events
    """
    
    def __init__(self):
        """Initialize order manager."""
        self._orders: Dict[str, Order] = {}
        self._fills: Dict[str, List[Fill]] = defaultdict(list)
        
        # Callbacks
        self._order_callbacks: List[Callable[[Order], None]] = []
        self._fill_callbacks: List[Callable[[Fill], None]] = []
        
        # Threading
        self._lock = threading.Lock()
        
        # Metrics
        self._order_count = 0
        self._fill_count = 0
        
        logger.info("Initialized OrderManager")
    
    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.DAY,
        strategy_id: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> Order:
        """Create a new order."""
        with self._lock:
            self._order_count += 1
            order_id = f"ORD-{self._order_count:08d}"
            client_order_id = f"CLT-{self._order_count:08d}"
        
        order = Order(
            order_id=order_id,
            client_order_id=client_order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            strategy_id=strategy_id,
            tags=tags or {}
        )
        
        with self._lock:
            self._orders[order_id] = order
        
        logger.info(f"Created order: {order_id} {side.value} {quantity} {symbol}")
        
        return order
    
    def submit_order(self, order_id: str) -> bool:
        """Mark order as submitted."""
        with self._lock:
            order = self._orders.get(order_id)
            
            if not order:
                logger.error(f"Order not found: {order_id}")
                return False
            
            if order.status != OrderStatus.PENDING:
                logger.warning(f"Order {order_id} already submitted")
                return False
            
            order.status = OrderStatus.SUBMITTED
            order.submitted_at = datetime.now()
        
        self._trigger_order_callbacks(order)
        
        logger.info(f"Submitted order: {order_id}")
        return True
    
    def acknowledge_order(self, order_id: str, broker_order_id: Optional[str] = None) -> bool:
        """Acknowledge order receipt by broker."""
        with self._lock:
            order = self._orders.get(order_id)
            
            if not order:
                return False
            
            order.status = OrderStatus.ACKNOWLEDGED
            
            if broker_order_id:
                order.tags['broker_order_id'] = broker_order_id
        
        self._trigger_order_callbacks(order)
        
        logger.info(f"Acknowledged order: {order_id}")
        return True
    
    def process_fill(
        self,
        order_id: str,
        quantity: float,
        price: float,
        commission: float = 0.0,
        execution_id: str = ""
    ) -> Optional[Fill]:
        """Process an order fill."""
        with self._lock:
            order = self._orders.get(order_id)
            
            if not order:
                logger.error(f"Order not found: {order_id}")
                return None
            
            if order.is_complete:
                logger.warning(f"Order {order_id} already complete")
                return None
            
            # Create fill
            self._fill_count += 1
            fill = Fill(
                fill_id=f"FILL-{self._fill_count:08d}",
                order_id=order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=quantity,
                price=price,
                commission=commission,
                timestamp=datetime.now(),
                execution_id=execution_id
            )
            
            # Update order
            order.filled_quantity += quantity
            order.commission += commission
            
            # Update average fill price
            total_value = order.avg_fill_price * (order.filled_quantity - quantity) + price * quantity
            order.avg_fill_price = total_value / order.filled_quantity
            
            # Update status
            if order.filled_quantity >= order.quantity:
                order.status = OrderStatus.FILLED
                order.filled_at = datetime.now()
            else:
                order.status = OrderStatus.PARTIAL_FILL
            
            # Store fill
            self._fills[order_id].append(fill)
        
        # Trigger callbacks
        self._trigger_fill_callbacks(fill)
        self._trigger_order_callbacks(order)
        
        logger.info(
            f"Processed fill: {fill.fill_id} - {quantity} @ {price} "
            f"({order.filled_quantity}/{order.quantity} filled)"
        )
        
        return fill
    
    def cancel_order(self, order_id: str, reason: str = "") -> bool:
        """Cancel an order."""
        with self._lock:
            order = self._orders.get(order_id)
            
            if not order:
                return False
            
            if order.is_complete:
                logger.warning(f"Order {order_id} already complete")
                return False
            
            order.status = OrderStatus.CANCELLED
            
            if reason:
                order.tags['cancel_reason'] = reason
        
        self._trigger_order_callbacks(order)
        
        logger.info(f"Cancelled order: {order_id}")
        return True
    
    def reject_order(self, order_id: str, reason: str = "") -> bool:
        """Reject an order."""
        with self._lock:
            order = self._orders.get(order_id)
            
            if not order:
                return False
            
            order.status = OrderStatus.REJECTED
            
            if reason:
                order.tags['reject_reason'] = reason
        
        self._trigger_order_callbacks(order)
        
        logger.warning(f"Rejected order: {order_id} - {reason}")
        return True
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        with self._lock:
            return self._orders.get(order_id)
    
    def get_active_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get all active orders."""
        with self._lock:
            orders = [o for o in self._orders.values() if not o.is_complete]
            
            if symbol:
                orders = [o for o in orders if o.symbol == symbol]
            
            return orders
    
    def get_filled_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get all filled orders."""
        with self._lock:
            orders = [o for o in self._orders.values() if o.status == OrderStatus.FILLED]
            
            if symbol:
                orders = [o for o in orders if o.symbol == symbol]
            
            return orders
    
    def get_fills(self, order_id: str) -> List[Fill]:
        """Get fills for an order."""
        with self._lock:
            return list(self._fills.get(order_id, []))
    
    def register_order_callback(self, callback: Callable[[Order], None]):
        """Register callback for order events."""
        self._order_callbacks.append(callback)
    
    def register_fill_callback(self, callback: Callable[[Fill], None]):
        """Register callback for fill events."""
        self._fill_callbacks.append(callback)
    
    def _trigger_order_callbacks(self, order: Order):
        """Trigger order callbacks."""
        for callback in self._order_callbacks:
            try:
                callback(order)
            except Exception as e:
                logger.error(f"Error in order callback: {e}")
    
    def _trigger_fill_callbacks(self, fill: Fill):
        """Trigger fill callbacks."""
        for callback in self._fill_callbacks:
            try:
                callback(fill)
            except Exception as e:
                logger.error(f"Error in fill callback: {e}")
    
    def get_statistics(self) -> dict:
        """Get order statistics."""
        with self._lock:
            total_orders = len(self._orders)
            active_orders = sum(1 for o in self._orders.values() if not o.is_complete)
            filled_orders = sum(1 for o in self._orders.values() if o.status == OrderStatus.FILLED)
            cancelled_orders = sum(1 for o in self._orders.values() if o.status == OrderStatus.CANCELLED)
            rejected_orders = sum(1 for o in self._orders.values() if o.status == OrderStatus.REJECTED)
            
            total_fills = sum(len(fills) for fills in self._fills.values())
            
            return {
                'total_orders': total_orders,
                'active_orders': active_orders,
                'filled_orders': filled_orders,
                'cancelled_orders': cancelled_orders,
                'rejected_orders': rejected_orders,
                'total_fills': total_fills,
                'fill_rate': filled_orders / total_orders if total_orders > 0 else 0.0
            }


# Global order manager instance
_default_order_manager: Optional[OrderManager] = None


def get_default_order_manager() -> OrderManager:
    """Get global default order manager."""
    global _default_order_manager
    if _default_order_manager is None:
        _default_order_manager = OrderManager()
    return _default_order_manager

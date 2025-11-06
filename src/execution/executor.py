"""
Live execution engine.

Orchestrates live trading by connecting strategy signals to broker execution.
"""

from typing import Optional, Callable, List
from datetime import datetime
import threading
import time
from loguru import logger

from src.execution.order_manager import OrderManager, Order, OrderStatus, Fill
from src.execution.broker import BrokerInterface


class LiveExecutor:
    """
    Live execution engine.
    
    Connects trading strategies to broker execution with:
    - Order submission and tracking
    - Fill processing
    - Position management
    - Risk checks
    - Performance monitoring
    """
    
    def __init__(
        self,
        broker: BrokerInterface,
        order_manager: Optional[OrderManager] = None,
        max_position_size: Optional[float] = None,
        max_order_value: Optional[float] = None
    ):
        """Initialize live executor."""
        self.broker = broker
        self.order_manager = order_manager or OrderManager()
        
        # Risk limits
        self.max_position_size = max_position_size
        self.max_order_value = max_order_value
        
        # State
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # Register callbacks
        self.order_manager.register_order_callback(self._on_order_update)
        self.order_manager.register_fill_callback(self._on_fill)
        
        logger.info("Initialized LiveExecutor")
    
    def start(self) -> bool:
        """Start live execution."""
        if self._running:
            logger.warning("LiveExecutor already running")
            return False
        
        # Connect to broker
        if not self.broker.connect():
            logger.error("Failed to connect to broker")
            return False
        
        self._running = True
        
        # Start monitoring thread
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        logger.info("Started LiveExecutor")
        return True
    
    def stop(self) -> bool:
        """Stop live execution."""
        if not self._running:
            return False
        
        self._running = False
        
        # Wait for monitor thread
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        
        # Disconnect from broker
        self.broker.disconnect()
        
        logger.info("Stopped LiveExecutor")
        return True
    
    def submit_order(self, order: Order) -> bool:
        """Submit order for execution."""
        # Risk checks
        if not self._check_risk_limits(order):
            logger.warning(f"Order failed risk checks: {order.order_id}")
            self.order_manager.reject_order(order.order_id, "Risk limit exceeded")
            return False
        
        # Submit to order manager
        if not self.order_manager.submit_order(order.order_id):
            return False
        
        # Submit to broker
        if not self.broker.submit_order(order):
            self.order_manager.reject_order(order.order_id, "Broker submission failed")
            return False
        
        # Acknowledge
        self.order_manager.acknowledge_order(order.order_id)
        
        logger.info(f"Submitted order: {order.order_id}")
        return True
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        # Cancel with broker
        if not self.broker.cancel_order(order_id):
            logger.error(f"Failed to cancel order with broker: {order_id}")
            return False
        
        # Update order manager
        self.order_manager.cancel_order(order_id)
        
        logger.info(f"Cancelled order: {order_id}")
        return True
    
    def get_positions(self):
        """Get current positions from broker."""
        return self.broker.get_positions()
    
    def get_account(self):
        """Get account information from broker."""
        return self.broker.get_account()
    
    def _check_risk_limits(self, order: Order) -> bool:
        """Check if order passes risk limits."""
        # Check max order value
        if self.max_order_value:
            estimated_value = order.quantity * (order.limit_price or 100.0)  # Use limit or estimate
            if estimated_value > self.max_order_value:
                logger.warning(f"Order value ${estimated_value:.2f} exceeds limit ${self.max_order_value:.2f}")
                return False
        
        # Check max position size
        if self.max_position_size:
            current_position = self.broker.get_position(order.symbol)
            current_qty = current_position.quantity if current_position else 0.0
            
            new_qty = current_qty
            if order.side.value == 'buy':
                new_qty += order.quantity
            else:
                new_qty -= order.quantity
            
            if abs(new_qty) > self.max_position_size:
                logger.warning(f"Position size {new_qty} exceeds limit {self.max_position_size}")
                return False
        
        return True
    
    def _monitor_loop(self):
        """Monitor orders and positions."""
        logger.info("Started order monitoring loop")
        
        while self._running:
            try:
                # Check active orders
                active_orders = self.order_manager.get_active_orders()
                
                for order in active_orders:
                    # Get status from broker
                    broker_order_id = order.tags.get('broker_order_id') or order.order_id
                    status = self.broker.get_order_status(broker_order_id)
                    
                    if status and status != order.status:
                        logger.info(f"Order {order.order_id} status changed: {status.value}")
                        # Would update order manager here
                
                # Sleep before next iteration
                time.sleep(1)  # Check every second
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(5)
        
        logger.info("Stopped order monitoring loop")
    
    def _on_order_update(self, order: Order):
        """Callback for order updates."""
        logger.debug(f"Order update: {order.order_id} - {order.status.value}")
    
    def _on_fill(self, fill: Fill):
        """Callback for order fills."""
        logger.info(
            f"Fill received: {fill.fill_id} - {fill.quantity} @ {fill.price} "
            f"(commission: ${fill.commission:.2f})"
        )

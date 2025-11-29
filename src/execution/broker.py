"""
Broker interface and integrations.

Provides unified interface for multiple brokers:
- Interactive Brokers (IB)
- Alpaca
- TD Ameritrade
- Paper trading (simulation)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from loguru import logger

from src.execution.order_manager import Order, OrderStatus


class BrokerType(Enum):
    """Supported broker types."""
    INTERACTIVE_BROKERS = "interactive_brokers"
    ALPACA = "alpaca"
    TD_AMERITRADE = "td_ameritrade"
    PAPER = "paper"  # Simulated trading


@dataclass
class BrokerConfig:
    """Broker configuration."""
    broker_type: BrokerType
    api_key: str | None = None
    api_secret: str | None = None
    account_id: str | None = None
    paper_trading: bool = True
    base_url: str | None = None


@dataclass
class Position:
    """Broker position."""
    symbol: str
    quantity: float
    avg_cost: float
    market_value: float
    unrealized_pnl: float
    side: str  # 'long' or 'short'


@dataclass
class Account:
    """Broker account information."""
    account_id: str
    cash: float
    buying_power: float
    portfolio_value: float
    positions: list[Position]
    timestamp: datetime


class BrokerInterface(ABC):
    """
    Abstract broker interface.
    
    All broker integrations must implement this interface.
    """

    def __init__(self, config: BrokerConfig):
        """Initialize broker connection."""
        self.config = config
        self._connected = False
        logger.info(f"Initialized {config.broker_type.value} broker")

    @abstractmethod
    def connect(self) -> bool:
        """Connect to broker."""

    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from broker."""

    @abstractmethod
    def submit_order(self, order: Order) -> bool:
        """Submit order to broker."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order."""

    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderStatus | None:
        """Get order status from broker."""

    @abstractmethod
    def get_account(self) -> Account | None:
        """Get account information."""

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Get current positions."""

    @abstractmethod
    def get_position(self, symbol: str) -> Position | None:
        """Get position for specific symbol."""

    @property
    def is_connected(self) -> bool:
        """Check if connected to broker."""
        return self._connected


class AlpacaBroker(BrokerInterface):
    """
    Alpaca broker integration.
    
    Uses Alpaca's REST API for order submission and market data.
    """

    def __init__(self, config: BrokerConfig):
        """Initialize Alpaca broker."""
        super().__init__(config)

        # Initialize Alpaca client
        try:
            import alpaca_trade_api as tradeapi

            base_url = config.base_url or (
                "https://paper-api.alpaca.markets" if config.paper_trading
                else "https://api.alpaca.markets"
            )

            self._api = tradeapi.REST(
                key_id=config.api_key,
                secret_key=config.api_secret,
                base_url=base_url
            )

            logger.info("Initialized Alpaca API client")

        except ImportError:
            logger.error("alpaca-trade-api not installed. Install with: pip install alpaca-trade-api")
            self._api = None

    def connect(self) -> bool:
        """Connect to Alpaca."""
        try:
            if not self._api:
                return False

            # Test connection by getting account
            account = self._api.get_account()
            self._connected = True

            logger.info(f"Connected to Alpaca - Account: {account.account_number}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Alpaca: {e}")
            return False

    def disconnect(self) -> bool:
        """Disconnect from Alpaca."""
        self._connected = False
        logger.info("Disconnected from Alpaca")
        return True

    def submit_order(self, order: Order) -> bool:
        """Submit order to Alpaca."""
        try:
            if not self._api or not self._connected:
                return False

            # Submit order
            alpaca_order = self._api.submit_order(
                symbol=order.symbol,
                qty=order.quantity,
                side=order.side.value,
                type=order.order_type.value,
                time_in_force=order.time_in_force.value,
                limit_price=order.limit_price,
                stop_price=order.stop_price
            )

            # Update order with broker ID
            order.tags["alpaca_order_id"] = alpaca_order.id

            logger.info(f"Submitted order to Alpaca: {alpaca_order.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to submit order to Alpaca: {e}")
            return False

    def cancel_order(self, order_id: str) -> bool:
        """Cancel order on Alpaca."""
        try:
            if not self._api or not self._connected:
                return False

            self._api.cancel_order(order_id)

            logger.info(f"Cancelled order on Alpaca: {order_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel order on Alpaca: {e}")
            return False

    def get_order_status(self, order_id: str) -> OrderStatus | None:
        """Get order status from Alpaca."""
        try:
            if not self._api or not self._connected:
                return None

            alpaca_order = self._api.get_order(order_id)

            # Map Alpaca status to our status
            status_map = {
                "new": OrderStatus.SUBMITTED,
                "partially_filled": OrderStatus.PARTIAL_FILL,
                "filled": OrderStatus.FILLED,
                "canceled": OrderStatus.CANCELLED,
                "rejected": OrderStatus.REJECTED,
                "expired": OrderStatus.EXPIRED
            }

            return status_map.get(alpaca_order.status, OrderStatus.PENDING)

        except Exception as e:
            logger.error(f"Failed to get order status from Alpaca: {e}")
            return None

    def get_account(self) -> Account | None:
        """Get account information from Alpaca."""
        try:
            if not self._api or not self._connected:
                return None

            alpaca_account = self._api.get_account()
            positions = self.get_positions()

            return Account(
                account_id=alpaca_account.account_number,
                cash=float(alpaca_account.cash),
                buying_power=float(alpaca_account.buying_power),
                portfolio_value=float(alpaca_account.portfolio_value),
                positions=positions,
                timestamp=datetime.now()
            )

        except Exception as e:
            logger.error(f"Failed to get account from Alpaca: {e}")
            return None

    def get_positions(self) -> list[Position]:
        """Get positions from Alpaca."""
        try:
            if not self._api or not self._connected:
                return []

            alpaca_positions = self._api.list_positions()

            positions = []
            for pos in alpaca_positions:
                position = Position(
                    symbol=pos.symbol,
                    quantity=float(pos.qty),
                    avg_cost=float(pos.avg_entry_price),
                    market_value=float(pos.market_value),
                    unrealized_pnl=float(pos.unrealized_pl),
                    side="long" if float(pos.qty) > 0 else "short"
                )
                positions.append(position)

            return positions

        except Exception as e:
            logger.error(f"Failed to get positions from Alpaca: {e}")
            return []

    def get_position(self, symbol: str) -> Position | None:
        """Get position for symbol from Alpaca."""
        try:
            if not self._api or not self._connected:
                return None

            pos = self._api.get_position(symbol)

            return Position(
                symbol=pos.symbol,
                quantity=float(pos.qty),
                avg_cost=float(pos.avg_entry_price),
                market_value=float(pos.market_value),
                unrealized_pnl=float(pos.unrealized_pl),
                side="long" if float(pos.qty) > 0 else "short"
            )

        except (KeyError, AttributeError, ValueError):
            logger.debug(f"No position found for {symbol}")
            return None


class PaperBroker(BrokerInterface):
    """
    Paper trading broker (simulation).
    
    Simulates order execution for testing without real money.
    """

    def __init__(self, config: BrokerConfig, initial_cash: float = 1000000.0):
        """Initialize paper broker."""
        super().__init__(config)

        self._cash = initial_cash
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, Order] = {}

        logger.info(f"Initialized paper broker with ${initial_cash:,.2f}")

    def connect(self) -> bool:
        """Connect to paper broker (always succeeds)."""
        self._connected = True
        logger.info("Connected to paper broker")
        return True

    def disconnect(self) -> bool:
        """Disconnect from paper broker."""
        self._connected = False
        logger.info("Disconnected from paper broker")
        return True

    def submit_order(self, order: Order) -> bool:
        """Submit order to paper broker."""
        if not self._connected:
            return False

        self._orders[order.order_id] = order

        # Simulate immediate fill at market price (simplified)
        # In reality, would use current market price
        simulated_price = 100.0  # Would get from market data

        # Check if we have enough cash/shares
        if order.side.value == "buy":
            cost = order.quantity * simulated_price
            if cost > self._cash:
                logger.warning(f"Insufficient cash for order {order.order_id}")
                return False

        logger.info(f"Submitted order to paper broker: {order.order_id}")
        return True

    def cancel_order(self, order_id: str) -> bool:
        """Cancel order in paper broker."""
        if order_id in self._orders:
            del self._orders[order_id]
            logger.info(f"Cancelled order in paper broker: {order_id}")
            return True
        return False

    def get_order_status(self, order_id: str) -> OrderStatus | None:
        """Get order status from paper broker."""
        order = self._orders.get(order_id)
        return order.status if order else None

    def get_account(self) -> Account | None:
        """Get paper account information."""
        if not self._connected:
            return None

        positions = list(self._positions.values())
        portfolio_value = self._cash + sum(p.market_value for p in positions)

        return Account(
            account_id="PAPER-001",
            cash=self._cash,
            buying_power=self._cash * 4,  # Simulated 4x margin
            portfolio_value=portfolio_value,
            positions=positions,
            timestamp=datetime.now()
        )

    def get_positions(self) -> list[Position]:
        """Get all positions from paper broker."""
        return list(self._positions.values())

    def get_position(self, symbol: str) -> Position | None:
        """Get position for symbol from paper broker."""
        return self._positions.get(symbol)


def create_broker(config: BrokerConfig) -> BrokerInterface:
    """Factory function to create broker instance."""
    if config.broker_type == BrokerType.ALPACA:
        return AlpacaBroker(config)
    if config.broker_type == BrokerType.PAPER:
        return PaperBroker(config)
    raise ValueError(f"Unsupported broker type: {config.broker_type}")

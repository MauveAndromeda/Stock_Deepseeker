"""
Base classes for real-time data streaming.
"""

from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional, Set, Any
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import logging


class MessageType(Enum):
    """Types of streaming messages."""
    TRADE = "trade"
    QUOTE = "quote"
    BAR = "bar"
    ORDER_UPDATE = "order_update"
    POSITION_UPDATE = "position_update"
    ERROR = "error"
    STATUS = "status"
    HEARTBEAT = "heartbeat"


@dataclass
class StreamingMessage:
    """Container for streaming data messages."""
    message_type: MessageType
    symbol: str
    timestamp: datetime
    data: Dict[str, Any]
    sequence: Optional[int] = None

    def __repr__(self) -> str:
        return (
            f"StreamingMessage({self.message_type.value}, "
            f"{self.symbol}, {self.timestamp})"
        )


@dataclass
class Subscription:
    """Subscription configuration."""
    symbols: Set[str] = field(default_factory=set)
    message_types: Set[MessageType] = field(default_factory=set)
    callback: Optional[Callable[[StreamingMessage], None]] = None
    filters: Dict[str, Any] = field(default_factory=dict)

    def matches(self, message: StreamingMessage) -> bool:
        """Check if message matches subscription criteria."""
        if self.symbols and message.symbol not in self.symbols:
            return False

        if self.message_types and message.message_type not in self.message_types:
            return False

        # Apply custom filters
        for key, value in self.filters.items():
            if key not in message.data or message.data[key] != value:
                return False

        return True


class StreamingDataProvider(ABC):
    """
    Abstract base class for real-time data streaming providers.

    Provides a unified interface for different data sources.
    """

    def __init__(
        self,
        name: str = "StreamProvider",
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 10,
        reconnect_delay: float = 5.0
    ):
        """
        Initialize streaming provider.

        Args:
            name: Provider name
            auto_reconnect: Automatically reconnect on disconnection
            max_reconnect_attempts: Maximum reconnection attempts
            reconnect_delay: Delay between reconnection attempts (seconds)
        """
        self.name = name
        self.auto_reconnect = auto_reconnect
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay

        self.logger = logging.getLogger(f"{__name__}.{name}")

        # State
        self._connected = False
        self._running = False
        self._subscriptions: List[Subscription] = []
        self._message_handlers: Dict[MessageType, List[Callable]] = {}
        self._reconnect_count = 0
        self._message_count = 0
        self._error_count = 0

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to data source.

        Returns:
            True if connection successful
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to data source."""
        pass

    @abstractmethod
    async def subscribe(
        self,
        symbols: List[str],
        message_types: Optional[List[MessageType]] = None
    ) -> bool:
        """
        Subscribe to real-time data for symbols.

        Args:
            symbols: List of symbols to subscribe
            message_types: Types of messages to receive (None = all)

        Returns:
            True if subscription successful
        """
        pass

    @abstractmethod
    async def unsubscribe(
        self,
        symbols: List[str],
        message_types: Optional[List[MessageType]] = None
    ) -> bool:
        """
        Unsubscribe from real-time data.

        Args:
            symbols: List of symbols to unsubscribe
            message_types: Types of messages to stop receiving

        Returns:
            True if unsubscription successful
        """
        pass

    @abstractmethod
    async def _process_message(self, raw_message: Any) -> Optional[StreamingMessage]:
        """
        Process raw message from data source.

        Args:
            raw_message: Raw message from provider

        Returns:
            Parsed StreamingMessage or None
        """
        pass

    async def start(self) -> None:
        """Start the streaming provider."""
        if self._running:
            self.logger.warning("Provider already running")
            return

        self._running = True
        self.logger.info(f"Starting {self.name}")

        # Connect
        connected = await self.connect()
        if not connected:
            self.logger.error("Failed to connect")
            self._running = False
            return

        # Start message processing loop
        await self._run_loop()

    async def stop(self) -> None:
        """Stop the streaming provider."""
        if not self._running:
            return

        self.logger.info(f"Stopping {self.name}")
        self._running = False
        await self.disconnect()

    async def _run_loop(self) -> None:
        """Main message processing loop."""
        while self._running:
            try:
                # This will be overridden by specific implementations
                await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Error in run loop: {e}")
                self._error_count += 1

                if self.auto_reconnect and self._reconnect_count < self.max_reconnect_attempts:
                    await self._attempt_reconnect()
                else:
                    self.logger.error("Max reconnection attempts reached")
                    break

    async def _attempt_reconnect(self) -> None:
        """Attempt to reconnect to data source."""
        self._reconnect_count += 1
        self.logger.info(
            f"Reconnection attempt {self._reconnect_count}/{self.max_reconnect_attempts}"
        )

        await asyncio.sleep(self.reconnect_delay)

        try:
            await self.disconnect()
            connected = await self.connect()

            if connected:
                self.logger.info("Reconnection successful")
                self._reconnect_count = 0
            else:
                self.logger.error("Reconnection failed")
        except Exception as e:
            self.logger.error(f"Reconnection error: {e}")

    def add_subscription(self, subscription: Subscription) -> None:
        """Add a subscription."""
        self._subscriptions.append(subscription)

    def remove_subscription(self, subscription: Subscription) -> None:
        """Remove a subscription."""
        if subscription in self._subscriptions:
            self._subscriptions.remove(subscription)

    def register_handler(
        self,
        message_type: MessageType,
        handler: Callable[[StreamingMessage], None]
    ) -> None:
        """
        Register a message handler.

        Args:
            message_type: Type of message to handle
            handler: Callback function
        """
        if message_type not in self._message_handlers:
            self._message_handlers[message_type] = []
        self._message_handlers[message_type].append(handler)

    def unregister_handler(
        self,
        message_type: MessageType,
        handler: Callable[[StreamingMessage], None]
    ) -> None:
        """Unregister a message handler."""
        if message_type in self._message_handlers:
            if handler in self._message_handlers[message_type]:
                self._message_handlers[message_type].remove(handler)

    async def _dispatch_message(self, message: StreamingMessage) -> None:
        """
        Dispatch message to registered handlers and subscriptions.

        Args:
            message: Streaming message to dispatch
        """
        self._message_count += 1

        # Dispatch to message type handlers
        if message.message_type in self._message_handlers:
            for handler in self._message_handlers[message.message_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(message)
                    else:
                        handler(message)
                except Exception as e:
                    self.logger.error(f"Error in message handler: {e}")
                    self._error_count += 1

        # Dispatch to subscriptions
        for subscription in self._subscriptions:
            if subscription.matches(message):
                if subscription.callback:
                    try:
                        if asyncio.iscoroutinefunction(subscription.callback):
                            await subscription.callback(message)
                        else:
                            subscription.callback(message)
                    except Exception as e:
                        self.logger.error(f"Error in subscription callback: {e}")
                        self._error_count += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get provider statistics."""
        return {
            'name': self.name,
            'connected': self._connected,
            'running': self._running,
            'messages_received': self._message_count,
            'errors': self._error_count,
            'reconnect_attempts': self._reconnect_count,
            'subscriptions': len(self._subscriptions),
            'handlers': sum(len(h) for h in self._message_handlers.values())
        }

    @property
    def is_connected(self) -> bool:
        """Check if provider is connected."""
        return self._connected

    @property
    def is_running(self) -> bool:
        """Check if provider is running."""
        return self._running

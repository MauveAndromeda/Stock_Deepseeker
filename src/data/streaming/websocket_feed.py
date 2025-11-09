"""
Generic WebSocket data feed implementation.
"""

import asyncio
from collections.abc import Callable
from datetime import datetime
import json
from typing import Any

from src.data.streaming.base import MessageType, StreamingDataProvider, StreamingMessage

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False


class WebSocketFeed(StreamingDataProvider):
    """
    Generic WebSocket data feed.

    Supports custom WebSocket-based data sources with configurable
    message parsing and authentication.
    """

    def __init__(
        self,
        url: str,
        auth_handler: Callable[[Any], dict] | None = None,
        message_parser: Callable[[dict], StreamingMessage | None] | None = None,
        headers: dict[str, str] | None = None,
        **kwargs
    ):
        """
        Initialize WebSocket feed.

        Args:
            url: WebSocket URL
            auth_handler: Function to generate auth message
            message_parser: Function to parse incoming messages
            headers: HTTP headers for connection
        """
        super().__init__(name="WebSocketFeed", **kwargs)

        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("websockets library required")

        self.url = url
        self.auth_handler = auth_handler
        self.message_parser = message_parser or self._default_message_parser
        self.headers = headers or {}

        self._ws = None
        self._ping_task = None

    async def connect(self) -> bool:
        """Establish WebSocket connection."""
        try:
            self.logger.info(f"Connecting to {self.url}")

            self._ws = await websockets.connect(
                self.url,
                extra_headers=self.headers
            )

            # Authenticate if handler provided
            if self.auth_handler:
                auth_message = self.auth_handler(None)
                await self._ws.send(json.dumps(auth_message))

                # Wait for auth response (optional)
                try:
                    response = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
                    self.logger.debug(f"Auth response: {response}")
                except asyncio.TimeoutError:
                    self.logger.warning("No auth response received")

            self._connected = True
            self.logger.info("Connected successfully")

            # Start ping task
            self._ping_task = asyncio.create_task(self._ping_loop())

            return True

        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        if self._ping_task:
            self._ping_task.cancel()
            self._ping_task = None

        if self._ws:
            try:
                await self._ws.close()
            except Exception as e:
                self.logger.error(f"Disconnect error: {e}")
            finally:
                self._ws = None
                self._connected = False
                self.logger.info("Disconnected")

    async def subscribe(
        self,
        symbols: list[str],
        message_types: list[MessageType] | None = None
    ) -> bool:
        """
        Subscribe to symbols.

        Default implementation sends a JSON message.
        Override for custom protocols.
        """
        if not self._connected:
            return False

        try:
            subscribe_message = {
                "action": "subscribe",
                "symbols": symbols
            }

            if message_types:
                subscribe_message["types"] = [t.value for t in message_types]

            await self._ws.send(json.dumps(subscribe_message))
            self.logger.info(f"Subscribed to {len(symbols)} symbols")
            return True

        except Exception as e:
            self.logger.error(f"Subscription error: {e}")
            return False

    async def unsubscribe(
        self,
        symbols: list[str],
        message_types: list[MessageType] | None = None
    ) -> bool:
        """Unsubscribe from symbols."""
        if not self._connected:
            return False

        try:
            unsubscribe_message = {
                "action": "unsubscribe",
                "symbols": symbols
            }

            await self._ws.send(json.dumps(unsubscribe_message))
            self.logger.info(f"Unsubscribed from {len(symbols)} symbols")
            return True

        except Exception as e:
            self.logger.error(f"Unsubscription error: {e}")
            return False

    async def _run_loop(self) -> None:
        """Main message processing loop."""
        while self._running and self._connected:
            try:
                raw_message = await asyncio.wait_for(
                    self._ws.recv(),
                    timeout=60.0
                )

                # Parse message
                try:
                    data = json.loads(raw_message)
                except json.JSONDecodeError:
                    self.logger.warning(f"Invalid JSON: {raw_message}")
                    continue

                # Process message
                parsed = await self._process_message(data)
                if parsed:
                    await self._dispatch_message(parsed)

            except asyncio.TimeoutError:
                self.logger.debug("Receive timeout")
                continue

            except Exception as e:
                self.logger.error(f"Error in run loop: {e}")
                self._error_count += 1

                if self.auto_reconnect:
                    await self._attempt_reconnect()
                else:
                    break

    async def _process_message(self, raw_message: dict[str, Any]) -> StreamingMessage | None:
        """Process raw message using custom parser."""
        try:
            return self.message_parser(raw_message)
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            return None

    def _default_message_parser(self, data: dict[str, Any]) -> StreamingMessage | None:
        """
        Default message parser.

        Expected format:
        {
            "type": "trade" | "quote" | "bar",
            "symbol": "AAPL",
            "timestamp": "2024-01-01T12:00:00Z",
            "data": { ... }
        }
        """
        try:
            msg_type_str = data.get("type", "")
            type_map = {
                "trade": MessageType.TRADE,
                "quote": MessageType.QUOTE,
                "bar": MessageType.BAR,
                "error": MessageType.ERROR,
                "status": MessageType.STATUS
            }

            message_type = type_map.get(msg_type_str)
            if not message_type:
                return None

            symbol = data.get("symbol", "")
            timestamp_str = data.get("timestamp", "")

            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            else:
                timestamp = datetime.utcnow()

            message_data = data.get("data", {})

            return StreamingMessage(
                message_type=message_type,
                symbol=symbol,
                timestamp=timestamp,
                data=message_data
            )

        except Exception as e:
            self.logger.error(f"Parse error: {e}")
            return None

    async def _ping_loop(self) -> None:
        """Send periodic pings to keep connection alive."""
        while self._connected:
            try:
                await asyncio.sleep(30)
                if self._ws:
                    await self._ws.ping()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Ping error: {e}")
                break

    async def send_message(self, message: dict[str, Any]) -> bool:
        """
        Send custom message to server.

        Args:
            message: Message dictionary

        Returns:
            True if sent successfully
        """
        if not self._connected or not self._ws:
            return False

        try:
            await self._ws.send(json.dumps(message))
            return True
        except Exception as e:
            self.logger.error(f"Send error: {e}")
            return False

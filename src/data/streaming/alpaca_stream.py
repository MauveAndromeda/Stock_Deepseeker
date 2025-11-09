"""
Alpaca real-time data streaming implementation.
"""

import asyncio
from datetime import datetime
import json
from typing import Any

from src.data.streaming.base import MessageType, StreamingDataProvider, StreamingMessage

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False


class AlpacaStreamingProvider(StreamingDataProvider):
    """
    Alpaca real-time data streaming provider.

    Supports:
    - Real-time trades
    - Real-time quotes
    - Minute bars
    - Trade updates
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        feed: str = "iex",  # "iex" or "sip"
        paper_trading: bool = True,
        **kwargs
    ):
        """
        Initialize Alpaca streaming provider.

        Args:
            api_key: Alpaca API key
            api_secret: Alpaca API secret
            feed: Data feed ("iex" for free, "sip" for premium)
            paper_trading: Use paper trading endpoint
        """
        super().__init__(name="AlpacaStream", **kwargs)

        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("websockets library required for streaming")

        self.api_key = api_key
        self.api_secret = api_secret
        self.feed = feed
        self.paper_trading = paper_trading

        # WebSocket connection
        self._ws = None
        self._subscribed_symbols: set = set()

        # Determine endpoint
        if paper_trading:
            self.data_url = f"wss://stream.data.alpaca.markets/v2/{feed}"
            self.trading_url = "wss://paper-api.alpaca.markets/stream"
        else:
            self.data_url = f"wss://stream.data.alpaca.markets/v2/{feed}"
            self.trading_url = "wss://api.alpaca.markets/stream"

    async def connect(self) -> bool:
        """Establish WebSocket connection to Alpaca."""
        try:
            self.logger.info(f"Connecting to {self.data_url}")

            self._ws = await websockets.connect(self.data_url)

            # Authenticate
            auth_message = {
                "action": "auth",
                "key": self.api_key,
                "secret": self.api_secret
            }

            await self._ws.send(json.dumps(auth_message))

            # Wait for auth response
            response = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
            response_data = json.loads(response)

            if isinstance(response_data, list):
                response_data = response_data[0]

            if response_data.get("T") == "success":
                self._connected = True
                self.logger.info("Authentication successful")
                return True
            self.logger.error(f"Authentication failed: {response_data}")
            return False

        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
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
        Subscribe to real-time data for symbols.

        Args:
            symbols: List of symbols
            message_types: Types to subscribe (TRADE, QUOTE, BAR)

        Returns:
            True if subscription successful
        """
        if not self._connected:
            self.logger.error("Not connected")
            return False

        # Map message types to Alpaca channels
        channels = []
        if message_types is None or MessageType.TRADE in message_types:
            channels.append("trades")
        if message_types is None or MessageType.QUOTE in message_types:
            channels.append("quotes")
        if message_types is None or MessageType.BAR in message_types:
            channels.append("bars")

        try:
            subscribe_message = {
                "action": "subscribe",
                **dict.fromkeys(channels, symbols)
            }

            await self._ws.send(json.dumps(subscribe_message))

            # Wait for confirmation
            response = await asyncio.wait_for(self._ws.recv(), timeout=5.0)
            response_data = json.loads(response)

            self._subscribed_symbols.update(symbols)
            self.logger.info(f"Subscribed to {len(symbols)} symbols: {symbols}")

            return True

        except Exception as e:
            self.logger.error(f"Subscription error: {e}")
            return False

    async def unsubscribe(
        self,
        symbols: list[str],
        message_types: list[MessageType] | None = None
    ) -> bool:
        """Unsubscribe from real-time data."""
        if not self._connected:
            return False

        channels = []
        if message_types is None or MessageType.TRADE in message_types:
            channels.append("trades")
        if message_types is None or MessageType.QUOTE in message_types:
            channels.append("quotes")
        if message_types is None or MessageType.BAR in message_types:
            channels.append("bars")

        try:
            unsubscribe_message = {
                "action": "unsubscribe",
                **dict.fromkeys(channels, symbols)
            }

            await self._ws.send(json.dumps(unsubscribe_message))

            for symbol in symbols:
                self._subscribed_symbols.discard(symbol)

            self.logger.info(f"Unsubscribed from {len(symbols)} symbols")
            return True

        except Exception as e:
            self.logger.error(f"Unsubscription error: {e}")
            return False

    async def _run_loop(self) -> None:
        """Main message processing loop."""
        while self._running and self._connected:
            try:
                # Receive message with timeout
                raw_message = await asyncio.wait_for(
                    self._ws.recv(),
                    timeout=30.0  # 30s timeout
                )

                # Parse and dispatch
                messages = json.loads(raw_message)

                # Alpaca sends messages as list
                if not isinstance(messages, list):
                    messages = [messages]

                for msg in messages:
                    parsed = await self._process_message(msg)
                    if parsed:
                        await self._dispatch_message(parsed)

            except asyncio.TimeoutError:
                # Send heartbeat/ping
                self.logger.debug("Timeout, sending heartbeat")
                try:
                    await self._ws.ping()
                except Exception:
                    self.logger.warning("Heartbeat failed, reconnecting")
                    if self.auto_reconnect:
                        await self._attempt_reconnect()
                    break

            except Exception as e:
                self.logger.error(f"Error in run loop: {e}")
                self._error_count += 1

                if self.auto_reconnect and self._reconnect_count < self.max_reconnect_attempts:
                    await self._attempt_reconnect()
                else:
                    break

    async def _process_message(self, raw_message: dict[str, Any]) -> StreamingMessage | None:
        """
        Process raw Alpaca message.

        Alpaca message format:
        - T: Message type (t=trade, q=quote, b=bar, etc.)
        - S: Symbol
        - t: Timestamp
        - ... other fields depending on type
        """
        try:
            msg_type_code = raw_message.get("T")

            # Map Alpaca message types
            type_map = {
                "t": MessageType.TRADE,
                "q": MessageType.QUOTE,
                "b": MessageType.BAR,
                "success": MessageType.STATUS,
                "subscription": MessageType.STATUS,
                "error": MessageType.ERROR
            }

            message_type = type_map.get(msg_type_code)

            if not message_type:
                return None

            # Skip status messages
            if message_type == MessageType.STATUS:
                return None

            symbol = raw_message.get("S", "")
            timestamp_str = raw_message.get("t", "")

            # Parse timestamp (Alpaca uses RFC3339)
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            else:
                timestamp = datetime.utcnow()

            # Extract data based on message type
            data = {}

            if message_type == MessageType.TRADE:
                data = {
                    "price": float(raw_message.get("p", 0)),
                    "size": int(raw_message.get("s", 0)),
                    "exchange": raw_message.get("x", ""),
                    "conditions": raw_message.get("c", []),
                    "tape": raw_message.get("z", "")
                }

            elif message_type == MessageType.QUOTE:
                data = {
                    "bid_price": float(raw_message.get("bp", 0)),
                    "bid_size": int(raw_message.get("bs", 0)),
                    "ask_price": float(raw_message.get("ap", 0)),
                    "ask_size": int(raw_message.get("as", 0)),
                    "bid_exchange": raw_message.get("bx", ""),
                    "ask_exchange": raw_message.get("ax", "")
                }

            elif message_type == MessageType.BAR:
                data = {
                    "open": float(raw_message.get("o", 0)),
                    "high": float(raw_message.get("h", 0)),
                    "low": float(raw_message.get("l", 0)),
                    "close": float(raw_message.get("c", 0)),
                    "volume": int(raw_message.get("v", 0)),
                    "vwap": float(raw_message.get("vw", 0)),
                    "trade_count": int(raw_message.get("n", 0))
                }

            elif message_type == MessageType.ERROR:
                data = {
                    "code": raw_message.get("code", 0),
                    "msg": raw_message.get("msg", "")
                }
                self.logger.error(f"Alpaca error: {data}")

            return StreamingMessage(
                message_type=message_type,
                symbol=symbol,
                timestamp=timestamp,
                data=data
            )

        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            return None

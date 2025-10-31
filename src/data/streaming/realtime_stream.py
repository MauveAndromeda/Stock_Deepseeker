"""
Real-Time Data Stream
WebSocket-based real-time market data streaming
"""

import asyncio
import json
from typing import List, Optional, Callable
from datetime import datetime
from loguru import logger
import websockets


class RealTimeDataStream:
    """Real-time data stream via WebSocket"""

    def __init__(self, url: str, symbols: List[str]):
        """
        Args:
            url: WebSocket URL
            symbols: List of symbols to stream
        """
        self.url = url
        self.symbols = symbols
        self.ws = None
        self.is_connected = False
        logger.info(f"Real-time stream initialized for {len(symbols)} symbols")

    async def connect(self):
        """Connect to WebSocket"""
        try:
            self.ws = await websockets.connect(self.url)
            self.is_connected = True
            
            # Subscribe to symbols
            await self.subscribe(self.symbols)
            
            logger.info(f"Connected to {self.url}")
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.is_connected = False

    async def disconnect(self):
        """Disconnect from WebSocket"""
        if self.ws:
            await self.ws.close()
            self.is_connected = False
            logger.info("Disconnected")

    async def subscribe(self, symbols: List[str]):
        """Subscribe to symbols"""
        if not self.ws:
            return
        
        subscription_message = {
            "action": "subscribe",
            "symbols": symbols
        }
        
        await self.ws.send(json.dumps(subscription_message))
        logger.info(f"Subscribed to {len(symbols)} symbols")

    async def get_data(self):
        """Get next data message"""
        if not self.is_connected or not self.ws:
            await self.connect()
        
        try:
            message = await self.ws.recv()
            data = json.loads(message)
            return data
        except Exception as e:
            logger.error(f"Error receiving data: {e}")
            self.is_connected = False
            return None

    async def stream(self, callback: Callable):
        """Stream data and call callback"""
        while True:
            try:
                data = await self.get_data()
                
                if data:
                    callback(data)
                
            except Exception as e:
                logger.error(f"Stream error: {e}")
                await asyncio.sleep(1)

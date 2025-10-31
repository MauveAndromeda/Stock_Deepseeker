"""
Stream Manager  
Manages real-time data streams
"""

import asyncio
from typing import Dict, List, Callable, Optional
from datetime import datetime
from loguru import logger
import websockets
import json


class StreamManager:
    """Manages multiple data streams"""

    def __init__(self):
        self.streams = {}
        self.callbacks = {}
        self.is_running = False
        logger.info("Stream manager initialized")

    async def start(self):
        """Start all streams"""
        self.is_running = True
        logger.info("Starting streams...")
        
        tasks = [
            asyncio.create_task(self._run_stream(name, stream))
            for name, stream in self.streams.items()
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self):
        """Stop all streams"""
        self.is_running = False
        logger.info("Stopping streams...")

    def add_stream(self, name: str, stream):
        """Add a stream"""
        self.streams[name] = stream
        logger.info(f"Added stream: {name}")

    def remove_stream(self, name: str):
        """Remove a stream"""
        if name in self.streams:
            del self.streams[name]
            logger.info(f"Removed stream: {name}")

    def register_callback(self, stream_name: str, callback: Callable):
        """Register callback for stream data"""
        if stream_name not in self.callbacks:
            self.callbacks[stream_name] = []
        self.callbacks[stream_name].append(callback)

    async def _run_stream(self, name: str, stream):
        """Run a single stream"""
        while self.is_running:
            try:
                data = await stream.get_data()
                
                # Call registered callbacks
                if name in self.callbacks:
                    for callback in self.callbacks[name]:
                        try:
                            callback(data)
                        except Exception as e:
                            logger.error(f"Callback error in {name}: {e}")
                
            except Exception as e:
                logger.error(f"Stream error in {name}: {e}")
                await asyncio.sleep(1)

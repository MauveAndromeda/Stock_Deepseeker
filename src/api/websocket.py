"""
WebSocket实时数据流
"""

import asyncio
from collections import defaultdict
from datetime import datetime
import json
from typing import Any

from fastapi import WebSocket


class WebSocketManager:
    """WebSocket连接管理器"""

    def __init__(self):
        # 活跃连接: {client_id: WebSocket}
        self.active_connections: dict[str, WebSocket] = {}

        # 订阅关系: {topic: {client_ids}}
        self.subscriptions: dict[str, set[str]] = defaultdict(set)

        # 统计
        self.stats = {
            "total_connections": 0,
            "current_connections": 0,
            "messages_sent": 0,
            "messages_received": 0
        }

    async def connect(self, websocket: WebSocket, client_id: str):
        """建立连接"""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.stats["total_connections"] += 1
        self.stats["current_connections"] += 1

        # 发送欢迎消息
        await self.send_personal_message(
            json.dumps({
                "type": "connection",
                "status": "connected",
                "client_id": client_id,
                "timestamp": datetime.now().isoformat()
            }),
            websocket
        )

    def disconnect(self, client_id: str):
        """断开连接"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            self.stats["current_connections"] -= 1

        # 清理订阅
        for topic in self.subscriptions:
            self.subscriptions[topic].discard(client_id)

    def subscribe(self, client_id: str, topic: str):
        """订阅主题"""
        self.subscriptions[topic].add(client_id)

    def unsubscribe(self, client_id: str, topic: str):
        """取消订阅"""
        self.subscriptions[topic].discard(client_id)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """发送个人消息"""
        try:
            await websocket.send_text(message)
            self.stats["messages_sent"] += 1
        except Exception as e:
            print(f"Error sending message: {e}")

    async def broadcast(self, message: str, topic: str | None = None):
        """广播消息"""
        if topic:
            # 发送给订阅该主题的客户端
            for client_id in self.subscriptions.get(topic, set()):
                if client_id in self.active_connections:
                    websocket = self.active_connections[client_id]
                    await self.send_personal_message(message, websocket)
        else:
            # 发送给所有客户端
            for websocket in self.active_connections.values():
                await self.send_personal_message(message, websocket)

    async def handle_message(self, client_id: str, data: dict[str, Any]):
        """处理客户端消息"""
        self.stats["messages_received"] += 1

        action = data.get("action")

        if action == "subscribe":
            topic = data.get("topic")
            if topic:
                self.subscribe(client_id, topic)
                await self.send_personal_message(
                    json.dumps({
                        "type": "subscription",
                        "status": "subscribed",
                        "topic": topic
                    }),
                    self.active_connections[client_id]
                )

        elif action == "unsubscribe":
            topic = data.get("topic")
            if topic:
                self.unsubscribe(client_id, topic)
                await self.send_personal_message(
                    json.dumps({
                        "type": "subscription",
                        "status": "unsubscribed",
                        "topic": topic
                    }),
                    self.active_connections[client_id]
                )

    def get_stats(self) -> dict[str, int]:
        """获取统计信息"""
        return self.stats.copy()


class MarketDataStream:
    """市场数据流"""

    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager
        self.running = False

    async def start(self):
        """启动数据流"""
        self.running = True
        asyncio.create_task(self._stream_loop())

    async def stop(self):
        """停止数据流"""
        self.running = False

    async def _stream_loop(self):
        """数据流主循环"""
        while self.running:
            try:
                # 模拟获取市场数据
                market_data = await self._fetch_market_data()

                # 广播市场数据
                await self.ws_manager.broadcast(
                    json.dumps({
                        "type": "market_data",
                        "data": market_data,
                        "timestamp": datetime.now().isoformat()
                    }),
                    topic="market_data"
                )

                # 等待下一次更新
                await asyncio.sleep(1)

            except Exception as e:
                print(f"Error in market data stream: {e}")
                await asyncio.sleep(5)

    async def _fetch_market_data(self) -> dict[str, Any]:
        """获取市场数据（示例）"""
        import random

        return {
            "symbol": "AAPL",
            "price": 150.0 + random.uniform(-5, 5),
            "volume": random.randint(1000000, 5000000),
            "timestamp": datetime.now().isoformat()
        }


class OrderUpdateStream:
    """订单更新流"""

    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager

    async def send_order_update(self, order: dict[str, Any]):
        """发送订单更新"""
        await self.ws_manager.broadcast(
            json.dumps({
                "type": "order_update",
                "data": order,
                "timestamp": datetime.now().isoformat()
            }),
            topic="orders"
        )


class PortfolioUpdateStream:
    """投资组合更新流"""

    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager
        self.running = False

    async def start(self):
        """启动更新流"""
        self.running = True
        asyncio.create_task(self._update_loop())

    async def stop(self):
        """停止更新流"""
        self.running = False

    async def _update_loop(self):
        """更新循环"""
        while self.running:
            try:
                # 获取投资组合数据
                portfolio = await self._fetch_portfolio()

                # 广播更新
                await self.ws_manager.broadcast(
                    json.dumps({
                        "type": "portfolio_update",
                        "data": portfolio,
                        "timestamp": datetime.now().isoformat()
                    }),
                    topic="portfolio"
                )

                await asyncio.sleep(5)

            except Exception as e:
                print(f"Error in portfolio update stream: {e}")
                await asyncio.sleep(10)

    async def _fetch_portfolio(self) -> dict[str, Any]:
        """获取投资组合数据（示例）"""
        return {
            "total_value": 1000000,
            "cash": 500000,
            "positions_value": 500000,
            "daily_pnl": 5000,
            "return_rate": 0.05
        }

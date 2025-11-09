"""
交易执行引擎核心
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import uuid

import numpy as np


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class Order:
    """订单"""
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    quantity: int = 0
    price: float | None = None
    stop_price: float | None = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    average_fill_price: float = 0.0
    commission: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Trade:
    """成交记录"""
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    quantity: int = 0
    price: float = 0.0
    commission: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


class ExecutionEngine:
    """交易执行引擎"""

    def __init__(
        self,
        broker_config: dict[str, Any],
        commission_rate: float = 0.001,
        slippage_model: str = "fixed",
        max_slippage: float = 0.002
    ):
        self.broker_config = broker_config
        self.commission_rate = commission_rate
        self.slippage_model = slippage_model
        self.max_slippage = max_slippage

        self.orders: dict[str, Order] = {}
        self.trades: list[Trade] = []
        self.pending_orders: list[Order] = []

        # 回调函数
        self.on_order_update: Callable | None = None
        self.on_trade: Callable | None = None

        # 统计
        self.stats = {
            "total_orders": 0,
            "filled_orders": 0,
            "rejected_orders": 0,
            "cancelled_orders": 0,
            "total_volume": 0.0,
            "total_commission": 0.0,
        }

    async def submit_order(self, order: Order) -> bool:
        """提交订单"""
        try:
            # 验证订单
            if not self._validate_order(order):
                order.status = OrderStatus.REJECTED
                self._update_order(order)
                return False

            # 保存订单
            self.orders[order.order_id] = order
            self.pending_orders.append(order)

            # 更新状态
            order.status = OrderStatus.SUBMITTED
            self._update_order(order)

            self.stats["total_orders"] += 1

            # 异步执行订单
            asyncio.create_task(self._execute_order(order))

            return True

        except Exception as e:
            print(f"Submit order error: {e}")
            order.status = OrderStatus.REJECTED
            self._update_order(order)
            return False

    async def _execute_order(self, order: Order):
        """执行订单"""
        try:
            # 模拟执行延迟
            await asyncio.sleep(0.1)

            # 获取市场价格
            market_price = self._get_market_price(order.symbol)

            # 计算成交价格
            fill_price = self._calculate_fill_price(order, market_price)

            # 计算佣金
            commission = self._calculate_commission(order.quantity, fill_price)

            # 创建成交记录
            trade = Trade(
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=fill_price,
                commission=commission
            )

            # 更新订单
            order.filled_quantity = order.quantity
            order.average_fill_price = fill_price
            order.commission = commission
            order.status = OrderStatus.FILLED
            order.updated_at = datetime.now()

            # 保存成交
            self.trades.append(trade)

            # 更新统计
            self.stats["filled_orders"] += 1
            self.stats["total_volume"] += order.quantity * fill_price
            self.stats["total_commission"] += commission

            # 从待处理列表移除
            if order in self.pending_orders:
                self.pending_orders.remove(order)

            # 触发回调
            self._update_order(order)
            if self.on_trade:
                self.on_trade(trade)

        except Exception as e:
            print(f"Execute order error: {e}")
            order.status = OrderStatus.REJECTED
            self._update_order(order)

    async def cancel_order(self, order_id: str) -> bool:
        """取消订单"""
        if order_id not in self.orders:
            return False

        order = self.orders[order_id]

        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
            return False

        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now()

        if order in self.pending_orders:
            self.pending_orders.remove(order)

        self.stats["cancelled_orders"] += 1
        self._update_order(order)

        return True

    def _validate_order(self, order: Order) -> bool:
        """验证订单"""
        if order.quantity <= 0:
            return False

        if order.order_type == OrderType.LIMIT and order.price is None:
            return False

        return not (order.order_type in [OrderType.STOP, OrderType.STOP_LIMIT] and order.stop_price is None)

    def _get_market_price(self, symbol: str) -> float:
        """获取市场价格（模拟）"""
        # 实际应该从市场数据获取
        return 100.0 + np.random.randn() * 2

    def _calculate_fill_price(self, order: Order, market_price: float) -> float:
        """计算成交价格"""
        if order.order_type == OrderType.MARKET:
            # 市价单 - 应用滑点
            slippage = self._calculate_slippage(order, market_price)
            if order.side == OrderSide.BUY:
                return market_price * (1 + slippage)
            return market_price * (1 - slippage)

        if order.order_type == OrderType.LIMIT:
            # 限价单
            if order.price is None:
                return market_price

            if order.side == OrderSide.BUY:
                return min(order.price, market_price)
            return max(order.price, market_price)

        return market_price

    def _calculate_slippage(self, order: Order, market_price: float) -> float:
        """计算滑点"""
        if self.slippage_model == "fixed":
            return self.max_slippage

        if self.slippage_model == "volume":
            # 基于订单量的滑点模型
            volume_impact = min(0.01, order.quantity / 100000)
            return min(self.max_slippage, volume_impact)

        if self.slippage_model == "adaptive":
            # 自适应滑点
            base_slippage = 0.0005
            volatility_factor = np.random.random() * 0.001
            return min(self.max_slippage, base_slippage + volatility_factor)

        return 0.0

    def _calculate_commission(self, quantity: int, price: float) -> float:
        """计算佣金"""
        return quantity * price * self.commission_rate

    def _update_order(self, order: Order):
        """更新订单状态"""
        if self.on_order_update:
            self.on_order_update(order)

    def get_order(self, order_id: str) -> Order | None:
        """获取订单"""
        return self.orders.get(order_id)

    def get_pending_orders(self) -> list[Order]:
        """获取待处理订单"""
        return self.pending_orders.copy()

    def get_filled_orders(self) -> list[Order]:
        """获取已成交订单"""
        return [o for o in self.orders.values() if o.status == OrderStatus.FILLED]

    def get_trades(self, symbol: str | None = None) -> list[Trade]:
        """获取成交记录"""
        if symbol:
            return [t for t in self.trades if t.symbol == symbol]
        return self.trades.copy()

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息"""
        fill_rate = (self.stats["filled_orders"] / self.stats["total_orders"]
                    if self.stats["total_orders"] > 0 else 0)

        return {
            **self.stats,
            "fill_rate": fill_rate,
            "avg_commission": (self.stats["total_commission"] / self.stats["filled_orders"]
                             if self.stats["filled_orders"] > 0 else 0)
        }

    async def shutdown(self):
        """关闭引擎"""
        # 取消所有待处理订单
        for order in self.pending_orders[:]:
            await self.cancel_order(order.order_id)

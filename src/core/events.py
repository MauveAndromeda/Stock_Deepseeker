"""
事件系统
支持发布-订阅模式、事件队列、异步处理
"""

import asyncio
from collections import defaultdict, deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading
from typing import Any
import uuid


class EventType(Enum):
    """事件类型枚举"""

    # 系统事件
    SYSTEM_STARTED = "system.started"
    SYSTEM_STOPPED = "system.stopped"
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"

    # 数据事件
    DATA_RECEIVED = "data.received"
    DATA_UPDATED = "data.updated"
    DATA_ERROR = "data.error"
    MARKET_DATA_TICK = "data.market.tick"
    MARKET_DATA_BAR = "data.market.bar"

    # 模型事件
    MODEL_LOADED = "model.loaded"
    MODEL_PREDICTION = "model.prediction"
    MODEL_TRAINED = "model.trained"
    MODEL_ERROR = "model.error"

    # 交易事件
    ORDER_CREATED = "order.created"
    ORDER_SUBMITTED = "order.submitted"
    ORDER_FILLED = "order.filled"
    ORDER_PARTIALLY_FILLED = "order.partially_filled"
    ORDER_CANCELLED = "order.cancelled"
    ORDER_REJECTED = "order.rejected"
    ORDER_ERROR = "order.error"

    # 持仓事件
    POSITION_OPENED = "position.opened"
    POSITION_UPDATED = "position.updated"
    POSITION_CLOSED = "position.closed"

    # 风险事件
    RISK_LIMIT_WARNING = "risk.limit.warning"
    RISK_LIMIT_BREACHED = "risk.limit.breached"
    CIRCUIT_BREAKER = "risk.circuit_breaker"
    STOP_LOSS_TRIGGERED = "risk.stop_loss"
    TAKE_PROFIT_TRIGGERED = "risk.take_profit"

    # 智能体事件
    AGENT_DECISION = "agent.decision"
    AGENT_CONSENSUS = "agent.consensus"
    AGENT_ERROR = "agent.error"

    # 监控事件
    METRIC_RECORDED = "monitoring.metric"
    ALERT_TRIGGERED = "monitoring.alert"
    PERFORMANCE_WARNING = "monitoring.performance"


@dataclass
class Event:
    """事件类"""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.SYSTEM_STARTED
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "system"
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # 0=normal, 1=high, 2=critical

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "data": self.data,
            "metadata": self.metadata,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """从字典创建"""
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            event_type=EventType(data["event_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data.get("source", "system"),
            data=data.get("data", {}),
            metadata=data.get("metadata", {}),
            priority=data.get("priority", 0),
        )


class EventBus:
    """事件总线 - 支持同步和异步事件处理"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            # 订阅者字典 {event_type: [handlers]}
            self._subscribers: dict[EventType, list[Callable]] = defaultdict(list)

            # 异步订阅者
            self._async_subscribers: dict[EventType, list[Callable]] = defaultdict(list)

            # 事件历史
            self._event_history = deque(maxlen=10000)
            self._history_enabled = False

            # 事件队列
            self._event_queue = deque()
            self._queue_lock = threading.Lock()

            # 线程池
            self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="EventBus")

            # 统计
            self._stats = {
                "published": 0,
                "delivered": 0,
                "failed": 0,
            }

            self._initialized = True

    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], None],
        async_handler: bool = False
    ):
        """
        订阅事件

        Args:
            event_type: 事件类型
            handler: 事件处理函数
            async_handler: 是否为异步处理器
        """
        if async_handler:
            self._async_subscribers[event_type].append(handler)
        else:
            self._subscribers[event_type].append(handler)

    def unsubscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], None]
    ):
        """
        取消订阅

        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)
        if handler in self._async_subscribers[event_type]:
            self._async_subscribers[event_type].remove(handler)

    def publish(self, event: Event):
        """
        发布事件（同步）

        Args:
            event: 事件对象
        """
        self._stats["published"] += 1

        # 添加到历史
        if self._history_enabled:
            self._event_history.append(event)

        # 获取订阅者
        subscribers = self._subscribers.get(event.event_type, [])

        # 执行同步处理器
        for handler in subscribers:
            try:
                handler(event)
                self._stats["delivered"] += 1
            except Exception as e:
                self._stats["failed"] += 1
                print(f"Error in event handler: {e}")

        # 异步处理器提交到线程池
        async_subscribers = self._async_subscribers.get(event.event_type, [])
        for handler in async_subscribers:
            self._executor.submit(self._handle_async, handler, event)

    def _handle_async(self, handler: Callable, event: Event):
        """异步处理事件"""
        try:
            handler(event)
            self._stats["delivered"] += 1
        except Exception as e:
            self._stats["failed"] += 1
            print(f"Error in async event handler: {e}")

    async def publish_async(self, event: Event):
        """
        异步发布事件

        Args:
            event: 事件对象
        """
        self._stats["published"] += 1

        # 添加到历史
        if self._history_enabled:
            self._event_history.append(event)

        # 获取订阅者
        subscribers = self._subscribers.get(event.event_type, [])
        async_subscribers = self._async_subscribers.get(event.event_type, [])

        # 创建任务
        tasks = []

        # 同步处理器在线程池中执行
        for handler in subscribers:
            task = asyncio.get_event_loop().run_in_executor(
                self._executor,
                self._handle_sync,
                handler,
                event
            )
            tasks.append(task)

        # 异步处理器直接调用
        for handler in async_subscribers:
            if asyncio.iscoroutinefunction(handler):
                tasks.append(handler(event))
            else:
                task = asyncio.get_event_loop().run_in_executor(
                    self._executor,
                    handler,
                    event
                )
                tasks.append(task)

        # 等待所有任务完成
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _handle_sync(self, handler: Callable, event: Event):
        """同步处理事件（在线程池中）"""
        try:
            handler(event)
            self._stats["delivered"] += 1
        except Exception as e:
            self._stats["failed"] += 1
            print(f"Error in sync event handler: {e}")

    def enable_history(self, max_size: int = 10000):
        """启用事件历史"""
        self._history_enabled = True
        self._event_history = deque(maxlen=max_size)

    def disable_history(self):
        """禁用事件历史"""
        self._history_enabled = False

    def get_history(
        self,
        event_type: EventType | None = None,
        limit: int = 100
    ) -> list[Event]:
        """
        获取事件历史

        Args:
            event_type: 过滤事件类型
            limit: 返回数量限制

        Returns:
            事件列表
        """
        events = list(self._event_history)

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        return events[-limit:]

    def clear_history(self):
        """清空事件历史"""
        self._event_history.clear()

    def get_stats(self) -> dict[str, int]:
        """获取统计信息"""
        return self._stats.copy()

    def reset_stats(self):
        """重置统计信息"""
        self._stats = {
            "published": 0,
            "delivered": 0,
            "failed": 0,
        }

    def shutdown(self):
        """关闭事件总线"""
        self._executor.shutdown(wait=True)


# 全局事件总线实例
_global_event_bus = EventBus()


def get_event_bus() -> EventBus:
    """获取全局事件总线"""
    return _global_event_bus


def subscribe(event_type: EventType, handler: Callable, async_handler: bool = False):
    """订阅事件"""
    _global_event_bus.subscribe(event_type, handler, async_handler)


def unsubscribe(event_type: EventType, handler: Callable):
    """取消订阅"""
    _global_event_bus.unsubscribe(event_type, handler)


def publish(event: Event):
    """发布事件"""
    _global_event_bus.publish(event)


async def publish_async(event: Event):
    """异步发布事件"""
    await _global_event_bus.publish_async(event)


# 便捷函数 - 创建特定类型的事件

def create_order_event(
    event_type: EventType,
    order_id: str,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    **kwargs
) -> Event:
    """创建订单事件"""
    return Event(
        event_type=event_type,
        source="trading",
        data={
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            **kwargs
        }
    )


def create_risk_event(
    event_type: EventType,
    message: str,
    severity: str,
    **kwargs
) -> Event:
    """创建风险事件"""
    priority = 2 if severity == "CRITICAL" else (1 if severity == "HIGH" else 0)
    return Event(
        event_type=event_type,
        source="risk",
        priority=priority,
        data={
            "message": message,
            "severity": severity,
            **kwargs
        }
    )


def create_data_event(
    event_type: EventType,
    symbol: str,
    data: dict[str, Any],
    **kwargs
) -> Event:
    """创建数据事件"""
    return Event(
        event_type=event_type,
        source="data",
        data={
            "symbol": symbol,
            "data": data,
            **kwargs
        }
    )


class EventDispatcher:
    """事件分发器 - 用于复杂的事件路由"""

    def __init__(self, event_bus: EventBus | None = None):
        self.event_bus = event_bus or get_event_bus()
        self._rules: list[dict[str, Any]] = []

    def add_rule(
        self,
        source_event: EventType,
        target_events: list[EventType],
        condition: Callable[[Event], bool] | None = None,
        transform: Callable[[Event], dict[str, Any]] | None = None
    ):
        """
        添加路由规则

        Args:
            source_event: 源事件类型
            target_events: 目标事件类型列表
            condition: 条件函数，返回True时才路由
            transform: 数据转换函数
        """
        self._rules.append({
            "source": source_event,
            "targets": target_events,
            "condition": condition,
            "transform": transform,
        })

        # 订阅源事件
        self.event_bus.subscribe(source_event, self._dispatch)

    def _dispatch(self, event: Event):
        """分发事件"""
        for rule in self._rules:
            if rule["source"] != event.event_type:
                continue

            # 检查条件
            if rule["condition"] and not rule["condition"](event):
                continue

            # 转换数据
            data = event.data
            if rule["transform"]:
                data = rule["transform"](event)

            # 发布到目标事件
            for target in rule["targets"]:
                target_event = Event(
                    event_type=target,
                    source=f"dispatcher:{event.source}",
                    data=data,
                    metadata={"original_event_id": event.event_id}
                )
                self.event_bus.publish(target_event)

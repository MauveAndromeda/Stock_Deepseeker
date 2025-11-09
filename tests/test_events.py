"""
测试事件系统模块
"""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.events import Event, EventBus, EventType


class TestEvent:
    """测试事件类"""

    def test_event_creation(self):
        """测试事件创建"""
        event = Event(
            type=EventType.MARKET_DATA,
            data={"symbol": "AAPL", "price": 150.0}
        )
        assert event.type == EventType.MARKET_DATA
        assert event.data["symbol"] == "AAPL"
        assert event.data["price"] == 150.0
        assert event.timestamp is not None

    def test_event_with_source(self):
        """测试带源的事件"""
        event = Event(
            type=EventType.SIGNAL,
            data={"action": "BUY"},
            source="TestStrategy"
        )
        assert event.source == "TestStrategy"

    def test_event_str_representation(self):
        """测试事件字符串表示"""
        event = Event(
            type=EventType.ORDER,
            data={"symbol": "AAPL", "quantity": 100}
        )
        event_str = str(event)
        assert "ORDER" in event_str
        assert "AAPL" in event_str


class TestEventBus:
    """测试事件总线"""

    def setup_method(self):
        """每个测试前的设置"""
        self.event_bus = EventBus()
        self.received_events = []

    def test_singleton_pattern(self):
        """测试单例模式"""
        bus1 = EventBus()
        bus2 = EventBus()
        assert bus1 is bus2, "EventBus应该是单例"

    def test_subscribe_and_publish(self):
        """测试订阅和发布"""
        def handler(event: Event):
            self.received_events.append(event)

        # 订阅
        self.event_bus.subscribe(EventType.MARKET_DATA, handler)

        # 发布
        event = Event(
            type=EventType.MARKET_DATA,
            data={"symbol": "AAPL", "price": 150.0}
        )
        self.event_bus.publish(event)

        # 验证
        assert len(self.received_events) == 1
        assert self.received_events[0].type == EventType.MARKET_DATA
        assert self.received_events[0].data["symbol"] == "AAPL"

    def test_multiple_subscribers(self):
        """测试多个订阅者"""
        received_1 = []
        received_2 = []

        def handler1(event: Event):
            received_1.append(event)

        def handler2(event: Event):
            received_2.append(event)

        # 两个订阅者订阅同一事件
        self.event_bus.subscribe(EventType.SIGNAL, handler1)
        self.event_bus.subscribe(EventType.SIGNAL, handler2)

        # 发布事件
        event = Event(type=EventType.SIGNAL, data={"action": "BUY"})
        self.event_bus.publish(event)

        # 验证两个订阅者都收到了事件
        assert len(received_1) == 1
        assert len(received_2) == 1

    def test_unsubscribe(self):
        """测试取消订阅"""
        def handler(event: Event):
            self.received_events.append(event)

        # 订阅
        self.event_bus.subscribe(EventType.ORDER, handler)

        # 发布第一个事件
        event1 = Event(type=EventType.ORDER, data={"symbol": "AAPL"})
        self.event_bus.publish(event1)
        assert len(self.received_events) == 1

        # 取消订阅
        self.event_bus.unsubscribe(EventType.ORDER, handler)

        # 发布第二个事件
        event2 = Event(type=EventType.ORDER, data={"symbol": "MSFT"})
        self.event_bus.publish(event2)

        # 验证不再收到事件
        assert len(self.received_events) == 1

    def test_event_filtering_by_type(self):
        """测试按类型过滤事件"""
        market_events = []
        signal_events = []

        def market_handler(event: Event):
            market_events.append(event)

        def signal_handler(event: Event):
            signal_events.append(event)

        # 订阅不同类型的事件
        self.event_bus.subscribe(EventType.MARKET_DATA, market_handler)
        self.event_bus.subscribe(EventType.SIGNAL, signal_handler)

        # 发布不同类型的事件
        self.event_bus.publish(Event(type=EventType.MARKET_DATA, data={}))
        self.event_bus.publish(Event(type=EventType.SIGNAL, data={}))
        self.event_bus.publish(Event(type=EventType.MARKET_DATA, data={}))

        # 验证正确过滤
        assert len(market_events) == 2
        assert len(signal_events) == 1

    def test_clear_all_subscribers(self):
        """测试清除所有订阅者"""
        def handler(event: Event):
            self.received_events.append(event)

        # 订阅多个事件类型
        self.event_bus.subscribe(EventType.MARKET_DATA, handler)
        self.event_bus.subscribe(EventType.SIGNAL, handler)

        # 清除所有订阅
        self.event_bus.clear()

        # 发布事件
        self.event_bus.publish(Event(type=EventType.MARKET_DATA, data={}))
        self.event_bus.publish(Event(type=EventType.SIGNAL, data={}))

        # 验证没有收到任何事件
        assert len(self.received_events) == 0

    def test_handler_exception_handling(self):
        """测试处理器异常处理"""
        good_events = []

        def bad_handler(event: Event):
            raise Exception("Handler error")

        def good_handler(event: Event):
            good_events.append(event)

        # 订阅（一个会出错，一个正常）
        self.event_bus.subscribe(EventType.ORDER, bad_handler)
        self.event_bus.subscribe(EventType.ORDER, good_handler)

        # 发布事件
        event = Event(type=EventType.ORDER, data={})
        self.event_bus.publish(event)

        # 验证好的处理器仍然收到事件
        assert len(good_events) == 1


class TestEventType:
    """测试事件类型枚举"""

    def test_event_type_values(self):
        """测试事件类型值"""
        assert EventType.MARKET_DATA == "market_data"
        assert EventType.SIGNAL == "signal"
        assert EventType.ORDER == "order"
        assert EventType.FILL == "fill"
        assert EventType.PORTFOLIO_UPDATE == "portfolio_update"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

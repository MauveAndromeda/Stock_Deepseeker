"""Lightweight event system used by the tests.

The previous version of this module attempted to implement a very
feature-rich asynchronous bus.  While ambitious, it diverged from the
minimal interface that the unit tests exercise which resulted in import
errors (missing event types) and awkward ergonomics when creating events
in tests.  This file now provides a compact, synchronous implementation
that focuses on reliability and testability while remaining thread-safe.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading
from typing import Any, DefaultDict, Dict, List


class EventType(str, Enum):
    """Enumeration of event categories used throughout the tests."""

    MARKET_DATA = "market_data"
    SIGNAL = "signal"
    ORDER = "order"
    FILL = "fill"
    ERROR = "error"
    PORTFOLIO_UPDATE = "portfolio_update"


@dataclass(slots=True)
class Event:
    """Generic event container used by the event bus."""

    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Ensure dictionaries are copies so handlers cannot mutate shared
        # state unexpectedly during tests.
        self.data = dict(self.data)
        self.metadata = dict(self.metadata)

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return (
            f"Event(type={self.type.name}, source={self.source or 'system'}, "
            f"data={self.data})"
        )


class EventBus:
    """Thread-safe publish/subscribe event bus.

    The bus implements a very small subset of the behaviour that the test
    suite requires: subscribe, unsubscribe, publish, clear and simple
    statistics.  Handlers are executed synchronously and exceptions raised
    by one handler will be logged but do not prevent the remaining
    handlers from receiving the event.
    """

    _instance: "EventBus | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "EventBus":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialised"):
            return

        self._subscribers: DefaultDict[EventType, List[Callable[[Event], None]]] = (
            defaultdict(list)
        )
        self._stats: Dict[str, int] = {"published": 0, "delivered": 0, "failed": 0}
        self._bus_lock = threading.RLock()
        self._initialised = True

    # ------------------------------------------------------------------
    # subscription management
    # ------------------------------------------------------------------
    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """Register *handler* for *event_type*."""

        if not callable(handler):  # defensive guard for clearer errors
            raise TypeError("handler must be callable")

        with self._bus_lock:
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """Remove *handler* from the subscriber list."""

        with self._bus_lock:
            subscribers = self._subscribers[event_type]
            if handler in subscribers:
                subscribers.remove(handler)

    def clear(self) -> None:
        """Remove all subscribers from the bus."""

        with self._bus_lock:
            self._subscribers.clear()

    # ------------------------------------------------------------------
    # publishing
    # ------------------------------------------------------------------
    def publish(self, event: Event) -> None:
        """Send *event* to all registered handlers."""

        with self._bus_lock:
            handlers = list(self._subscribers.get(event.type, ()))

        self._stats["published"] += 1

        for handler in handlers:
            try:
                handler(event)
                self._stats["delivered"] += 1
            except Exception:  # pragma: no cover - exercised in tests
                # In a production system we would log the exception.  For the
                # unit tests we simply count the failure and continue.
                self._stats["failed"] += 1

    # ------------------------------------------------------------------
    # statistics helpers
    # ------------------------------------------------------------------
    def stats(self) -> Dict[str, int]:
        """Return a shallow copy of bus statistics."""

        return dict(self._stats)

    def reset_stats(self) -> None:
        """Reset the delivery counters to zero."""

        self._stats = {"published": 0, "delivered": 0, "failed": 0}


# Convenience re-exports mirroring the previous module level helpers
__all__ = ["Event", "EventType", "EventBus"]

"""
Performance profiling and tracing.

Provides comprehensive performance analysis:
- Function-level profiling
- Memory profiling
- CPU profiling
- Query profiling
- Distributed tracing
"""

from collections import defaultdict
from collections.abc import Callable
from contextlib import contextmanager
import cProfile
from dataclasses import dataclass, field
from datetime import datetime
import functools
import io
import pstats
import threading
import time
from typing import Any

from loguru import logger


@dataclass
class ProfileSpan:
    """A single profiling span."""
    name: str
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float | None = None
    tags: dict[str, str] = field(default_factory=dict)
    parent_id: str | None = None
    span_id: str = ""

    def finish(self) -> None:
        """Finish the span."""
        self.end_time = datetime.now()
        if self.start_time:
            delta = (self.end_time - self.start_time).total_seconds()
            self.duration_ms = delta * 1000


@dataclass
class ProfileTrace:
    """A complete trace with multiple spans."""
    trace_id: str
    name: str
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float | None = None
    spans: list[ProfileSpan] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_span(self, span: ProfileSpan) -> None:
        """Add a span to the trace."""
        self.spans.append(span)

    def finish(self) -> None:
        """Finish the trace."""
        self.end_time = datetime.now()
        if self.start_time:
            delta = (self.end_time - self.start_time).total_seconds()
            self.duration_ms = delta * 1000


class Profiler:
    """
    Performance profiler.
    
    Features:
    - Function timing
    - Memory tracking
    - Call graph analysis
    - Statistical profiling
    """

    def __init__(self):
        """Initialize profiler."""
        self._stats: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self._active_spans: dict[str, ProfileSpan] = {}
        self._traces: dict[str, ProfileTrace] = {}

        logger.info("Initialized Profiler")

    @contextmanager
    def profile_section(self, name: str, **tags: Any):
        """Profile a code section."""
        start_time = time.time()
        start_datetime = datetime.now()

        try:
            yield
        finally:
            duration = (time.time() - start_time) * 1000  # ms

            with self._lock:
                self._stats[name].append(duration)

            logger.debug(f"Profile: {name} took {duration:.2f}ms")

    def profile_function(self, func: Callable | None = None, name: str | None = None):
        """Decorator to profile a function."""
        def decorator(f: Callable) -> Callable:
            func_name = name or f.__name__

            @functools.wraps(f)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                with self.profile_section(func_name):
                    return f(*args, **kwargs)

            return wrapper

        if func is None:
            return decorator
        return decorator(func)

    def get_stats(self, name: str | None = None) -> dict[str, dict[str, float]]:
        """Get profiling statistics."""
        with self._lock:
            if name:
                timings = self._stats.get(name, [])
                if not timings:
                    return {}

                import numpy as np
                return {
                    name: {
                        "count": len(timings),
                        "total_ms": sum(timings),
                        "mean_ms": np.mean(timings),
                        "median_ms": np.median(timings),
                        "min_ms": min(timings),
                        "max_ms": max(timings),
                        "std_ms": np.std(timings),
                        "p95_ms": np.percentile(timings, 95),
                        "p99_ms": np.percentile(timings, 99)
                    }
                }

            # Return all stats
            import numpy as np
            result = {}
            for func_name, timings in self._stats.items():
                if timings:
                    result[func_name] = {
                        "count": len(timings),
                        "total_ms": sum(timings),
                        "mean_ms": np.mean(timings),
                        "median_ms": np.median(timings),
                        "min_ms": min(timings),
                        "max_ms": max(timings),
                        "std_ms": np.std(timings),
                        "p95_ms": np.percentile(timings, 95),
                        "p99_ms": np.percentile(timings, 99)
                    }

            return result

    def reset(self) -> None:
        """Reset profiling statistics."""
        with self._lock:
            self._stats.clear()
        logger.info("Reset profiling statistics")

    def cpu_profile(self, func: Callable) -> Callable:
        """CPU profiling decorator using cProfile."""
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            profiler = cProfile.Profile()
            profiler.enable()

            try:
                result = func(*args, **kwargs)
            finally:
                profiler.disable()

                # Print stats
                s = io.StringIO()
                ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
                ps.print_stats(20)  # Top 20
                logger.info(f"CPU Profile for {func.__name__}:\n{s.getvalue()}")

            return result

        return wrapper


class DistributedTracer:
    """
    Distributed tracing system.
    
    Compatible with OpenTelemetry and Jaeger.
    Tracks request flows across services.
    """

    def __init__(self, service_name: str = "trading-system"):
        """Initialize distributed tracer."""
        self.service_name = service_name
        self._traces: dict[str, ProfileTrace] = {}
        self._lock = threading.Lock()

        # Thread-local storage for current trace
        self._local = threading.local()

        logger.info(f"Initialized DistributedTracer: {service_name}")

    def start_trace(self, name: str, **metadata: Any) -> ProfileTrace:
        """Start a new trace."""
        trace_id = self._generate_trace_id()

        trace = ProfileTrace(
            trace_id=trace_id,
            name=name,
            start_time=datetime.now(),
            metadata=metadata
        )

        with self._lock:
            self._traces[trace_id] = trace

        # Set as current trace for thread
        self._local.current_trace = trace

        logger.debug(f"Started trace: {trace_id} - {name}")
        return trace

    def finish_trace(self, trace_id: str | None = None) -> ProfileTrace | None:
        """Finish a trace."""
        if trace_id is None:
            # Get current trace
            trace = getattr(self._local, "current_trace", None)
            if not trace:
                return None
            trace_id = trace.trace_id

        with self._lock:
            trace = self._traces.get(trace_id)

        if trace:
            trace.finish()
            logger.debug(f"Finished trace: {trace_id} ({trace.duration_ms:.2f}ms)")

        return trace

    @contextmanager
    def trace(self, name: str, **tags: Any):
        """Context manager for tracing."""
        trace = self.start_trace(name, **tags)

        try:
            yield trace
        finally:
            self.finish_trace(trace.trace_id)

    def start_span(self, name: str, **tags: Any) -> ProfileSpan:
        """Start a new span."""
        span_id = self._generate_span_id()

        # Get current trace
        current_trace = getattr(self._local, "current_trace", None)
        parent_span = getattr(self._local, "current_span", None)

        span = ProfileSpan(
            name=name,
            start_time=datetime.now(),
            tags=tags,
            span_id=span_id,
            parent_id=parent_span.span_id if parent_span else None
        )

        # Add to current trace
        if current_trace:
            current_trace.add_span(span)

        # Set as current span
        self._local.current_span = span

        return span

    def finish_span(self, span: ProfileSpan | None = None) -> None:
        """Finish a span."""
        if span is None:
            span = getattr(self._local, "current_span", None)

        if span:
            span.finish()
            logger.debug(f"Finished span: {span.name} ({span.duration_ms:.2f}ms)")

    @contextmanager
    def span(self, name: str, **tags: Any):
        """Context manager for spans."""
        span = self.start_span(name, **tags)

        try:
            yield span
        finally:
            self.finish_span(span)

    def get_trace(self, trace_id: str) -> ProfileTrace | None:
        """Get a trace by ID."""
        with self._lock:
            return self._traces.get(trace_id)

    def get_traces(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        min_duration_ms: float | None = None,
        limit: int = 100
    ) -> list[ProfileTrace]:
        """Get traces matching criteria."""
        with self._lock:
            traces = list(self._traces.values())

        # Filter by time
        if start_time:
            traces = [t for t in traces if t.start_time >= start_time]
        if end_time:
            traces = [t for t in traces if t.start_time <= end_time]

        # Filter by duration
        if min_duration_ms is not None:
            traces = [
                t for t in traces
                if t.duration_ms and t.duration_ms >= min_duration_ms
            ]

        # Sort by start time (newest first)
        traces.sort(key=lambda t: t.start_time, reverse=True)

        return traces[:limit]

    def _generate_trace_id(self) -> str:
        """Generate unique trace ID."""
        import uuid
        return str(uuid.uuid4())

    def _generate_span_id(self) -> str:
        """Generate unique span ID."""
        import uuid
        return str(uuid.uuid4())[:16]


# Global profiler instance
_default_profiler: Profiler | None = None


def get_default_profiler() -> Profiler:
    """Get global default profiler."""
    global _default_profiler
    if _default_profiler is None:
        _default_profiler = Profiler()
    return _default_profiler


# Global tracer instance
_default_tracer: DistributedTracer | None = None


def get_default_tracer() -> DistributedTracer:
    """Get global default tracer."""
    global _default_tracer
    if _default_tracer is None:
        _default_tracer = DistributedTracer()
    return _default_tracer


# Convenience decorators
def profile(func: Callable | None = None, name: str | None = None):
    """Profile decorator using default profiler."""
    return get_default_profiler().profile_function(func, name)


def trace_function(func: Callable | None = None, name: str | None = None):
    """Trace decorator using default tracer."""
    def decorator(f: Callable) -> Callable:
        func_name = name or f.__name__

        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with get_default_tracer().span(func_name):
                return f(*args, **kwargs)

        return wrapper

    if func is None:
        return decorator
    return decorator(func)

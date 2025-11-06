"""
Metrics collection and aggregation system.

Provides a comprehensive metrics system with support for:
- Counters (monotonically increasing values)
- Gauges (point-in-time values)
- Histograms (distributions)
- Summaries (statistical summaries)
- Time-series export to Prometheus/InfluxDB
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from collections import defaultdict, deque
import threading
import time
import numpy as np
from loguru import logger


class MetricType(Enum):
    """Metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class Metric:
    """Base metric class."""
    name: str
    type: MetricType
    description: str
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    value: float = 0.0


class Counter:
    """
    Counter metric - monotonically increasing value.
    
    Use cases: trades executed, errors, API calls
    """
    
    def __init__(self, name: str, description: str, labels: Optional[Dict[str, str]] = None):
        """Initialize counter."""
        self.name = name
        self.description = description
        self.labels = labels or {}
        self._value = 0.0
        self._lock = threading.Lock()
    
    def inc(self, amount: float = 1.0) -> None:
        """Increment counter."""
        with self._lock:
            self._value += amount
    
    def get(self) -> float:
        """Get current value."""
        with self._lock:
            return self._value
    
    def reset(self) -> None:
        """Reset counter to 0."""
        with self._lock:
            self._value = 0.0
    
    def to_metric(self) -> Metric:
        """Convert to Metric object."""
        return Metric(
            name=self.name,
            type=MetricType.COUNTER,
            description=self.description,
            labels=self.labels,
            value=self.get()
        )


class Gauge:
    """
    Gauge metric - can go up or down.
    
    Use cases: portfolio value, position count, memory usage
    """
    
    def __init__(self, name: str, description: str, labels: Optional[Dict[str, str]] = None):
        """Initialize gauge."""
        self.name = name
        self.description = description
        self.labels = labels or {}
        self._value = 0.0
        self._lock = threading.Lock()
    
    def set(self, value: float) -> None:
        """Set gauge value."""
        with self._lock:
            self._value = value
    
    def inc(self, amount: float = 1.0) -> None:
        """Increment gauge."""
        with self._lock:
            self._value += amount
    
    def dec(self, amount: float = 1.0) -> None:
        """Decrement gauge."""
        with self._lock:
            self._value -= amount
    
    def get(self) -> float:
        """Get current value."""
        with self._lock:
            return self._value
    
    def to_metric(self) -> Metric:
        """Convert to Metric object."""
        return Metric(
            name=self.name,
            type=MetricType.GAUGE,
            description=self.description,
            labels=self.labels,
            value=self.get()
        )


class Histogram:
    """
    Histogram metric - tracks distribution of values.
    
    Use cases: trade execution latency, order sizes, returns distribution
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        buckets: Optional[List[float]] = None,
        labels: Optional[Dict[str, str]] = None
    ):
        """Initialize histogram."""
        self.name = name
        self.description = description
        self.labels = labels or {}
        
        # Default buckets for latency (seconds)
        self.buckets = buckets or [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0]
        
        self._counts = [0] * (len(self.buckets) + 1)  # +1 for +Inf bucket
        self._sum = 0.0
        self._count = 0
        self._lock = threading.Lock()
    
    def observe(self, value: float) -> None:
        """Observe a value."""
        with self._lock:
            self._sum += value
            self._count += 1
            
            # Find appropriate bucket
            for i, bucket in enumerate(self.buckets):
                if value <= bucket:
                    self._counts[i] += 1
                    return
            
            # Value exceeds all buckets - goes to +Inf
            self._counts[-1] += 1
    
    def get_buckets(self) -> Dict[str, int]:
        """Get bucket counts."""
        with self._lock:
            result = {}
            for i, bucket in enumerate(self.buckets):
                result[f"le_{bucket}"] = self._counts[i]
            result["le_inf"] = self._counts[-1]
            return result
    
    def get_stats(self) -> Dict[str, float]:
        """Get statistical summary."""
        with self._lock:
            if self._count == 0:
                return {"sum": 0.0, "count": 0, "avg": 0.0}
            
            return {
                "sum": self._sum,
                "count": self._count,
                "avg": self._sum / self._count
            }
    
    def to_metric(self) -> Metric:
        """Convert to Metric object."""
        stats = self.get_stats()
        return Metric(
            name=self.name,
            type=MetricType.HISTOGRAM,
            description=self.description,
            labels=self.labels,
            value=stats["avg"]
        )


class Summary:
    """
    Summary metric - provides statistical summary over sliding time window.
    
    Use cases: Sharpe ratio, win rate, average PnL
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        max_age_seconds: int = 600,
        quantiles: Optional[List[float]] = None,
        labels: Optional[Dict[str, str]] = None
    ):
        """Initialize summary."""
        self.name = name
        self.description = description
        self.labels = labels or {}
        self.max_age_seconds = max_age_seconds
        self.quantiles = quantiles or [0.5, 0.9, 0.95, 0.99]
        
        self._observations: deque = deque()
        self._lock = threading.Lock()
    
    def observe(self, value: float) -> None:
        """Observe a value."""
        with self._lock:
            now = time.time()
            self._observations.append((now, value))
            
            # Remove old observations
            cutoff = now - self.max_age_seconds
            while self._observations and self._observations[0][0] < cutoff:
                self._observations.popleft()
    
    def get_stats(self) -> Dict[str, float]:
        """Get statistical summary."""
        with self._lock:
            if not self._observations:
                return {
                    "count": 0,
                    "sum": 0.0,
                    "mean": 0.0,
                    "std": 0.0
                }
            
            values = np.array([v for _, v in self._observations])
            
            stats = {
                "count": len(values),
                "sum": float(np.sum(values)),
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
            }
            
            # Add quantiles
            for q in self.quantiles:
                stats[f"q{int(q*100)}"] = float(np.percentile(values, q * 100))
            
            return stats
    
    def to_metric(self) -> Metric:
        """Convert to Metric object."""
        stats = self.get_stats()
        return Metric(
            name=self.name,
            type=MetricType.SUMMARY,
            description=self.description,
            labels=self.labels,
            value=stats["mean"]
        )


class MetricsCollector:
    """
    Central metrics collection and export.
    
    Features:
    - Thread-safe metric registration
    - Automatic metrics export
    - Support for multiple export targets (Prometheus, InfluxDB)
    - Metric aggregation and transformation
    """
    
    def __init__(self, prefix: str = "trading"):
        """Initialize metrics collector."""
        self.prefix = prefix
        self._metrics: Dict[str, Any] = {}
        self._lock = threading.Lock()
        
        # Built-in system metrics
        self._register_system_metrics()
        
        logger.info(f"Initialized MetricsCollector with prefix: {prefix}")
    
    def _register_system_metrics(self) -> None:
        """Register built-in system metrics."""
        self.register_gauge(
            "system_cpu_usage",
            "System CPU usage percentage"
        )
        self.register_gauge(
            "system_memory_usage",
            "System memory usage in bytes"
        )
        self.register_gauge(
            "system_disk_usage",
            "System disk usage percentage"
        )
    
    def register_counter(
        self,
        name: str,
        description: str,
        labels: Optional[Dict[str, str]] = None
    ) -> Counter:
        """Register a counter metric."""
        full_name = f"{self.prefix}_{name}"
        
        with self._lock:
            if full_name in self._metrics:
                return self._metrics[full_name]
            
            counter = Counter(full_name, description, labels)
            self._metrics[full_name] = counter
            logger.debug(f"Registered counter: {full_name}")
            return counter
    
    def register_gauge(
        self,
        name: str,
        description: str,
        labels: Optional[Dict[str, str]] = None
    ) -> Gauge:
        """Register a gauge metric."""
        full_name = f"{self.prefix}_{name}"
        
        with self._lock:
            if full_name in self._metrics:
                return self._metrics[full_name]
            
            gauge = Gauge(full_name, description, labels)
            self._metrics[full_name] = gauge
            logger.debug(f"Registered gauge: {full_name}")
            return gauge
    
    def register_histogram(
        self,
        name: str,
        description: str,
        buckets: Optional[List[float]] = None,
        labels: Optional[Dict[str, str]] = None
    ) -> Histogram:
        """Register a histogram metric."""
        full_name = f"{self.prefix}_{name}"
        
        with self._lock:
            if full_name in self._metrics:
                return self._metrics[full_name]
            
            histogram = Histogram(full_name, description, buckets, labels)
            self._metrics[full_name] = histogram
            logger.debug(f"Registered histogram: {full_name}")
            return histogram
    
    def register_summary(
        self,
        name: str,
        description: str,
        max_age_seconds: int = 600,
        quantiles: Optional[List[float]] = None,
        labels: Optional[Dict[str, str]] = None
    ) -> Summary:
        """Register a summary metric."""
        full_name = f"{self.prefix}_{name}"
        
        with self._lock:
            if full_name in self._metrics:
                return self._metrics[full_name]
            
            summary = Summary(full_name, description, max_age_seconds, quantiles, labels)
            self._metrics[full_name] = summary
            logger.debug(f"Registered summary: {full_name}")
            return summary
    
    def get_all_metrics(self) -> List[Metric]:
        """Get all metrics as Metric objects."""
        with self._lock:
            return [m.to_metric() for m in self._metrics.values()]
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        for metric in self.get_all_metrics():
            # HELP line
            lines.append(f"# HELP {metric.name} {metric.description}")
            
            # TYPE line
            lines.append(f"# TYPE {metric.name} {metric.type.value}")
            
            # Metric line
            labels_str = ",".join([f'{k}="{v}"' for k, v in metric.labels.items()])
            if labels_str:
                lines.append(f"{metric.name}{{{labels_str}}} {metric.value}")
            else:
                lines.append(f"{metric.name} {metric.value}")
        
        return "\n".join(lines)
    
    def export_influxdb(self) -> List[Dict[str, Any]]:
        """Export metrics in InfluxDB line protocol format."""
        points = []
        
        for metric in self.get_all_metrics():
            point = {
                "measurement": metric.name,
                "tags": metric.labels,
                "fields": {"value": metric.value},
                "time": int(metric.timestamp.timestamp() * 1e9)  # nanoseconds
            }
            points.append(point)
        
        return points
    
    def get_metric(self, name: str) -> Optional[Any]:
        """Get metric by name."""
        full_name = f"{self.prefix}_{name}"
        with self._lock:
            return self._metrics.get(full_name)
    
    def clear(self) -> None:
        """Clear all metrics."""
        with self._lock:
            self._metrics.clear()
            self._register_system_metrics()
        
        logger.info("Cleared all metrics")


# Global metrics collector instance
_default_collector: Optional[MetricsCollector] = None


def get_default_collector() -> MetricsCollector:
    """Get global default metrics collector."""
    global _default_collector
    if _default_collector is None:
        _default_collector = MetricsCollector()
    return _default_collector

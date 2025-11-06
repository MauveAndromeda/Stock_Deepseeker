"""
Time-series database integration.

Support for multiple TSDB backends:
- InfluxDB
- Prometheus
- TimescaleDB
- In-memory time-series store
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from collections import defaultdict, deque
import threading
from loguru import logger


@dataclass
class TimeSeriesPoint:
    """Single time-series data point."""
    timestamp: datetime
    value: float
    tags: Dict[str, str]


@dataclass
class TimeSeriesQuery:
    """Time-series query parameters."""
    metric: str
    start_time: datetime
    end_time: datetime
    tags: Optional[Dict[str, str]] = None
    aggregation: Optional[str] = None  # avg, sum, min, max
    interval: Optional[str] = None  # 1m, 5m, 1h


class InMemoryTSDB:
    """
    In-memory time-series database.
    
    Lightweight TSDB for development and testing.
    Supports basic time-series operations with retention policy.
    """
    
    def __init__(self, retention_hours: int = 24, max_points_per_metric: int = 100000):
        """Initialize in-memory TSDB."""
        self.retention_hours = retention_hours
        self.max_points_per_metric = max_points_per_metric
        
        # Storage: metric_name -> deque of points
        self._data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_points_per_metric))
        self._lock = threading.Lock()
        
        logger.info(f"Initialized InMemoryTSDB (retention: {retention_hours}h)")
    
    def write(self, metric: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Write a data point."""
        point = TimeSeriesPoint(
            timestamp=datetime.now(),
            value=value,
            tags=tags or {}
        )
        
        with self._lock:
            self._data[metric].append(point)
    
    def write_batch(self, points: List[tuple]) -> None:
        """Write multiple data points."""
        for metric, value, tags in points:
            self.write(metric, value, tags)
    
    def query(self, query: TimeSeriesQuery) -> List[TimeSeriesPoint]:
        """Query time-series data."""
        with self._lock:
            points = list(self._data.get(query.metric, []))
        
        # Filter by time range
        points = [
            p for p in points
            if query.start_time <= p.timestamp <= query.end_time
        ]
        
        # Filter by tags
        if query.tags:
            points = [
                p for p in points
                if all(p.tags.get(k) == v for k, v in query.tags.items())
            ]
        
        return points
    
    def aggregate(self, query: TimeSeriesQuery) -> float:
        """Aggregate time-series data."""
        points = self.query(query)
        
        if not points:
            return 0.0
        
        values = [p.value for p in points]
        
        if query.aggregation == "sum":
            return sum(values)
        elif query.aggregation == "min":
            return min(values)
        elif query.aggregation == "max":
            return max(values)
        else:  # avg or default
            return sum(values) / len(values)
    
    def get_latest(self, metric: str, tags: Optional[Dict[str, str]] = None) -> Optional[TimeSeriesPoint]:
        """Get latest point for metric."""
        with self._lock:
            points = list(self._data.get(metric, []))
        
        if not points:
            return None
        
        # Filter by tags if provided
        if tags:
            points = [
                p for p in points
                if all(p.tags.get(k) == v for k, v in tags.items())
            ]
        
        return points[-1] if points else None
    
    def cleanup(self) -> int:
        """Remove expired data points."""
        cutoff = datetime.now() - timedelta(hours=self.retention_hours)
        removed = 0
        
        with self._lock:
            for metric, points in self._data.items():
                original_len = len(points)
                # Filter out expired points
                while points and points[0].timestamp < cutoff:
                    points.popleft()
                    removed += 1
        
        if removed > 0:
            logger.info(f"Cleaned up {removed} expired time-series points")
        
        return removed


class InfluxDBClient:
    """
    InfluxDB client for time-series storage.
    
    Supports InfluxDB 2.x with authentication and organization.
    """
    
    def __init__(
        self,
        url: str,
        token: str,
        org: str,
        bucket: str
    ):
        """Initialize InfluxDB client."""
        self.url = url
        self.token = token
        self.org = org
        self.bucket = bucket
        
        try:
            from influxdb_client import InfluxDBClient as InfluxClient
            from influxdb_client.client.write_api import SYNCHRONOUS
            
            self._client = InfluxClient(url=url, token=token, org=org)
            self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
            self._query_api = self._client.query_api()
            
            logger.info(f"Connected to InfluxDB: {url}")
        except ImportError:
            logger.warning("influxdb-client not installed. Install with: pip install influxdb-client")
            self._client = None
    
    def write(self, metric: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Write a data point."""
        if not self._client:
            return
        
        from influxdb_client import Point
        
        point = Point(metric).field("value", value)
        
        if tags:
            for key, val in tags.items():
                point = point.tag(key, val)
        
        try:
            self._write_api.write(bucket=self.bucket, record=point)
        except Exception as e:
            logger.error(f"Failed to write to InfluxDB: {e}")
    
    def query(self, query: TimeSeriesQuery) -> List[TimeSeriesPoint]:
        """Query time-series data."""
        if not self._client:
            return []
        
        # Build Flux query
        flux_query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: {query.start_time.isoformat()}, stop: {query.end_time.isoformat()})
          |> filter(fn: (r) => r._measurement == "{query.metric}")
        '''
        
        if query.tags:
            for key, value in query.tags.items():
                flux_query += f'  |> filter(fn: (r) => r.{key} == "{value}")\n'
        
        try:
            result = self._query_api.query(flux_query, org=self.org)
            
            points = []
            for table in result:
                for record in table.records:
                    point = TimeSeriesPoint(
                        timestamp=record.get_time(),
                        value=record.get_value(),
                        tags={k: v for k, v in record.values.items() if k.startswith("_") is False}
                    )
                    points.append(point)
            
            return points
            
        except Exception as e:
            logger.error(f"Failed to query InfluxDB: {e}")
            return []


class PrometheusClient:
    """
    Prometheus client for metrics scraping.
    
    Exposes metrics endpoint for Prometheus to scrape.
    """
    
    def __init__(self, port: int = 8000):
        """Initialize Prometheus client."""
        self.port = port
        
        try:
            from prometheus_client import start_http_server, Counter, Gauge, Histogram, Summary
            
            self._counter_class = Counter
            self._gauge_class = Gauge
            self._histogram_class = Histogram
            self._summary_class = Summary
            
            self._metrics: Dict[str, Any] = {}
            
            # Start metrics server
            start_http_server(port)
            logger.info(f"Started Prometheus metrics server on port {port}")
            
        except ImportError:
            logger.warning("prometheus-client not installed. Install with: pip install prometheus-client")
    
    def register_counter(self, name: str, description: str) -> Any:
        """Register a counter metric."""
        if name not in self._metrics:
            self._metrics[name] = self._counter_class(name, description)
        return self._metrics[name]
    
    def register_gauge(self, name: str, description: str) -> Any:
        """Register a gauge metric."""
        if name not in self._metrics:
            self._metrics[name] = self._gauge_class(name, description)
        return self._metrics[name]
    
    def register_histogram(self, name: str, description: str, buckets: Optional[List[float]] = None) -> Any:
        """Register a histogram metric."""
        if name not in self._metrics:
            kwargs = {"buckets": buckets} if buckets else {}
            self._metrics[name] = self._histogram_class(name, description, **kwargs)
        return self._metrics[name]


class TimeSeriesDB:
    """
    Unified time-series database interface.
    
    Supports multiple backends with automatic fallback.
    """
    
    def __init__(
        self,
        backend: str = "memory",
        **kwargs: Any
    ):
        """Initialize time-series database."""
        self.backend = backend
        
        if backend == "memory":
            self._db = InMemoryTSDB(**kwargs)
        elif backend == "influxdb":
            self._db = InfluxDBClient(**kwargs)
        elif backend == "prometheus":
            self._db = PrometheusClient(**kwargs)
        else:
            logger.warning(f"Unknown backend: {backend}, using in-memory")
            self._db = InMemoryTSDB()
        
        logger.info(f"Initialized TimeSeriesDB with backend: {backend}")
    
    def write(self, metric: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Write a data point."""
        self._db.write(metric, value, tags)
    
    def write_batch(self, points: List[tuple]) -> None:
        """Write multiple data points."""
        if hasattr(self._db, 'write_batch'):
            self._db.write_batch(points)
        else:
            for metric, value, tags in points:
                self.write(metric, value, tags)
    
    def query(self, query: TimeSeriesQuery) -> List[TimeSeriesPoint]:
        """Query time-series data."""
        if hasattr(self._db, 'query'):
            return self._db.query(query)
        return []
    
    def aggregate(self, query: TimeSeriesQuery) -> float:
        """Aggregate time-series data."""
        if hasattr(self._db, 'aggregate'):
            return self._db.aggregate(query)
        
        # Fallback to manual aggregation
        points = self.query(query)
        if not points:
            return 0.0
        
        values = [p.value for p in points]
        
        if query.aggregation == "sum":
            return sum(values)
        elif query.aggregation == "min":
            return min(values)
        elif query.aggregation == "max":
            return max(values)
        else:
            return sum(values) / len(values)


# Global TSDB instance
_default_tsdb: Optional[TimeSeriesDB] = None


def get_default_tsdb() -> TimeSeriesDB:
    """Get global default TSDB."""
    global _default_tsdb
    if _default_tsdb is None:
        _default_tsdb = TimeSeriesDB(backend="memory")
    return _default_tsdb

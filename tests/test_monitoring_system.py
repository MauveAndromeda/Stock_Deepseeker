"""
Comprehensive monitoring system test suite.

Tests for:
- Metrics collection
- Logging
- Alerts
- Health checks
- Time-series database
- Performance profiling
"""

from datetime import datetime, timedelta
import time

import pytest

from src.monitoring.alerts import Alert, AlertLevel, AlertManager, AlertRule
from src.monitoring.health import HealthChecker, HealthStatus
from src.monitoring.logger import LogContext, LogLevel, StructuredLogger
from src.monitoring.metrics import Counter, Gauge, Histogram, MetricsCollector, Summary
from src.monitoring.profiler import DistributedTracer, Profiler
from src.monitoring.tsdb import InMemoryTSDB, TimeSeriesQuery


class TestMetricsCollection:
    """Test metrics collection system."""
    
    @pytest.fixture
    def collector(self):
        """Create metrics collector."""
        return MetricsCollector(prefix="test")
    
    def test_counter_registration(self, collector):
        """Test counter registration and increment."""
        counter = collector.register_counter(
            "requests_total",
            "Total number of requests"
        )
        
        assert counter.get() == 0
        
        counter.inc()
        assert counter.get() == 1
        
        counter.inc(5)
        assert counter.get() == 6
    
    def test_gauge_operations(self, collector):
        """Test gauge set/inc/dec."""
        gauge = collector.register_gauge(
            "temperature",
            "Current temperature"
        )
        
        gauge.set(25.5)
        assert gauge.get() == 25.5
        
        gauge.inc(2.5)
        assert gauge.get() == 28.0
        
        gauge.dec(3.0)
        assert gauge.get() == 25.0
    
    def test_histogram_observations(self, collector):
        """Test histogram observations."""
        histogram = collector.register_histogram(
            "request_duration",
            "Request duration in seconds",
            buckets=[0.1, 0.5, 1.0, 5.0]
        )
        
        # Observe some values
        histogram.observe(0.05)
        histogram.observe(0.3)
        histogram.observe(0.8)
        histogram.observe(2.5)
        
        stats = histogram.get_stats()
        
        assert stats["count"] == 4
        assert stats["sum"] == 0.05 + 0.3 + 0.8 + 2.5
        assert stats["avg"] == stats["sum"] / 4
    
    def test_summary_statistics(self, collector):
        """Test summary statistical calculations."""
        summary = collector.register_summary(
            "response_time",
            "Response time in seconds",
            quantiles=[0.5, 0.9, 0.99]
        )
        
        # Add observations
        for i in range(100):
            summary.observe(i / 100.0)
        
        stats = summary.get_stats()
        
        assert stats["count"] == 100
        assert "q50" in stats
        assert "q90" in stats
        assert "q99" in stats
        
        assert 0.4 < stats["q50"] < 0.6  # Median around 0.5
        assert 0.85 < stats["q90"] < 0.95  # 90th percentile
    
    def test_prometheus_export(self, collector):
        """Test Prometheus format export."""
        counter = collector.register_counter("test_counter", "Test counter")
        counter.inc(5)
        
        export = collector.export_prometheus()
        
        assert "test_counter" in export
        assert "# HELP" in export
        assert "# TYPE" in export
        assert " 5" in export or " 5.0" in export
    
    def test_thread_safety(self, collector):
        """Test thread-safe metric updates."""
        import threading
        
        counter = collector.register_counter("concurrent_counter", "Test")
        
        def increment():
            for _ in range(1000):
                counter.inc()
        
        threads = [threading.Thread(target=increment) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should be exactly 10000
        assert counter.get() == 10000


class TestStructuredLogging:
    """Test structured logging system."""
    
    @pytest.fixture
    def logger(self):
        """Create structured logger."""
        return StructuredLogger(
            name="test",
            buffer_logs=True,
            buffer_size=100
        )
    
    def test_log_levels(self, logger):
        """Test different log levels."""
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        
        logs = logger.get_recent_logs(n=10)
        
        assert len(logs) >= 4
    
    def test_context_propagation(self, logger):
        """Test logging context."""
        context = LogContext(
            request_id="req-123",
            user_id="user-456",
            symbol="AAPL"
        )
        
        logger.set_context(context)
        logger.info("Trade executed", quantity=100, price=150.0)
        
        logs = logger.get_recent_logs(n=1)
        
        assert logs[0]["context"]["request_id"] == "req-123"
        assert logs[0]["context"]["symbol"] == "AAPL"
    
    def test_error_logging_with_exception(self, logger):
        """Test logging errors with exceptions."""
        try:
            raise ValueError("Test error")
        except ValueError as e:
            logger.error("An error occurred", exc_info=e)
        
        errors = logger.get_errors(n=1)
        
        assert len(errors) > 0
        assert errors[0]["exception"] is not None
        assert "ValueError" in errors[0]["exception"]["type"]
    
    def test_log_filtering(self, logger):
        """Test log filtering by level."""
        logger.info("Info 1")
        logger.error("Error 1")
        logger.info("Info 2")
        logger.error("Error 2")
        
        errors = logger.get_errors(n=10)
        
        assert len(errors) >= 2
        assert all(log["level"] in ["ERROR", "CRITICAL"] for log in errors)


class TestAlertManagement:
    """Test alert management system."""
    
    @pytest.fixture
    def alert_manager(self):
        """Create alert manager."""
        return AlertManager()
    
    def test_alert_creation(self, alert_manager):
        """Test creating alerts."""
        alert = alert_manager.create_alert(
            level=AlertLevel.WARNING,
            title="High CPU Usage",
            message="CPU usage is at 85%",
            tags={"host": "server-1"}
        )
        
        assert alert.id is not None
        assert alert.level == AlertLevel.WARNING
        assert not alert.resolved
    
    def test_alert_resolution(self, alert_manager):
        """Test resolving alerts."""
        alert = alert_manager.create_alert(
            level=AlertLevel.WARNING,
            title="Test Alert",
            message="Test"
        )
        
        assert alert_manager.resolve_alert(alert.id)
        
        # Should not be in active alerts anymore
        active = alert_manager.get_active_alerts()
        assert all(a.id != alert.id for a in active)
    
    def test_alert_acknowledgment(self, alert_manager):
        """Test acknowledging alerts."""
        alert = alert_manager.create_alert(
            level=AlertLevel.CRITICAL,
            title="System Down",
            message="System is offline"
        )
        
        assert alert_manager.acknowledge_alert(alert.id, "operator-1")
        
        active = alert_manager.get_active_alerts()
        alert_obj = next((a for a in active if a.id == alert.id), None)
        
        assert alert_obj is not None
        assert alert_obj.acknowledged
        assert alert_obj.acknowledged_by == "operator-1"
    
    def test_alert_rules(self, alert_manager):
        """Test alert rules."""
        trigger_count = [0]
        
        def condition():
            trigger_count[0] += 1
            return trigger_count[0] > 2
        
        rule = AlertRule(
            name="test_rule",
            condition=condition,
            level=AlertLevel.WARNING,
            message_template="Rule triggered {count} times",
            throttle_seconds=1
        )
        
        alert_manager.add_rule(rule)
        
        # Check rule multiple times
        alert1 = rule.check()
        assert alert1 is None  # Not triggered yet
        
        alert2 = rule.check()
        assert alert2 is None
        
        alert3 = rule.check()
        assert alert3 is not None  # Should trigger now
    
    def test_alert_statistics(self, alert_manager):
        """Test alert statistics."""
        # Create some alerts
        for i in range(5):
            alert_manager.create_alert(
                level=AlertLevel.INFO if i < 3 else AlertLevel.WARNING,
                title=f"Alert {i}",
                message="Test"
            )
        
        stats = alert_manager.get_alert_stats(hours=24)
        
        assert stats["total"] >= 5
        assert stats["by_level"]["info"] >= 3
        assert stats["by_level"]["warning"] >= 2


class TestHealthChecking:
    """Test health checking system."""
    
    @pytest.fixture
    def health_checker(self):
        """Create health checker."""
        return HealthChecker()
    
    def test_system_health_checks(self, health_checker):
        """Test built-in system health checks."""
        # Run all checks
        results = health_checker.check_all()
        
        # Should have CPU, memory, disk checks
        assert "system_cpu" in results
        assert "system_memory" in results
        assert "system_disk" in results
        
        # All should return results
        for result in results.values():
            assert result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]
    
    def test_custom_health_check(self, health_checker):
        """Test registering custom health check."""
        check_called = [False]
        
        def custom_check():
            check_called[0] = True
            return True
        
        health_checker.register_check(
            "custom_check",
            custom_check,
            timeout_seconds=5.0
        )
        
        result = health_checker.check("custom_check")
        
        assert check_called[0]
        assert result.status == HealthStatus.HEALTHY
    
    def test_failed_health_check(self, health_checker):
        """Test failed health check."""
        def failing_check():
            return False
        
        health_checker.register_check("failing_check", failing_check)
        
        result = health_checker.check("failing_check")
        
        assert result.status == HealthStatus.UNHEALTHY
    
    def test_health_check_timeout(self, health_checker):
        """Test health check timeout."""
        def slow_check():
            time.sleep(10)
            return True
        
        health_checker.register_check(
            "slow_check",
            slow_check,
            timeout_seconds=0.5
        )
        
        result = health_checker.check("slow_check")
        
        # Should timeout and return unhealthy
        assert result.status == HealthStatus.UNHEALTHY
        assert "timeout" in result.message.lower()
    
    def test_overall_health_status(self, health_checker):
        """Test overall system health status."""
        health_checker.register_check("check1", lambda: True)
        health_checker.register_check("check2", lambda: True)
        
        health_checker.check_all()
        
        status = health_checker.get_status()
        
        assert status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]


class TestTimeSeriesDatabase:
    """Test time-series database."""
    
    @pytest.fixture
    def tsdb(self):
        """Create in-memory TSDB."""
        return InMemoryTSDB(retention_hours=24)
    
    def test_write_and_query(self, tsdb):
        """Test writing and querying data."""
        # Write some points
        for i in range(10):
            tsdb.write("cpu_usage", 50.0 + i, {"host": "server-1"})
            time.sleep(0.01)
        
        # Query
        query = TimeSeriesQuery(
            metric="cpu_usage",
            start_time=datetime.now() - timedelta(minutes=1),
            end_time=datetime.now() + timedelta(minutes=1),
            tags={"host": "server-1"}
        )
        
        points = tsdb.query(query)
        
        assert len(points) == 10
        assert all(p.tags["host"] == "server-1" for p in points)
    
    def test_aggregation(self, tsdb):
        """Test time-series aggregation."""
        # Write points
        values = [10, 20, 30, 40, 50]
        for v in values:
            tsdb.write("metric", float(v))
        
        # Query with aggregation
        query = TimeSeriesQuery(
            metric="metric",
            start_time=datetime.now() - timedelta(minutes=1),
            end_time=datetime.now() + timedelta(minutes=1),
            aggregation="avg"
        )
        
        avg = tsdb.aggregate(query)
        
        assert abs(avg - 30.0) < 0.1  # Average of [10,20,30,40,50]
    
    def test_latest_point(self, tsdb):
        """Test getting latest point."""
        tsdb.write("metric", 100.0)
        time.sleep(0.01)
        tsdb.write("metric", 200.0)
        
        latest = tsdb.get_latest("metric")
        
        assert latest is not None
        assert latest.value == 200.0


class TestPerformanceProfiling:
    """Test performance profiling."""
    
    @pytest.fixture
    def profiler(self):
        """Create profiler."""
        return Profiler()
    
    def test_function_profiling(self, profiler):
        """Test profiling a function."""
        @profiler.profile_function
        def slow_function():
            time.sleep(0.1)
            return 42
        
        result = slow_function()
        
        assert result == 42
        
        stats = profiler.get_stats("slow_function")
        
        assert stats is not None
        assert stats["slow_function"]["count"] >= 1
        assert stats["slow_function"]["mean_ms"] >= 100  # At least 100ms
    
    def test_context_profiling(self, profiler):
        """Test profiling with context manager."""
        with profiler.profile_section("test_section"):
            time.sleep(0.05)
        
        stats = profiler.get_stats("test_section")
        
        assert stats["test_section"]["count"] == 1
        assert stats["test_section"]["mean_ms"] >= 50
    
    def test_profiling_statistics(self, profiler):
        """Test profiling statistical measures."""
        # Profile multiple calls
        for i in range(10):
            with profiler.profile_section("variable_time"):
                time.sleep(0.01 * (i + 1))
        
        stats = profiler.get_stats("variable_time")
        
        assert "mean_ms" in stats["variable_time"]
        assert "median_ms" in stats["variable_time"]
        assert "p95_ms" in stats["variable_time"]
        assert "p99_ms" in stats["variable_time"]
        assert "std_ms" in stats["variable_time"]


class TestDistributedTracing:
    """Test distributed tracing."""
    
    @pytest.fixture
    def tracer(self):
        """Create distributed tracer."""
        return DistributedTracer(service_name="test-service")
    
    def test_trace_creation(self, tracer):
        """Test creating traces."""
        with tracer.trace("test_operation") as trace:
            time.sleep(0.01)
        
        assert trace.trace_id is not None
        assert trace.duration_ms is not None
        assert trace.duration_ms >= 10
    
    def test_span_creation(self, tracer):
        """Test creating spans within trace."""
        with tracer.trace("parent_operation") as trace:
            with tracer.span("child_span_1"):
                time.sleep(0.01)
            
            with tracer.span("child_span_2"):
                time.sleep(0.01)
        
        assert len(trace.spans) == 2
        assert trace.spans[0].name == "child_span_1"
        assert trace.spans[1].name == "child_span_2"
    
    def test_nested_spans(self, tracer):
        """Test nested span relationships."""
        with tracer.trace("root"), tracer.span("parent") as parent_span:
            with tracer.span("child") as child_span:
                time.sleep(0.01)
            
            assert child_span.parent_id == parent_span.span_id


@pytest.mark.benchmark
class TestMonitoringPerformance:
    """Performance benchmarks for monitoring system."""
    
    def test_metric_update_speed(self, benchmark):
        """Benchmark metric update speed."""
        collector = MetricsCollector()
        counter = collector.register_counter("test", "test")
        
        benchmark(counter.inc)
    
    def test_logging_speed(self, benchmark):
        """Benchmark logging speed."""
        logger = StructuredLogger(buffer_logs=False)
        
        benchmark(logger.info, "Test message")
    
    def test_health_check_speed(self, benchmark):
        """Benchmark health check speed."""
        checker = HealthChecker()
        checker.register_check("fast_check", lambda: True)
        
        benchmark(checker.check, "fast_check")

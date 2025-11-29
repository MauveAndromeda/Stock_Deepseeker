"""
Health check and system status monitoring.

Provides comprehensive health checking for:
- System resources (CPU, memory, disk)
- Database connections
- External API availability
- Service dependencies
- Application-specific health indicators
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import os
import shutil
import threading
import time
from typing import Any

from loguru import logger

try:  # pragma: no cover - optional dependency
    import psutil
except ImportError:  # pragma: no cover - optional dependency
    psutil = None


class HealthStatus(Enum):
    """Health check status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Health check result."""
    name: str
    status: HealthStatus
    message: str
    timestamp: datetime
    response_time_ms: float
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "response_time_ms": self.response_time_ms,
            "details": self.details
        }


class HealthCheckFunction:
    """
    Health check function wrapper.
    
    Defines a health check with automatic timeout and error handling.
    """

    def __init__(
        self,
        name: str,
        check_func: Callable[[], bool],
        timeout_seconds: float = 5.0,
        details_func: Callable[[], dict[str, Any]] | None = None
    ):
        """Initialize health check function."""
        self.name = name
        self.check_func = check_func
        self.timeout_seconds = timeout_seconds
        self.details_func = details_func

    def execute(self) -> HealthCheck:
        """Execute health check."""
        start_time = time.time()

        try:
            # Run check with timeout
            result = self._run_with_timeout()

            response_time = (time.time() - start_time) * 1000  # ms

            if isinstance(result, HealthStatus):
                status = result
                message = {
                    HealthStatus.HEALTHY: "Check passed",
                    HealthStatus.DEGRADED: "Check degraded",
                    HealthStatus.UNKNOWN: "Check status unknown",
                    HealthStatus.UNHEALTHY: "Check failed",
                }[status]
            else:
                if result:
                    status = HealthStatus.HEALTHY
                    message = "Check passed"
                else:
                    status = HealthStatus.UNHEALTHY
                    message = "Check failed"

            # Get details if available
            details = {}
            if self.details_func:
                try:
                    details = self.details_func()
                except Exception as e:
                    details = {"error": str(e)}

            return HealthCheck(
                name=self.name,
                status=status,
                message=message,
                timestamp=datetime.now(),
                response_time_ms=response_time,
                details=details
            )

        except TimeoutError:
            return HealthCheck(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check timeout after {self.timeout_seconds}s",
                timestamp=datetime.now(),
                response_time_ms=(time.time() - start_time) * 1000,
                details={}
            )
        except Exception as e:
            return HealthCheck(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {e!s}",
                timestamp=datetime.now(),
                response_time_ms=(time.time() - start_time) * 1000,
                details={"error": str(e)}
            )

    def _run_with_timeout(self) -> bool:
        """Run check function with timeout using a worker thread."""
        result_container: dict[str, Any] = {}
        exception_container: dict[str, BaseException] = {}

        def target() -> None:
            try:
                result_container["result"] = self.check_func()
            except BaseException as exc:  # pragma: no cover - defensive
                exception_container["exception"] = exc

        worker = threading.Thread(target=target, daemon=True)
        worker.start()
        worker.join(self.timeout_seconds)

        if worker.is_alive():
            raise TimeoutError(
                f"{self.name} exceeded {self.timeout_seconds} seconds"
            )

        if exception_container:
            raise exception_container["exception"]

        return result_container.get("result", False)


class HealthChecker:
    """
    Central health checking system.
    
    Features:
    - Multiple health check types
    - Periodic health monitoring
    - Health status aggregation
    - Historical health data
    - Integration with alerting
    """

    def __init__(self):
        """Initialize health checker."""
        self._checks: dict[str, HealthCheckFunction] = {}
        self._last_results: dict[str, HealthCheck] = {}
        self._lock = threading.Lock()

        # Monitoring
        self._monitoring = False
        self._monitor_thread: threading.Thread | None = None

        # Register default system checks
        self._register_system_checks()

        logger.info("Initialized HealthChecker")

    def _register_system_checks(self) -> None:
        """Register default system health checks."""
        if psutil is None:
            logger.warning(
                "psutil is not available; registering degraded system health checks"
            )

            def cpu_details() -> dict[str, Any]:
                try:
                    load1, load5, load15 = os.getloadavg()
                except OSError:
                    load1 = load5 = load15 = 0.0
                return {
                    "psutil_available": False,
                    "load_average": {
                        "1m": load1,
                        "5m": load5,
                        "15m": load15,
                    },
                }

            def memory_details() -> dict[str, Any]:
                return {"psutil_available": False}

            def disk_details() -> dict[str, Any]:
                usage = shutil.disk_usage("/")
                percent = usage.used / usage.total * 100 if usage.total else 0.0
                return {
                    "psutil_available": False,
                    "disk_percent": percent,
                    "disk_total_gb": usage.total / (1024**3),
                    "disk_free_gb": usage.free / (1024**3),
                }

            self.register_check(
                "system_cpu",
                lambda: HealthStatus.DEGRADED,
                details_func=cpu_details,
            )

            self.register_check(
                "system_memory",
                lambda: HealthStatus.DEGRADED,
                details_func=memory_details,
            )

            self.register_check(
                "system_disk",
                lambda: HealthStatus.DEGRADED,
                details_func=disk_details,
            )
            return

        # CPU check
        self.register_check(
            "system_cpu",
            lambda: psutil.cpu_percent(interval=0.1) < 90.0,
            details_func=lambda: {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "cpu_count": psutil.cpu_count()
            }
        )

        # Memory check
        self.register_check(
            "system_memory",
            lambda: psutil.virtual_memory().percent < 90.0,
            details_func=lambda: {
                "memory_percent": psutil.virtual_memory().percent,
                "memory_total_gb": psutil.virtual_memory().total / (1024**3),
                "memory_available_gb": psutil.virtual_memory().available / (1024**3)
            }
        )

        # Disk check
        self.register_check(
            "system_disk",
            lambda: psutil.disk_usage("/").percent < 90.0,
            details_func=lambda: {
                "disk_percent": psutil.disk_usage("/").percent,
                "disk_total_gb": psutil.disk_usage("/").total / (1024**3),
                "disk_free_gb": psutil.disk_usage("/").free / (1024**3)
            }
        )

    def register_check(
        self,
        name: str,
        check_func: Callable[[], bool],
        timeout_seconds: float = 5.0,
        details_func: Callable[[], dict[str, Any]] | None = None
    ) -> None:
        """Register a health check."""
        with self._lock:
            self._checks[name] = HealthCheckFunction(
                name, check_func, timeout_seconds, details_func
            )
        logger.info(f"Registered health check: {name}")

    def unregister_check(self, name: str) -> None:
        """Unregister a health check."""
        with self._lock:
            if name in self._checks:
                del self._checks[name]
                if name in self._last_results:
                    del self._last_results[name]
        logger.info(f"Unregistered health check: {name}")

    def check(self, name: str) -> HealthCheck | None:
        """Run a specific health check."""
        with self._lock:
            check_func = self._checks.get(name)

        if not check_func:
            logger.warning(f"Health check not found: {name}")
            return None

        result = check_func.execute()

        with self._lock:
            self._last_results[name] = result

        return result

    def check_all(self) -> dict[str, HealthCheck]:
        """Run all health checks."""
        with self._lock:
            checks = list(self._checks.items())

        results = {}
        for name, check_func in checks:
            result = check_func.execute()
            results[name] = result

            with self._lock:
                self._last_results[name] = result

        return results

    def get_status(self) -> HealthStatus:
        """Get overall system health status."""
        with self._lock:
            if not self._last_results:
                return HealthStatus.UNKNOWN

            statuses = [r.status for r in self._last_results.values()]

        # If any check is unhealthy, system is unhealthy
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY

        # If any check is degraded, system is degraded
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED

        # If all checks are healthy, system is healthy
        if all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY

        return HealthStatus.UNKNOWN

    def get_summary(self) -> dict[str, Any]:
        """Get health summary."""
        with self._lock:
            results = dict(self._last_results)

        if not results:
            return {
                "status": HealthStatus.UNKNOWN.value,
                "checks": {},
                "timestamp": datetime.now().isoformat()
            }

        return {
            "status": self.get_status().value,
            "checks": {name: check.to_dict() for name, check in results.items()},
            "timestamp": datetime.now().isoformat(),
            "total_checks": len(results),
            "healthy": sum(1 for c in results.values() if c.status == HealthStatus.HEALTHY),
            "degraded": sum(1 for c in results.values() if c.status == HealthStatus.DEGRADED),
            "unhealthy": sum(1 for c in results.values() if c.status == HealthStatus.UNHEALTHY)
        }

    def start_monitoring(self, interval_seconds: int = 30) -> None:
        """Start periodic health monitoring."""
        if self._monitoring:
            logger.warning("Health monitoring already started")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"Started health monitoring (interval: {interval_seconds}s)")

    def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Stopped health monitoring")

    def _monitor_loop(self, interval_seconds: int) -> None:
        """Health monitoring loop."""
        while self._monitoring:
            try:
                self.check_all()
                time.sleep(interval_seconds)
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                time.sleep(interval_seconds)


# Database health checks
def check_database_connection(connection_string: str) -> Callable[[], bool]:
    """Create database connection health check."""
    def check() -> bool:
        try:
            import sqlalchemy
            engine = sqlalchemy.create_engine(connection_string)
            with engine.connect() as conn:
                conn.execute(sqlalchemy.text("SELECT 1"))
            return True
        except (ImportError, OSError, ConnectionError):
            return False
    return check


# Redis health check
def check_redis_connection(host: str = "localhost", port: int = 6379) -> Callable[[], bool]:
    """Create Redis connection health check."""
    def check() -> bool:
        try:
            import redis
            r = redis.Redis(host=host, port=port, socket_connect_timeout=2)
            return r.ping()
        except (ImportError, OSError, ConnectionError, TimeoutError):
            return False
    return check


# API health check
def check_api_endpoint(url: str, timeout: float = 5.0) -> Callable[[], bool]:
    """Create API endpoint health check."""
    def check() -> bool:
        try:
            import requests
            response = requests.get(url, timeout=timeout)
            return response.status_code == 200
        except (ImportError, OSError, ConnectionError, TimeoutError):
            return False
    return check


# Global health checker instance
_default_health_checker: HealthChecker | None = None


def get_default_health_checker() -> HealthChecker:
    """Get global default health checker."""
    global _default_health_checker
    if _default_health_checker is None:
        _default_health_checker = HealthChecker()
    return _default_health_checker

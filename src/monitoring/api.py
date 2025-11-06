"""
Monitoring API and dashboard backend.

Provides REST API endpoints for:
- Metrics query and export
- Health status
- Alerts management
- Logs access
- Profiling data
- System status
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel
from loguru import logger

# Import monitoring components
from src.monitoring.metrics import get_default_collector
from src.monitoring.logger import get_default_logger, LogLevel
from src.monitoring.alerts import get_default_alert_manager, AlertLevel
from src.monitoring.health import get_default_health_checker, HealthStatus
from src.monitoring.profiler import get_default_profiler, get_default_tracer


# Pydantic models for API
class MetricResponse(BaseModel):
    """Metric response model."""
    name: str
    value: float
    timestamp: str
    labels: Dict[str, str]


class AlertRequest(BaseModel):
    """Alert creation request."""
    level: str
    title: str
    message: str
    tags: Optional[Dict[str, str]] = None


class AlertResponse(BaseModel):
    """Alert response model."""
    id: str
    level: str
    title: str
    message: str
    timestamp: str
    resolved: bool
    acknowledged: bool


# Create FastAPI app
app = FastAPI(
    title="Trading System Monitoring API",
    description="REST API for monitoring and observability",
    version="3.0.0"
)


# ============= Metrics Endpoints =============

@app.get("/metrics", response_class=PlainTextResponse)
async def get_metrics_prometheus():
    """
    Get all metrics in Prometheus format.
    
    This endpoint is designed to be scraped by Prometheus.
    """
    try:
        collector = get_default_collector()
        return collector.export_prometheus()
    except Exception as e:
        logger.error(f"Failed to export metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/metrics")
async def get_metrics_json() -> Dict[str, Any]:
    """Get all metrics in JSON format."""
    try:
        collector = get_default_collector()
        metrics = collector.get_all_metrics()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "metrics": [
                {
                    "name": m.name,
                    "type": m.type.value,
                    "value": m.value,
                    "labels": m.labels,
                    "description": m.description
                }
                for m in metrics
            ],
            "count": len(metrics)
        }
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/metrics/{metric_name}")
async def get_metric(metric_name: str) -> Dict[str, Any]:
    """Get specific metric by name."""
    try:
        collector = get_default_collector()
        metric = collector.get_metric(metric_name)
        
        if not metric:
            raise HTTPException(status_code=404, detail="Metric not found")
        
        metric_obj = metric.to_metric()
        return {
            "name": metric_obj.name,
            "type": metric_obj.type.value,
            "value": metric_obj.value,
            "labels": metric_obj.labels,
            "timestamp": metric_obj.timestamp.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get metric: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= Health Endpoints =============

@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Quick health check endpoint."""
    try:
        checker = get_default_health_checker()
        status = checker.get_status()
        
        return {
            "status": status.value,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.get("/api/v1/health")
async def health_detailed() -> Dict[str, Any]:
    """Detailed health status."""
    try:
        checker = get_default_health_checker()
        return checker.get_summary()
    except Exception as e:
        logger.error(f"Failed to get health status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/health/{check_name}")
async def health_check_specific(check_name: str) -> Dict[str, Any]:
    """Get specific health check result."""
    try:
        checker = get_default_health_checker()
        result = checker.check(check_name)
        
        if not result:
            raise HTTPException(status_code=404, detail="Health check not found")
        
        return result.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to run health check: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= Alerts Endpoints =============

@app.get("/api/v1/alerts")
async def get_alerts(
    level: Optional[str] = Query(None, description="Filter by alert level"),
    active_only: bool = Query(True, description="Show only active alerts")
) -> Dict[str, Any]:
    """Get alerts."""
    try:
        manager = get_default_alert_manager()
        
        # Parse level
        alert_level = None
        if level:
            try:
                alert_level = AlertLevel(level.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid alert level: {level}")
        
        # Get alerts
        if active_only:
            alerts = manager.get_active_alerts(level=alert_level)
        else:
            alerts = manager.get_alert_history(level=alert_level, limit=100)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "alerts": [a.to_dict() for a in alerts],
            "count": len(alerts)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/alerts")
async def create_alert(request: AlertRequest) -> Dict[str, Any]:
    """Create a new alert."""
    try:
        manager = get_default_alert_manager()
        
        # Parse level
        try:
            level = AlertLevel(request.level.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid alert level: {request.level}")
        
        # Create alert
        alert = manager.create_alert(
            level=level,
            title=request.title,
            message=request.message,
            source="api",
            tags=request.tags or {}
        )
        
        return alert.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str) -> Dict[str, str]:
    """Resolve an alert."""
    try:
        manager = get_default_alert_manager()
        
        if not manager.resolve_alert(alert_id):
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {"status": "resolved", "alert_id": alert_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/alerts/stats")
async def get_alert_stats(
    hours: int = Query(24, description="Time window in hours")
) -> Dict[str, Any]:
    """Get alert statistics."""
    try:
        manager = get_default_alert_manager()
        return manager.get_alert_stats(hours=hours)
    except Exception as e:
        logger.error(f"Failed to get alert stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= Logs Endpoints =============

@app.get("/api/v1/logs")
async def get_logs(
    level: Optional[str] = Query(None, description="Filter by log level"),
    limit: int = Query(100, ge=1, le=1000, description="Number of logs to return")
) -> Dict[str, Any]:
    """Get recent logs."""
    try:
        log_system = get_default_logger()
        
        if level and level.lower() == "error":
            logs = log_system.get_errors(n=limit)
        else:
            logs = log_system.get_recent_logs(n=limit)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "logs": logs,
            "count": len(logs)
        }
    except Exception as e:
        logger.error(f"Failed to get logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= Profiling Endpoints =============

@app.get("/api/v1/profiling/stats")
async def get_profiling_stats(
    function: Optional[str] = Query(None, description="Filter by function name")
) -> Dict[str, Any]:
    """Get profiling statistics."""
    try:
        profiler = get_default_profiler()
        stats = profiler.get_stats(name=function)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Failed to get profiling stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/tracing/traces")
async def get_traces(
    min_duration_ms: Optional[float] = Query(None, description="Minimum duration in ms"),
    limit: int = Query(100, ge=1, le=1000, description="Number of traces to return")
) -> Dict[str, Any]:
    """Get distributed traces."""
    try:
        tracer = get_default_tracer()
        
        traces = tracer.get_traces(
            min_duration_ms=min_duration_ms,
            limit=limit
        )
        
        return {
            "timestamp": datetime.now().isoformat(),
            "traces": [
                {
                    "trace_id": t.trace_id,
                    "name": t.name,
                    "start_time": t.start_time.isoformat(),
                    "duration_ms": t.duration_ms,
                    "span_count": len(t.spans),
                    "metadata": t.metadata
                }
                for t in traces
            ],
            "count": len(traces)
        }
    except Exception as e:
        logger.error(f"Failed to get traces: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= System Status Endpoint =============

@app.get("/api/v1/status")
async def get_system_status() -> Dict[str, Any]:
    """Get overall system status."""
    try:
        # Get health status
        checker = get_default_health_checker()
        health = checker.get_summary()
        
        # Get alert stats
        alert_manager = get_default_alert_manager()
        alerts = alert_manager.get_alert_stats(hours=1)
        
        # Get metrics count
        collector = get_default_collector()
        metrics = collector.get_all_metrics()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "health": {
                "status": health["status"],
                "checks": {
                    "total": health["total_checks"],
                    "healthy": health["healthy"],
                    "unhealthy": health["unhealthy"]
                }
            },
            "alerts": {
                "active": alerts["active"],
                "total_last_hour": alerts["total"]
            },
            "metrics": {
                "count": len(metrics)
            },
            "uptime_seconds": get_uptime_seconds()
        }
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Helper functions
_start_time = datetime.now()


def get_uptime_seconds() -> float:
    """Get system uptime in seconds."""
    return (datetime.now() - _start_time).total_seconds()


# Application startup/shutdown events
@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("Monitoring API started")
    
    # Start health monitoring
    checker = get_default_health_checker()
    checker.start_monitoring(interval_seconds=30)
    
    # Start alert monitoring
    alert_manager = get_default_alert_manager()
    alert_manager.start_monitoring(check_interval=60)


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Monitoring API shutting down")
    
    # Stop monitoring
    checker = get_default_health_checker()
    checker.stop_monitoring()
    
    alert_manager = get_default_alert_manager()
    alert_manager.stop_monitoring()

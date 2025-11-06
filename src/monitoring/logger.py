"""
Structured logging infrastructure.

Provides comprehensive logging with:
- Structured JSON logging
- Log levels and filtering
- Context management
- Log aggregation
- Integration with ELK stack / Loki
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
import json
import threading
from collections import deque
from loguru import logger as loguru_logger
import sys


class LogLevel(Enum):
    """Log levels."""
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogContext:
    """Log context for structured logging."""
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    strategy_id: Optional[str] = None
    symbol: Optional[str] = None
    trade_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        # Remove None values
        return {k: v for k, v in result.items() if v is not None}


@dataclass
class LogEntry:
    """Structured log entry."""
    timestamp: datetime
    level: LogLevel
    message: str
    context: LogContext
    location: Dict[str, str]  # file, function, line
    exception: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "message": self.message,
            "context": self.context.to_dict(),
            "location": self.location,
            "exception": self.exception
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class LogBuffer:
    """
    In-memory log buffer for recent logs.
    
    Useful for:
    - Quick access to recent logs
    - Log aggregation
    - Error context
    """
    
    def __init__(self, max_size: int = 10000):
        """Initialize log buffer."""
        self.max_size = max_size
        self._buffer: deque = deque(maxlen=max_size)
        self._lock = threading.Lock()
    
    def append(self, entry: LogEntry) -> None:
        """Append log entry."""
        with self._lock:
            self._buffer.append(entry)
    
    def get_recent(self, n: int = 100) -> List[LogEntry]:
        """Get N most recent log entries."""
        with self._lock:
            return list(self._buffer)[-n:]
    
    def filter(
        self,
        level: Optional[LogLevel] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        context_filter: Optional[Dict[str, Any]] = None
    ) -> List[LogEntry]:
        """Filter log entries."""
        with self._lock:
            filtered = list(self._buffer)
        
        # Filter by level
        if level:
            filtered = [e for e in filtered if e.level == level]
        
        # Filter by time range
        if start_time:
            filtered = [e for e in filtered if e.timestamp >= start_time]
        if end_time:
            filtered = [e for e in filtered if e.timestamp <= end_time]
        
        # Filter by context
        if context_filter:
            filtered = [
                e for e in filtered
                if all(
                    getattr(e.context, k, None) == v
                    for k, v in context_filter.items()
                )
            ]
        
        return filtered
    
    def clear(self) -> None:
        """Clear buffer."""
        with self._lock:
            self._buffer.clear()


class StructuredLogger:
    """
    Structured logger with context support.
    
    Features:
    - Structured JSON logging
    - Context propagation
    - Log buffering
    - Multiple output targets
    - Performance tracking
    """
    
    def __init__(
        self,
        name: str = "trading",
        level: LogLevel = LogLevel.INFO,
        json_output: bool = True,
        buffer_logs: bool = True,
        buffer_size: int = 10000
    ):
        """Initialize structured logger."""
        self.name = name
        self.level = level
        self.json_output = json_output
        
        # Log buffer
        self.buffer: Optional[LogBuffer] = None
        if buffer_logs:
            self.buffer = LogBuffer(max_size=buffer_size)
        
        # Thread-local context
        self._local = threading.local()
        
        # Configure loguru
        self._configure_loguru()
    
    def _configure_loguru(self) -> None:
        """Configure loguru logger."""
        # Remove default handler
        loguru_logger.remove()
        
        # Add custom handler
        if self.json_output:
            # JSON format
            loguru_logger.add(
                sys.stderr,
                format="{message}",
                level=self.level.value,
                serialize=True
            )
        else:
            # Human-readable format
            loguru_logger.add(
                sys.stderr,
                format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                       "<level>{level: <8}</level> | "
                       "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                       "<level>{message}</level>",
                level=self.level.value
            )
    
    def set_context(self, context: LogContext) -> None:
        """Set context for current thread."""
        self._local.context = context
    
    def get_context(self) -> LogContext:
        """Get context for current thread."""
        if not hasattr(self._local, 'context'):
            self._local.context = LogContext()
        return self._local.context
    
    def clear_context(self) -> None:
        """Clear context for current thread."""
        if hasattr(self._local, 'context'):
            delattr(self._local, 'context')
    
    def _log(
        self,
        level: LogLevel,
        message: str,
        exc_info: Optional[Exception] = None,
        **kwargs: Any
    ) -> None:
        """Internal log method."""
        import inspect
        
        # Get caller info
        frame = inspect.currentframe()
        if frame and frame.f_back and frame.f_back.f_back:
            caller_frame = frame.f_back.f_back
            location = {
                "file": caller_frame.f_code.co_filename,
                "function": caller_frame.f_code.co_name,
                "line": str(caller_frame.f_lineno)
            }
        else:
            location = {"file": "unknown", "function": "unknown", "line": "0"}
        
        # Get context
        context = self.get_context()
        
        # Merge extra kwargs into context
        if kwargs:
            context.extra.update(kwargs)
        
        # Create log entry
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            message=message,
            context=context,
            location=location,
            exception=self._format_exception(exc_info) if exc_info else None
        )
        
        # Add to buffer
        if self.buffer:
            self.buffer.append(entry)
        
        # Log via loguru
        if self.json_output:
            loguru_logger.opt(depth=2).log(level.value, entry.to_json())
        else:
            loguru_logger.opt(depth=2).log(level.value, message)
    
    def _format_exception(self, exc: Exception) -> Dict[str, Any]:
        """Format exception for logging."""
        import traceback
        
        return {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc()
        }
    
    def trace(self, message: str, **kwargs: Any) -> None:
        """Log trace message."""
        self._log(LogLevel.TRACE, message, **kwargs)
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self._log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, exc_info: Optional[Exception] = None, **kwargs: Any) -> None:
        """Log error message."""
        self._log(LogLevel.ERROR, message, exc_info=exc_info, **kwargs)
    
    def critical(self, message: str, exc_info: Optional[Exception] = None, **kwargs: Any) -> None:
        """Log critical message."""
        self._log(LogLevel.CRITICAL, message, exc_info=exc_info, **kwargs)
    
    def get_recent_logs(self, n: int = 100) -> List[Dict[str, Any]]:
        """Get recent logs as dictionaries."""
        if not self.buffer:
            return []
        
        entries = self.buffer.get_recent(n)
        return [e.to_dict() for e in entries]
    
    def get_errors(self, n: int = 50) -> List[Dict[str, Any]]:
        """Get recent error logs."""
        if not self.buffer:
            return []
        
        errors = self.buffer.filter(level=LogLevel.ERROR)
        errors += self.buffer.filter(level=LogLevel.CRITICAL)
        
        return [e.to_dict() for e in errors[-n:]]


# Global logger instance
_default_logger: Optional[StructuredLogger] = None


def get_default_logger() -> StructuredLogger:
    """Get global default logger."""
    global _default_logger
    if _default_logger is None:
        _default_logger = StructuredLogger()
    return _default_logger


# Convenience functions
def set_context(context: LogContext) -> None:
    """Set logging context."""
    get_default_logger().set_context(context)


def info(message: str, **kwargs: Any) -> None:
    """Log info message."""
    get_default_logger().info(message, **kwargs)


def error(message: str, exc_info: Optional[Exception] = None, **kwargs: Any) -> None:
    """Log error message."""
    get_default_logger().error(message, exc_info=exc_info, **kwargs)


def warning(message: str, **kwargs: Any) -> None:
    """Log warning message."""
    get_default_logger().warning(message, **kwargs)

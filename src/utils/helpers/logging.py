"""
Logging utilities
Provides advanced logging setup with rotation, JSON formatting, and multiple outputs
"""

import sys
from pathlib import Path
from typing import Optional
from loguru import logger
import json
from datetime import datetime


class JSONFormatter:
    """Custom JSON formatter for structured logging"""

    def __call__(self, record):
        """Format log record as JSON"""
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record["level"].name,
            "message": record["message"],
            "module": record["module"],
            "function": record["function"],
            "line": record["line"],
        }

        # Add extra fields
        if record["extra"]:
            log_obj["extra"] = record["extra"]

        # Add exception info if present
        if record["exception"]:
            log_obj["exception"] = {
                "type": record["exception"].type.__name__,
                "value": str(record["exception"].value),
                "traceback": record["exception"].traceback,
            }

        return json.dumps(log_obj)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
    rotation: str = "1 day",
    retention: str = "30 days",
    json_format: bool = False,
) -> logger:
    """
    Setup advanced logging configuration

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (default: logs/trading.log)
        rotation: When to rotate logs (e.g., "1 day", "500 MB")
        retention: How long to keep logs (e.g., "30 days")
        json_format: Whether to use JSON formatting

    Returns:
        Configured logger instance
    """
    # Remove default handler
    logger.remove()

    # Console handler with color
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>",
        colorize=True,
    )

    # File handler
    if log_file is None:
        log_file = Path("logs/trading.log")

    log_file.parent.mkdir(parents=True, exist_ok=True)

    if json_format:
        logger.add(
            log_file,
            level=log_level,
            rotation=rotation,
            retention=retention,
            format=JSONFormatter(),
            serialize=True,
        )
    else:
        logger.add(
            log_file,
            level=log_level,
            rotation=rotation,
            retention=retention,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} | {message}",
        )

    # Error log file (separate file for errors)
    error_log = log_file.parent / "errors.log"
    logger.add(
        error_log,
        level="ERROR",
        rotation=rotation,
        retention=retention,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
        "{name}:{function}:{line} | {message}\n{exception}",
    )

    logger.info(f"Logging initialized: level={log_level}, file={log_file}")
    return logger


def get_logger(name: str) -> logger:
    """
    Get a logger instance for a specific module

    Args:
        name: Name of the module

    Returns:
        Logger instance
    """
    return logger.bind(module=name)


class LogContext:
    """Context manager for adding extra fields to logs"""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.token = None

    def __enter__(self):
        self.token = logger.contextualize(**self.kwargs)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token:
            self.token.__exit__(exc_type, exc_val, exc_tb)


def log_execution_time(func):
    """Decorator to log function execution time"""
    import time
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        logger.debug(f"{func.__name__} executed in {elapsed:.4f}s")
        return result

    return wrapper


def log_exceptions(func):
    """Decorator to log exceptions"""
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Exception in {func.__name__}: {str(e)}")
            raise

    return wrapper

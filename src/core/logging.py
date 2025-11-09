"""
日志系统
支持结构化日志、多目标输出、日志聚合
"""

from collections import deque
from datetime import datetime
from enum import Enum
import json
from pathlib import Path
import sys
import threading
from typing import Any

from loguru import logger as loguru_logger


class LogLevel(Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(Enum):
    """日志格式"""
    JSON = "json"
    TEXT = "text"
    COLORED = "colored"


class Logger:
    """增强的日志记录器"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._logger = loguru_logger
            self._handlers: list[dict[str, Any]] = []
            self._context: dict[str, Any] = {}
            self._buffer = deque(maxlen=10000)  # 内存缓冲区
            self._buffer_enabled = False
            self._initialized = True

    def configure(
        self,
        level: str = "INFO",
        log_file: str | None = None,
        rotation: str = "1 day",
        retention: str = "30 days",
        format_type: str = "colored",
        json_logs: bool = False,
        enable_buffer: bool = False,
        **kwargs
    ):
        """
        配置日志系统

        Args:
            level: 日志级别
            log_file: 日志文件路径
            rotation: 日志轮转策略
            retention: 日志保留时间
            format_type: 日志格式类型
            json_logs: 是否输出JSON格式
            enable_buffer: 是否启用内存缓冲
            **kwargs: 其他配置项
        """
        # 移除默认处理器
        self._logger.remove()

        # 控制台输出格式
        if format_type == "colored":
            console_format = (
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            )
        elif format_type == "json":
            console_format = self._json_formatter
        else:
            console_format = (
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
                "{level: <8} | "
                "{name}:{function}:{line} | "
                "{message}"
            )

        # 添加控制台处理器
        handler_id = self._logger.add(
            sys.stderr,
            format=console_format,
            level=level,
            colorize=(format_type == "colored"),
            backtrace=True,
            diagnose=True,
            enqueue=True,
        )
        self._handlers.append({"id": handler_id, "type": "console"})

        # 添加文件处理器
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            if json_logs:
                file_format = self._json_formatter
            else:
                file_format = (
                    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
                    "{level: <8} | "
                    "{name}:{function}:{line} | "
                    "{message}"
                )

            handler_id = self._logger.add(
                log_file,
                format=file_format,
                level=level,
                rotation=rotation,
                retention=retention,
                compression="gz",
                backtrace=True,
                diagnose=True,
                enqueue=True,
            )
            self._handlers.append({"id": handler_id, "type": "file", "path": log_file})

        # 启用缓冲
        self._buffer_enabled = enable_buffer

    def _json_formatter(self, record: dict[str, Any]) -> str:
        """JSON格式化器"""
        log_entry = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "logger": record["name"],
            "function": record["function"],
            "line": record["line"],
            "message": record["message"],
            "extra": record.get("extra", {}),
        }

        if record.get("exception"):
            log_entry["exception"] = {
                "type": record["exception"].type.__name__,
                "value": str(record["exception"].value),
                "traceback": record["exception"].traceback,
            }

        # 添加上下文
        if self._context:
            log_entry["context"] = self._context

        return json.dumps(log_entry, ensure_ascii=False)

    def set_context(self, **kwargs):
        """设置日志上下文"""
        self._context.update(kwargs)

    def clear_context(self):
        """清除日志上下文"""
        self._context.clear()

    def debug(self, message: str, **kwargs):
        """Debug级别日志"""
        extra = {**self._context, **kwargs}
        self._logger.bind(**extra).debug(message)
        self._add_to_buffer("DEBUG", message, extra)

    def info(self, message: str, **kwargs):
        """Info级别日志"""
        extra = {**self._context, **kwargs}
        self._logger.bind(**extra).info(message)
        self._add_to_buffer("INFO", message, extra)

    def warning(self, message: str, **kwargs):
        """Warning级别日志"""
        extra = {**self._context, **kwargs}
        self._logger.bind(**extra).warning(message)
        self._add_to_buffer("WARNING", message, extra)

    def error(self, message: str, exc_info: bool = False, **kwargs):
        """Error级别日志"""
        extra = {**self._context, **kwargs}
        if exc_info:
            self._logger.bind(**extra).exception(message)
        else:
            self._logger.bind(**extra).error(message)
        self._add_to_buffer("ERROR", message, extra)

    def critical(self, message: str, exc_info: bool = False, **kwargs):
        """Critical级别日志"""
        extra = {**self._context, **kwargs}
        if exc_info:
            self._logger.bind(**extra).exception(message)
        else:
            self._logger.bind(**extra).critical(message)
        self._add_to_buffer("CRITICAL", message, extra)

    def _add_to_buffer(self, level: str, message: str, extra: dict[str, Any]):
        """添加到内存缓冲区"""
        if self._buffer_enabled:
            self._buffer.append({
                "timestamp": datetime.now().isoformat(),
                "level": level,
                "message": message,
                "extra": extra
            })

    def get_buffer(self, level: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """
        获取缓冲区内容

        Args:
            level: 过滤日志级别
            limit: 返回数量限制

        Returns:
            日志列表
        """
        logs = list(self._buffer)

        if level:
            logs = [log for log in logs if log["level"] == level]

        return logs[-limit:]

    def clear_buffer(self):
        """清空缓冲区"""
        self._buffer.clear()

    def add_handler(self, sink, **kwargs):
        """添加自定义处理器"""
        handler_id = self._logger.add(sink, **kwargs)
        self._handlers.append({"id": handler_id, "sink": sink})
        return handler_id

    def remove_handler(self, handler_id: int):
        """移除处理器"""
        self._logger.remove(handler_id)
        self._handlers = [h for h in self._handlers if h["id"] != handler_id]

    def get_handlers(self) -> list[dict[str, Any]]:
        """获取所有处理器"""
        return self._handlers.copy()


# 全局日志实例
_global_logger = Logger()


def get_logger() -> Logger:
    """获取全局日志实例"""
    return _global_logger


def configure_logging(
    level: str = "INFO",
    log_file: str | None = None,
    **kwargs
):
    """配置全局日志"""
    _global_logger.configure(level=level, log_file=log_file, **kwargs)


# 便捷函数
def debug(message: str, **kwargs):
    """Debug日志"""
    _global_logger.debug(message, **kwargs)


def info(message: str, **kwargs):
    """Info日志"""
    _global_logger.info(message, **kwargs)


def warning(message: str, **kwargs):
    """Warning日志"""
    _global_logger.warning(message, **kwargs)


def error(message: str, exc_info: bool = False, **kwargs):
    """Error日志"""
    _global_logger.error(message, exc_info=exc_info, **kwargs)


def critical(message: str, exc_info: bool = False, **kwargs):
    """Critical日志"""
    _global_logger.critical(message, exc_info=exc_info, **kwargs)


def set_context(**kwargs):
    """设置日志上下文"""
    _global_logger.set_context(**kwargs)


def clear_context():
    """清除日志上下文"""
    _global_logger.clear_context()


class PerformanceLogger:
    """性能日志记录器"""

    def __init__(self, operation: str, logger: Logger | None = None):
        self.operation = operation
        self.logger = logger or get_logger()
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.debug(f"Starting: {self.operation}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()

        if exc_type is None:
            self.logger.info(
                f"Completed: {self.operation}",
                duration_seconds=duration
            )
        else:
            self.logger.error(
                f"Failed: {self.operation}",
                duration_seconds=duration,
                error=str(exc_val),
                exc_info=True
            )

        return False  # 不抑制异常


class TradeLogger:
    """交易专用日志记录器"""

    def __init__(self, logger: Logger | None = None):
        self.logger = logger or get_logger()

    def log_order(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        **kwargs
    ):
        """记录订单"""
        self.logger.info(
            "Order created",
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            **kwargs
        )

    def log_fill(
        self,
        order_id: str,
        symbol: str,
        filled_qty: float,
        filled_price: float,
        **kwargs
    ):
        """记录成交"""
        self.logger.info(
            "Order filled",
            order_id=order_id,
            symbol=symbol,
            filled_qty=filled_qty,
            filled_price=filled_price,
            **kwargs
        )

    def log_position(
        self,
        symbol: str,
        quantity: float,
        avg_price: float,
        current_price: float,
        pnl: float,
        **kwargs
    ):
        """记录持仓"""
        self.logger.info(
            "Position update",
            symbol=symbol,
            quantity=quantity,
            avg_price=avg_price,
            current_price=current_price,
            pnl=pnl,
            **kwargs
        )

    def log_risk_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        **kwargs
    ):
        """记录风险事件"""
        if severity.upper() == "CRITICAL":
            self.logger.critical(
                f"Risk Event: {event_type}",
                message=message,
                **kwargs
            )
        elif severity.upper() == "HIGH":
            self.logger.error(
                f"Risk Event: {event_type}",
                message=message,
                **kwargs
            )
        else:
            self.logger.warning(
                f"Risk Event: {event_type}",
                message=message,
                **kwargs
            )

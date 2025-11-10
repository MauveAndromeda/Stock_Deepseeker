"""
指标收集系统
支持实时指标收集、聚合、导出
"""

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading
import time
from typing import Any

import numpy as np
import pandas as pd


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"  # 计数器
    GAUGE = "gauge"  # 仪表
    HISTOGRAM = "histogram"  # 直方图
    SUMMARY = "summary"  # 摘要


@dataclass
class Metric:
    """指标数据"""
    name: str
    metric_type: MetricType
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    labels: dict[str, str] = field(default_factory=dict)
    help_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "type": self.metric_type.value,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels,
            "help": self.help_text,
        }


class Counter:
    """计数器 - 只能增加"""

    def __init__(self, name: str, help_text: str = ""):
        self.name = name
        self.help_text = help_text
        self._value = 0.0
        self._lock = threading.Lock()

    def inc(self, amount: float = 1.0):
        """增加计数"""
        with self._lock:
            self._value += amount

    def get(self) -> float:
        """获取当前值"""
        with self._lock:
            return self._value

    def reset(self):
        """重置计数器"""
        with self._lock:
            self._value = 0.0

    def to_metric(self, labels: dict[str, str] | None = None) -> Metric:
        """转换为指标"""
        return Metric(
            name=self.name,
            metric_type=MetricType.COUNTER,
            value=self.get(),
            labels=labels or {},
            help_text=self.help_text
        )


class Gauge:
    """仪表 - 可以增加或减少"""

    def __init__(self, name: str, help_text: str = ""):
        self.name = name
        self.help_text = help_text
        self._value = 0.0
        self._lock = threading.Lock()

    def set(self, value: float):
        """设置值"""
        with self._lock:
            self._value = value

    def inc(self, amount: float = 1.0):
        """增加"""
        with self._lock:
            self._value += amount

    def dec(self, amount: float = 1.0):
        """减少"""
        with self._lock:
            self._value -= amount

    def get(self) -> float:
        """获取当前值"""
        with self._lock:
            return self._value

    def to_metric(self, labels: dict[str, str] | None = None) -> Metric:
        """转换为指标"""
        return Metric(
            name=self.name,
            metric_type=MetricType.GAUGE,
            value=self.get(),
            labels=labels or {},
            help_text=self.help_text
        )


class Histogram:
    """直方图 - 用于分布统计"""

    def __init__(
        self,
        name: str,
        help_text: str = "",
        buckets: list[float] | None = None
    ):
        self.name = name
        self.help_text = help_text
        self.buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0]
        self._observations = deque(maxlen=10000)
        self._sum = 0.0
        self._count = 0
        self._lock = threading.Lock()

    def observe(self, value: float):
        """记录观察值"""
        with self._lock:
            self._observations.append(value)
            self._sum += value
            self._count += 1

    def get_stats(self) -> dict[str, float]:
        """获取统计信息"""
        with self._lock:
            if not self._observations:
                return {
                    "count": 0,
                    "sum": 0.0,
                    "mean": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "median": 0.0,
                    "p95": 0.0,
                    "p99": 0.0,
                }

            observations = sorted(self._observations)
            count = len(observations)

            return {
                "count": self._count,
                "sum": self._sum,
                "mean": self._sum / self._count if self._count > 0 else 0.0,
                "min": observations[0],
                "max": observations[-1],
                "median": observations[count // 2],
                "p95": observations[int(count * 0.95)] if count > 0 else 0.0,
                "p99": observations[int(count * 0.99)] if count > 0 else 0.0,
            }

    def get_buckets(self) -> dict[float, int]:
        """获取桶计数"""
        with self._lock:
            bucket_counts = dict.fromkeys(self.buckets, 0)
            bucket_counts[float("inf")] = 0

            for obs in self._observations:
                for bucket in self.buckets:
                    if obs <= bucket:
                        bucket_counts[bucket] += 1
                        break
                else:
                    bucket_counts[float("inf")] += 1

            return bucket_counts


class Timer:
    """计时器 - 用于测量执行时间"""

    def __init__(self, histogram: Histogram):
        self.histogram = histogram
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        self.histogram.observe(duration)
        return False


class MetricsCollector:
    """指标收集器"""

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
            self._counters: dict[str, Counter] = {}
            self._gauges: dict[str, Gauge] = {}
            self._histograms: dict[str, Histogram] = {}
            self._lock = threading.Lock()

            # 内置系统指标
            self._init_system_metrics()

            self._initialized = True

    def _init_system_metrics(self):
        """初始化系统指标"""
        # 订单指标
        self.register_counter("orders_created_total", "Total number of orders created")
        self.register_counter("orders_filled_total", "Total number of orders filled")
        self.register_counter("orders_cancelled_total", "Total number of orders cancelled")
        self.register_counter("orders_rejected_total", "Total number of orders rejected")

        # 交易指标
        self.register_counter("trades_total", "Total number of trades")
        self.register_gauge("trades_value_usd", "Total value of trades in USD")
        self.register_gauge("positions_count", "Number of open positions")
        self.register_gauge("portfolio_value_usd", "Current portfolio value in USD")

        # 风险指标
        self.register_gauge("var_95", "Value at Risk (95%)")
        self.register_gauge("max_drawdown", "Maximum drawdown")
        self.register_gauge("sharpe_ratio", "Sharpe ratio")
        self.register_gauge("exposure_pct", "Portfolio exposure percentage")

        # 性能指标
        self.register_histogram("order_latency_seconds", "Order execution latency")
        self.register_histogram("data_fetch_latency_seconds", "Data fetch latency")
        self.register_histogram("model_inference_latency_seconds", "Model inference latency")

        # 错误指标
        self.register_counter("errors_total", "Total number of errors")
        self.register_counter("api_errors_total", "Total number of API errors")
        self.register_counter("data_errors_total", "Total number of data errors")

    def register_counter(self, name: str, help_text: str = "") -> Counter:
        """注册计数器"""
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name, help_text)
            return self._counters[name]

    def register_gauge(self, name: str, help_text: str = "") -> Gauge:
        """注册仪表"""
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(name, help_text)
            return self._gauges[name]

    def register_histogram(
        self,
        name: str,
        help_text: str = "",
        buckets: list[float] | None = None
    ) -> Histogram:
        """注册直方图"""
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = Histogram(name, help_text, buckets)
            return self._histograms[name]

    def get_counter(self, name: str) -> Counter | None:
        """获取计数器"""
        return self._counters.get(name)

    def get_gauge(self, name: str) -> Gauge | None:
        """获取仪表"""
        return self._gauges.get(name)

    def get_histogram(self, name: str) -> Histogram | None:
        """获取直方图"""
        return self._histograms.get(name)

    def get_all_metrics(self, labels: dict[str, str] | None = None) -> list[Metric]:
        """获取所有指标"""
        metrics = []

        # 收集计数器
        for counter in self._counters.values():
            metrics.append(counter.to_metric(labels))

        # 收集仪表
        for gauge in self._gauges.values():
            metrics.append(gauge.to_metric(labels))

        # 收集直方图（转换为多个指标）
        for histogram in self._histograms.values():
            stats = histogram.get_stats()
            for stat_name, stat_value in stats.items():
                metric = Metric(
                    name=f"{histogram.name}_{stat_name}",
                    metric_type=MetricType.HISTOGRAM,
                    value=stat_value,
                    labels=labels or {},
                    help_text=histogram.help_text
                )
                metrics.append(metric)

        return metrics

    def export_prometheus(self) -> str:
        """导出为Prometheus格式"""
        lines = []

        # 导出计数器
        for counter in self._counters.values():
            if counter.help_text:
                lines.append(f"# HELP {counter.name} {counter.help_text}")
            lines.append(f"# TYPE {counter.name} counter")
            lines.append(f"{counter.name} {counter.get()}")

        # 导出仪表
        for gauge in self._gauges.values():
            if gauge.help_text:
                lines.append(f"# HELP {gauge.name} {gauge.help_text}")
            lines.append(f"# TYPE {gauge.name} gauge")
            lines.append(f"{gauge.name} {gauge.get()}")

        # 导出直方图
        for histogram in self._histograms.values():
            if histogram.help_text:
                lines.append(f"# HELP {histogram.name} {histogram.help_text}")
            lines.append(f"# TYPE {histogram.name} histogram")

            stats = histogram.get_stats()
            lines.append(f"{histogram.name}_count {stats['count']}")
            lines.append(f"{histogram.name}_sum {stats['sum']}")

            buckets = histogram.get_buckets()
            cumulative = 0
            for bucket, count in sorted(buckets.items()):
                cumulative += count
                le = "+Inf" if bucket == float("inf") else str(bucket)
                lines.append(f'{histogram.name}_bucket{{le="{le}"}} {cumulative}')

        return "\n".join(lines)

    def export_json(self) -> dict[str, Any]:
        """导出为JSON格式"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "counters": {},
            "gauges": {},
            "histograms": {}
        }

        for name, counter in self._counters.items():
            result["counters"][name] = {
                "value": counter.get(),
                "help": counter.help_text
            }

        for name, gauge in self._gauges.items():
            result["gauges"][name] = {
                "value": gauge.get(),
                "help": gauge.help_text
            }

        for name, histogram in self._histograms.items():
            result["histograms"][name] = {
                "stats": histogram.get_stats(),
                "help": histogram.help_text
            }

        return result

    def reset_all(self):
        """重置所有指标"""
        with self._lock:
            for counter in self._counters.values():
                counter.reset()

            for gauge in self._gauges.values():
                gauge.set(0.0)

            # 重新创建直方图
            for name, histogram in list(self._histograms.items()):
                self._histograms[name] = Histogram(
                    name,
                    histogram.help_text,
                    histogram.buckets
                )


# 全局指标收集器
_global_metrics = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器"""
    return _global_metrics


# 便捷函数

def counter(name: str, help_text: str = "") -> Counter:
    """获取或创建计数器"""
    return _global_metrics.register_counter(name, help_text)


def gauge(name: str, help_text: str = "") -> Gauge:
    """获取或创建仪表"""
    return _global_metrics.register_gauge(name, help_text)


def histogram(name: str, help_text: str = "", buckets: list[float] | None = None) -> Histogram:
    """获取或创建直方图"""
    return _global_metrics.register_histogram(name, help_text, buckets)


def timer(name: str) -> Timer:
    """创建计时器"""
    hist = _global_metrics.get_histogram(name)
    if hist is None:
        hist = _global_metrics.register_histogram(name)
    return Timer(hist)


# 装饰器

def measure_time(metric_name: str):
    """测量函数执行时间的装饰器"""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            hist = histogram(metric_name, f"Execution time of {func.__name__}")
            with Timer(hist):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def count_calls(metric_name: str):
    """计数函数调用次数的装饰器"""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            cnt = counter(metric_name, f"Call count of {func.__name__}")
            cnt.inc()
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Alias for backward compatibility
MetricsCalculator = MetricsCollector


class MetricsCalculator:
    """Utility class for common trading performance metrics."""

    def _ensure_series(self, data: pd.Series | np.ndarray | list | None) -> pd.Series:
        if data is None:
            return pd.Series(dtype=float)
        if isinstance(data, pd.Series):
            return data.astype(float)
        return pd.Series(data, dtype=float)

    def calculate_total_return(self, equity_curve: pd.Series | np.ndarray | list) -> float:
        equity = self._ensure_series(equity_curve)
        if equity.empty or len(equity) < 2:
            return 0.0
        start = equity.iloc[0]
        end = equity.iloc[-1]
        if start == 0:
            return 0.0
        return (end - start) / start

    def calculate_annualized_return(
        self,
        equity_curve: pd.Series | np.ndarray | list,
        periods: int = 252,
    ) -> float:
        equity = self._ensure_series(equity_curve)
        if equity.empty or len(equity) < 2:
            return 0.0
        start, end = equity.iloc[0], equity.iloc[-1]
        if start <= 0:
            return 0.0
        total_return = end / start
        years = len(equity) / periods
        if years <= 0:
            return 0.0
        return total_return ** (1 / years) - 1

    def calculate_volatility(
        self,
        returns: pd.Series | np.ndarray | list,
        periods: int = 252,
    ) -> float:
        series = self._ensure_series(returns)
        if series.empty:
            return 0.0
        std = series.std(ddof=1)
        if np.isnan(std) or std == 0:
            return 0.0
        return float(std * np.sqrt(periods))

    def calculate_sharpe_ratio(
        self,
        returns: pd.Series | np.ndarray | list,
        risk_free_rate: float = 0.0,
        periods: int = 252,
    ) -> float:
        series = self._ensure_series(returns)
        if series.empty:
            return 0.0
        excess = series - risk_free_rate / periods
        std = excess.std(ddof=1)
        if np.isnan(std) or std == 0:
            return 0.0
        return float(excess.mean() / std * np.sqrt(periods))

    def calculate_sortino_ratio(
        self,
        returns: pd.Series | np.ndarray | list,
        risk_free_rate: float = 0.0,
        periods: int = 252,
    ) -> float:
        series = self._ensure_series(returns)
        if series.empty:
            return 0.0
        excess = series - risk_free_rate / periods
        downside = excess[excess < 0]
        if downside.empty:
            return float(self.calculate_sharpe_ratio(series, risk_free_rate, periods))
        downside_std = downside.std(ddof=1)
        if np.isnan(downside_std) or downside_std == 0:
            return 0.0
        return float(excess.mean() / downside_std * np.sqrt(periods))

    def calculate_max_drawdown(self, equity_curve: pd.Series | np.ndarray | list) -> float:
        equity = self._ensure_series(equity_curve)
        if equity.empty:
            return 0.0
        running_max = equity.cummax()
        drawdown = (equity - running_max) / running_max.replace(0, np.nan)
        drawdown = drawdown.fillna(0.0)
        return float(drawdown.min())

    def calculate_max_drawdown_duration(self, equity_curve: pd.Series | np.ndarray | list) -> int:
        equity = self._ensure_series(equity_curve)
        if equity.empty:
            return 0
        running_max = equity.cummax()
        drawdown = running_max - equity
        duration = 0
        max_duration = 0
        for value in drawdown:
            if value > 0:
                duration += 1
                max_duration = max(max_duration, duration)
            else:
                duration = 0
        return int(max_duration)

    def calculate_calmar_ratio(
        self,
        equity_curve: pd.Series | np.ndarray | list,
        returns: pd.Series | np.ndarray | list,
    ) -> float:
        annual_return = self.calculate_annualized_return(equity_curve)
        max_dd = self.calculate_max_drawdown(equity_curve)
        if max_dd == 0:
            return float("inf")
        return float(annual_return / abs(max_dd))

    def calculate_win_rate(self, trades: pd.DataFrame) -> float:
        if trades.empty or "pnl" not in trades:
            return 0.0
        pnl = trades["pnl"]
        wins = (pnl > 0).sum()
        total = len(pnl)
        if total == 0:
            return 0.0
        return wins / total

    def calculate_profit_factor(self, trades: pd.DataFrame) -> float:
        if trades.empty or "pnl" not in trades:
            return 0.0
        pnl = trades["pnl"]
        gross_profit = pnl[pnl > 0].sum()
        gross_loss = -pnl[pnl < 0].sum()
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    def calculate_information_ratio(
        self,
        returns: pd.Series | np.ndarray | list,
        benchmark_returns: pd.Series | np.ndarray | list,
        periods: int = 252,
    ) -> float:
        series = self._ensure_series(returns)
        benchmark = self._ensure_series(benchmark_returns)
        if series.empty or benchmark.empty:
            return 0.0
        aligned = pd.DataFrame({"strategy": series, "benchmark": benchmark}).dropna()
        if aligned.empty:
            return 0.0
        excess = aligned["strategy"] - aligned["benchmark"]
        std = excess.std(ddof=1)
        if np.isnan(std) or std == 0:
            return 0.0
        return float(excess.mean() / std * np.sqrt(periods))

    def calculate_all_metrics(
        self,
        equity_curve: pd.Series,
        returns: pd.Series,
        trades: pd.DataFrame,
    ) -> dict[str, float]:
        return {
            "total_return": self.calculate_total_return(equity_curve),
            "annualized_return": self.calculate_annualized_return(equity_curve),
            "volatility": self.calculate_volatility(returns),
            "sharpe_ratio": self.calculate_sharpe_ratio(returns),
            "sortino_ratio": self.calculate_sortino_ratio(returns),
            "max_drawdown": self.calculate_max_drawdown(equity_curve),
            "calmar_ratio": self.calculate_calmar_ratio(equity_curve, returns),
            "win_rate": self.calculate_win_rate(trades),
            "profit_factor": self.calculate_profit_factor(trades),
        }

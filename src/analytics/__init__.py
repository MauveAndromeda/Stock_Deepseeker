"""
Advanced performance analytics and reporting module.

Provides comprehensive analysis tools for trading strategies:
- Performance metrics
- Attribution analysis
- Risk analytics
- Trade analytics
- Report generation
"""

from src.analytics.attribution import AttributionAnalyzer
from src.analytics.metrics import PerformanceMetrics
from src.analytics.reporter import PerformanceReporter
from src.analytics.trades import TradeAnalyzer

__all__ = [
    "AttributionAnalyzer",
    "PerformanceMetrics",
    "PerformanceReporter",
    "TradeAnalyzer",
]

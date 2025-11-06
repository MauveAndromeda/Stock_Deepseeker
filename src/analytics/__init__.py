"""
Advanced performance analytics and reporting module.

Provides comprehensive analysis tools for trading strategies:
- Performance metrics
- Attribution analysis
- Risk analytics
- Trade analytics
- Report generation
"""

from src.analytics.metrics import PerformanceMetrics
from src.analytics.attribution import AttributionAnalyzer
from src.analytics.trades import TradeAnalyzer
from src.analytics.reporter import PerformanceReporter

__all__ = [
    'PerformanceMetrics',
    'AttributionAnalyzer',
    'TradeAnalyzer',
    'PerformanceReporter',
]

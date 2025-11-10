"""
Portable Runner - Minimal backtest engine for ZIP→Extract→Run workflow

This package provides a minimal, Windows-friendly backtest implementation
that works without AI dependencies. Advanced features are optional.
"""

__version__ = "1.0.0"

from .downloader import download_market_data, DataSource
from .strategy import SimpleMovingAverageStrategy
from .report import generate_report, calculate_metrics

__all__ = [
    "download_market_data",
    "DataSource",
    "SimpleMovingAverageStrategy",
    "generate_report",
    "calculate_metrics",
]

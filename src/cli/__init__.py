"""
CLI commands for Stock Deepseeker.
"""

from src.cli.backtest import main as backtest_main
from src.cli.optimize import main as optimize_main

__all__ = ["backtest_main", "optimize_main"]

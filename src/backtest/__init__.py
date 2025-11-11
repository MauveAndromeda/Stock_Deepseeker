"""
Backtest Engine Module

Event-driven backtest engine with strict no-lookahead bias enforcement.
"""

from src.backtest.analyzer import PerformanceAnalyzer, TradeAnalyzer
from src.backtest.engine import BacktestEngine, BacktestResult
from src.backtest.engine_v2 import BacktestConfig, BacktestEngineV2
from src.backtest.events import (
    Event,
    EventType,
    FillEvent,
    MarketEvent,
    OrderEvent,
    OrderSide,
    OrderType,
    SignalEvent,
)
from src.backtest.execution import ExecutionHandler
from src.backtest.portfolio_v2 import PortfolioV2

# Main exports
__all__ = [
    # Core engines
    "BacktestEngine",
    "BacktestEngineV2",
    "BacktestConfig",
    "BacktestResult",

    # Events
    "Event",
    "MarketEvent",
    "SignalEvent",
    "OrderEvent",
    "FillEvent",
    "EventType",
    "OrderType",
    "OrderSide",

    # Execution
    "ExecutionHandler",
    "PortfolioV2",

    # Analysis
    "PerformanceAnalyzer",
    "TradeAnalyzer",
]

# Backward compatibility alias
Portfolio = PortfolioV2

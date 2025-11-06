"""
Backtest Engine Module

Event-driven backtest engine with strict no-lookahead bias enforcement.
"""

from src.backtest.engine_v2 import BacktestEngineV2, BacktestConfig
from src.backtest.events import (
    Event, MarketEvent, SignalEvent, OrderEvent, FillEvent,
    EventType, OrderType, OrderSide
)
from src.backtest.execution import ExecutionHandler
from src.backtest.portfolio_v2 import PortfolioV2
from src.backtest.analyzer import PerformanceAnalyzer, TradeAnalyzer

# Main exports
__all__ = [
    # Core engine
    "BacktestEngineV2",
    "BacktestConfig",

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

# Backward compatibility aliases
BacktestEngine = BacktestEngineV2
Portfolio = PortfolioV2

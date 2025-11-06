"""
Strategy templates and implementations.

Pre-built trading strategies ready to use.
"""

from src.strategies.base import BaseStrategy, Signal
from src.strategies.momentum import MomentumStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.pairs_trading import PairsTradingStrategy

__all__ = [
    'BaseStrategy',
    'Signal',
    'MomentumStrategy',
    'MeanReversionStrategy',
    'PairsTradingStrategy',
]

"""
Trading strategies module.

Contains various algorithmic trading strategies:
- Momentum strategies
- Mean reversion strategies
- Value strategies
- Multi-factor strategies
- Volatility strategies
- Sector rotation
- Breakout strategies
- Trend following
- Market neutral strategies
- Pairs trading
"""

from src.strategies.base import BaseStrategy, Signal, SignalType
from src.strategies.breakout import BreakoutStrategy, BreakoutType
from src.strategies.market_neutral import MarketNeutralStrategy, SecurityScore
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.momentum import MomentumStrategy
from src.strategies.multi_factor import FactorScore, MultiFactorStrategy
from src.strategies.pairs_trading import PairsTradingStrategy
from src.strategies.sector_rotation import MarketRegime, SectorRotationStrategy
from src.strategies.trend_following import TrendFollowingStrategy, TrendState
from src.strategies.value import ValueStrategy
from src.strategies.volatility_arbitrage import VolatilityArbitrageStrategy

__all__ = [
    # Base classes
    "BaseStrategy",
    "Signal",
    "SignalType",

    # Momentum strategies
    "MomentumStrategy",

    # Mean reversion strategies
    "MeanReversionStrategy",
    "PairsTradingStrategy",

    # Value strategies
    "ValueStrategy",

    # Multi-factor strategies
    "MultiFactorStrategy",
    "FactorScore",

    # Volatility strategies
    "VolatilityArbitrageStrategy",

    # Sector strategies
    "SectorRotationStrategy",
    "MarketRegime",

    # Technical strategies
    "BreakoutStrategy",
    "BreakoutType",
    "TrendFollowingStrategy",
    "TrendState",

    # Market neutral
    "MarketNeutralStrategy",
    "SecurityScore",
]

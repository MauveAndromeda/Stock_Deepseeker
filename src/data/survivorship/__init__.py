"""
Survivorship bias handling package.

Provides point-in-time universe construction to eliminate survivorship bias
in backtests.
"""

from src.data.survivorship.universe import (
    UniverseManager,
    PointInTimeUniverse,
    UniverseConstituent,
    DelistingReason,
)
from src.data.survivorship.database import SurvivorshipDatabase
from src.data.survivorship.validator import BacktestValidator

__all__ = [
    "UniverseManager",
    "PointInTimeUniverse",
    "UniverseConstituent",
    "DelistingReason",
    "SurvivorshipDatabase",
    "BacktestValidator",
]

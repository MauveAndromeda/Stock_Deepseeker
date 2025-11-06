"""
Corporate actions processing package.

Handles splits, dividends, mergers, acquisitions, and other corporate actions.
Ensures proper price adjustment and historical accuracy.
"""

from src.data.corporate_actions.base import (
    CorporateActionType,
    CorporateActionProcessor,
    AdjustmentMethod,
)
from src.data.corporate_actions.splits import SplitAdjuster
from src.data.corporate_actions.dividends import DividendProcessor
from src.data.corporate_actions.mergers import MergerHandler
from src.data.corporate_actions.adjustments import PriceAdjuster

__all__ = [
    "CorporateActionType",
    "CorporateActionProcessor",
    "AdjustmentMethod",
    "SplitAdjuster",
    "DividendProcessor",
    "MergerHandler",
    "PriceAdjuster",
]

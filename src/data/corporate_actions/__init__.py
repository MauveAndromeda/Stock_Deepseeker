"""
Corporate actions processing package.

Handles splits, dividends, mergers, acquisitions, and other corporate actions.
Ensures proper price adjustment and historical accuracy.
"""

from src.data.corporate_actions.adjustments import PriceAdjuster
from src.data.corporate_actions.base import (
    AdjustmentMethod,
    CorporateActionProcessor,
    CorporateActionType,
)
from src.data.corporate_actions.dividends import DividendProcessor
from src.data.corporate_actions.mergers import MergerHandler
from src.data.corporate_actions.splits import SplitAdjuster

__all__ = [
    "AdjustmentMethod",
    "CorporateActionProcessor",
    "CorporateActionType",
    "DividendProcessor",
    "MergerHandler",
    "PriceAdjuster",
    "SplitAdjuster",
]

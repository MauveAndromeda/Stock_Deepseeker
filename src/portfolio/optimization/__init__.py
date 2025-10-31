"""
Portfolio Optimization Module

This module provides advanced portfolio optimization algorithms including:
- Markowitz Mean-Variance Optimization
- Black-Litterman Model
- Efficient Frontier calculation
"""

from typing import Dict, List
import logging

__version__ = "1.0.0"

logger = logging.getLogger(__name__)

try:
    from .markowitz import (
        MarkowitzOptimizer,
        EfficientFrontier,
        PortfolioPoint,
    )
    from .black_litterman import (
        BlackLittermanModel,
        MarketView,
        ViewConfidence,
    )

    __all__ = [
        'MarkowitzOptimizer',
        'EfficientFrontier',
        'PortfolioPoint',
        'BlackLittermanModel',
        'MarketView',
        'ViewConfidence',
    ]

except ImportError as e:
    logger.warning(f"Could not import optimization components: {e}")
    __all__ = []

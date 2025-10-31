"""
Portfolio Rebalancing Module

This module provides portfolio rebalancing strategies including:
- Threshold-based rebalancing
- Time-based rebalancing
- Volatility-adaptive rebalancing
- Tax-aware rebalancing
"""

from typing import Dict, List
import logging

__version__ = "1.0.0"

logger = logging.getLogger(__name__)

try:
    from .rebalancer import (
        RebalancingEngine,
        RebalancingStrategy,
        RebalancingSignal,
        RebalancingResult,
        TaxLot,
    )

    __all__ = [
        'RebalancingEngine',
        'RebalancingStrategy',
        'RebalancingSignal',
        'RebalancingResult',
        'TaxLot',
    ]

except ImportError as e:
    logger.warning(f"Could not import rebalancing components: {e}")
    __all__ = []


# Predefined rebalancing strategies
REBALANCING_STRATEGIES = {
    'threshold': {
        'description': 'Rebalance when allocation drifts beyond threshold',
        'threshold': 0.05,
        'relative': True,
    },
    'calendar': {
        'description': 'Rebalance on fixed calendar schedule',
        'frequency': 'monthly',
    },
    'volatility': {
        'description': 'Rebalance based on volatility changes',
        'vol_threshold': 0.2,
    },
    'combined': {
        'description': 'Combine threshold and time-based rebalancing',
        'threshold': 0.05,
        'frequency': 'quarterly',
    },
}


def get_rebalancing_strategy(name: str) -> Dict:
    """Get predefined rebalancing strategy"""
    return REBALANCING_STRATEGIES.get(name, {})

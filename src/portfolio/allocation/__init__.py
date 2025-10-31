"""
Portfolio Allocation Module

This module provides portfolio allocation strategies and optimization algorithms
for determining optimal portfolio weights.

Components:
    - optimizer: Main portfolio optimizer with multiple allocation strategies
"""

from typing import Dict, List, Optional
import logging

__version__ = "1.0.0"

logger = logging.getLogger(__name__)

try:
    from .optimizer import (
        PortfolioOptimizer,
        OptimizationObjective,
        AllocationConstraints,
        AllocationResult,
    )

    __all__ = [
        'PortfolioOptimizer',
        'OptimizationObjective',
        'AllocationConstraints',
        'AllocationResult',
    ]

except ImportError as e:
    logger.warning(f"Could not import allocation components: {e}")
    __all__ = []


# Allocation strategy presets
ALLOCATION_STRATEGIES = {
    'equal_weight': {
        'description': 'Equal weight allocation',
        'objective': 'equal_weight',
        'constraints': {},
    },
    'min_variance': {
        'description': 'Minimum variance portfolio',
        'objective': 'min_variance',
        'constraints': {'long_only': True},
    },
    'max_sharpe': {
        'description': 'Maximum Sharpe ratio portfolio',
        'objective': 'max_sharpe',
        'constraints': {'long_only': True},
    },
    'risk_parity': {
        'description': 'Risk parity allocation',
        'objective': 'risk_parity',
        'constraints': {'long_only': True},
    },
    'kelly': {
        'description': 'Kelly criterion position sizing',
        'objective': 'kelly',
        'constraints': {'long_only': True, 'max_leverage': 1.0},
    },
}


def get_strategy(name: str) -> Optional[Dict]:
    """
    Get allocation strategy configuration by name.

    Args:
        name: Strategy name

    Returns:
        Strategy configuration dictionary or None if not found
    """
    return ALLOCATION_STRATEGIES.get(name)


def list_strategies() -> List[str]:
    """
    List available allocation strategies.

    Returns:
        List of strategy names
    """
    return list(ALLOCATION_STRATEGIES.keys())

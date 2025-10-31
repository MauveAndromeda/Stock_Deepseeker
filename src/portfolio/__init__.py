"""
Portfolio Management Package

This package provides comprehensive portfolio management capabilities including:
- Portfolio allocation and optimization
- Rebalancing strategies
- Performance tracking and attribution
- Risk management integration

Main Components:
    - allocation: Portfolio allocation strategies and optimizers
    - optimization: Advanced optimization algorithms (Markowitz, Black-Litterman)
    - rebalancing: Portfolio rebalancing engines
    - manager: Main portfolio management orchestrator
    - attribution: Performance attribution analysis
"""

from typing import Dict, List, Optional, Any
import logging

# Version information
__version__ = "1.0.0"
__author__ = "Stock DeepSeeker Team"

# Configure logging
logger = logging.getLogger(__name__)

# Import main classes for convenient access
try:
    from .manager import PortfolioManager
    from .allocation.optimizer import PortfolioOptimizer
    from .optimization.markowitz import MarkowitzOptimizer
    from .optimization.black_litterman import BlackLittermanModel
    from .rebalancing.rebalancer import RebalancingEngine

    __all__ = [
        'PortfolioManager',
        'PortfolioOptimizer',
        'MarkowitzOptimizer',
        'BlackLittermanModel',
        'RebalancingEngine',
    ]

except ImportError as e:
    logger.warning(f"Some portfolio modules could not be imported: {e}")
    __all__ = []


# Package-level configuration
DEFAULT_CONFIG = {
    'optimization': {
        'max_iterations': 1000,
        'convergence_threshold': 1e-6,
        'risk_free_rate': 0.02,
        'max_leverage': 1.0,
    },
    'rebalancing': {
        'threshold': 0.05,  # 5% threshold
        'frequency': 'monthly',
        'tax_aware': True,
        'transaction_cost': 0.001,  # 10 bps
    },
    'risk': {
        'max_position_size': 0.2,  # 20% max per position
        'max_sector_exposure': 0.4,  # 40% max per sector
        'min_cash': 0.05,  # 5% minimum cash
    },
    'performance': {
        'benchmark': 'SPY',
        'attribution_frequency': 'daily',
        'rolling_window': 252,  # Trading days
    }
}


def get_config() -> Dict[str, Any]:
    """
    Get default package configuration.

    Returns:
        Dictionary containing default configuration settings
    """
    return DEFAULT_CONFIG.copy()


def set_config(config: Dict[str, Any]) -> None:
    """
    Update package configuration.

    Args:
        config: Dictionary with configuration updates
    """
    global DEFAULT_CONFIG
    for key, value in config.items():
        if key in DEFAULT_CONFIG:
            if isinstance(value, dict) and isinstance(DEFAULT_CONFIG[key], dict):
                DEFAULT_CONFIG[key].update(value)
            else:
                DEFAULT_CONFIG[key] = value
        else:
            DEFAULT_CONFIG[key] = value
    logger.info(f"Portfolio configuration updated")

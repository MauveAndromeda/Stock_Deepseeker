"""
Risk Management Module

This module provides comprehensive risk management capabilities including:
- Risk metrics calculation (VaR, CVaR, drawdown, ratios)
- Risk limits enforcement (position, concentration, loss limits)
- Real-time risk monitoring and reporting
- Pre-trade and post-trade risk checks
- Emergency shutdown procedures

Version: 1.0.0
"""

from .manager import RiskManager
from .metrics.risk_calculator import RiskCalculator
from .limits.risk_limiter import RiskLimiter

__all__ = [
    'RiskManager',
    'RiskCalculator',
    'RiskLimiter',
]

__version__ = '1.0.0'

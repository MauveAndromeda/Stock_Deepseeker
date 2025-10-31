"""
Risk Limits Module

Provides comprehensive risk limit enforcement including:
- Position size limits
- Portfolio concentration limits
- Daily loss limits with auto-shutdown
- Leverage limits
- Sector exposure limits
- Correlation-based limits
- Dynamic position sizing based on volatility

Version: 1.0.0
"""

from .risk_limiter import RiskLimiter, LimitType, LimitViolation

__all__ = ['RiskLimiter', 'LimitType', 'LimitViolation']

__version__ = '1.0.0'

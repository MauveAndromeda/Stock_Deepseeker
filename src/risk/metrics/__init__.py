"""
Risk Metrics Module

Provides comprehensive risk metric calculations including:
- Value at Risk (VaR) - Historical, Parametric, Monte Carlo
- Conditional Value at Risk (CVaR)
- Maximum Drawdown tracking
- Risk-adjusted performance ratios (Sharpe, Sortino, Calmar)
- Greek calculations (Beta, Alpha)
- Correlation and volatility metrics
- Stress testing scenarios

Version: 1.0.0
"""

from .risk_calculator import RiskCalculator

__all__ = ['RiskCalculator']

__version__ = '1.0.0'

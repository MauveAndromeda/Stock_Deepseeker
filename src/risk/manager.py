"""
Risk Management System
Comprehensive risk monitoring and control
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from loguru import logger

@dataclass
class RiskLimits:
    """Risk limit configuration"""
    max_position_size: float = 0.1
    max_portfolio_risk: float = 0.20
    max_daily_loss: float = 0.03
    max_drawdown: float = 0.15
    max_leverage: float = 1.0
    max_sector_exposure: float = 0.30
    max_correlation: float = 0.7

class RiskManager:
    """Main risk management system"""

    def __init__(self, limits: Optional[RiskLimits] = None):
        self.limits = limits or RiskLimits()
        self.daily_pnl = 0.0
        self.daily_start_value = 0.0
        self.peak_value = 0.0
        self.current_drawdown = 0.0
        self.positions = {}
        self.risk_events = []
        logger.info("Risk Manager initialized")

    def can_trade(self, symbol: str, action: str) -> bool:
        """Check if trade is allowed"""
        # Check daily loss limit
        if self.daily_pnl / self.daily_start_value < -self.limits.max_daily_loss:
            logger.warning("Daily loss limit exceeded!")
            return False
        
        # Check drawdown limit
        if self.current_drawdown > self.limits.max_drawdown:
            logger.warning("Maximum drawdown limit exceeded!")
            return False
        
        # Check position limit
        if len(self.positions) >= 20:
            logger.warning("Maximum position count reached")
            return False
        
        return True

    def calculate_var(self, returns: np.ndarray, confidence: float = 0.95) -> float:
        """Calculate Value at Risk"""
        if len(returns) == 0:
            return 0.0
        var = np.percentile(returns, (1 - confidence) * 100)
        return abs(var)

    def calculate_cvar(self, returns: np.ndarray, confidence: float = 0.95) -> float:
        """Calculate Conditional VaR (Expected Shortfall)"""
        var = self.calculate_var(returns, confidence)
        cvar = abs(np.mean(returns[returns <= -var]))
        return cvar

    def calculate_sharpe_ratio(self, returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) < 2:
            return 0.0
        excess_returns = returns - risk_free_rate / 252
        if np.std(excess_returns) == 0:
            return 0.0
        sharpe = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
        return sharpe

    def calculate_max_drawdown(self, equity_curve: np.ndarray) -> float:
        """Calculate maximum drawdown"""
        running_max = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - running_max) / running_max
        return abs(np.min(drawdown))

    def update_daily_pnl(self, current_value: float):
        """Update daily P&L tracking"""
        if self.daily_start_value == 0:
            self.daily_start_value = current_value
        self.daily_pnl = current_value - self.daily_start_value
        
        # Update drawdown
        if current_value > self.peak_value:
            self.peak_value = current_value
        self.current_drawdown = (self.peak_value - current_value) / self.peak_value

    def check_stop_loss(self, position: Dict, current_price: float) -> bool:
        """Check if position hit stop loss"""
        if 'stop_loss' not in position:
            return False
        
        if position['type'] == 'long':
            return current_price <= position['stop_loss']
        else:
            return current_price >= position['stop_loss']

    def calculate_position_size(
        self, symbol: str, price: float, portfolio_value: float,
        volatility: float, risk_per_trade: float = 0.01
    ) -> int:
        """Calculate optimal position size using Kelly Criterion"""
        # Risk amount
        risk_amount = portfolio_value * risk_per_trade
        
        # Position size based on volatility
        if volatility > 0:
            position_value = risk_amount / volatility
        else:
            position_value = portfolio_value * self.limits.max_position_size
        
        # Apply limits
        max_value = portfolio_value * self.limits.max_position_size
        position_value = min(position_value, max_value)
        
        shares = int(position_value / price)
        return shares

    def get_risk_metrics(self) -> Dict:
        """Get current risk metrics"""
        return {
            'daily_pnl': self.daily_pnl,
            'current_drawdown': self.current_drawdown,
            'num_positions': len(self.positions),
            'daily_loss_pct': self.daily_pnl / self.daily_start_value if self.daily_start_value > 0 else 0
        }

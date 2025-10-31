"""
Tests for risk management
"""

import pytest
import numpy as np

from src.risk.manager import RiskManager, RiskLimits


class TestRiskManager:
    """Test RiskManager"""

    def setup_method(self):
        """Setup test fixtures"""
        limits = RiskLimits(
            max_daily_loss=0.03,
            max_drawdown=0.15,
            max_position_size=0.1
        )
        self.risk_manager = RiskManager(limits)

    def test_initialization(self):
        """Test risk manager initialization"""
        assert self.risk_manager.limits.max_daily_loss == 0.03
        assert self.risk_manager.daily_pnl == 0.0

    def test_can_trade_checks(self):
        """Test trading permission checks"""
        # Should allow trading initially
        assert self.risk_manager.can_trade('TEST', 'buy')
        
        # Simulate daily loss
        self.risk_manager.daily_start_value = 100000
        self.risk_manager.daily_pnl = -3500  # -3.5% loss
        
        # Should block trading
        assert not self.risk_manager.can_trade('TEST', 'buy')

    def test_var_calculation(self):
        """Test VaR calculation"""
        returns = np.random.randn(1000) * 0.02
        
        var = self.risk_manager.calculate_var(returns, confidence=0.95)
        
        assert var > 0
        assert isinstance(var, float)

    def test_cvar_calculation(self):
        """Test CVaR calculation"""
        returns = np.random.randn(1000) * 0.02
        
        cvar = self.risk_manager.calculate_cvar(returns, confidence=0.95)
        
        assert cvar > 0
        assert cvar >= self.risk_manager.calculate_var(returns, 0.95)

    def test_sharpe_ratio_calculation(self):
        """Test Sharpe ratio calculation"""
        # Positive returns
        returns = np.random.randn(252) * 0.01 + 0.001
        
        sharpe = self.risk_manager.calculate_sharpe_ratio(returns)
        
        assert isinstance(sharpe, float)

    def test_max_drawdown_calculation(self):
        """Test max drawdown calculation"""
        # Create equity curve with drawdown
        equity = np.array([100, 105, 103, 98, 102, 110, 95, 100])
        
        max_dd = self.risk_manager.calculate_max_drawdown(equity)
        
        assert max_dd > 0
        assert max_dd <= 1.0

    def test_position_sizing(self):
        """Test position size calculation"""
        size = self.risk_manager.calculate_position_size(
            symbol='TEST',
            price=100.0,
            portfolio_value=100000.0,
            volatility=0.02,
            risk_per_trade=0.01
        )
        
        assert size > 0
        assert isinstance(size, int)
        
        # Position value should not exceed limits
        position_value = size * 100
        assert position_value <= 100000 * self.risk_manager.limits.max_position_size

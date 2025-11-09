"""
Risk Management System Tests
风险管理系统测试

Research-grade implementation (Under Development)
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from src.risk import (
    RiskAdjustment,
    RiskCheckResult,
    RiskLimit,
    RiskManager,
    RiskMetrics,
    VaRCalculator,
)


class TestVaRCalculator:
    """测试VaR计算器"""

    def test_historical_var_calculation(self):
        """测试历史模拟法VaR"""
        # 生成模拟收益率数据
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 1000)  # 均值0.1%，标准差2%

        calculator = VaRCalculator()
        var_95 = calculator.historical_var(returns, confidence_level=0.95)
        var_99 = calculator.historical_var(returns, confidence_level=0.99)

        # VaR应该是正数（表示潜在损失）
        assert var_95 > 0
        assert var_99 > 0
        # 99% VaR应该大于95% VaR
        assert var_99 > var_95

    def test_parametric_var_calculation(self):
        """测试参数法VaR"""
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 1000)

        calculator = VaRCalculator()
        var_95 = calculator.parametric_var(returns, confidence_level=0.95)
        var_99 = calculator.parametric_var(returns, confidence_level=0.99)

        assert var_95 > 0
        assert var_99 > 0
        assert var_99 > var_95

    def test_var_with_empty_returns(self):
        """测试空收益率序列"""
        calculator = VaRCalculator()
        var = calculator.historical_var(np.array([]))
        assert var == 0.0


class TestRiskManager:
    """测试风险管理器"""

    def test_risk_manager_initialization(self):
        """测试风险管理器初始化"""
        risk_manager = RiskManager()
        assert risk_manager is not None
        assert risk_manager.risk_limits is not None
        assert isinstance(risk_manager.risk_limits, RiskLimit)

    def test_custom_risk_limits(self):
        """测试自定义风险限制"""
        custom_limits = RiskLimit(
            max_position_size=0.15,
            max_drawdown=0.10,
            stop_loss_pct=0.05
        )
        risk_manager = RiskManager(risk_limits=custom_limits)

        assert risk_manager.risk_limits.max_position_size == 0.15
        assert risk_manager.risk_limits.max_drawdown == 0.10
        assert risk_manager.risk_limits.stop_loss_pct == 0.05

    def test_position_limit_check_approved(self):
        """测试仓位限制检查 - 通过"""
        risk_manager = RiskManager()

        # 提议仓位：10% (在限制内)
        proposed_size = 10000
        portfolio_value = 100000
        current_positions = {}

        result, adjustment = risk_manager.check_position_limits(
            symbol="AAPL",
            proposed_size=proposed_size,
            current_positions=current_positions,
            portfolio_value=portfolio_value
        )

        assert result == RiskCheckResult.APPROVED
        assert adjustment.adjusted_size == proposed_size
        assert len(adjustment.warnings) == 0

    def test_position_limit_check_adjusted(self):
        """测试仓位限制检查 - 调整"""
        risk_manager = RiskManager()

        # 提议仓位：25% (超过20%限制)
        proposed_size = 25000
        portfolio_value = 100000
        current_positions = {}

        result, adjustment = risk_manager.check_position_limits(
            symbol="AAPL",
            proposed_size=proposed_size,
            current_positions=current_positions,
            portfolio_value=portfolio_value
        )

        assert result == RiskCheckResult.ADJUSTED
        # 应调整为最大20%
        assert adjustment.adjusted_size == 20000
        assert len(adjustment.warnings) > 0
        assert "exceeds limit" in adjustment.warnings[0]

    def test_stop_loss_check(self):
        """测试止损检查"""
        risk_manager = RiskManager(
            risk_limits=RiskLimit(stop_loss_pct=0.08)
        )

        # 情况1：未触发止损（-5%）
        triggered, loss_pct = risk_manager.check_stop_loss(
            symbol="AAPL",
            entry_price=100.0,
            current_price=95.0
        )
        assert not triggered
        assert loss_pct == -0.05

        # 情况2：触发止损（-10%）
        triggered, loss_pct = risk_manager.check_stop_loss(
            symbol="AAPL",
            entry_price=100.0,
            current_price=90.0
        )
        assert triggered
        assert loss_pct == -0.10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

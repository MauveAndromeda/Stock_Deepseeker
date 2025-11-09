"""
测试配置模块
"""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import Config, DataSource, TradingMode


class TestConfig:
    """测试配置类"""

    def test_singleton_pattern(self):
        """测试单例模式"""
        config1 = Config()
        config2 = Config()
        assert config1 is config2, "Config应该是单例"

    def test_default_values(self):
        """测试默认配置值"""
        config = Config()
        assert config.initial_capital > 0, "初始资金应该大于0"
        assert config.max_position_size > 0, "最大仓位应该大于0"
        assert config.max_position_size <= 1.0, "最大仓位不应超过100%"

    def test_trading_mode_validation(self):
        """测试交易模式验证"""
        config = Config()
        assert config.trading_mode in [TradingMode.BACKTEST, TradingMode.PAPER, TradingMode.LIVE]

    def test_data_source_validation(self):
        """测试数据源验证"""
        config = Config()
        assert config.data_source in [
            DataSource.YAHOO,
            DataSource.ALPACA,
            DataSource.ALPHA_VANTAGE,
            DataSource.IEX
        ]

    def test_risk_limits(self):
        """测试风险限制配置"""
        config = Config()
        assert 0 < config.stop_loss_pct < 1, "止损百分比应该在0-100%之间"
        assert config.take_profit_pct > 0, "止盈百分比应该大于0"

    def test_commission_settings(self):
        """测试手续费配置"""
        config = Config()
        assert config.commission_rate >= 0, "手续费率不应为负"
        assert config.slippage_rate >= 0, "滑点率不应为负"


class TestTradingMode:
    """测试交易模式枚举"""

    def test_trading_mode_values(self):
        """测试交易模式值"""
        assert TradingMode.BACKTEST == "backtest"
        assert TradingMode.PAPER == "paper"
        assert TradingMode.LIVE == "live"


class TestDataSource:
    """测试数据源枚举"""

    def test_data_source_values(self):
        """测试数据源值"""
        assert DataSource.YAHOO == "yahoo"
        assert DataSource.ALPACA == "alpaca"
        assert DataSource.ALPHA_VANTAGE == "alpha_vantage"
        assert DataSource.IEX == "iex"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

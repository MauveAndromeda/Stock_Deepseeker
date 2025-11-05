"""
测试性能指标模块
"""

import pytest
import numpy as np
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.metrics import MetricsCalculator


class TestMetricsCalculator:
    """测试指标计算器"""

    def setup_method(self):
        """每个测试前的设置"""
        # 创建测试数据
        np.random.seed(42)
        self.returns = pd.Series(np.random.normal(0.001, 0.02, 252))  # 1年的日收益
        self.equity_curve = (1 + self.returns).cumprod() * 100000  # 起始资金10万

    def test_total_return(self):
        """测试总收益率计算"""
        calculator = MetricsCalculator()
        total_return = calculator.calculate_total_return(self.equity_curve)

        expected = (self.equity_curve.iloc[-1] - self.equity_curve.iloc[0]) / self.equity_curve.iloc[0]
        assert abs(total_return - expected) < 1e-6, "总收益率计算错误"

    def test_annualized_return(self):
        """测试年化收益率计算"""
        calculator = MetricsCalculator()

        # 1年数据
        annual_return = calculator.calculate_annualized_return(
            self.equity_curve,
            periods=252
        )
        assert isinstance(annual_return, float), "年化收益率应该是浮点数"

        # 验证年化收益率与总收益率的关系（1年数据应该近似相等）
        total_return = calculator.calculate_total_return(self.equity_curve)
        assert abs(annual_return - total_return) < 0.01, "1年数据年化收益应接近总收益"

    def test_volatility(self):
        """测试波动率计算"""
        calculator = MetricsCalculator()
        volatility = calculator.calculate_volatility(self.returns)

        # 年化波动率
        expected_vol = self.returns.std() * np.sqrt(252)
        assert abs(volatility - expected_vol) < 1e-6, "波动率计算错误"
        assert volatility > 0, "波动率应该大于0"

    def test_sharpe_ratio(self):
        """测试夏普比率计算"""
        calculator = MetricsCalculator()
        sharpe = calculator.calculate_sharpe_ratio(
            self.returns,
            risk_free_rate=0.02
        )

        # 手动计算验证
        excess_returns = self.returns - 0.02 / 252  # 日无风险利率
        expected_sharpe = excess_returns.mean() / self.returns.std() * np.sqrt(252)

        assert abs(sharpe - expected_sharpe) < 0.01, "夏普比率计算错误"

    def test_sharpe_ratio_with_zero_volatility(self):
        """测试零波动率情况下的夏普比率"""
        calculator = MetricsCalculator()
        zero_vol_returns = pd.Series([0.0] * 252)
        sharpe = calculator.calculate_sharpe_ratio(zero_vol_returns)
        assert sharpe == 0, "零波动率时夏普比率应为0"

    def test_sortino_ratio(self):
        """测试索提诺比率计算"""
        calculator = MetricsCalculator()
        sortino = calculator.calculate_sortino_ratio(
            self.returns,
            risk_free_rate=0.02
        )

        # 索提诺比率应该大于或等于夏普比率（因为只考虑下行波动）
        sharpe = calculator.calculate_sharpe_ratio(self.returns, risk_free_rate=0.02)
        assert sortino >= sharpe or abs(sortino - sharpe) < 0.01, "索提诺比率应 >= 夏普比率"

    def test_max_drawdown(self):
        """测试最大回撤计算"""
        calculator = MetricsCalculator()
        max_dd = calculator.calculate_max_drawdown(self.equity_curve)

        # 最大回撤应该是负数或0
        assert max_dd <= 0, "最大回撤应该 <= 0"

        # 手动计算验证
        running_max = self.equity_curve.expanding().max()
        drawdown = (self.equity_curve - running_max) / running_max
        expected_max_dd = drawdown.min()

        assert abs(max_dd - expected_max_dd) < 1e-6, "最大回撤计算错误"

    def test_max_drawdown_duration(self):
        """测试最大回撤持续时间"""
        calculator = MetricsCalculator()
        duration = calculator.calculate_max_drawdown_duration(self.equity_curve)

        assert isinstance(duration, int), "回撤持续时间应该是整数"
        assert duration >= 0, "回撤持续时间应该 >= 0"

    def test_calmar_ratio(self):
        """测试卡玛比率计算"""
        calculator = MetricsCalculator()
        calmar = calculator.calculate_calmar_ratio(
            self.equity_curve,
            self.returns
        )

        # 卡玛比率 = 年化收益率 / 最大回撤
        annual_return = calculator.calculate_annualized_return(self.equity_curve)
        max_dd = calculator.calculate_max_drawdown(self.equity_curve)

        if max_dd != 0:
            expected_calmar = annual_return / abs(max_dd)
            assert abs(calmar - expected_calmar) < 0.01, "卡玛比率计算错误"

    def test_win_rate(self):
        """测试胜率计算"""
        calculator = MetricsCalculator()

        # 创建测试交易
        trades = pd.DataFrame({
            'pnl': [100, -50, 200, -30, 150, -20, 80]
        })

        win_rate = calculator.calculate_win_rate(trades)

        # 4笔盈利 / 7笔总交易 = 57.14%
        assert abs(win_rate - 4/7) < 0.01, "胜率计算错误"

    def test_profit_factor(self):
        """测试盈利因子计算"""
        calculator = MetricsCalculator()

        trades = pd.DataFrame({
            'pnl': [100, -50, 200, -30, 150]
        })

        profit_factor = calculator.calculate_profit_factor(trades)

        # 总盈利 / 总亏损 = (100+200+150) / (50+30) = 5.625
        expected = 450 / 80
        assert abs(profit_factor - expected) < 0.01, "盈利因子计算错误"

    def test_profit_factor_no_losses(self):
        """测试无亏损时的盈利因子"""
        calculator = MetricsCalculator()

        trades = pd.DataFrame({
            'pnl': [100, 200, 150]
        })

        profit_factor = calculator.calculate_profit_factor(trades)
        assert profit_factor == float('inf'), "无亏损时盈利因子应为无穷大"

    def test_information_ratio(self):
        """测试信息比率计算"""
        calculator = MetricsCalculator()

        # 创建策略和基准收益
        benchmark_returns = pd.Series(np.random.normal(0.0005, 0.015, 252))

        ir = calculator.calculate_information_ratio(
            self.returns,
            benchmark_returns
        )

        # 信息比率 = 超额收益均值 / 超额收益标准差
        excess = self.returns - benchmark_returns
        expected_ir = excess.mean() / excess.std() * np.sqrt(252)

        assert abs(ir - expected_ir) < 0.01, "信息比率计算错误"

    def test_calculate_all_metrics(self):
        """测试计算所有指标"""
        calculator = MetricsCalculator()

        trades = pd.DataFrame({
            'pnl': [100, -50, 200, -30, 150, -20, 80],
            'symbol': ['AAPL'] * 7
        })

        metrics = calculator.calculate_all_metrics(
            equity_curve=self.equity_curve,
            returns=self.returns,
            trades=trades
        )

        # 验证所有关键指标都存在
        required_metrics = [
            'total_return',
            'annualized_return',
            'volatility',
            'sharpe_ratio',
            'sortino_ratio',
            'max_drawdown',
            'calmar_ratio',
            'win_rate',
            'profit_factor'
        ]

        for metric in required_metrics:
            assert metric in metrics, f"缺少指标: {metric}"
            assert isinstance(metrics[metric], (int, float)), f"{metric}应该是数值"


class TestEdgeCases:
    """测试边界情况"""

    def test_empty_data(self):
        """测试空数据"""
        calculator = MetricsCalculator()

        empty_series = pd.Series([])

        # 空数据应该返回0或NaN
        assert calculator.calculate_volatility(empty_series) == 0

    def test_single_value(self):
        """测试单个值"""
        calculator = MetricsCalculator()

        single_value = pd.Series([100000])

        # 单个值的收益率应该是0
        total_return = calculator.calculate_total_return(single_value)
        assert total_return == 0

    def test_negative_equity(self):
        """测试负权益值"""
        calculator = MetricsCalculator()

        # 从正到负的权益曲线
        equity = pd.Series([100000, 80000, 60000, 40000, 20000, -10000])

        max_dd = calculator.calculate_max_drawdown(equity)

        # 最大回撤应该超过100%
        assert max_dd < -1.0, "爆仓情况下回撤应超过100%"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

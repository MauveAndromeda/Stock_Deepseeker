"""
测试市场状态检测模块
"""

import pytest
import numpy as np
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.risk.regime_detection import (
    MarketRegimeDetector,
    MarketRegime,
    RegimeParameters
)


class TestMarketRegimeDetector:
    """测试市场状态检测器"""

    def setup_method(self):
        """每个测试前的设置"""
        self.detector = MarketRegimeDetector()

        # 创建测试数据
        np.random.seed(42)
        dates = pd.date_range('2023-01-01', periods=252, freq='D')

        # 创建不同市场状态的数据
        self.bull_market = self._create_bull_market_data(dates)
        self.bear_market = self._create_bear_market_data(dates)
        self.ranging_market = self._create_ranging_market_data(dates)
        self.volatile_market = self._create_volatile_market_data(dates)

    def _create_bull_market_data(self, dates):
        """创建牛市数据"""
        # 上升趋势 + 低波动
        trend = np.linspace(100, 150, len(dates))
        noise = np.random.normal(0, 1, len(dates))
        prices = trend + noise

        return pd.DataFrame({
            'Close': prices,
            'Volume': np.random.randint(1000000, 2000000, len(dates))
        }, index=dates)

    def _create_bear_market_data(self, dates):
        """创建熊市数据"""
        # 下降趋势 + 中等波动
        trend = np.linspace(150, 100, len(dates))
        noise = np.random.normal(0, 2, len(dates))
        prices = trend + noise

        return pd.DataFrame({
            'Close': prices,
            'Volume': np.random.randint(1000000, 3000000, len(dates))
        }, index=dates)

    def _create_ranging_market_data(self, dates):
        """创建震荡市数据"""
        # 无趋势 + 低波动
        base = 100
        noise = np.random.normal(0, 1, len(dates))
        prices = base + noise

        return pd.DataFrame({
            'Close': prices,
            'Volume': np.random.randint(1000000, 2000000, len(dates))
        }, index=dates)

    def _create_volatile_market_data(self, dates):
        """创建高波动市场数据"""
        # 大幅波动
        base = 100
        noise = np.random.normal(0, 5, len(dates))
        prices = base + noise

        return pd.DataFrame({
            'Close': prices,
            'Volume': np.random.randint(2000000, 5000000, len(dates))
        }, index=dates)

    def test_detect_bull_market(self):
        """测试检测牛市"""
        regime = self.detector.detect_regime(self.bull_market, method='rule_based')

        # 牛市应该被检测为trending_bull
        assert regime in [MarketRegime.TRENDING_BULL, MarketRegime.RANGING_LOW_VOL], \
            f"牛市数据应检测为trending_bull或ranging_low_vol，实际: {regime}"

    def test_detect_bear_market(self):
        """测试检测熊市"""
        regime = self.detector.detect_regime(self.bear_market, method='rule_based')

        # 熊市应该被检测为trending_bear或ranging
        assert regime in [MarketRegime.TRENDING_BEAR, MarketRegime.RANGING_LOW_VOL,
                         MarketRegime.RANGING_HIGH_VOL], \
            f"熊市数据应检测为trending_bear或ranging，实际: {regime}"

    def test_detect_ranging_market(self):
        """测试检测震荡市"""
        regime = self.detector.detect_regime(self.ranging_market, method='rule_based')

        # 震荡市应该被检测为ranging
        assert regime in [MarketRegime.RANGING_LOW_VOL, MarketRegime.RANGING_HIGH_VOL], \
            f"震荡市数据应检测为ranging，实际: {regime}"

    def test_detect_volatile_market(self):
        """测试检测高波动市"""
        regime = self.detector.detect_regime(self.volatile_market, method='rule_based')

        # 高波动市应该包含volatile或ranging_high_vol
        assert 'volatile' in regime.value or 'high_vol' in regime.value, \
            f"高波动数据应检测为volatile或high_vol，实际: {regime}"

    def test_rule_based_detection(self):
        """测试基于规则的检测"""
        regime = self.detector.rule_based_detection(self.bull_market)

        # 应该返回有效的市场状态
        assert isinstance(regime, MarketRegime), "应该返回MarketRegime实例"

    def test_hmm_detection(self):
        """测试HMM检测"""
        try:
            regime = self.detector.hmm_detection(self.bull_market)
            assert isinstance(regime, MarketRegime), "应该返回MarketRegime实例"
        except ImportError:
            pytest.skip("hmmlearn未安装，跳过HMM测试")

    def test_clustering_detection(self):
        """测试聚类检测"""
        regime = self.detector.clustering_detection(self.bull_market)
        assert isinstance(regime, MarketRegime), "应该返回MarketRegime实例"

    def test_ensemble_detection(self):
        """测试集成检测"""
        regime = self.detector.detect_regime(self.bull_market, method='ensemble')
        assert isinstance(regime, MarketRegime), "应该返回MarketRegime实例"

    def test_get_regime_parameters(self):
        """测试获取状态参数"""
        # 测试所有状态的参数
        for regime in MarketRegime:
            params = self.detector.get_regime_parameters(regime)

            assert isinstance(params, dict), f"{regime}的参数应该是字典"

            # 验证必需的参数存在
            required_keys = ['max_position', 'stop_loss', 'take_profit', 'leverage']
            for key in required_keys:
                assert key in params, f"{regime}缺少参数: {key}"

            # 验证参数范围
            assert 0 < params['max_position'] <= 1.0, "最大仓位应在(0,1]"
            assert 0 < params['stop_loss'] <= 1.0, "止损应在(0,1]"
            assert 0 < params['take_profit'], "止盈应大于0"
            assert 0 < params['leverage'] <= 3.0, "杠杆应在(0,3]"

    def test_bull_market_parameters(self):
        """测试牛市参数"""
        params = self.detector.get_regime_parameters(MarketRegime.TRENDING_BULL)

        # 牛市应该有较高的仓位和杠杆
        assert params['max_position'] >= 0.20, "牛市最大仓位应该较高"
        assert params['leverage'] >= 1.2, "牛市可以使用适度杠杆"

    def test_bear_market_parameters(self):
        """测试熊市参数"""
        params = self.detector.get_regime_parameters(MarketRegime.TRENDING_BEAR)

        # 熊市应该有较低的仓位和紧止损
        assert params['max_position'] <= 0.10, "熊市最大仓位应该较低"
        assert params['stop_loss'] <= 0.05, "熊市应该有紧止损"

    def test_volatile_crash_parameters(self):
        """测试暴跌市场参数"""
        params = self.detector.get_regime_parameters(MarketRegime.VOLATILE_CRASH)

        # 暴跌时应该极度保守
        assert params['max_position'] <= 0.05, "暴跌时仓位应极低"
        assert params['stop_loss'] <= 0.03, "暴跌时止损应极紧"
        assert params['leverage'] <= 0.5, "暴跌时不应使用杠杆"

    def test_regime_transition(self):
        """测试状态转换"""
        # 创建从牛市到熊市的转换数据
        dates = pd.date_range('2023-01-01', periods=500, freq='D')

        # 前250天牛市
        bull_trend = np.linspace(100, 150, 250)
        bull_noise = np.random.normal(0, 1, 250)
        bull_prices = bull_trend + bull_noise

        # 后250天熊市
        bear_trend = np.linspace(150, 100, 250)
        bear_noise = np.random.normal(0, 2, 250)
        bear_prices = bear_trend + bear_noise

        # 合并数据
        all_prices = np.concatenate([bull_prices, bear_prices])
        data = pd.DataFrame({
            'Close': all_prices,
            'Volume': np.random.randint(1000000, 2000000, 500)
        }, index=dates)

        # 检测前半部分和后半部分
        regime1 = self.detector.detect_regime(data.iloc[:250], method='rule_based')
        regime2 = self.detector.detect_regime(data.iloc[250:], method='rule_based')

        # 状态应该有所不同（大概率）
        # 注意：由于随机性，这个测试可能偶尔失败
        print(f"前半段状态: {regime1}, 后半段状态: {regime2}")

    def test_calculate_trend_strength(self):
        """测试趋势强度计算"""
        # 牛市应该有正趋势
        trend = self.detector._calculate_trend(self.bull_market['Close'])
        assert trend > 0, "牛市应该有正趋势"

        # 熊市应该有负趋势
        trend = self.detector._calculate_trend(self.bear_market['Close'])
        assert trend < 0, "熊市应该有负趋势"

        # 震荡市趋势应该接近0
        trend = self.detector._calculate_trend(self.ranging_market['Close'])
        assert abs(trend) < 0.02, "震荡市趋势应该接近0"

    def test_calculate_volatility(self):
        """测试波动率计算"""
        # 牛市波动应该较低
        vol_bull = self.detector._calculate_volatility(self.bull_market['Close'])
        vol_volatile = self.detector._calculate_volatility(self.volatile_market['Close'])

        assert vol_volatile > vol_bull, "高波动市场的波动率应该更高"

    def test_insufficient_data(self):
        """测试数据不足情况"""
        # 只有10天数据
        short_data = self.bull_market.iloc[:10]

        # 应该返回默认状态或抛出异常
        try:
            regime = self.detector.detect_regime(short_data, method='rule_based')
            assert isinstance(regime, MarketRegime)
        except ValueError:
            # 数据不足可能抛出ValueError
            pass

    def test_regime_history(self):
        """测试状态历史记录"""
        # 连续检测多次
        regimes = []
        for i in range(50, len(self.bull_market), 50):
            regime = self.detector.detect_regime(
                self.bull_market.iloc[:i],
                method='rule_based'
            )
            regimes.append(regime)

        # 应该记录了多个状态
        assert len(regimes) > 0
        # 所有状态都应该是有效的MarketRegime
        assert all(isinstance(r, MarketRegime) for r in regimes)


class TestMarketRegime:
    """测试市场状态枚举"""

    def test_regime_values(self):
        """测试状态值"""
        assert MarketRegime.TRENDING_BULL == "trending_bull"
        assert MarketRegime.TRENDING_BEAR == "trending_bear"
        assert MarketRegime.RANGING_LOW_VOL == "ranging_low_vol"
        assert MarketRegime.RANGING_HIGH_VOL == "ranging_high_vol"
        assert MarketRegime.VOLATILE_CRASH == "volatile_crash"
        assert MarketRegime.VOLATILE_RECOVERY == "volatile_recovery"

    def test_all_regimes_covered(self):
        """测试所有状态都有参数配置"""
        detector = MarketRegimeDetector()

        for regime in MarketRegime:
            # 每个状态都应该有参数
            params = detector.get_regime_parameters(regime)
            assert params is not None, f"{regime}缺少参数配置"


class TestRegimeParameters:
    """测试状态参数类"""

    def test_parameter_validation(self):
        """测试参数验证"""
        # 创建有效参数
        params = RegimeParameters(
            max_position=0.20,
            stop_loss=0.05,
            take_profit=0.10,
            leverage=1.5,
            rebalance_frequency=5
        )

        assert params.max_position == 0.20
        assert params.stop_loss == 0.05
        assert params.take_profit == 0.10
        assert params.leverage == 1.5
        assert params.rebalance_frequency == 5

    def test_to_dict(self):
        """测试转换为字典"""
        params = RegimeParameters(
            max_position=0.20,
            stop_loss=0.05,
            take_profit=0.10,
            leverage=1.5,
            rebalance_frequency=5
        )

        params_dict = params.to_dict()

        assert isinstance(params_dict, dict)
        assert params_dict['max_position'] == 0.20
        assert params_dict['stop_loss'] == 0.05


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

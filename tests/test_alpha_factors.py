"""
测试Alpha因子库
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.alpha_factors import AlphaFactorLibrary, FactorCategory


class TestAlphaFactorLibrary:
    """测试Alpha因子库"""

    def setup_method(self):
        """每个测试前的设置"""
        self.library = AlphaFactorLibrary()

        # 创建测试数据
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=300, freq="D")

        # 生成价格数据（带趋势）
        trend = np.linspace(100, 150, 300)
        noise = np.random.normal(0, 2, 300)
        self.prices = pd.Series(trend + noise, index=dates)

        # 生成成交量数据
        self.volume = pd.Series(
            np.random.randint(1000000, 10000000, 300),
            index=dates
        )

        # 生成完整的OHLCV数据
        self.ohlcv = pd.DataFrame({
            "Open": self.prices * 0.98,
            "High": self.prices * 1.02,
            "Low": self.prices * 0.97,
            "Close": self.prices,
            "Volume": self.volume
        }, index=dates)

    def test_momentum_factors(self):
        """测试动量因子"""
        # 测试12月动量
        mom_12m = self.library.momentum_12m(self.prices)
        assert len(mom_12m) == len(self.prices), "因子长度应与价格序列相同"
        assert not np.all(np.isnan(mom_12m)), "因子不应全为NaN"

        # 测试6月动量
        mom_6m = self.library.momentum_6m(self.prices)
        assert len(mom_6m) == len(self.prices)

        # 测试1月动量
        mom_1m = self.library.momentum_1m(self.prices)
        assert len(mom_1m) == len(self.prices)

    def test_reversal_factors(self):
        """测试反转因子"""
        # 测试短期反转
        reversal_5d = self.library.reversal_5d(self.prices)
        assert len(reversal_5d) == len(self.prices)

        # 反转因子应该是动量的负值
        mom_5d = self.prices.pct_change(5)
        expected_reversal = -mom_5d
        np.testing.assert_array_almost_equal(
            reversal_5d[5:],
            expected_reversal[5:],
            decimal=6
        )

    def test_value_factors(self):
        """测试价值因子"""
        # 创建基本面数据
        fundamentals = {
            "market_cap": 1000000000,  # 10亿市值
            "book_value": 500000000,   # 5亿账面价值
            "earnings": 100000000,     # 1亿盈利
            "revenue": 1000000000,     # 10亿收入
            "cash_flow": 150000000     # 1.5亿现金流
        }

        # 测试BP因子
        bp = self.library.book_to_price(fundamentals)
        assert bp > 0, "BP因子应该大于0"
        expected_bp = fundamentals["book_value"] / fundamentals["market_cap"]
        assert abs(bp - expected_bp) < 1e-6

        # 测试EP因子
        ep = self.library.earnings_to_price(fundamentals)
        assert ep > 0, "EP因子应该大于0"

    def test_quality_factors(self):
        """测试质量因子"""
        fundamentals = {
            "roa": 0.15,           # 15% ROA
            "delta_roa": 0.02,     # ROA增长
            "cash_flow": 100,      # 正现金流
            "delta_leverage": -0.01,  # 降低杠杆
            "delta_liquidity": 0.05,  # 提高流动性
            "delta_margin": 0.01,  # 提高毛利率
            "delta_turnover": 0.02,  # 提高周转率
            "accruals": 10,
            "revenue": 1000
        }

        # 测试Piotroski F-Score
        f_score = self.library.piotroski_f_score(fundamentals)
        assert 0 <= f_score <= 9, "F-Score应该在0-9之间"
        assert isinstance(f_score, (int, np.integer)), "F-Score应该是整数"

        # 测试ROA
        roa = self.library.roa(fundamentals)
        assert roa == fundamentals["roa"]

    def test_volatility_factors(self):
        """测试波动率因子"""
        # 测试历史波动率
        vol_60d = self.library.volatility_60d(self.prices)
        assert len(vol_60d) == len(self.prices)
        assert np.all(vol_60d[60:] >= 0), "波动率应该非负"

        # 测试ATR
        atr = self.library.atr_14d(self.ohlcv)
        assert len(atr) == len(self.ohlcv)
        assert np.all(atr[14:] >= 0), "ATR应该非负"

    def test_liquidity_factors(self):
        """测试流动性因子"""
        # 测试成交量
        volume_factor = self.library.volume_20d(self.volume)
        assert len(volume_factor) == len(self.volume)

        # 测试换手率
        market_cap = 1000000000  # 10亿市值
        turnover = self.library.turnover_20d(self.volume, self.prices, market_cap)
        assert len(turnover) == len(self.volume)
        assert np.all(turnover[20:] >= 0), "换手率应该非负"

    def test_technical_indicators(self):
        """测试技术指标"""
        # 测试RSI
        rsi = self.library.rsi_14d(self.prices)
        assert len(rsi) == len(self.prices)
        # RSI应该在0-100之间
        valid_rsi = rsi[~np.isnan(rsi)]
        assert np.all((valid_rsi >= 0) & (valid_rsi <= 100)), "RSI应该在0-100之间"

        # 测试MACD
        macd, signal = self.library.macd(self.prices)
        assert len(macd) == len(self.prices)
        assert len(signal) == len(self.prices)

    def test_compute_all_factors(self):
        """测试计算所有因子"""
        # 准备完整数据
        data = {
            "AAPL": {
                "prices": self.prices,
                "ohlcv": self.ohlcv,
                "volume": self.volume,
                "fundamentals": {
                    "market_cap": 1000000000,
                    "book_value": 500000000,
                    "earnings": 100000000,
                    "revenue": 1000000000,
                    "cash_flow": 150000000,
                    "roa": 0.15,
                    "delta_roa": 0.02,
                    "delta_leverage": -0.01,
                    "delta_liquidity": 0.05,
                    "delta_margin": 0.01,
                    "delta_turnover": 0.02,
                    "accruals": 10
                }
            }
        }

        # 计算所有因子
        all_factors = self.library.compute_all_factors(data)

        # 验证返回结果
        assert "AAPL" in all_factors, "应该包含AAPL的因子"
        assert isinstance(all_factors["AAPL"], pd.DataFrame), "因子应该是DataFrame"

        # 验证因子数量
        factor_df = all_factors["AAPL"]
        assert len(factor_df.columns) > 10, "应该计算多个因子"

        # 验证没有全为NaN的列
        for col in factor_df.columns:
            assert not factor_df[col].isna().all(), f"因子 {col} 不应全为NaN"

    def test_factor_categories(self):
        """测试因子分类"""
        # 验证因子分类枚举
        assert FactorCategory.MOMENTUM == "momentum"
        assert FactorCategory.REVERSAL == "reversal"
        assert FactorCategory.VALUE == "value"
        assert FactorCategory.QUALITY == "quality"
        assert FactorCategory.VOLATILITY == "volatility"
        assert FactorCategory.LIQUIDITY == "liquidity"

    def test_factor_normalization(self):
        """测试因子标准化"""
        # 计算一个因子
        factor = self.library.momentum_1m(self.prices)

        # 标准化
        normalized = self.library.normalize_factor(factor)

        # 验证标准化结果
        valid_values = normalized[~np.isnan(normalized)]
        if len(valid_values) > 0:
            mean = valid_values.mean()
            std = valid_values.std()
            assert abs(mean) < 0.1, "标准化后均值应接近0"
            assert abs(std - 1.0) < 0.1, "标准化后标准差应接近1"

    def test_factor_ranking(self):
        """测试因子排名"""
        # 创建多只股票的因子数据
        factor_data = pd.Series({
            "AAPL": 0.15,
            "MSFT": 0.08,
            "GOOGL": 0.20,
            "AMZN": -0.05,
            "TSLA": 0.12
        })

        # 排名（降序）
        ranks = self.library.rank_by_factor(factor_data, ascending=False)

        # 验证排名
        assert ranks["GOOGL"] == 1, "GOOGL应该排第一"
        assert ranks["AMZN"] == 5, "AMZN应该排最后"

    def test_composite_factor(self):
        """测试复合因子"""
        # 创建多个因子
        factors = {
            "momentum": pd.Series([0.1, 0.2, -0.1]),
            "value": pd.Series([0.05, -0.05, 0.15]),
            "quality": pd.Series([0.2, 0.1, 0.0])
        }

        # 等权重复合
        composite = self.library.create_composite_factor(
            factors,
            weights={"momentum": 1/3, "value": 1/3, "quality": 1/3}
        )

        # 验证复合因子
        assert len(composite) == 3
        expected_0 = (0.1 + 0.05 + 0.2) / 3
        assert abs(composite.iloc[0] - expected_0) < 1e-6


class TestEdgeCases:
    """测试边界情况"""

    def test_insufficient_data(self):
        """测试数据不足的情况"""
        library = AlphaFactorLibrary()

        # 只有10天数据
        short_prices = pd.Series([100, 101, 102, 103, 104, 105, 106, 107, 108, 109])

        # 计算需要252天的因子
        mom_12m = library.momentum_12m(short_prices)

        # 应该返回相同长度，但大部分是NaN
        assert len(mom_12m) == len(short_prices)
        assert np.isnan(mom_12m).sum() > len(short_prices) - 20

    def test_missing_values(self):
        """测试缺失值处理"""
        library = AlphaFactorLibrary()

        # 含有缺失值的价格序列
        prices_with_nan = pd.Series([100, 101, np.nan, 103, 104, np.nan, 106])

        # 计算因子
        mom = library.momentum_1m(prices_with_nan)

        # 应该正确处理NaN
        assert len(mom) == len(prices_with_nan)

    def test_zero_division(self):
        """测试除零情况"""
        library = AlphaFactorLibrary()

        # 创建市值为0的情况
        fundamentals = {
            "market_cap": 0,
            "book_value": 500000000
        }

        # BP因子应该返回0或inf
        bp = library.book_to_price(fundamentals)
        assert bp == 0 or np.isinf(bp), "市值为0时BP因子应为0或inf"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

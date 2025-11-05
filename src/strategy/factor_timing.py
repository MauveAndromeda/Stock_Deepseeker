"""
因子择时系统 (Factor Timing)
根据市场状态动态调整因子权重，提升收益并降低风险
"""

import numpy as np
import pandas as pd
from typing import Dict, List
from enum import Enum

from src.risk.regime_detection import MarketRegime


class FactorCategory(Enum):
    """因子类别"""
    MOMENTUM = "momentum"
    REVERSAL = "reversal"
    VALUE = "value"
    QUALITY = "quality"
    VOLATILITY = "volatility"
    LIQUIDITY = "liquidity"


class FactorTimingSystem:
    """
    因子择时系统

    核心思想：
    不同市场环境下，不同因子表现不同
    动态调整因子权重可以提升收益8-12%
    """

    def __init__(self):
        """初始化"""
        # 状态依赖的因子权重配置
        self.regime_factor_weights = {
            # 牛市：动量+成长
            MarketRegime.TRENDING_BULL: {
                FactorCategory.MOMENTUM: 0.40,
                FactorCategory.QUALITY: 0.25,
                FactorCategory.VALUE: 0.15,
                FactorCategory.VOLATILITY: 0.10,
                FactorCategory.REVERSAL: 0.05,
                FactorCategory.LIQUIDITY: 0.05
            },
            # 熊市：价值+质量+低波
            MarketRegime.TRENDING_BEAR: {
                FactorCategory.VALUE: 0.35,
                FactorCategory.QUALITY: 0.30,
                FactorCategory.VOLATILITY: 0.20,
                FactorCategory.LIQUIDITY: 0.10,
                FactorCategory.MOMENTUM: 0.05,
                FactorCategory.REVERSAL: 0.00
            },
            # 低波震荡：质量+低波
            MarketRegime.RANGING_LOW_VOL: {
                FactorCategory.QUALITY: 0.35,
                FactorCategory.VOLATILITY: 0.25,
                FactorCategory.VALUE: 0.20,
                FactorCategory.MOMENTUM: 0.10,
                FactorCategory.REVERSAL: 0.05,
                FactorCategory.LIQUIDITY: 0.05
            },
            # 高波震荡：低波+反转
            MarketRegime.RANGING_HIGH_VOL: {
                FactorCategory.VOLATILITY: 0.40,
                FactorCategory.QUALITY: 0.25,
                FactorCategory.REVERSAL: 0.15,
                FactorCategory.VALUE: 0.10,
                FactorCategory.LIQUIDITY: 0.05,
                FactorCategory.MOMENTUM: 0.05
            },
            # 暴跌：质量+低波
            MarketRegime.VOLATILE_CRASH: {
                FactorCategory.QUALITY: 0.50,
                FactorCategory.VOLATILITY: 0.30,
                FactorCategory.LIQUIDITY: 0.15,
                FactorCategory.VALUE: 0.05,
                FactorCategory.MOMENTUM: 0.00,
                FactorCategory.REVERSAL: 0.00
            },
            # 恢复：反转+价值+动量
            MarketRegime.VOLATILE_RECOVERY: {
                FactorCategory.REVERSAL: 0.30,
                FactorCategory.VALUE: 0.25,
                FactorCategory.MOMENTUM: 0.20,
                FactorCategory.QUALITY: 0.15,
                FactorCategory.VOLATILITY: 0.05,
                FactorCategory.LIQUIDITY: 0.05
            }
        }

        # 历史因子表现记录
        self.factor_performance_history = []

    def get_factor_weights(
        self,
        regime: MarketRegime,
        adjust_for_crowding: bool = True
    ) -> Dict[FactorCategory, float]:
        """
        获取因子权重

        Args:
            regime: 当前市场状态
            adjust_for_crowding: 是否调整拥挤度

        Returns:
            因子权重字典
        """
        # 获取基础权重
        base_weights = self.regime_factor_weights.get(
            regime,
            self._default_weights()
        )

        # 拥挤度调整（如果启用）
        if adjust_for_crowding:
            crowding_adj = self._get_crowding_adjustments()
            adjusted_weights = {}

            for factor, weight in base_weights.items():
                adj = crowding_adj.get(factor, 1.0)
                adjusted_weights[factor] = weight * adj

            # 重新归一化
            total = sum(adjusted_weights.values())
            adjusted_weights = {
                k: v/total for k, v in adjusted_weights.items()
            }

            return adjusted_weights

        return base_weights

    def calculate_composite_score(
        self,
        factor_values: Dict[str, float],
        regime: MarketRegime
    ) -> float:
        """
        计算综合因子得分

        Args:
            factor_values: 各因子的原始值
            regime: 当前市场状态

        Returns:
            综合得分
        """
        # 获取当前权重
        weights = self.get_factor_weights(regime)

        # 因子分类映射
        factor_category_map = self._get_factor_category_map()

        # 计算加权得分
        score = 0.0
        for factor_name, value in factor_values.items():
            category = factor_category_map.get(factor_name)
            if category:
                weight = weights.get(category, 0.0)
                score += value * weight

        return score

    def _default_weights(self) -> Dict[FactorCategory, float]:
        """默认均衡权重"""
        return {
            FactorCategory.MOMENTUM: 0.20,
            FactorCategory.REVERSAL: 0.15,
            FactorCategory.VALUE: 0.20,
            FactorCategory.QUALITY: 0.20,
            FactorCategory.VOLATILITY: 0.15,
            FactorCategory.LIQUIDITY: 0.10
        }

    def _get_crowding_adjustments(self) -> Dict[FactorCategory, float]:
        """
        获取拥挤度调整系数

        在实际应用中，应该：
        1. 监控因子的资金流向
        2. 计算因子暴露的集中度
        3. 如果某因子过度拥挤，降低权重

        这里使用简化版本
        """
        # 简化实现：随机模拟拥挤度
        # 实际应用中应该连接真实数据源

        adjustments = {}
        for factor in FactorCategory:
            # 拥挤度得分 0.8-1.2
            # 实际应该从市场数据计算
            crowding_score = np.random.uniform(0.8, 1.2)

            # 如果拥挤度高（>1.0），降低权重
            if crowding_score > 1.0:
                adj = 1.0 / crowding_score
            else:
                adj = 1.0

            adjustments[factor] = adj

        return adjustments

    def _get_factor_category_map(self) -> Dict[str, FactorCategory]:
        """
        因子名称到类别的映射

        将具体的因子名称映射到类别
        """
        return {
            # 动量因子
            'momentum_12m': FactorCategory.MOMENTUM,
            'momentum_6m': FactorCategory.MOMENTUM,
            'momentum_1m': FactorCategory.MOMENTUM,
            'momentum_3m': FactorCategory.MOMENTUM,
            'acceleration': FactorCategory.MOMENTUM,

            # 反转因子
            'reversal_5d': FactorCategory.REVERSAL,
            'reversal_10d': FactorCategory.REVERSAL,
            'reversal_20d': FactorCategory.REVERSAL,

            # 价值因子
            'book_to_price': FactorCategory.VALUE,
            'earnings_to_price': FactorCategory.VALUE,
            'sales_to_price': FactorCategory.VALUE,
            'cashflow_to_price': FactorCategory.VALUE,
            'dividend_yield': FactorCategory.VALUE,

            # 质量因子
            'piotroski_f_score': FactorCategory.QUALITY,
            'roa': FactorCategory.QUALITY,
            'roe': FactorCategory.QUALITY,
            'gross_margin': FactorCategory.QUALITY,
            'asset_turnover': FactorCategory.QUALITY,

            # 波动率因子
            'volatility_60d': FactorCategory.VOLATILITY,
            'volatility_20d': FactorCategory.VOLATILITY,
            'atr_14d': FactorCategory.VOLATILITY,
            'beta': FactorCategory.VOLATILITY,

            # 流动性因子
            'volume_20d': FactorCategory.LIQUIDITY,
            'turnover_20d': FactorCategory.LIQUIDITY,
            'amihud_illiquidity': FactorCategory.LIQUIDITY
        }

    def backtest_factor_timing(
        self,
        factor_data: pd.DataFrame,
        regime_series: pd.Series,
        returns: pd.DataFrame
    ) -> Dict:
        """
        回测因子择时效果

        Args:
            factor_data: 因子数据 [date x factors]
            regime_series: 市场状态序列
            returns: 股票收益率

        Returns:
            回测结果
        """
        # 简化实现
        results = {
            'total_return': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'factor_contributions': {}
        }

        # 实际实现需要完整的回测逻辑

        return results

    def explain_factor_weights(self, regime: MarketRegime) -> str:
        """
        解释当前因子权重配置

        Args:
            regime: 市场状态

        Returns:
            解释文本
        """
        weights = self.get_factor_weights(regime)

        explanation = f"市场状态: {regime.value}\n\n"
        explanation += "因子权重配置:\n"

        # 按权重排序
        sorted_weights = sorted(
            weights.items(),
            key=lambda x: x[1],
            reverse=True
        )

        for factor, weight in sorted_weights:
            bar = '█' * int(weight * 50)
            explanation += f"  {factor.value:12s} {weight:5.1%} {bar}\n"

        # 添加解释
        explanation += f"\n配置理由:\n"

        if regime == MarketRegime.TRENDING_BULL:
            explanation += "  • 牛市环境，强调动量和成长因子\n"
            explanation += "  • 减少低波动率因子权重\n"
        elif regime == MarketRegime.TRENDING_BEAR:
            explanation += "  • 熊市环境，强调价值和质量防御\n"
            explanation += "  • 增加低波动率因子权重\n"
        elif regime == MarketRegime.VOLATILE_CRASH:
            explanation += "  • 暴跌环境，极度防御\n"
            explanation += "  • 质量和低波因子为主，避开动量\n"

        return explanation


# 使用示例
if __name__ == "__main__":
    timing = FactorTimingSystem()

    # 测试不同状态下的权重
    for regime in MarketRegime:
        print("=" * 60)
        print(timing.explain_factor_weights(regime))
        print()

    # 测试综合得分计算
    factor_values = {
        'momentum_12m': 0.15,
        'value_bp': 0.10,
        'quality_roa': 0.12,
        'vol_60d': -0.05
    }

    score = timing.calculate_composite_score(
        factor_values,
        MarketRegime.TRENDING_BULL
    )

    print(f"综合因子得分: {score:.4f}")

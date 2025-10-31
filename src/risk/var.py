"""
VaR (Value at Risk) 计算
包括历史模拟法、方差-协方差法、蒙特卡洛模拟法
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from scipy import stats
from dataclasses import dataclass
from enum import Enum


class VaRMethod(Enum):
    """VaR计算方法"""
    HISTORICAL = "historical"  # 历史模拟法
    PARAMETRIC = "parametric"  # 方差-协方差法
    MONTE_CARLO = "monte_carlo"  # 蒙特卡洛模拟


@dataclass
class VaRResult:
    """VaR计算结果"""
    var_value: float  # VaR值
    confidence_level: float  # 置信水平
    time_horizon: int  # 时间跨度（天）
    method: VaRMethod  # 计算方法
    percentile: float  # 分位数
    worst_loss: float  # 最大损失
    expected_shortfall: Optional[float] = None  # 期望损失（CVaR/ES）
    metadata: Dict = None


class VaRCalculator:
    """VaR计算器"""

    def __init__(
        self,
        confidence_level: float = 0.95,
        time_horizon: int = 1,
        lookback_period: int = 252
    ):
        """
        初始化VaR计算器

        Args:
            confidence_level: 置信水平（如0.95表示95%）
            time_horizon: 时间跨度（天）
            lookback_period: 回溯期（天）
        """
        self.confidence_level = confidence_level
        self.time_horizon = time_horizon
        self.lookback_period = lookback_period

    def calculate_var(
        self,
        returns: np.ndarray,
        portfolio_value: float,
        method: VaRMethod = VaRMethod.HISTORICAL
    ) -> VaRResult:
        """
        计算VaR

        Args:
            returns: 收益率序列
            portfolio_value: 投资组合价值
            method: 计算方法

        Returns:
            VaR计算结果
        """
        if method == VaRMethod.HISTORICAL:
            return self._historical_var(returns, portfolio_value)
        elif method == VaRMethod.PARAMETRIC:
            return self._parametric_var(returns, portfolio_value)
        elif method == VaRMethod.MONTE_CARLO:
            return self._monte_carlo_var(returns, portfolio_value)
        else:
            raise ValueError(f"Unknown VaR method: {method}")

    def _historical_var(
        self,
        returns: np.ndarray,
        portfolio_value: float
    ) -> VaRResult:
        """历史模拟法计算VaR"""

        # 使用最近的历史数据
        recent_returns = returns[-self.lookback_period:]

        # 调整时间跨度
        if self.time_horizon > 1:
            # 简化假设：sqrt(time) scaling
            scaled_returns = recent_returns * np.sqrt(self.time_horizon)
        else:
            scaled_returns = recent_returns

        # 计算分位数
        percentile = (1 - self.confidence_level) * 100
        var_percentile = np.percentile(scaled_returns, percentile)

        # VaR值（负的损失）
        var_value = -var_percentile * portfolio_value

        # 最大损失
        worst_loss = -np.min(scaled_returns) * portfolio_value

        return VaRResult(
            var_value=var_value,
            confidence_level=self.confidence_level,
            time_horizon=self.time_horizon,
            method=VaRMethod.HISTORICAL,
            percentile=percentile,
            worst_loss=worst_loss
        )

    def _parametric_var(
        self,
        returns: np.ndarray,
        portfolio_value: float
    ) -> VaRResult:
        """方差-协方差法（参数法）计算VaR"""

        # 使用最近的历史数据
        recent_returns = returns[-self.lookback_period:]

        # 计算均值和标准差
        mean_return = np.mean(recent_returns)
        std_return = np.std(recent_returns)

        # Z-score（标准正态分位数）
        z_score = stats.norm.ppf(1 - self.confidence_level)

        # 调整时间跨度
        if self.time_horizon > 1:
            mean_return = mean_return * self.time_horizon
            std_return = std_return * np.sqrt(self.time_horizon)

        # VaR = -(μ + z * σ) * 投资组合价值
        var_return = -(mean_return + z_score * std_return)
        var_value = var_return * portfolio_value

        # 估计最大损失（3倍标准差）
        worst_loss = (mean_return - 3 * std_return) * portfolio_value

        return VaRResult(
            var_value=var_value,
            confidence_level=self.confidence_level,
            time_horizon=self.time_horizon,
            method=VaRMethod.PARAMETRIC,
            percentile=(1 - self.confidence_level) * 100,
            worst_loss=abs(worst_loss),
            metadata={
                'mean_return': mean_return,
                'std_return': std_return,
                'z_score': z_score
            }
        )

    def _monte_carlo_var(
        self,
        returns: np.ndarray,
        portfolio_value: float,
        num_simulations: int = 10000
    ) -> VaRResult:
        """蒙特卡洛模拟法计算VaR"""

        # 使用最近的历史数据估计参数
        recent_returns = returns[-self.lookback_period:]

        mean_return = np.mean(recent_returns)
        std_return = np.std(recent_returns)

        # 蒙特卡洛模拟
        simulated_returns = np.random.normal(
            loc=mean_return * self.time_horizon,
            scale=std_return * np.sqrt(self.time_horizon),
            size=num_simulations
        )

        # 计算VaR
        percentile = (1 - self.confidence_level) * 100
        var_percentile = np.percentile(simulated_returns, percentile)
        var_value = -var_percentile * portfolio_value

        # 最大损失
        worst_loss = -np.min(simulated_returns) * portfolio_value

        return VaRResult(
            var_value=var_value,
            confidence_level=self.confidence_level,
            time_horizon=self.time_horizon,
            method=VaRMethod.MONTE_CARLO,
            percentile=percentile,
            worst_loss=worst_loss,
            metadata={
                'num_simulations': num_simulations,
                'mean_return': mean_return,
                'std_return': std_return
            }
        )

    def calculate_portfolio_var(
        self,
        returns_matrix: np.ndarray,
        weights: np.ndarray,
        portfolio_value: float,
        method: VaRMethod = VaRMethod.PARAMETRIC
    ) -> VaRResult:
        """
        计算投资组合VaR（考虑相关性）

        Args:
            returns_matrix: 收益率矩阵 (T x N)，T是时间，N是资产数量
            weights: 权重向量 (N,)
            portfolio_value: 投资组合价值
            method: 计算方法

        Returns:
            VaR计算结果
        """
        # 计算投资组合收益率
        portfolio_returns = returns_matrix @ weights

        # 计算VaR
        return self.calculate_var(portfolio_returns, portfolio_value, method)

    def calculate_component_var(
        self,
        returns_matrix: np.ndarray,
        weights: np.ndarray,
        portfolio_value: float
    ) -> Dict[str, float]:
        """
        计算成分VaR（Component VaR）

        Args:
            returns_matrix: 收益率矩阵
            weights: 权重向量
            portfolio_value: 投资组合价值

        Returns:
            各成分的VaR贡献
        """
        n_assets = returns_matrix.shape[1]

        # 计算协方差矩阵
        cov_matrix = np.cov(returns_matrix, rowvar=False)

        # 投资组合方差
        portfolio_variance = weights.T @ cov_matrix @ weights

        # 投资组合标准差
        portfolio_std = np.sqrt(portfolio_variance)

        # 边际VaR
        z_score = stats.norm.ppf(1 - self.confidence_level)
        marginal_var = z_score * (cov_matrix @ weights) / portfolio_std

        # 成分VaR
        component_var = weights * marginal_var * portfolio_value

        return {
            f"asset_{i}": float(component_var[i])
            for i in range(n_assets)
        }


class ExpectedShortfall:
    """期望损失（Expected Shortfall / CVaR）计算器"""

    def __init__(
        self,
        confidence_level: float = 0.95,
        time_horizon: int = 1
    ):
        """
        初始化ES计算器

        Args:
            confidence_level: 置信水平
            time_horizon: 时间跨度（天）
        """
        self.confidence_level = confidence_level
        self.time_horizon = time_horizon

    def calculate_es(
        self,
        returns: np.ndarray,
        portfolio_value: float,
        method: str = "historical"
    ) -> float:
        """
        计算期望损失

        Args:
            returns: 收益率序列
            portfolio_value: 投资组合价值
            method: 计算方法（historical或parametric）

        Returns:
            期望损失值
        """
        if method == "historical":
            return self._historical_es(returns, portfolio_value)
        elif method == "parametric":
            return self._parametric_es(returns, portfolio_value)
        else:
            raise ValueError(f"Unknown ES method: {method}")

    def _historical_es(
        self,
        returns: np.ndarray,
        portfolio_value: float
    ) -> float:
        """历史模拟法计算ES"""

        # 调整时间跨度
        if self.time_horizon > 1:
            scaled_returns = returns * np.sqrt(self.time_horizon)
        else:
            scaled_returns = returns

        # VaR阈值
        percentile = (1 - self.confidence_level) * 100
        var_threshold = np.percentile(scaled_returns, percentile)

        # ES = 超过VaR的损失的平均值
        tail_losses = scaled_returns[scaled_returns <= var_threshold]

        if len(tail_losses) > 0:
            es_return = np.mean(tail_losses)
            es_value = -es_return * portfolio_value
        else:
            es_value = 0.0

        return es_value

    def _parametric_es(
        self,
        returns: np.ndarray,
        portfolio_value: float
    ) -> float:
        """参数法计算ES（假设正态分布）"""

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        # 调整时间跨度
        if self.time_horizon > 1:
            mean_return = mean_return * self.time_horizon
            std_return = std_return * np.sqrt(self.time_horizon)

        # 正态分布的ES公式
        z_score = stats.norm.ppf(1 - self.confidence_level)

        # ES = μ - σ * φ(z) / (1 - α)
        # 其中 φ 是标准正态PDF
        phi_z = stats.norm.pdf(z_score)
        es_return = -(mean_return - std_return * phi_z / (1 - self.confidence_level))

        es_value = es_return * portfolio_value

        return es_value


class MarginalVaR:
    """边际VaR计算器"""

    def __init__(
        self,
        confidence_level: float = 0.95,
        time_horizon: int = 1
    ):
        self.confidence_level = confidence_level
        self.time_horizon = time_horizon
        self.var_calculator = VaRCalculator(confidence_level, time_horizon)

    def calculate_marginal_var(
        self,
        returns_matrix: np.ndarray,
        weights: np.ndarray,
        portfolio_value: float,
        asset_index: int,
        delta: float = 0.01
    ) -> float:
        """
        计算边际VaR（单个资产权重变化对VaR的影响）

        Args:
            returns_matrix: 收益率矩阵
            weights: 当前权重
            portfolio_value: 投资组合价值
            asset_index: 资产索引
            delta: 权重变化量

        Returns:
            边际VaR
        """
        # 当前VaR
        current_var = self.var_calculator.calculate_portfolio_var(
            returns_matrix,
            weights,
            portfolio_value,
            VaRMethod.PARAMETRIC
        )

        # 调整权重
        new_weights = weights.copy()
        new_weights[asset_index] += delta

        # 重新归一化
        new_weights = new_weights / np.sum(new_weights)

        # 新VaR
        new_var = self.var_calculator.calculate_portfolio_var(
            returns_matrix,
            new_weights,
            portfolio_value,
            VaRMethod.PARAMETRIC
        )

        # 边际VaR
        marginal_var = (new_var.var_value - current_var.var_value) / delta

        return marginal_var


class IncrementalVaR:
    """增量VaR计算器"""

    def __init__(
        self,
        confidence_level: float = 0.95,
        time_horizon: int = 1
    ):
        self.confidence_level = confidence_level
        self.time_horizon = time_horizon
        self.var_calculator = VaRCalculator(confidence_level, time_horizon)

    def calculate_incremental_var(
        self,
        returns_matrix: np.ndarray,
        weights: np.ndarray,
        portfolio_value: float,
        asset_index: int
    ) -> float:
        """
        计算增量VaR（移除某个资产对VaR的影响）

        Args:
            returns_matrix: 收益率矩阵
            weights: 当前权重
            portfolio_value: 投资组合价值
            asset_index: 要移除的资产索引

        Returns:
            增量VaR
        """
        # 当前VaR
        current_var = self.var_calculator.calculate_portfolio_var(
            returns_matrix,
            weights,
            portfolio_value,
            VaRMethod.PARAMETRIC
        )

        # 移除资产
        new_weights = weights.copy()
        new_weights[asset_index] = 0

        # 重新归一化
        if np.sum(new_weights) > 0:
            new_weights = new_weights / np.sum(new_weights)
        else:
            # 如果只有一个资产，返回当前VaR
            return current_var.var_value

        # 新VaR
        new_var = self.var_calculator.calculate_portfolio_var(
            returns_matrix,
            new_weights,
            portfolio_value,
            VaRMethod.PARAMETRIC
        )

        # 增量VaR = 当前VaR - 移除后的VaR
        incremental_var = current_var.var_value - new_var.var_value

        return incremental_var

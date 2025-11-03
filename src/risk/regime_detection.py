"""
市场Regime检测器
用于识别不同的市场状态并动态调整策略
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from enum import Enum
from dataclasses import dataclass
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from hmmlearn import hmm


class MarketRegime(Enum):
    """市场regime类型"""
    TRENDING_BULL = "trending_bull"          # 牛市趋势
    TRENDING_BEAR = "trending_bear"          # 熊市趋势
    RANGING_LOW_VOL = "ranging_low_vol"      # 低波震荡
    RANGING_HIGH_VOL = "ranging_high_vol"    # 高波震荡
    VOLATILE_CRASH = "volatile_crash"        # 暴跌期
    VOLATILE_RECOVERY = "volatile_recovery"  # 反弹期


@dataclass
class RegimeState:
    """Regime状态"""
    regime: MarketRegime
    confidence: float  # 置信度 0-1
    duration: int  # 持续天数
    characteristics: Dict[str, float]  # 特征值
    timestamp: pd.Timestamp


class MarketRegimeDetector:
    """市场Regime检测器 - 多方法集成"""

    def __init__(self, lookback_period: int = 252):
        """
        初始化

        Args:
            lookback_period: 回溯期（天）
        """
        self.lookback_period = lookback_period
        self.scaler = StandardScaler()
        self.current_regime = None
        self.regime_history = []

    # ==================== 方法1: 规则基检测 ====================

    def rule_based_detection(self, market_data: pd.DataFrame) -> MarketRegime:
        """
        基于规则的regime检测

        Args:
            market_data: 包含 close, volume 等列的DataFrame

        Returns:
            检测到的regime
        """
        prices = market_data['close']
        returns = prices.pct_change()

        # 计算关键指标
        # 1. 趋势强度
        ma_20 = prices.rolling(20).mean()
        ma_50 = prices.rolling(50).mean()
        ma_200 = prices.rolling(200).mean()

        current_price = prices.iloc[-1]
        trend_strength = (current_price - ma_200.iloc[-1]) / ma_200.iloc[-1]

        # 2. 波动率
        realized_vol = returns.rolling(20).std() * np.sqrt(252)
        current_vol = realized_vol.iloc[-1]
        avg_vol = realized_vol.mean()

        # 3. 动量
        momentum_20 = (current_price - prices.iloc[-20]) / prices.iloc[-20]
        momentum_60 = (current_price - prices.iloc[-60]) / prices.iloc[-60]

        # 4. 最大回撤
        cummax = prices.cummax()
        drawdown = (prices - cummax) / cummax
        max_drawdown = drawdown.min()

        # 规则判断
        if trend_strength > 0.1 and momentum_60 > 0.15 and current_vol < avg_vol * 1.2:
            # 强势上涨 + 低波动
            regime = MarketRegime.TRENDING_BULL

        elif trend_strength < -0.1 and momentum_60 < -0.15:
            # 强势下跌
            if current_vol > avg_vol * 2.0:
                regime = MarketRegime.VOLATILE_CRASH
            else:
                regime = MarketRegime.TRENDING_BEAR

        elif abs(trend_strength) < 0.05 and abs(momentum_20) < 0.05:
            # 横盘震荡
            if current_vol > avg_vol * 1.5:
                regime = MarketRegime.RANGING_HIGH_VOL
            else:
                regime = MarketRegime.RANGING_LOW_VOL

        elif trend_strength > 0.05 and max_drawdown > -0.20:
            # 从底部反弹
            regime = MarketRegime.VOLATILE_RECOVERY

        else:
            # 默认：震荡市
            if current_vol > avg_vol * 1.2:
                regime = MarketRegime.RANGING_HIGH_VOL
            else:
                regime = MarketRegime.RANGING_LOW_VOL

        return regime

    # ==================== 方法2: 隐马尔可夫模型 ====================

    def hmm_detection(self, market_data: pd.DataFrame, n_states: int = 4) -> MarketRegime:
        """
        基于隐马尔可夫模型的regime检测

        Args:
            market_data: 市场数据
            n_states: 隐藏状态数量

        Returns:
            检测到的regime
        """
        # 准备特征
        features = self._prepare_features(market_data)

        # 训练HMM模型
        model = hmm.GaussianHMM(
            n_components=n_states,
            covariance_type="full",
            n_iter=100
        )

        try:
            model.fit(features)

            # 预测当前状态
            current_state = model.predict(features)[-1]

            # 根据状态特征映射到regime
            regime = self._map_hmm_state_to_regime(
                current_state,
                features,
                model
            )

            return regime

        except Exception as e:
            print(f"HMM detection failed: {e}")
            # 回退到规则检测
            return self.rule_based_detection(market_data)

    def _prepare_features(self, market_data: pd.DataFrame) -> np.ndarray:
        """准备HMM特征"""
        prices = market_data['close']
        returns = prices.pct_change()
        volumes = market_data.get('volume', pd.Series([1] * len(prices)))

        # 特征工程
        features = pd.DataFrame({
            # 收益率
            'returns': returns,

            # 波动率
            'volatility': returns.rolling(20).std(),

            # 趋势
            'ma_ratio': prices / prices.rolling(50).mean(),

            # 动量
            'momentum': returns.rolling(20).mean(),

            # 成交量
            'volume_ratio': volumes / volumes.rolling(20).mean(),

            # 偏度
            'skewness': returns.rolling(60).apply(lambda x: stats.skew(x)),

            # 最大回撤
            'drawdown': (prices - prices.cummax()) / prices.cummax(),
        })

        # 标准化
        features_clean = features.fillna(0).values
        features_scaled = self.scaler.fit_transform(features_clean)

        return features_scaled

    def _map_hmm_state_to_regime(self, state: int, features: np.ndarray,
                                 model: hmm.GaussianHMM) -> MarketRegime:
        """将HMM状态映射到regime"""
        # 获取状态的均值特征
        state_means = model.means_[state]

        returns_mean = state_means[0]
        volatility_mean = state_means[1]
        trend_mean = state_means[2]

        # 映射逻辑
        if returns_mean > 0.5 and volatility_mean < 0:
            return MarketRegime.TRENDING_BULL
        elif returns_mean < -0.5 and volatility_mean > 1:
            return MarketRegime.VOLATILE_CRASH
        elif returns_mean < -0.3:
            return MarketRegime.TRENDING_BEAR
        elif abs(returns_mean) < 0.2 and volatility_mean > 0.5:
            return MarketRegime.RANGING_HIGH_VOL
        elif abs(returns_mean) < 0.2 and volatility_mean < 0.5:
            return MarketRegime.RANGING_LOW_VOL
        else:
            return MarketRegime.VOLATILE_RECOVERY

    # ==================== 方法3: 聚类检测 ====================

    def clustering_detection(self, market_data: pd.DataFrame,
                            n_clusters: int = 6) -> MarketRegime:
        """
        基于聚类的regime检测

        Args:
            market_data: 市场数据
            n_clusters: 聚类数量

        Returns:
            检测到的regime
        """
        # 准备特征
        features = self._prepare_features(market_data)

        # K-means聚类
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(features)

        # 当前聚类
        current_cluster = clusters[-1]

        # 分析聚类特征
        cluster_mask = (clusters == current_cluster)
        cluster_features = features[cluster_mask]

        # 计算聚类中心特征
        cluster_mean = cluster_features.mean(axis=0)

        returns_mean = cluster_mean[0]
        volatility_mean = cluster_mean[1]
        trend_mean = cluster_mean[2]

        # 映射到regime
        if returns_mean > 0.3 and trend_mean > 0.3:
            return MarketRegime.TRENDING_BULL
        elif returns_mean < -0.3 and volatility_mean > 0.5:
            return MarketRegime.VOLATILE_CRASH
        elif returns_mean < -0.2:
            return MarketRegime.TRENDING_BEAR
        elif abs(returns_mean) < 0.1 and volatility_mean > 0.3:
            return MarketRegime.RANGING_HIGH_VOL
        elif abs(returns_mean) < 0.1:
            return MarketRegime.RANGING_LOW_VOL
        else:
            return MarketRegime.VOLATILE_RECOVERY

    # ==================== 集成方法 ====================

    def detect_regime(self, market_data: pd.DataFrame,
                     method: str = 'ensemble') -> RegimeState:
        """
        检测市场regime

        Args:
            market_data: 市场数据
            method: 检测方法 ('rule', 'hmm', 'clustering', 'ensemble')

        Returns:
            RegimeState对象
        """
        if method == 'rule':
            regime = self.rule_based_detection(market_data)
            confidence = 0.7

        elif method == 'hmm':
            regime = self.hmm_detection(market_data)
            confidence = 0.75

        elif method == 'clustering':
            regime = self.clustering_detection(market_data)
            confidence = 0.7

        elif method == 'ensemble':
            # 集成三种方法
            regimes = [
                self.rule_based_detection(market_data),
                self.hmm_detection(market_data),
                self.clustering_detection(market_data)
            ]

            # 投票
            from collections import Counter
            regime_counts = Counter(regimes)
            regime = regime_counts.most_common(1)[0][0]

            # 置信度 = 投票比例
            confidence = regime_counts[regime] / len(regimes)

        else:
            raise ValueError(f"Unknown method: {method}")

        # 计算持续时间
        duration = self._calculate_duration(regime)

        # 提取特征
        characteristics = self._extract_characteristics(market_data)

        # 创建状态对象
        state = RegimeState(
            regime=regime,
            confidence=confidence,
            duration=duration,
            characteristics=characteristics,
            timestamp=market_data.index[-1]
        )

        # 更新历史
        self.current_regime = regime
        self.regime_history.append(state)

        return state

    def _calculate_duration(self, regime: MarketRegime) -> int:
        """计算regime持续时间"""
        if not self.regime_history:
            return 1

        duration = 1
        for past_state in reversed(self.regime_history):
            if past_state.regime == regime:
                duration += 1
            else:
                break

        return duration

    def _extract_characteristics(self, market_data: pd.DataFrame) -> Dict[str, float]:
        """提取regime特征"""
        prices = market_data['close']
        returns = prices.pct_change()

        return {
            'volatility': returns.std() * np.sqrt(252),
            'trend': (prices.iloc[-1] - prices.iloc[-60]) / prices.iloc[-60] if len(prices) > 60 else 0,
            'momentum': returns.tail(20).mean(),
            'max_drawdown': ((prices - prices.cummax()) / prices.cummax()).min(),
            'skewness': stats.skew(returns.dropna()),
            'kurtosis': stats.kurtosis(returns.dropna())
        }

    # ==================== Regime特定策略参数 ====================

    def get_regime_parameters(self, regime: MarketRegime) -> Dict[str, float]:
        """
        获取regime特定的策略参数

        Args:
            regime: Market regime

        Returns:
            参数字典
        """
        params = {
            MarketRegime.TRENDING_BULL: {
                'max_position': 0.25,      # 高仓位
                'stop_loss': 0.08,         # 宽止损
                'take_profit': 0.20,       # 高止盈
                'leverage': 1.5,           # 适度杠杆
                'holding_period': 20,      # 长持仓
                'rebalance_threshold': 0.15,
            },

            MarketRegime.TRENDING_BEAR: {
                'max_position': 0.05,      # 极低仓位
                'stop_loss': 0.03,         # 紧止损
                'take_profit': 0.05,       # 低止盈
                'leverage': 0.3,           # 低杠杆
                'holding_period': 3,       # 短持仓
                'rebalance_threshold': 0.05,
            },

            MarketRegime.RANGING_LOW_VOL: {
                'max_position': 0.15,      # 中等仓位
                'stop_loss': 0.05,         # 中等止损
                'take_profit': 0.08,       # 中等止盈
                'leverage': 1.0,           # 无杠杆
                'holding_period': 10,      # 中等持仓
                'rebalance_threshold': 0.08,
            },

            MarketRegime.RANGING_HIGH_VOL: {
                'max_position': 0.08,      # 低仓位
                'stop_loss': 0.04,         # 紧止损
                'take_profit': 0.10,       # 中高止盈
                'leverage': 0.7,           # 低杠杆
                'holding_period': 5,       # 短持仓
                'rebalance_threshold': 0.10,
            },

            MarketRegime.VOLATILE_CRASH: {
                'max_position': 0.02,      # 极低仓位
                'stop_loss': 0.02,         # 极紧止损
                'take_profit': 0.03,       # 极低止盈
                'leverage': 0.2,           # 极低杠杆
                'holding_period': 1,       # 极短持仓
                'rebalance_threshold': 0.03,
            },

            MarketRegime.VOLATILE_RECOVERY: {
                'max_position': 0.18,      # 较高仓位
                'stop_loss': 0.06,         # 中等止损
                'take_profit': 0.15,       # 高止盈
                'leverage': 1.2,           # 适度杠杆
                'holding_period': 7,       # 较短持仓
                'rebalance_threshold': 0.12,
            },
        }

        return params.get(regime, params[MarketRegime.RANGING_LOW_VOL])

    def get_regime_statistics(self) -> pd.DataFrame:
        """获取regime统计信息"""
        if not self.regime_history:
            return pd.DataFrame()

        stats_list = []
        for state in self.regime_history:
            stats_list.append({
                'timestamp': state.timestamp,
                'regime': state.regime.value,
                'confidence': state.confidence,
                'duration': state.duration,
                **state.characteristics
            })

        return pd.DataFrame(stats_list)


# 使用示例
if __name__ == "__main__":
    # 创建检测器
    detector = MarketRegimeDetector()

    # 模拟市场数据
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', '2024-01-01', freq='D')
    n = len(dates)

    # 模拟不同regime的数据
    close_prices = []
    current_price = 100

    for i in range(n):
        # 模拟regime切换
        if i < 300:  # 牛市
            drift = 0.0005
            vol = 0.01
        elif i < 600:  # 震荡
            drift = 0
            vol = 0.015
        elif i < 800:  # 崩盘
            drift = -0.002
            vol = 0.03
        else:  # 恢复
            drift = 0.001
            vol = 0.02

        ret = drift + vol * np.random.randn()
        current_price *= (1 + ret)
        close_prices.append(current_price)

    market_data = pd.DataFrame({
        'close': close_prices,
        'volume': np.random.randint(1000000, 5000000, n)
    }, index=dates)

    # 检测regime
    print("检测市场regime...")
    state = detector.detect_regime(market_data, method='ensemble')

    print(f"\n当前Regime: {state.regime.value}")
    print(f"置信度: {state.confidence:.2%}")
    print(f"持续时间: {state.duration} 天")
    print(f"\n特征:")
    for key, value in state.characteristics.items():
        print(f"  {key}: {value:.4f}")

    # 获取策略参数
    params = detector.get_regime_parameters(state.regime)
    print(f"\n推荐策略参数:")
    for key, value in params.items():
        print(f"  {key}: {value}")

    # 获取历史统计
    stats = detector.get_regime_statistics()
    print(f"\nRegime统计:")
    print(stats.tail())

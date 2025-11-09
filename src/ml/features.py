"""
特征提取和选择
"""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif
from sklearn.preprocessing import MinMaxScaler, StandardScaler


class FeatureExtractor:
    """特征提取器"""

    def __init__(self):
        self.scalers: dict[str, Any] = {}

    def extract_price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """提取价格特征"""
        features = pd.DataFrame(index=df.index)

        # 收益率
        features["returns"] = df["close"].pct_change()
        features["log_returns"] = np.log(df["close"] / df["close"].shift(1))

        # 多周期收益率
        for period in [5, 10, 20, 60]:
            features[f"returns_{period}d"] = df["close"].pct_change(period)

        # 价格位置
        features["price_position"] = (df["close"] - df["low"]) / (df["high"] - df["low"])

        # 与移动平均的偏离
        for period in [20, 50, 200]:
            sma = df["close"].rolling(period).mean()
            features[f"distance_from_sma_{period}"] = (df["close"] - sma) / sma

        return features

    def extract_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """提取成交量特征"""
        features = pd.DataFrame(index=df.index)

        # 成交量变化
        features["volume_change"] = df["volume"].pct_change()

        # 成交量比率
        for period in [5, 20, 60]:
            avg_volume = df["volume"].rolling(period).mean()
            features[f"volume_ratio_{period}"] = df["volume"] / avg_volume

        # 价格成交量相关性
        features["price_volume_corr"] = df["close"].rolling(20).corr(df["volume"])

        return features

    def extract_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """提取波动率特征"""
        features = pd.DataFrame(index=df.index)

        # 历史波动率
        returns = df["close"].pct_change()
        for period in [5, 10, 20, 60]:
            features[f"volatility_{period}"] = returns.rolling(period).std() * np.sqrt(252)

        # Parkinson波动率
        features["parkinson_volatility"] = np.sqrt(
            1/(4*np.log(2)) * (np.log(df["high"]/df["low"]))**2
        )

        # 波动率变化
        vol_20 = returns.rolling(20).std()
        features["volatility_change"] = vol_20.pct_change()

        return features

    def extract_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """提取动量特征"""
        features = pd.DataFrame(index=df.index)

        # RSI
        for period in [14, 28]:
            delta = df["close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
            rs = gain / loss
            features[f"rsi_{period}"] = 100 - (100 / (1 + rs))

        # 动量
        for period in [10, 20, 60]:
            features[f"momentum_{period}"] = df["close"] - df["close"].shift(period)

        # ROC
        for period in [10, 20]:
            features[f"roc_{period}"] = ((df["close"] - df["close"].shift(period)) /
                                         df["close"].shift(period) * 100)

        return features

    def extract_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """提取所有特征"""
        all_features = []

        # 价格特征
        price_features = self.extract_price_features(df)
        all_features.append(price_features)

        # 成交量特征
        volume_features = self.extract_volume_features(df)
        all_features.append(volume_features)

        # 波动率特征
        volatility_features = self.extract_volatility_features(df)
        all_features.append(volatility_features)

        # 动量特征
        momentum_features = self.extract_momentum_features(df)
        all_features.append(momentum_features)

        # 合并所有特征
        features = pd.concat(all_features, axis=1)

        return features

    def normalize_features(
        self,
        features: pd.DataFrame,
        method: str = "standard"
    ) -> tuple[pd.DataFrame, Any]:
        """归一化特征"""
        if method == "standard":
            scaler = StandardScaler()
        elif method == "minmax":
            scaler = MinMaxScaler()
        else:
            raise ValueError(f"Unknown normalization method: {method}")

        normalized = pd.DataFrame(
            scaler.fit_transform(features),
            index=features.index,
            columns=features.columns
        )

        self.scalers[method] = scaler

        return normalized, scaler


class FeatureSelector:
    """特征选择器"""

    def __init__(self):
        self.selected_features: list[str] = []
        self.selector = None

    def select_k_best(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        k: int = 50,
        score_func: str = "f_classif"
    ) -> pd.DataFrame:
        """选择K个最佳特征"""
        if score_func == "f_classif":
            func = f_classif
        elif score_func == "mutual_info":
            func = mutual_info_classif
        else:
            raise ValueError(f"Unknown score function: {score_func}")

        self.selector = SelectKBest(score_func=func, k=k)
        X_selected = self.selector.fit_transform(X, y)

        # 获取选中的特征名
        mask = self.selector.get_support()
        self.selected_features = X.columns[mask].tolist()

        return pd.DataFrame(
            X_selected,
            index=X.index,
            columns=self.selected_features
        )

    def get_feature_scores(self, X: pd.DataFrame) -> pd.Series:
        """获取特征分数"""
        if self.selector is None:
            raise ValueError("Selector not fitted")

        scores = pd.Series(
            self.selector.scores_,
            index=X.columns
        )

        return scores.sort_values(ascending=False)

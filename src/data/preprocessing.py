"""
数据预处理和特征工程
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from sklearn.impute import SimpleImputer, KNNImputer
import talib as ta


class DataPreprocessor:
    """数据预处理器"""

    def __init__(self):
        self.scalers = {}
        self.imputers = {}

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗数据"""
        df = df.copy()

        # 移除重复行
        df = df.drop_duplicates()

        # 移除空值过多的列（超过50%）
        threshold = len(df) * 0.5
        df = df.dropna(thresh=threshold, axis=1)

        # 处理无限值
        df = df.replace([np.inf, -np.inf], np.nan)

        return df

    def handle_missing_values(
        self,
        df: pd.DataFrame,
        method: str = "forward_fill",
        **kwargs
    ) -> pd.DataFrame:
        """处理缺失值"""
        df = df.copy()

        if method == "forward_fill":
            df = df.fillna(method='ffill')
        elif method == "backward_fill":
            df = df.fillna(method='bfill')
        elif method == "interpolate":
            df = df.interpolate(method='linear')
        elif method == "mean":
            df = df.fillna(df.mean())
        elif method == "median":
            df = df.fillna(df.median())
        elif method == "knn":
            imputer = KNNImputer(n_neighbors=5, **kwargs)
            df = pd.DataFrame(
                imputer.fit_transform(df),
                index=df.index,
                columns=df.columns
            )
        elif method == "zero":
            df = df.fillna(0)

        return df

    def detect_outliers(
        self,
        df: pd.DataFrame,
        method: str = "iqr",
        threshold: float = 3.0
    ) -> pd.DataFrame:
        """检测异常值"""
        outlier_mask = pd.DataFrame(False, index=df.index, columns=df.columns)

        if method == "iqr":
            for col in df.select_dtypes(include=[np.number]).columns:
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                lower = Q1 - 1.5 * IQR
                upper = Q3 + 1.5 * IQR
                outlier_mask[col] = (df[col] < lower) | (df[col] > upper)

        elif method == "zscore":
            for col in df.select_dtypes(include=[np.number]).columns:
                z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
                outlier_mask[col] = z_scores > threshold

        elif method == "modified_zscore":
            for col in df.select_dtypes(include=[np.number]).columns:
                median = df[col].median()
                mad = np.median(np.abs(df[col] - median))
                modified_z_scores = 0.6745 * (df[col] - median) / mad if mad != 0 else 0
                outlier_mask[col] = np.abs(modified_z_scores) > threshold

        return outlier_mask

    def handle_outliers(
        self,
        df: pd.DataFrame,
        method: str = "clip",
        detection_method: str = "iqr"
    ) -> pd.DataFrame:
        """处理异常值"""
        df = df.copy()
        outlier_mask = self.detect_outliers(df, method=detection_method)

        if method == "remove":
            df[outlier_mask] = np.nan
        elif method == "clip":
            for col in df.select_dtypes(include=[np.number]).columns:
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                lower = Q1 - 1.5 * IQR
                upper = Q3 + 1.5 * IQR
                df[col] = df[col].clip(lower=lower, upper=upper)
        elif method == "winsorize":
            for col in df.select_dtypes(include=[np.number]).columns:
                lower = df[col].quantile(0.05)
                upper = df[col].quantile(0.95)
                df[col] = df[col].clip(lower=lower, upper=upper)

        return df

    def normalize_data(
        self,
        df: pd.DataFrame,
        method: str = "standard",
        feature_range: Tuple[float, float] = (0, 1)
    ) -> pd.DataFrame:
        """归一化数据"""
        df = df.copy()

        numeric_cols = df.select_dtypes(include=[np.number]).columns

        if method == "standard":
            scaler = StandardScaler()
        elif method == "minmax":
            scaler = MinMaxScaler(feature_range=feature_range)
        elif method == "robust":
            scaler = RobustScaler()
        else:
            return df

        df[numeric_cols] = scaler.fit_transform(df[numeric_cols])
        self.scalers[method] = scaler

        return df

    def create_lag_features(
        self,
        df: pd.DataFrame,
        columns: List[str],
        lags: List[int]
    ) -> pd.DataFrame:
        """创建滞后特征"""
        df = df.copy()

        for col in columns:
            for lag in lags:
                df[f"{col}_lag_{lag}"] = df[col].shift(lag)

        return df

    def create_rolling_features(
        self,
        df: pd.DataFrame,
        columns: List[str],
        windows: List[int],
        functions: List[str] = ['mean', 'std', 'min', 'max']
    ) -> pd.DataFrame:
        """创建滚动窗口特征"""
        df = df.copy()

        for col in columns:
            for window in windows:
                for func in functions:
                    if func == 'mean':
                        df[f"{col}_rolling_{window}_mean"] = df[col].rolling(window).mean()
                    elif func == 'std':
                        df[f"{col}_rolling_{window}_std"] = df[col].rolling(window).std()
                    elif func == 'min':
                        df[f"{col}_rolling_{window}_min"] = df[col].rolling(window).min()
                    elif func == 'max':
                        df[f"{col}_rolling_{window}_max"] = df[col].rolling(window).max()
                    elif func == 'sum':
                        df[f"{col}_rolling_{window}_sum"] = df[col].rolling(window).sum()

        return df


class FeatureEngineer:
    """特征工程"""

    @staticmethod
    def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """添加技术指标"""
        df = df.copy()

        # 确保有OHLCV数据
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            return df

        # 移动平均线
        for period in [5, 10, 20, 50, 100, 200]:
            df[f'SMA_{period}'] = ta.SMA(df['close'], timeperiod=period)
            df[f'EMA_{period}'] = ta.EMA(df['close'], timeperiod=period)

        # RSI
        for period in [14, 28]:
            df[f'RSI_{period}'] = ta.RSI(df['close'], timeperiod=period)

        # MACD
        macd, signal, hist = ta.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
        df['MACD'] = macd
        df['MACD_Signal'] = signal
        df['MACD_Hist'] = hist

        # 布林带
        upper, middle, lower = ta.BBANDS(df['close'], timeperiod=20)
        df['BB_Upper'] = upper
        df['BB_Middle'] = middle
        df['BB_Lower'] = lower
        df['BB_Width'] = (upper - lower) / middle

        # ATR
        df['ATR_14'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)

        # ADX
        df['ADX_14'] = ta.ADX(df['high'], df['low'], df['close'], timeperiod=14)

        # OBV
        df['OBV'] = ta.OBV(df['close'], df['volume'])

        # Stochastic
        slowk, slowd = ta.STOCH(df['high'], df['low'], df['close'])
        df['Stochastic_K'] = slowk
        df['Stochastic_D'] = slowd

        # Williams %R
        df['Williams_R'] = ta.WILLR(df['high'], df['low'], df['close'], timeperiod=14)

        # CCI
        df['CCI'] = ta.CCI(df['high'], df['low'], df['close'], timeperiod=14)

        # MFI
        df['MFI'] = ta.MFI(df['high'], df['low'], df['close'], df['volume'], timeperiod=14)

        # ROC
        df['ROC'] = ta.ROC(df['close'], timeperiod=10)

        return df

    @staticmethod
    def add_price_features(df: pd.DataFrame) -> pd.DataFrame:
        """添加价格特征"""
        df = df.copy()

        if 'close' in df.columns:
            # 收益率
            df['returns'] = df['close'].pct_change()
            df['log_returns'] = np.log(df['close'] / df['close'].shift(1))

            # 累积收益
            df['cumulative_returns'] = (1 + df['returns']).cumprod() - 1

        if 'high' in df.columns and 'low' in df.columns:
            # 价格范围
            df['price_range'] = df['high'] - df['low']
            df['price_range_pct'] = df['price_range'] / df['close']

        if 'open' in df.columns and 'close' in df.columns:
            # 开收盘差
            df['open_close_diff'] = df['close'] - df['open']
            df['open_close_pct'] = (df['close'] - df['open']) / df['open']

        return df

    @staticmethod
    def add_volume_features(df: pd.DataFrame) -> pd.DataFrame:
        """添加成交量特征"""
        df = df.copy()

        if 'volume' not in df.columns:
            return df

        # 成交量移动平均
        for period in [5, 10, 20]:
            df[f'Volume_SMA_{period}'] = ta.SMA(df['volume'], timeperiod=period)

        # 成交量比率
        df['Volume_Ratio'] = df['volume'] / df['Volume_SMA_20']

        # 价格成交量趋势
        if 'close' in df.columns:
            df['Price_Volume_Trend'] = df['volume'] * ((df['close'] - df['close'].shift(1)) / df['close'].shift(1))

        return df

    @staticmethod
    def add_volatility_features(df: pd.DataFrame) -> pd.DataFrame:
        """添加波动率特征"""
        df = df.copy()

        if 'returns' not in df.columns and 'close' in df.columns:
            df['returns'] = df['close'].pct_change()

        if 'returns' in df.columns:
            # 历史波动率
            for period in [5, 10, 20, 60]:
                df[f'Volatility_{period}'] = df['returns'].rolling(period).std() * np.sqrt(252)

            # Parkinson波动率
            if 'high' in df.columns and 'low' in df.columns:
                df['Parkinson_Volatility'] = np.sqrt(1/(4*np.log(2)) * (np.log(df['high']/df['low']))**2)

        return df

    @staticmethod
    def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
        """添加时间特征"""
        df = df.copy()

        if df.index.name == 'timestamp' or isinstance(df.index, pd.DatetimeIndex):
            df['hour'] = df.index.hour
            df['day_of_week'] = df.index.dayofweek
            df['day_of_month'] = df.index.day
            df['month'] = df.index.month
            df['quarter'] = df.index.quarter
            df['year'] = df.index.year
            df['is_month_start'] = df.index.is_month_start.astype(int)
            df['is_month_end'] = df.index.is_month_end.astype(int)
            df['is_quarter_start'] = df.index.is_quarter_start.astype(int)
            df['is_quarter_end'] = df.index.is_quarter_end.astype(int)

        return df


class DataValidator:
    """数据验证器"""

    @staticmethod
    def validate_ohlcv(df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """验证OHLCV数据"""
        errors = []

        # 检查必需列
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            errors.append(f"Missing required columns: {missing_cols}")
            return False, errors

        # 验证high >= low
        if not (df['high'] >= df['low']).all():
            errors.append("High price must be >= low price")

        # 验证high >= open, close
        if not (df['high'] >= df['open']).all():
            errors.append("High price must be >= open price")
        if not (df['high'] >= df['close']).all():
            errors.append("High price must be >= close price")

        # 验证low <= open, close
        if not (df['low'] <= df['open']).all():
            errors.append("Low price must be <= open price")
        if not (df['low'] <= df['close']).all():
            errors.append("Low price must be <= close price")

        # 验证volume >= 0
        if not (df['volume'] >= 0).all():
            errors.append("Volume must be non-negative")

        # 验证没有NaN
        if df[required_cols].isnull().any().any():
            errors.append("Data contains NaN values")

        return len(errors) == 0, errors

    @staticmethod
    def calculate_data_quality_score(df: pd.DataFrame) -> float:
        """计算数据质量分数"""
        score = 1.0

        # 缺失值惩罚
        missing_ratio = df.isnull().sum().sum() / (df.shape[0] * df.shape[1])
        score -= missing_ratio * 0.3

        # 重复值惩罚
        duplicate_ratio = df.duplicated().sum() / len(df)
        score -= duplicate_ratio * 0.2

        # 异常值检测
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        outlier_count = 0
        for col in numeric_cols:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            outlier_count += ((df[col] < (Q1 - 1.5 * IQR)) | (df[col] > (Q3 + 1.5 * IQR))).sum()
        
        outlier_ratio = outlier_count / (len(df) * len(numeric_cols))
        score -= outlier_ratio * 0.2

        return max(0.0, score)

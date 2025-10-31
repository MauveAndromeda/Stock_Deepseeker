"""
Data Processor
Processes and cleans raw market data
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from loguru import logger

class DataProcessor:
    """Processes raw market data into clean formats"""

    def __init__(self):
        self.processed_count = 0
        logger.info("Data processor initialized")

    def process_ohlcv(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        Process OHLCV data
        
        Args:
            df: Raw OHLCV DataFrame
            symbol: Stock symbol
            
        Returns:
            Cleaned DataFrame
        """
        df = df.copy()
        
        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'timestamp' in df.columns:
                df.index = pd.to_datetime(df['timestamp'])
                df = df.drop('timestamp', axis=1)
            elif 'date' in df.columns:
                df.index = pd.to_datetime(df['date'])
                df = df.drop('date', axis=1)
        
        # Standardize column names
        df.columns = [c.lower() for c in df.columns]
        
        # Remove duplicates
        df = df[~df.index.duplicated(keep='first')]
        
        # Sort by index
        df = df.sort_index()
        
        # Fill missing values
        df = self._handle_missing_values(df)
        
        # Detect and handle outliers
        df = self._handle_outliers(df)
        
        # Add symbol column
        df['symbol'] = symbol
        
        self.processed_count += 1
        
        logger.debug(f"Processed {len(df)} bars for {symbol}")
        
        return df

    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values in OHLCV data"""
        # Forward fill for small gaps
        df = df.fillna(method='ffill', limit=3)
        
        # Drop remaining NaN
        initial_len = len(df)
        df = df.dropna()
        
        if len(df) < initial_len:
            logger.warning(f"Dropped {initial_len - len(df)} rows with missing values")
        
        return df

    def _handle_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect and handle outliers"""
        # Calculate returns
        returns = df['close'].pct_change()
        
        # Z-score method for outlier detection
        mean_ret = returns.mean()
        std_ret = returns.std()
        z_scores = np.abs((returns - mean_ret) / std_ret)
        
        # Cap extreme values (>5 std)
        outlier_threshold = 5
        outliers = z_scores > outlier_threshold
        
        if outliers.sum() > 0:
            logger.warning(f"Found {outliers.sum()} outlier values")
            
            # Cap at threshold
            for col in ['open', 'high', 'low', 'close']:
                # Use previous value for outliers
                df.loc[outliers, col] = df.loc[outliers, col].shift(1)
        
        return df

    def align_multiple_symbols(self, data_dict: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """
        Align multiple symbol DataFrames to common index
        
        Args:
            data_dict: Dict of symbol -> DataFrame
            
        Returns:
            Dict with aligned DataFrames
        """
        if not data_dict:
            return {}
        
        # Find common index (intersection)
        common_index = None
        for symbol, df in data_dict.items():
            if common_index is None:
                common_index = df.index
            else:
                common_index = common_index.intersection(df.index)
        
        # Reindex all DataFrames
        aligned = {}
        for symbol, df in data_dict.items():
            aligned[symbol] = df.loc[common_index]
        
        logger.info(f"Aligned {len(aligned)} symbols to {len(common_index)} common timestamps")
        
        return aligned

    def resample_data(
        self,
        df: pd.DataFrame,
        timeframe: str = '1H',
        agg_method: Optional[Dict] = None
    ) -> pd.DataFrame:
        """
        Resample data to different timeframe
        
        Args:
            df: Input DataFrame
            timeframe: Target timeframe ('1H', '1D', etc.)
            agg_method: Aggregation method dict
            
        Returns:
            Resampled DataFrame
        """
        if agg_method is None:
            agg_method = {
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }
        
        # Filter to only columns that exist
        agg_method = {k: v for k, v in agg_method.items() if k in df.columns}
        
        resampled = df.resample(timeframe).agg(agg_method)
        resampled = resampled.dropna()
        
        logger.debug(f"Resampled to {timeframe}: {len(df)} -> {len(resampled)} bars")
        
        return resampled

    def calculate_returns(
        self,
        df: pd.DataFrame,
        method: str = 'simple',
        periods: int = 1
    ) -> pd.Series:
        """
        Calculate returns
        
        Args:
            df: DataFrame with 'close' column
            method: 'simple' or 'log'
            periods: Number of periods
            
        Returns:
            Returns series
        """
        if method == 'simple':
            returns = df['close'].pct_change(periods=periods)
        elif method == 'log':
            returns = np.log(df['close'] / df['close'].shift(periods))
        else:
            raise ValueError(f"Unknown method: {method}")
        
        return returns

    def normalize_data(
        self,
        df: pd.DataFrame,
        columns: List[str],
        method: str = 'zscore'
    ) -> pd.DataFrame:
        """
        Normalize specified columns
        
        Args:
            df: Input DataFrame
            columns: Columns to normalize
            method: Normalization method
            
        Returns:
            DataFrame with normalized columns
        """
        df = df.copy()
        
        for col in columns:
            if col not in df.columns:
                continue
            
            if method == 'zscore':
                mean = df[col].mean()
                std = df[col].std()
                if std > 0:
                    df[f'{col}_norm'] = (df[col] - mean) / std
                else:
                    df[f'{col}_norm'] = 0
            
            elif method == 'minmax':
                min_val = df[col].min()
                max_val = df[col].max()
                if max_val > min_val:
                    df[f'{col}_norm'] = (df[col] - min_val) / (max_val - min_val)
                else:
                    df[f'{col}_norm'] = 0
            
            elif method == 'robust':
                median = df[col].median()
                q1 = df[col].quantile(0.25)
                q3 = df[col].quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    df[f'{col}_norm'] = (df[col] - median) / iqr
                else:
                    df[f'{col}_norm'] = 0
        
        return df

    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create basic features from OHLCV
        
        Args:
            df: OHLCV DataFrame
            
        Returns:
            DataFrame with additional features
        """
        df = df.copy()
        
        # Returns
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        
        # Price features
        df['hl_pct'] = (df['high'] - df['low']) / df['close']
        df['oc_pct'] = (df['close'] - df['open']) / df['open']
        
        # Volume features
        df['volume_ma_20'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma_20']
        
        # Volatility
        df['volatility_20'] = df['returns'].rolling(20).std()
        
        # Gaps
        df['gap'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)
        
        return df

    def split_train_test(
        self,
        df: pd.DataFrame,
        train_ratio: float = 0.8
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Split data into train and test sets
        
        Args:
            df: Input DataFrame
            train_ratio: Ratio for training data
            
        Returns:
            (train_df, test_df)
        """
        split_idx = int(len(df) * train_ratio)
        
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]
        
        logger.info(f"Split data: train={len(train_df)}, test={len(test_df)}")
        
        return train_df, test_df

    def create_sequences(
        self,
        df: pd.DataFrame,
        sequence_length: int,
        target_column: str = 'close'
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create sequences for time series models
        
        Args:
            df: Input DataFrame
            sequence_length: Length of sequences
            target_column: Target column name
            
        Returns:
            (X, y) arrays
        """
        features = df.values
        targets = df[target_column].values
        
        X, y = [], []
        
        for i in range(len(df) - sequence_length):
            X.append(features[i:i+sequence_length])
            y.append(targets[i+sequence_length])
        
        return np.array(X), np.array(y)

    def get_stats(self) -> Dict:
        """Get processor statistics"""
        return {
            'processed_count': self.processed_count
        }

"""
Data Validator
Validates data quality and integrity
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from loguru import logger


class ValidationError(Exception):
    """Data validation error"""
    pass


class DataValidator:
    """Validates data quality"""

    @staticmethod
    def validate_ohlcv(df: pd.DataFrame) -> bool:
        """
        Validate OHLCV data
        
        Args:
            df: DataFrame to validate
            
        Returns:
            True if valid
            
        Raises:
            ValidationError if invalid
        """
        # Check required columns
        required = ['open', 'high', 'low', 'close', 'volume']
        missing = [col for col in required if col not in df.columns]
        
        if missing:
            raise ValidationError(f"Missing columns: {missing}")
        
        # Check for negative values
        if (df[['open', 'high', 'low', 'close']] < 0).any().any():
            raise ValidationError("Negative price values found")
        
        # Check volume
        if (df['volume'] < 0).any():
            raise ValidationError("Negative volume values found")
        
        # Check high >= low
        if (df['high'] < df['low']).any():
            raise ValidationError("High < Low found")
        
        # Check high >= open, close
        if ((df['high'] < df['open']) | (df['high'] < df['close'])).any():
            raise ValidationError("High < Open/Close found")
        
        # Check low <= open, close
        if ((df['low'] > df['open']) | (df['low'] > df['close'])).any():
            raise ValidationError("Low > Open/Close found")
        
        logger.debug(f"OHLCV validation passed: {len(df)} rows")
        return True

    @staticmethod
    def check_data_quality(df: pd.DataFrame) -> Dict:
        """
        Check data quality metrics
        
        Args:
            df: DataFrame to check
            
        Returns:
            Dict with quality metrics
        """
        metrics = {
            'total_rows': len(df),
            'missing_values': df.isnull().sum().to_dict(),
            'duplicate_rows': df.duplicated().sum(),
            'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024**2
        }
        
        # Check for outliers (using IQR method)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        outliers = {}
        
        for col in numeric_cols:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            
            outlier_mask = (df[col] < Q1 - 1.5*IQR) | (df[col] > Q3 + 1.5*IQR)
            outliers[col] = outlier_mask.sum()
        
        metrics['outliers'] = outliers
        
        return metrics

    @staticmethod
    def validate_returns(returns: pd.Series, max_return: float = 0.2) -> bool:
        """
        Validate returns are reasonable
        
        Args:
            returns: Returns series
            max_return: Maximum allowed single-period return
            
        Returns:
            True if valid
        """
        # Check for extreme returns
        extreme = (returns.abs() > max_return).sum()
        
        if extreme > 0:
            logger.warning(f"Found {extreme} extreme returns (>{max_return*100}%)")
            return False
        
        return True

    @staticmethod
    def check_data_gaps(df: pd.DataFrame, expected_freq: str = 'D') -> List:
        """
        Check for gaps in time series data
        
        Args:
            df: DataFrame with DatetimeIndex
            expected_freq: Expected frequency
            
        Returns:
            List of gaps
        """
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame must have DatetimeIndex")
        
        # Generate expected date range
        expected_dates = pd.date_range(
            start=df.index.min(),
            end=df.index.max(),
            freq=expected_freq
        )
        
        # Find missing dates
        missing = expected_dates.difference(df.index)
        
        gaps = []
        for date in missing:
            gaps.append({
                'date': date,
                'type': 'missing'
            })
        
        if gaps:
            logger.warning(f"Found {len(gaps)} gaps in data")
        
        return gaps

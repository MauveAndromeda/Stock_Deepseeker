"""
Feature Processor
Creates and transforms features for ML models
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from loguru import logger

class FeatureProcessor:
    """Processes and transforms features for ML"""

    def __init__(self):
        self.scalers = {}
        self.feature_names = []
        logger.info("Feature processor initialized")

    def create_lag_features(
        self,
        df: pd.DataFrame,
        columns: List[str],
        lags: List[int]
    ) -> pd.DataFrame:
        """
        Create lagged features
        
        Args:
            df: Input DataFrame
            columns: Columns to lag
            lags: List of lag periods
            
        Returns:
            DataFrame with lag features
        """
        df = df.copy()
        
        for col in columns:
            if col not in df.columns:
                continue
            
            for lag in lags:
                df[f'{col}_lag{lag}'] = df[col].shift(lag)
        
        return df

    def create_rolling_features(
        self,
        df: pd.DataFrame,
        columns: List[str],
        windows: List[int],
        functions: List[str] = ['mean', 'std', 'min', 'max']
    ) -> pd.DataFrame:
        """
        Create rolling window features
        
        Args:
            df: Input DataFrame
            columns: Columns to process
            windows: Window sizes
            functions: Aggregation functions
            
        Returns:
            DataFrame with rolling features
        """
        df = df.copy()
        
        for col in columns:
            if col not in df.columns:
                continue
            
            for window in windows:
                for func in functions:
                    if func == 'mean':
                        df[f'{col}_roll{window}_mean'] = df[col].rolling(window).mean()
                    elif func == 'std':
                        df[f'{col}_roll{window}_std'] = df[col].rolling(window).std()
                    elif func == 'min':
                        df[f'{col}_roll{window}_min'] = df[col].rolling(window).min()
                    elif func == 'max':
                        df[f'{col}_roll{window}_max'] = df[col].rolling(window).max()
                    elif func == 'median':
                        df[f'{col}_roll{window}_median'] = df[col].rolling(window).median()
        
        return df

    def create_expanding_features(
        self,
        df: pd.DataFrame,
        columns: List[str]
    ) -> pd.DataFrame:
        """Create expanding window features"""
        df = df.copy()
        
        for col in columns:
            if col not in df.columns:
                continue
            
            df[f'{col}_expanding_mean'] = df[col].expanding().mean()
            df[f'{col}_expanding_std'] = df[col].expanding().std()
            df[f'{col}_expanding_max'] = df[col].expanding().max()
            df[f'{col}_expanding_min'] = df[col].expanding().min()
        
        return df

    def create_diff_features(
        self,
        df: pd.DataFrame,
        columns: List[str],
        periods: List[int] = [1]
    ) -> pd.DataFrame:
        """Create differenced features"""
        df = df.copy()
        
        for col in columns:
            if col not in df.columns:
                continue
            
            for period in periods:
                df[f'{col}_diff{period}'] = df[col].diff(periods=period)
                df[f'{col}_pct_change{period}'] = df[col].pct_change(periods=period)
        
        return df

    def create_interaction_features(
        self,
        df: pd.DataFrame,
        column_pairs: List[Tuple[str, str]]
    ) -> pd.DataFrame:
        """
        Create interaction features between column pairs
        
        Args:
            df: Input DataFrame
            column_pairs: List of (col1, col2) tuples
            
        Returns:
            DataFrame with interaction features
        """
        df = df.copy()
        
        for col1, col2 in column_pairs:
            if col1 in df.columns and col2 in df.columns:
                # Multiplication
                df[f'{col1}_x_{col2}'] = df[col1] * df[col2]
                
                # Division (with safety)
                df[f'{col1}_div_{col2}'] = df[col1] / (df[col2] + 1e-10)
                
                # Difference
                df[f'{col1}_minus_{col2}'] = df[col1] - df[col2]
        
        return df

    def create_polynomial_features(
        self,
        df: pd.DataFrame,
        columns: List[str],
        degree: int = 2
    ) -> pd.DataFrame:
        """Create polynomial features"""
        df = df.copy()
        
        for col in columns:
            if col not in df.columns:
                continue
            
            for d in range(2, degree + 1):
                df[f'{col}_pow{d}'] = df[col] ** d
        
        return df

    def fit_scalers(self, df: pd.DataFrame, columns: List[str]):
        """Fit scalers on data"""
        for col in columns:
            if col not in df.columns:
                continue
            
            scaler = StandardScaler()
            scaler.fit(df[[col]])
            self.scalers[col] = scaler

    def transform_with_scalers(
        self,
        df: pd.DataFrame,
        columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Transform data using fitted scalers"""
        df = df.copy()
        
        if columns is None:
            columns = list(self.scalers.keys())
        
        for col in columns:
            if col in self.scalers and col in df.columns:
                df[col] = self.scalers[col].transform(df[[col]])
        
        return df

    def select_features(
        self,
        df: pd.DataFrame,
        target: str,
        method: str = 'correlation',
        k: int = 20
    ) -> List[str]:
        """
        Select top k features
        
        Args:
            df: Input DataFrame
            target: Target column
            method: Selection method
            k: Number of features to select
            
        Returns:
            List of selected feature names
        """
        if target not in df.columns:
            return []
        
        # Get numeric columns only
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        numeric_cols = [c for c in numeric_cols if c != target]
        
        if method == 'correlation':
            # Calculate correlation with target
            correlations = df[numeric_cols + [target]].corr()[target].abs()
            correlations = correlations.drop(target)
            
            # Sort and select top k
            top_features = correlations.nlargest(k).index.tolist()
            
            return top_features
        
        return numeric_cols[:k]

    def remove_highly_correlated(
        self,
        df: pd.DataFrame,
        threshold: float = 0.95
    ) -> pd.DataFrame:
        """Remove highly correlated features"""
        df = df.copy()
        
        # Calculate correlation matrix
        corr_matrix = df.corr().abs()
        
        # Find pairs above threshold
        upper = corr_matrix.where(
            np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
        )
        
        # Drop columns
        to_drop = [column for column in upper.columns if any(upper[column] > threshold)]
        
        logger.info(f"Dropping {len(to_drop)} highly correlated features")
        
        return df.drop(columns=to_drop)

    def handle_missing_features(
        self,
        df: pd.DataFrame,
        method: str = 'forward_fill'
    ) -> pd.DataFrame:
        """Handle missing values in features"""
        df = df.copy()
        
        if method == 'forward_fill':
            df = df.fillna(method='ffill')
        elif method == 'backward_fill':
            df = df.fillna(method='bfill')
        elif method == 'mean':
            df = df.fillna(df.mean())
        elif method == 'median':
            df = df.fillna(df.median())
        elif method == 'zero':
            df = df.fillna(0)
        
        # Drop any remaining NaN
        df = df.dropna()
        
        return df

"""
Tests for data processors
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.data.processors import DataProcessor, FeatureProcessor


class TestDataProcessor:
    """Test DataProcessor class"""

    def setup_method(self):
        """Setup test fixtures"""
        self.processor = DataProcessor()
        
        # Create sample data
        dates = pd.date_range(start='2020-01-01', end='2020-12-31', freq='D')
        self.sample_data = pd.DataFrame({
            'open': np.random.randn(len(dates)).cumsum() + 100,
            'high': np.random.randn(len(dates)).cumsum() + 102,
            'low': np.random.randn(len(dates)).cumsum() + 98,
            'close': np.random.randn(len(dates)).cumsum() + 100,
            'volume': np.random.randint(1000000, 10000000, len(dates))
        }, index=dates)

    def test_process_ohlcv(self):
        """Test OHLCV processing"""
        result = self.processor.process_ohlcv(self.sample_data, 'TEST')
        
        assert not result.empty
        assert 'symbol' in result.columns
        assert result['symbol'].iloc[0] == 'TEST'
        assert len(result) <= len(self.sample_data)

    def test_handle_missing_values(self):
        """Test missing value handling"""
        # Add some NaN values
        data = self.sample_data.copy()
        data.loc[data.index[5:10], 'close'] = np.nan
        
        result = self.processor._handle_missing_values(data)
        
        # Should have no NaN
        assert not result['close'].isna().any()

    def test_resample_data(self):
        """Test data resampling"""
        result = self.processor.resample_data(self.sample_data, '1W')
        
        # Should have fewer rows
        assert len(result) < len(self.sample_data)
        
        # Should have correct columns
        assert 'close' in result.columns

    def test_calculate_returns(self):
        """Test return calculation"""
        returns = self.processor.calculate_returns(self.sample_data, method='simple')
        
        # First return should be NaN
        assert pd.isna(returns.iloc[0])
        
        # Rest should be numeric
        assert not pd.isna(returns.iloc[1:]).all()

    def test_normalize_data(self):
        """Test data normalization"""
        result = self.processor.normalize_data(
            self.sample_data,
            columns=['close', 'volume'],
            method='zscore'
        )
        
        # Should have normalized columns
        assert 'close_norm' in result.columns
        assert 'volume_norm' in result.columns
        
        # Normalized columns should have mean ~0, std ~1
        assert abs(result['close_norm'].mean()) < 0.1
        assert abs(result['close_norm'].std() - 1) < 0.1


class TestFeatureProcessor:
    """Test FeatureProcessor class"""

    def setup_method(self):
        """Setup test fixtures"""
        self.processor = FeatureProcessor()
        
        dates = pd.date_range(start='2020-01-01', end='2020-12-31', freq='D')
        self.sample_data = pd.DataFrame({
            'close': np.random.randn(len(dates)).cumsum() + 100,
            'volume': np.random.randint(1000000, 10000000, len(dates))
        }, index=dates)

    def test_create_lag_features(self):
        """Test lag feature creation"""
        result = self.processor.create_lag_features(
            self.sample_data,
            columns=['close'],
            lags=[1, 2, 5]
        )
        
        # Should have lag columns
        assert 'close_lag1' in result.columns
        assert 'close_lag2' in result.columns
        assert 'close_lag5' in result.columns

    def test_create_rolling_features(self):
        """Test rolling feature creation"""
        result = self.processor.create_rolling_features(
            self.sample_data,
            columns=['close'],
            windows=[5, 10],
            functions=['mean', 'std']
        )
        
        # Should have rolling columns
        assert 'close_roll5_mean' in result.columns
        assert 'close_roll10_std' in result.columns

    def test_create_diff_features(self):
        """Test diff feature creation"""
        result = self.processor.create_diff_features(
            self.sample_data,
            columns=['close'],
            periods=[1]
        )
        
        # Should have diff columns
        assert 'close_diff1' in result.columns
        assert 'close_pct_change1' in result.columns

    def test_select_features(self):
        """Test feature selection"""
        # Add some features
        data = self.sample_data.copy()
        data['target'] = data['close'].shift(-1)
        data['feature1'] = np.random.randn(len(data))
        data['feature2'] = data['close'] * 0.9 + np.random.randn(len(data))
        data = data.dropna()
        
        selected = self.processor.select_features(
            data,
            target='target',
            method='correlation',
            k=2
        )
        
        # Should return list of feature names
        assert isinstance(selected, list)
        assert len(selected) <= 2

"""
Tests for trading strategies
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.trading.strategy import MomentumStrategy, TrendFollowingStrategy
from src.trading.strategy.base import StrategyConfig, Position


class TestMomentumStrategy:
    """Test MomentumStrategy"""

    def setup_method(self):
        """Setup test fixtures"""
        config = StrategyConfig(
            name="test_momentum",
            max_positions=5,
            stop_loss_pct=0.02,
            take_profit_pct=0.05
        )
        self.strategy = MomentumStrategy(config)
        
        # Create sample data
        dates = pd.date_range(start='2020-01-01', end='2020-12-31', freq='D')
        self.sample_data = pd.DataFrame({
            'open': np.random.randn(len(dates)).cumsum() + 100,
            'high': np.random.randn(len(dates)).cumsum() + 102,
            'low': np.random.randn(len(dates)).cumsum() + 98,
            'close': np.random.randn(len(dates)).cumsum() + 100,
            'volume': np.random.randint(1000000, 10000000, len(dates))
        }, index=dates)

    def test_strategy_initialization(self):
        """Test strategy initialization"""
        assert self.strategy.config.name == "test_momentum"
        assert len(self.strategy.positions) == 0
        assert len(self.strategy.closed_trades) == 0

    def test_analyze_signal(self):
        """Test signal generation"""
        signal = self.strategy.analyze(self.sample_data, 'TEST')
        
        # Should return a Signal object
        assert signal is not None
        assert signal.symbol == 'TEST'
        assert signal.action in ['buy', 'sell', 'hold']
        assert 0 <= signal.strength <= 1
        assert 0 <= signal.confidence <= 1

    def test_position_lifecycle(self):
        """Test opening and closing positions"""
        # Open position
        position = self.strategy.open_position(
            symbol='TEST',
            price=100.0,
            quantity=10,
            position_type='long'
        )
        
        assert position.symbol == 'TEST'
        assert position.quantity == 10
        assert position.entry_price == 100.0
        assert 'TEST' in self.strategy.positions
        
        # Close position
        trade = self.strategy.close_position(
            symbol='TEST',
            price=105.0,
            reason='take_profit'
        )
        
        assert trade is not None
        assert trade.pnl > 0  # Should be profitable
        assert 'TEST' not in self.strategy.positions
        assert len(self.strategy.closed_trades) == 1

    def test_position_size_calculation(self):
        """Test position size calculation"""
        size = self.strategy.calculate_position_size(
            symbol='TEST',
            price=100.0,
            portfolio_value=10000.0,
            volatility=0.02
        )
        
        assert size > 0
        assert isinstance(size, int)

    def test_performance_metrics(self):
        """Test performance metrics calculation"""
        # Make some trades
        self.strategy.open_position('TEST1', 100, 10)
        self.strategy.close_position('TEST1', 105, 'take_profit')
        
        self.strategy.open_position('TEST2', 200, 5)
        self.strategy.close_position('TEST2', 190, 'stop_loss')
        
        metrics = self.strategy.get_performance_metrics()
        
        assert 'total_trades' in metrics
        assert metrics['total_trades'] == 2
        assert 'win_rate' in metrics


class TestTrendFollowingStrategy:
    """Test TrendFollowingStrategy"""

    def setup_method(self):
        """Setup test fixtures"""
        config = StrategyConfig(
            name="test_trend",
            max_positions=5
        )
        self.strategy = TrendFollowingStrategy(config)
        
        # Create trending data
        dates = pd.date_range(start='2020-01-01', periods=500, freq='D')
        trend = np.linspace(100, 150, len(dates))
        noise = np.random.randn(len(dates)) * 2
        
        self.sample_data = pd.DataFrame({
            'open': trend + noise,
            'high': trend + noise + 1,
            'low': trend + noise - 1,
            'close': trend + noise,
            'volume': np.random.randint(1000000, 10000000, len(dates))
        }, index=dates)

    def test_trend_detection(self):
        """Test trend detection"""
        signal = self.strategy.analyze(self.sample_data, 'TEST')
        
        # With upward trend, should tend toward buy
        assert signal is not None
        assert signal.symbol == 'TEST'

    def test_moving_average_crossover(self):
        """Test MA crossover detection"""
        # Add MAs to data
        self.sample_data['sma_50'] = self.sample_data['close'].rolling(50).mean()
        self.sample_data['sma_200'] = self.sample_data['close'].rolling(200).mean()
        
        signal = self.strategy.analyze(self.sample_data, 'TEST')
        
        # Should detect golden cross in uptrend
        assert signal.metadata.get('golden_cross') or signal.metadata.get('death_cross') is not None

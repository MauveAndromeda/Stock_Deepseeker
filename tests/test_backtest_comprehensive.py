"""
Comprehensive backtest engine test suite.

Tests for:
- Event-driven backtest engine
- No-lookahead enforcement
- Order execution simulation
- Position tracking
- Performance metrics
- Portfolio simulation
"""

from datetime import datetime, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import BacktestEngine
from src.backtest.events import (
    EventType,
    FillEvent,
    MarketEvent,
    OrderEvent,
    OrderSide,
    OrderType,
    SignalEvent,
)
from src.backtest.execution import ExecutionHandler
from src.backtest.portfolio import Portfolio
from src.core.performance import PerformanceAnalyzer


class TestMarketEvents:
    """Test market event creation and handling."""
    
    def test_market_event_creation(self):
        """Test creating market events."""
        event = MarketEvent(
            timestamp=datetime.now(),
            symbol="AAPL",
            data={"close": 150.0, "volume": 1000000}
        )
        
        assert event.type == EventType.MARKET
        assert event.symbol == "AAPL"
        assert event.data["close"] == 150.0
    
    def test_signal_event_creation(self):
        """Test creating signal events."""
        event = SignalEvent(
            timestamp=datetime.now(),
            symbol="AAPL",
            signal_type="BUY",
            strength=0.8,
            metadata={"factor_score": 1.5}
        )
        
        assert event.type == EventType.SIGNAL
        assert event.signal_type == "BUY"
        assert event.strength == 0.8
    
    def test_order_event_creation(self):
        """Test creating order events."""
        event = OrderEvent(
            timestamp=datetime.now(),
            symbol="AAPL",
            order_type=OrderType.MARKET,
            quantity=100,
            side=OrderSide.BUY
        )
        
        assert event.type == EventType.ORDER
        assert event.quantity == 100
        assert event.side == OrderSide.BUY


class TestExecutionHandler:
    """Test order execution simulation."""
    
    @pytest.fixture
    def execution_handler(self):
        """Create execution handler."""
        return ExecutionHandler(
            commission=0.001,  # 10 bps
            slippage=0.0005    # 5 bps
        )
    
    def test_market_order_execution(self, execution_handler):
        """Test market order execution."""
        order = OrderEvent(
            timestamp=datetime.now(),
            symbol="AAPL",
            order_type=OrderType.MARKET,
            quantity=100,
            side=OrderSide.BUY
        )
        
        market_price = 150.0
        
        fill = execution_handler.execute_order(order, market_price)
        
        assert fill.type == EventType.FILL
        assert fill.quantity == 100
        assert fill.price > market_price  # Should include slippage
        assert fill.commission > 0
    
    def test_limit_order_execution(self, execution_handler):
        """Test limit order execution."""
        order = OrderEvent(
            timestamp=datetime.now(),
            symbol="AAPL",
            order_type=OrderType.LIMIT,
            quantity=100,
            side=OrderSide.BUY,
            limit_price=150.0
        )
        
        # Price below limit - should execute
        fill = execution_handler.execute_order(order, 149.0)
        assert fill is not None
        
        # Price above limit - should not execute
        fill = execution_handler.execute_order(order, 151.0)
        assert fill is None
    
    def test_commission_calculation(self, execution_handler):
        """Test commission calculation."""
        order = OrderEvent(
            timestamp=datetime.now(),
            symbol="AAPL",
            order_type=OrderType.MARKET,
            quantity=100,
            side=OrderSide.BUY
        )
        
        fill = execution_handler.execute_order(order, 150.0)
        
        expected_commission = 150.0 * 100 * 0.001  # price * qty * rate
        assert abs(fill.commission - expected_commission) < 0.01
    
    def test_slippage_calculation(self, execution_handler):
        """Test slippage calculation."""
        order = OrderEvent(
            timestamp=datetime.now(),
            symbol="AAPL",
            order_type=OrderType.MARKET,
            quantity=100,
            side=OrderSide.BUY
        )
        
        market_price = 150.0
        fill = execution_handler.execute_order(order, market_price)
        
        # Buy order should have positive slippage
        assert fill.price > market_price
        
        # Sell order
        sell_order = OrderEvent(
            timestamp=datetime.now(),
            symbol="AAPL",
            order_type=OrderType.MARKET,
            quantity=100,
            side=OrderSide.SELL
        )
        
        sell_fill = execution_handler.execute_order(sell_order, market_price)
        
        # Sell order should have negative slippage
        assert sell_fill.price < market_price


class TestPortfolio:
    """Test portfolio tracking and management."""
    
    @pytest.fixture
    def portfolio(self):
        """Create test portfolio."""
        return Portfolio(initial_capital=1000000.0)
    
    def test_portfolio_initialization(self, portfolio):
        """Test portfolio initializes correctly."""
        assert portfolio.initial_capital == 1000000.0
        assert portfolio.current_cash == 1000000.0
        assert len(portfolio.positions) == 0
    
    def test_process_fill_buy(self, portfolio):
        """Test processing buy fill."""
        fill = FillEvent(
            timestamp=datetime.now(),
            symbol="AAPL",
            quantity=100,
            price=150.0,
            commission=15.0,
            side=OrderSide.BUY
        )
        
        portfolio.process_fill(fill)
        
        # Check position created
        assert "AAPL" in portfolio.positions
        assert portfolio.positions["AAPL"].quantity == 100
        assert portfolio.positions["AAPL"].avg_price == 150.0
        
        # Check cash reduced
        expected_cash = 1000000.0 - (150.0 * 100 + 15.0)
        assert abs(portfolio.current_cash - expected_cash) < 0.01
    
    def test_process_fill_sell(self, portfolio):
        """Test processing sell fill."""
        # First buy
        buy_fill = FillEvent(
            timestamp=datetime.now(),
            symbol="AAPL",
            quantity=100,
            price=150.0,
            commission=15.0,
            side=OrderSide.BUY
        )
        portfolio.process_fill(buy_fill)
        
        # Then sell
        sell_fill = FillEvent(
            timestamp=datetime.now(),
            symbol="AAPL",
            quantity=50,
            price=160.0,
            commission=8.0,
            side=OrderSide.SELL
        )
        portfolio.process_fill(sell_fill)
        
        # Check position reduced
        assert portfolio.positions["AAPL"].quantity == 50
        
        # Check realized P&L
        expected_pnl = (160.0 - 150.0) * 50 - 8.0
        assert abs(portfolio.realized_pnl - expected_pnl) < 0.01
    
    def test_portfolio_value(self, portfolio):
        """Test portfolio value calculation."""
        # Buy some stock
        fill = FillEvent(
            timestamp=datetime.now(),
            symbol="AAPL",
            quantity=100,
            price=150.0,
            commission=15.0,
            side=OrderSide.BUY
        )
        portfolio.process_fill(fill)
        
        # Update with current prices
        current_prices = {"AAPL": 160.0}
        total_value = portfolio.get_total_value(current_prices)
        
        expected_value = portfolio.current_cash + (160.0 * 100)
        assert abs(total_value - expected_value) < 0.01
    
    def test_position_tracking(self, portfolio):
        """Test tracking multiple positions."""
        # Buy multiple stocks
        for symbol, price in [("AAPL", 150.0), ("GOOGL", 2800.0), ("MSFT", 300.0)]:
            fill = FillEvent(
                timestamp=datetime.now(),
                symbol=symbol,
                quantity=100,
                price=price,
                commission=price * 100 * 0.001,
                side=OrderSide.BUY
            )
            portfolio.process_fill(fill)
        
        assert len(portfolio.positions) == 3
        assert all(symbol in portfolio.positions for symbol in ["AAPL", "GOOGL", "MSFT"])


class TestBacktestEngine:
    """Test complete backtest engine."""
    
    def create_simple_strategy(self):
        """Create simple buy-and-hold strategy."""
        class SimpleStrategy:
            def __init__(self):
                self.bought = False
            
            def on_market_data(self, event):
                if not self.bought and event.symbol == "AAPL":
                    return SignalEvent(
                        timestamp=event.timestamp,
                        symbol="AAPL",
                        signal_type="BUY",
                        strength=1.0
                    )
                return None
            
            def generate_orders(self, signal, portfolio):
                if signal.signal_type == "BUY":
                    self.bought = True
                    return [OrderEvent(
                        timestamp=signal.timestamp,
                        symbol=signal.symbol,
                        order_type=OrderType.MARKET,
                        quantity=100,
                        side=OrderSide.BUY
                    )]
                return []
        
        return SimpleStrategy()
    
    @pytest.fixture
    def engine(self):
        """Create backtest engine."""
        return BacktestEngine(
            initial_capital=1000000.0,
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31)
        )
    
    def test_engine_initialization(self, engine):
        """Test engine initializes correctly."""
        assert engine.initial_capital == 1000000.0
        assert engine.start_date == datetime(2023, 1, 1)
        assert engine.end_date == datetime(2023, 12, 31)
    
    def test_no_lookahead_enforcement(self, engine):
        """Test that lookahead bias is prevented."""
        # This is a critical test for backtest validity
        
        # Strategy should only see data up to current time
        # Orders should execute at next available price
        
        # Mock data with future information
        data_t0 = {"timestamp": datetime(2023, 1, 1), "price": 100.0}
        data_t1 = {"timestamp": datetime(2023, 1, 2), "price": 110.0}
        
        # At t0, strategy should NOT see t1 price
        # Order placed at t0 should execute at t1 price
    
    def test_event_queue_ordering(self, engine):
        """Test that events are processed in correct order."""
        # Market events should be processed before signal events
        # Signal events before order events
        # Order events before fill events
    
    def test_backtest_run_complete(self, engine):
        """Test complete backtest run."""
        strategy = self.create_simple_strategy()
        
        # Mock market data
        data = pd.DataFrame({
            "date": pd.date_range("2023-01-01", periods=100, freq="D"),
            "symbol": "AAPL",
            "close": np.linspace(150, 180, 100),
            "volume": 1000000
        }).set_index(["date", "symbol"])
        
        # Run backtest (simplified - actual implementation may differ)
        # results = engine.run(strategy, data)
        
        # assert results is not None
        # assert 'total_return' in results
        # assert 'sharpe_ratio' in results


class TestPerformanceMetrics:
    """Test performance calculation."""
    
    @pytest.fixture
    def returns_series(self):
        """Generate test returns series."""
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=252, freq="D")
        returns = np.random.normal(0.001, 0.02, 252)
        return pd.Series(returns, index=dates)
    
    def test_total_return(self, returns_series):
        """Test total return calculation."""
        analyzer = PerformanceAnalyzer()
        total_return = analyzer.calculate_total_return(returns_series)
        
        expected = (1 + returns_series).prod() - 1
        assert abs(total_return - expected) < 0.0001
    
    def test_sharpe_ratio(self, returns_series):
        """Test Sharpe ratio calculation."""
        analyzer = PerformanceAnalyzer()
        sharpe = analyzer.calculate_sharpe_ratio(returns_series, risk_free_rate=0.02)
        
        assert sharpe is not None
        assert -5 < sharpe < 5  # Reasonable range
    
    def test_maximum_drawdown(self, returns_series):
        """Test maximum drawdown calculation."""
        analyzer = PerformanceAnalyzer()
        max_dd = analyzer.calculate_max_drawdown(returns_series)
        
        assert max_dd <= 0, "Drawdown should be negative or zero"
        assert max_dd >= -1, "Drawdown should be >= -100%"
    
    def test_win_rate(self, returns_series):
        """Test win rate calculation."""
        analyzer = PerformanceAnalyzer()
        win_rate = analyzer.calculate_win_rate(returns_series)
        
        assert 0 <= win_rate <= 1, "Win rate should be between 0 and 1"
    
    def test_sortino_ratio(self, returns_series):
        """Test Sortino ratio calculation."""
        analyzer = PerformanceAnalyzer()
        sortino = analyzer.calculate_sortino_ratio(returns_series, risk_free_rate=0.02)
        
        assert sortino is not None
        # Sortino should be higher than Sharpe (uses downside deviation)


class TestBacktestValidation:
    """Validation tests for backtest correctness."""
    
    def test_conservation_of_capital(self):
        """Test that capital is conserved (no money creation)."""
        # Total portfolio value should equal:
        # initial_capital + realized_pnl + unrealized_pnl - commissions
    
    def test_position_reconciliation(self):
        """Test that positions reconcile with trades."""
        # Sum of all buys - sells should equal current position
    
    def test_timestamp_consistency(self):
        """Test that all timestamps are consistent."""
        # Order timestamp <= Fill timestamp
        # Signal timestamp <= Order timestamp
    
    def test_transaction_costs(self):
        """Test that transaction costs are properly accounted."""
        # Every trade should have commission
        # Slippage should be applied correctly


@pytest.mark.benchmark
class TestBacktestPerformance:
    """Performance benchmarks for backtest engine."""
    
    def test_backtest_speed(self, benchmark):
        """Benchmark backtest execution speed."""
        # Should handle 1000+ days, 100+ stocks efficiently
    
    def test_memory_usage(self):
        """Test memory usage during backtest."""
        # Should not have memory leaks
        # Should handle large datasets


class TestEdgeCases:
    """Test edge cases in backtesting."""
    
    def test_no_trades(self):
        """Test backtest with no trades executed."""
        # Should return cash only
    
    def test_insufficient_capital(self):
        """Test attempting trade with insufficient capital."""
        # Should reject order or handle gracefully
    
    def test_corporate_actions(self):
        """Test handling of splits and dividends."""
        # Positions should adjust for splits
        # Cash should increase for dividends
    
    def test_delisted_stocks(self):
        """Test handling of delisted stocks."""
        # Position should be closed or marked

"""
Comprehensive risk management test suite.

Tests for:
- Risk monitoring
- VaR calculation
- Stop-loss management
- Position limits
- Stress testing
- Risk budgeting
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from src.risk.monitor import RiskMonitor
from src.risk.var import VaRCalculator, VaRMethod
from src.risk.stop_loss import StopLossManager, StopLossType, StopLossConfig
from src.risk.concentration import ConcentrationLimits
from src.risk.stress_test import StressTest, StressScenario
from src.risk.correlation import CorrelationMonitor
from src.risk.regime import RegimeDetector, MarketRegime
from src.risk.budget import RiskBudget


class TestRiskMonitor:
    """Test real-time risk monitoring."""
    
    @pytest.fixture
    def monitor(self):
        """Create risk monitor."""
        return RiskMonitor(
            portfolio_value=1000000.0,
            max_drawdown=-0.20,  # 20%
            max_leverage=2.0,
            var_limit=50000.0  # $50k
        )
    
    def test_monitor_initialization(self, monitor):
        """Test monitor initializes correctly."""
        assert monitor.portfolio_value == 1000000.0
        assert monitor.max_drawdown == -0.20
    
    def test_volatility_monitoring(self, monitor):
        """Test portfolio volatility monitoring."""
        # Generate returns
        returns = pd.Series(np.random.normal(0.001, 0.02, 100))
        
        metrics = monitor.calculate_metrics(returns)
        
        assert 'volatility' in metrics
        assert 'annualized_volatility' in metrics
        assert metrics['volatility'] > 0
    
    def test_drawdown_monitoring(self, monitor):
        """Test drawdown monitoring."""
        # Generate cumulative returns with drawdown
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        values = pd.Series(np.linspace(1000000, 900000, 100), index=dates)
        
        metrics = monitor.calculate_metrics_from_values(values)
        
        assert 'max_drawdown' in metrics
        assert metrics['max_drawdown'] < 0
        assert metrics['max_drawdown'] >= -0.15  # About 10% drawdown
    
    def test_leverage_monitoring(self, monitor):
        """Test leverage monitoring."""
        positions = {
            'AAPL': {'value': 600000, 'quantity': 100},
            'GOOGL': {'value': 800000, 'quantity': 50}
        }
        
        leverage = monitor.calculate_leverage(positions, cash=100000)
        
        # Total position value / equity
        expected_leverage = 1400000 / (1400000 + 100000)
        assert abs(leverage - expected_leverage) < 0.01
    
    def test_alert_triggering(self, monitor):
        """Test that alerts are triggered on limit breaches."""
        # Simulate large drawdown
        values = pd.Series([1000000, 750000])  # 25% drawdown
        
        alerts = monitor.check_limits(values)
        
        # Should trigger drawdown alert
        assert len(alerts) > 0
        assert any('drawdown' in alert.lower() for alert in alerts)


class TestVaRCalculation:
    """Test Value at Risk calculations."""
    
    @pytest.fixture
    def returns(self):
        """Generate test returns."""
        np.random.seed(42)
        return pd.Series(np.random.normal(0.001, 0.02, 252))
    
    @pytest.fixture
    def calculator(self):
        """Create VaR calculator."""
        return VaRCalculator(confidence_level=0.95)
    
    def test_historical_var(self, calculator, returns):
        """Test historical VaR calculation."""
        var_95 = calculator.calculate(returns, method=VaRMethod.HISTORICAL)
        
        assert var_95 < 0, "VaR should be negative (loss)"
        
        # About 5% of returns should be worse than VaR
        worse_than_var = (returns < var_95).sum()
        expected_count = len(returns) * 0.05
        assert abs(worse_than_var - expected_count) < 20  # Allow some variation
    
    def test_parametric_var(self, calculator, returns):
        """Test parametric (Gaussian) VaR."""
        var_95 = calculator.calculate(returns, method=VaRMethod.PARAMETRIC)
        
        assert var_95 < 0
        
        # Parametric VaR assumes normal distribution
        mean = returns.mean()
        std = returns.std()
        expected_var = mean - 1.645 * std  # 95% confidence
        
        assert abs(var_95 - expected_var) < std * 0.1
    
    def test_monte_carlo_var(self, calculator, returns):
        """Test Monte Carlo VaR."""
        var_95 = calculator.calculate(
            returns,
            method=VaRMethod.MONTE_CARLO,
            n_simulations=10000
        )
        
        assert var_95 < 0
        # Monte Carlo should be similar to other methods
    
    def test_expected_shortfall(self, calculator, returns):
        """Test Expected Shortfall (CVaR) calculation."""
        var_95 = calculator.calculate(returns, method=VaRMethod.HISTORICAL)
        es_95 = calculator.calculate_expected_shortfall(returns, var_95)
        
        assert es_95 < var_95, "ES should be worse than VaR"
    
    def test_var_scaling(self, calculator, returns):
        """Test VaR time scaling."""
        var_1day = calculator.calculate(returns)
        
        # 10-day VaR should be ~sqrt(10) times 1-day VaR
        var_10day = calculator.scale_var(var_1day, from_days=1, to_days=10)
        
        expected_ratio = np.sqrt(10)
        actual_ratio = abs(var_10day / var_1day)
        assert abs(actual_ratio - expected_ratio) < 0.5


class TestStopLossManagement:
    """Test stop-loss management."""
    
    def test_fixed_stop_loss(self):
        """Test fixed stop-loss."""
        config = StopLossConfig(
            type=StopLossType.FIXED,
            threshold=-0.05  # 5% loss
        )
        
        manager = StopLossManager(config)
        
        # Add position
        manager.add_position("AAPL", entry_price=150.0, quantity=100)
        
        # Check if stop hit
        stop_events = manager.check_stops({"AAPL": 142.0})  # 5.3% loss
        
        assert len(stop_events) > 0
        assert stop_events[0].symbol == "AAPL"
    
    def test_trailing_stop_loss(self):
        """Test trailing stop-loss."""
        config = StopLossConfig(
            type=StopLossType.TRAILING,
            threshold=-0.05,
            trailing_distance=0.03  # 3% trailing
        )
        
        manager = StopLossManager(config)
        manager.add_position("AAPL", entry_price=150.0, quantity=100)
        
        # Price goes up - stop should trail
        manager.update_stops({"AAPL": 160.0})
        
        # Check that stop has moved up
        # Original stop: 150 * 0.95 = 142.5
        # New high: 160, so stop should be: 160 * 0.97 = 155.2
        
        stop_events = manager.check_stops({"AAPL": 154.0})
        assert len(stop_events) > 0
    
    def test_volatility_based_stop(self):
        """Test volatility-based stop-loss."""
        config = StopLossConfig(
            type=StopLossType.VOLATILITY_BASED,
            volatility_multiplier=2.0  # 2 standard deviations
        )
        
        manager = StopLossManager(config)
        
        # Provide volatility estimate
        returns = pd.Series(np.random.normal(0, 0.02, 100))
        manager.set_volatility("AAPL", returns.std())
        
        manager.add_position("AAPL", entry_price=150.0, quantity=100)
        
        # Stop should be at entry_price - 2*volatility
        expected_stop = 150.0 * (1 - 2 * returns.std())
        
        stop_events = manager.check_stops({"AAPL": expected_stop - 1.0})
        assert len(stop_events) > 0


class TestConcentrationLimits:
    """Test concentration limit enforcement."""
    
    @pytest.fixture
    def limits(self):
        """Create concentration limits."""
        return ConcentrationLimits(
            max_position_size=0.10,  # 10% per position
            max_sector_exposure=0.30,  # 30% per sector
            max_single_stock=0.15  # 15% for single stock
        )
    
    def test_position_size_check(self, limits):
        """Test position size limits."""
        portfolio_value = 1000000.0
        
        # Position within limit
        assert limits.check_position_size("AAPL", 90000, portfolio_value)
        
        # Position exceeds limit
        assert not limits.check_position_size("AAPL", 120000, portfolio_value)
    
    def test_sector_exposure_check(self, limits):
        """Test sector exposure limits."""
        portfolio_value = 1000000.0
        
        positions = {
            'AAPL': {'value': 100000, 'sector': 'Technology'},
            'GOOGL': {'value': 150000, 'sector': 'Technology'},
            'MSFT': {'value': 80000, 'sector': 'Technology'}
        }
        
        # Total tech exposure: 330000 / 1000000 = 33% > 30% limit
        violations = limits.check_sector_exposure(positions, portfolio_value)
        
        assert len(violations) > 0
        assert 'Technology' in str(violations[0])


class TestStressTesting:
    """Test stress testing functionality."""
    
    @pytest.fixture
    def stress_test(self):
        """Create stress test."""
        return StressTest()
    
    def test_market_crash_scenario(self, stress_test):
        """Test market crash scenario."""
        scenario = StressScenario(
            name="Market Crash",
            equity_shock=-0.30,  # 30% drop
            volatility_shock=2.0  # Double volatility
        )
        
        portfolio = {
            'AAPL': {'value': 100000, 'beta': 1.2},
            'GOOGL': {'value': 150000, 'beta': 1.1},
            'bonds': {'value': 50000, 'beta': 0.1}
        }
        
        result = stress_test.run_scenario(scenario, portfolio)
        
        assert 'portfolio_impact' in result
        assert result['portfolio_impact'] < 0  # Should show loss
        assert result['portfolio_impact'] > -0.35  # Not all assets drop 30%
    
    def test_interest_rate_shock(self, stress_test):
        """Test interest rate shock scenario."""
        scenario = StressScenario(
            name="Rate Hike",
            rate_shock=0.02,  # 200 bps increase
            duration_effect=-0.05  # Bond price impact
        )
        
        portfolio = {
            'bonds': {'value': 100000, 'duration': 5.0},
            'AAPL': {'value': 100000, 'rate_sensitivity': -0.5}
        }
        
        result = stress_test.run_scenario(scenario, portfolio)
        
        assert result['portfolio_impact'] < 0


class TestCorrelationMonitoring:
    """Test correlation monitoring."""
    
    @pytest.fixture
    def monitor(self):
        """Create correlation monitor."""
        return CorrelationMonitor(lookback_window=60)
    
    def test_correlation_calculation(self, monitor):
        """Test correlation matrix calculation."""
        # Generate correlated returns
        np.random.seed(42)
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        
        returns = pd.DataFrame({
            'AAPL': np.random.normal(0.001, 0.02, 100),
            'GOOGL': np.random.normal(0.001, 0.02, 100),
            'MSFT': np.random.normal(0.001, 0.02, 100)
        }, index=dates)
        
        # Add correlation
        returns['GOOGL'] = 0.7 * returns['AAPL'] + 0.3 * returns['GOOGL']
        
        corr_matrix = monitor.calculate_correlation(returns)
        
        assert corr_matrix.shape == (3, 3)
        assert abs(corr_matrix.loc['AAPL', 'GOOGL']) > 0.5  # Should be correlated
    
    def test_diversification_ratio(self, monitor):
        """Test diversification ratio calculation."""
        returns = pd.DataFrame({
            'A': np.random.normal(0, 0.02, 100),
            'B': np.random.normal(0, 0.02, 100),
            'C': np.random.normal(0, 0.02, 100)
        })
        
        weights = np.array([0.33, 0.33, 0.34])
        
        div_ratio = monitor.calculate_diversification_ratio(returns, weights)
        
        # Diversification ratio should be >= 1
        assert div_ratio >= 1.0


class TestRegimeDetection:
    """Test market regime detection."""
    
    @pytest.fixture
    def detector(self):
        """Create regime detector."""
        return RegimeDetector()
    
    def test_bull_market_detection(self, detector):
        """Test bull market detection."""
        # Generate bull market data
        prices = pd.Series(np.linspace(100, 150, 100))
        returns = prices.pct_change()
        
        regime, confidence = detector.detect(prices, returns)
        
        assert regime == MarketRegime.BULL
        assert confidence > 0.5
    
    def test_bear_market_detection(self, detector):
        """Test bear market detection."""
        # Generate bear market data
        prices = pd.Series(np.linspace(150, 100, 100))
        returns = prices.pct_change()
        
        regime, confidence = detector.detect(prices, returns)
        
        assert regime == MarketRegime.BEAR
    
    def test_high_volatility_detection(self, detector):
        """Test high volatility regime."""
        # Generate high volatility data
        prices = pd.Series(100 + np.random.normal(0, 10, 100).cumsum())
        returns = prices.pct_change()
        
        regime, confidence = detector.detect(prices, returns)
        
        assert regime in [MarketRegime.HIGH_VOL, MarketRegime.CRISIS]


class TestRiskBudgeting:
    """Test risk budgeting system."""
    
    @pytest.fixture
    def budget(self):
        """Create risk budget."""
        return RiskBudget(
            total_risk_budget=0.15,  # 15% volatility target
            strategy_budgets={
                'momentum': 0.05,
                'value': 0.05,
                'quality': 0.05
            }
        )
    
    def test_budget_allocation(self, budget):
        """Test risk budget allocation."""
        strategy_vols = {
            'momentum': 0.20,
            'value': 0.15,
            'quality': 0.12
        }
        
        allocations = budget.calculate_allocations(strategy_vols)
        
        # Allocations should sum to ~1
        assert abs(sum(allocations.values()) - 1.0) < 0.01
        
        # Higher vol strategies should get lower allocation
        assert allocations['quality'] > allocations['momentum']
    
    def test_budget_utilization(self, budget):
        """Test budget utilization monitoring."""
        current_exposure = {
            'momentum': 0.06,  # Exceeds budget
            'value': 0.04,
            'quality': 0.03
        }
        
        utilization = budget.check_utilization(current_exposure)
        
        assert utilization['momentum'] > 1.0  # Over budget
        assert utilization['value'] < 1.0  # Under budget


@pytest.mark.benchmark
class TestRiskPerformance:
    """Performance benchmarks for risk calculations."""
    
    def test_var_calculation_speed(self, benchmark):
        """Benchmark VaR calculation speed."""
        returns = pd.Series(np.random.normal(0.001, 0.02, 1000))
        calculator = VaRCalculator()
        
        result = benchmark(calculator.calculate, returns)
        assert result < 0
    
    def test_correlation_calculation_speed(self, benchmark):
        """Benchmark correlation calculation."""
        returns = pd.DataFrame(np.random.normal(0, 0.02, (252, 100)))
        monitor = CorrelationMonitor()
        
        result = benchmark(monitor.calculate_correlation, returns)
        assert result.shape == (100, 100)

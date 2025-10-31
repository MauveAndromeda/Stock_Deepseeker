"""
Risk Calculator Module

Comprehensive risk metrics calculation system for portfolio and position analysis.
Implements multiple VaR methodologies, risk-adjusted returns, and stress testing.

Author: Stock_Deepseeker Team
Version: 1.0.0
"""

import logging
import warnings
from typing import Dict, List, Optional, Tuple, Union, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
import json

logger = logging.getLogger(__name__)


class VaRMethod(Enum):
    """Value at Risk calculation methods"""
    HISTORICAL = "historical"
    PARAMETRIC = "parametric"
    MONTE_CARLO = "monte_carlo"
    CORNISH_FISHER = "cornish_fisher"


class StressScenario(Enum):
    """Pre-defined stress testing scenarios"""
    MARKET_CRASH = "market_crash"
    VOLATILITY_SPIKE = "volatility_spike"
    CORRELATION_BREAKDOWN = "correlation_breakdown"
    LIQUIDITY_CRISIS = "liquidity_crisis"
    SECTOR_SHOCK = "sector_shock"
    CUSTOM = "custom"


@dataclass
class RiskMetrics:
    """Container for calculated risk metrics"""
    timestamp: datetime
    portfolio_value: float
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    max_drawdown: float
    current_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    volatility: float
    beta: float
    alpha: float
    correlation_to_benchmark: float
    var_method: str
    confidence_level: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'portfolio_value': self.portfolio_value,
            'var_95': self.var_95,
            'var_99': self.var_99,
            'cvar_95': self.cvar_95,
            'cvar_99': self.cvar_99,
            'max_drawdown': self.max_drawdown,
            'current_drawdown': self.current_drawdown,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'calmar_ratio': self.calmar_ratio,
            'volatility': self.volatility,
            'beta': self.beta,
            'alpha': self.alpha,
            'correlation_to_benchmark': self.correlation_to_benchmark,
            'var_method': self.var_method,
            'confidence_level': self.confidence_level
        }


@dataclass
class StressTestResult:
    """Results from stress testing scenarios"""
    scenario_name: str
    scenario_type: StressScenario
    expected_loss: float
    expected_loss_pct: float
    var_increase: float
    volatility_increase: float
    correlation_change: float
    affected_positions: List[str]
    severity_score: float
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'scenario_name': self.scenario_name,
            'scenario_type': self.scenario_type.value,
            'expected_loss': self.expected_loss,
            'expected_loss_pct': self.expected_loss_pct,
            'var_increase': self.var_increase,
            'volatility_increase': self.volatility_increase,
            'correlation_change': self.correlation_change,
            'affected_positions': self.affected_positions,
            'severity_score': self.severity_score,
            'timestamp': self.timestamp.isoformat()
        }


class RiskCalculator:
    """
    Comprehensive risk metrics calculator for portfolio analysis.

    Features:
    - Multiple VaR methodologies (Historical, Parametric, Monte Carlo)
    - CVaR (Expected Shortfall) calculation
    - Maximum drawdown tracking
    - Risk-adjusted performance ratios
    - Portfolio Greeks (Beta, Alpha)
    - Correlation and covariance analysis
    - Stress testing scenarios
    - Real-time risk monitoring
    """

    def __init__(
        self,
        lookback_period: int = 252,
        var_confidence_levels: List[float] = None,
        risk_free_rate: float = 0.02,
        min_data_points: int = 30,
        monte_carlo_simulations: int = 10000,
        enable_alerts: bool = True
    ):
        """
        Initialize Risk Calculator.

        Args:
            lookback_period: Number of days for historical analysis
            var_confidence_levels: List of confidence levels for VaR (default: [0.95, 0.99])
            risk_free_rate: Annual risk-free rate for ratio calculations
            min_data_points: Minimum required data points for calculations
            monte_carlo_simulations: Number of simulations for Monte Carlo VaR
            enable_alerts: Enable risk alert logging
        """
        self.lookback_period = lookback_period
        self.var_confidence_levels = var_confidence_levels or [0.95, 0.99]
        self.risk_free_rate = risk_free_rate
        self.min_data_points = min_data_points
        self.monte_carlo_simulations = monte_carlo_simulations
        self.enable_alerts = enable_alerts

        # Cache for performance
        self._correlation_matrix_cache = {}
        self._covariance_matrix_cache = {}
        self._last_cache_update = None
        self._cache_ttl = timedelta(hours=1)

        # Historical tracking
        self.portfolio_history = []
        self.drawdown_history = []
        self.returns_history = []

        logger.info(f"RiskCalculator initialized with lookback={lookback_period}, "
                   f"VaR levels={var_confidence_levels}")

    def calculate_var(
        self,
        returns: Union[np.ndarray, pd.Series, List[float]],
        method: VaRMethod = VaRMethod.HISTORICAL,
        confidence_level: float = 0.95,
        portfolio_value: float = None
    ) -> float:
        """
        Calculate Value at Risk using specified method.

        Args:
            returns: Array of historical returns
            method: VaR calculation method
            confidence_level: Confidence level (e.g., 0.95 for 95% VaR)
            portfolio_value: Current portfolio value for absolute VaR

        Returns:
            Value at Risk (loss amount)
        """
        try:
            returns = self._validate_returns(returns)

            if len(returns) < self.min_data_points:
                logger.warning(f"Insufficient data points: {len(returns)} < {self.min_data_points}")
                return 0.0

            if method == VaRMethod.HISTORICAL:
                var = self._calculate_historical_var(returns, confidence_level)
            elif method == VaRMethod.PARAMETRIC:
                var = self._calculate_parametric_var(returns, confidence_level)
            elif method == VaRMethod.MONTE_CARLO:
                var = self._calculate_monte_carlo_var(returns, confidence_level)
            elif method == VaRMethod.CORNISH_FISHER:
                var = self._calculate_cornish_fisher_var(returns, confidence_level)
            else:
                raise ValueError(f"Unknown VaR method: {method}")

            # Convert to absolute value if portfolio value provided
            if portfolio_value:
                var = abs(var * portfolio_value)

            logger.debug(f"VaR calculated: {var:.2f} using {method.value} method")
            return var

        except Exception as e:
            logger.error(f"Error calculating VaR: {e}", exc_info=True)
            return 0.0

    def _calculate_historical_var(self, returns: np.ndarray, confidence_level: float) -> float:
        """Calculate VaR using historical simulation method"""
        sorted_returns = np.sort(returns)
        index = int((1 - confidence_level) * len(sorted_returns))
        var = abs(sorted_returns[index])
        return var

    def _calculate_parametric_var(self, returns: np.ndarray, confidence_level: float) -> float:
        """Calculate VaR using parametric (variance-covariance) method"""
        mu = np.mean(returns)
        sigma = np.std(returns)
        z_score = stats.norm.ppf(1 - confidence_level)
        var = abs(mu + sigma * z_score)
        return var

    def _calculate_monte_carlo_var(self, returns: np.ndarray, confidence_level: float) -> float:
        """Calculate VaR using Monte Carlo simulation"""
        mu = np.mean(returns)
        sigma = np.std(returns)

        # Generate random returns
        simulated_returns = np.random.normal(mu, sigma, self.monte_carlo_simulations)

        # Calculate VaR from simulated returns
        sorted_returns = np.sort(simulated_returns)
        index = int((1 - confidence_level) * len(sorted_returns))
        var = abs(sorted_returns[index])
        return var

    def _calculate_cornish_fisher_var(self, returns: np.ndarray, confidence_level: float) -> float:
        """Calculate VaR using Cornish-Fisher expansion (accounts for skewness and kurtosis)"""
        mu = np.mean(returns)
        sigma = np.std(returns)
        skew = stats.skew(returns)
        kurt = stats.kurtosis(returns)

        z = stats.norm.ppf(1 - confidence_level)

        # Cornish-Fisher adjustment
        z_cf = (z +
                (z**2 - 1) * skew / 6 +
                (z**3 - 3*z) * kurt / 24 -
                (2*z**3 - 5*z) * skew**2 / 36)

        var = abs(mu + sigma * z_cf)
        return var

    def calculate_cvar(
        self,
        returns: Union[np.ndarray, pd.Series, List[float]],
        confidence_level: float = 0.95,
        portfolio_value: float = None
    ) -> float:
        """
        Calculate Conditional Value at Risk (Expected Shortfall).

        CVaR is the expected loss given that the loss exceeds VaR.

        Args:
            returns: Array of historical returns
            confidence_level: Confidence level
            portfolio_value: Current portfolio value for absolute CVaR

        Returns:
            Conditional VaR (expected loss in tail)
        """
        try:
            returns = self._validate_returns(returns)

            if len(returns) < self.min_data_points:
                return 0.0

            # Sort returns (ascending)
            sorted_returns = np.sort(returns)

            # Find VaR threshold
            var_index = int((1 - confidence_level) * len(sorted_returns))

            # CVaR is the average of all returns below VaR
            tail_returns = sorted_returns[:var_index + 1]
            cvar = abs(np.mean(tail_returns))

            # Convert to absolute value if portfolio value provided
            if portfolio_value:
                cvar = cvar * portfolio_value

            logger.debug(f"CVaR calculated: {cvar:.2f} at {confidence_level} confidence")
            return cvar

        except Exception as e:
            logger.error(f"Error calculating CVaR: {e}", exc_info=True)
            return 0.0

    def calculate_maximum_drawdown(
        self,
        portfolio_values: Union[np.ndarray, pd.Series, List[float]]
    ) -> Tuple[float, float, int, int]:
        """
        Calculate maximum drawdown from peak.

        Args:
            portfolio_values: Time series of portfolio values

        Returns:
            Tuple of (max_drawdown, current_drawdown, peak_idx, trough_idx)
        """
        try:
            values = np.array(portfolio_values)

            if len(values) < 2:
                return 0.0, 0.0, 0, 0

            # Calculate running maximum
            running_max = np.maximum.accumulate(values)

            # Calculate drawdown at each point
            drawdowns = (values - running_max) / running_max

            # Find maximum drawdown
            max_dd_idx = np.argmin(drawdowns)
            max_drawdown = abs(drawdowns[max_dd_idx])

            # Find peak before maximum drawdown
            peak_idx = np.argmax(values[:max_dd_idx + 1]) if max_dd_idx > 0 else 0

            # Current drawdown
            current_drawdown = abs(drawdowns[-1])

            # Store drawdown history
            self.drawdown_history.append({
                'timestamp': datetime.now(),
                'drawdown': current_drawdown,
                'max_drawdown': max_drawdown
            })

            return max_drawdown, current_drawdown, peak_idx, max_dd_idx

        except Exception as e:
            logger.error(f"Error calculating drawdown: {e}", exc_info=True)
            return 0.0, 0.0, 0, 0

    def calculate_sharpe_ratio(
        self,
        returns: Union[np.ndarray, pd.Series, List[float]],
        risk_free_rate: float = None,
        periods_per_year: int = 252
    ) -> float:
        """
        Calculate Sharpe ratio (risk-adjusted return).

        Args:
            returns: Array of returns
            risk_free_rate: Annual risk-free rate (uses instance default if None)
            periods_per_year: Number of periods per year (252 for daily)

        Returns:
            Sharpe ratio
        """
        try:
            returns = self._validate_returns(returns)

            if len(returns) < self.min_data_points:
                return 0.0

            rf_rate = risk_free_rate if risk_free_rate is not None else self.risk_free_rate

            # Annualized return
            mean_return = np.mean(returns) * periods_per_year

            # Annualized volatility
            volatility = np.std(returns) * np.sqrt(periods_per_year)

            # Sharpe ratio
            if volatility == 0:
                return 0.0

            sharpe = (mean_return - rf_rate) / volatility

            return sharpe

        except Exception as e:
            logger.error(f"Error calculating Sharpe ratio: {e}", exc_info=True)
            return 0.0

    def calculate_sortino_ratio(
        self,
        returns: Union[np.ndarray, pd.Series, List[float]],
        risk_free_rate: float = None,
        periods_per_year: int = 252
    ) -> float:
        """
        Calculate Sortino ratio (Sharpe ratio using only downside deviation).

        Args:
            returns: Array of returns
            risk_free_rate: Annual risk-free rate
            periods_per_year: Number of periods per year

        Returns:
            Sortino ratio
        """
        try:
            returns = self._validate_returns(returns)

            if len(returns) < self.min_data_points:
                return 0.0

            rf_rate = risk_free_rate if risk_free_rate is not None else self.risk_free_rate

            # Annualized return
            mean_return = np.mean(returns) * periods_per_year

            # Downside deviation (only negative returns)
            downside_returns = returns[returns < 0]

            if len(downside_returns) == 0:
                return float('inf')  # No downside risk

            downside_std = np.std(downside_returns) * np.sqrt(periods_per_year)

            if downside_std == 0:
                return 0.0

            sortino = (mean_return - rf_rate) / downside_std

            return sortino

        except Exception as e:
            logger.error(f"Error calculating Sortino ratio: {e}", exc_info=True)
            return 0.0

    def calculate_calmar_ratio(
        self,
        returns: Union[np.ndarray, pd.Series, List[float]],
        portfolio_values: Union[np.ndarray, pd.Series, List[float]] = None,
        periods_per_year: int = 252
    ) -> float:
        """
        Calculate Calmar ratio (return / maximum drawdown).

        Args:
            returns: Array of returns
            portfolio_values: Portfolio values for drawdown calculation
            periods_per_year: Number of periods per year

        Returns:
            Calmar ratio
        """
        try:
            returns = self._validate_returns(returns)

            if len(returns) < self.min_data_points:
                return 0.0

            # Annualized return
            mean_return = np.mean(returns) * periods_per_year

            # Calculate maximum drawdown
            if portfolio_values is not None:
                max_dd, _, _, _ = self.calculate_maximum_drawdown(portfolio_values)
            else:
                # Construct portfolio values from returns
                cumulative_returns = np.cumprod(1 + returns)
                max_dd, _, _, _ = self.calculate_maximum_drawdown(cumulative_returns)

            if max_dd == 0:
                return float('inf')  # No drawdown

            calmar = mean_return / max_dd

            return calmar

        except Exception as e:
            logger.error(f"Error calculating Calmar ratio: {e}", exc_info=True)
            return 0.0

    def calculate_beta(
        self,
        portfolio_returns: Union[np.ndarray, pd.Series, List[float]],
        benchmark_returns: Union[np.ndarray, pd.Series, List[float]]
    ) -> float:
        """
        Calculate portfolio beta relative to benchmark.

        Args:
            portfolio_returns: Portfolio returns
            benchmark_returns: Benchmark returns

        Returns:
            Beta coefficient
        """
        try:
            portfolio_returns = self._validate_returns(portfolio_returns)
            benchmark_returns = self._validate_returns(benchmark_returns)

            if len(portfolio_returns) != len(benchmark_returns):
                logger.warning("Portfolio and benchmark returns have different lengths")
                min_len = min(len(portfolio_returns), len(benchmark_returns))
                portfolio_returns = portfolio_returns[-min_len:]
                benchmark_returns = benchmark_returns[-min_len:]

            # Calculate covariance and variance
            covariance = np.cov(portfolio_returns, benchmark_returns)[0, 1]
            benchmark_variance = np.var(benchmark_returns)

            if benchmark_variance == 0:
                return 0.0

            beta = covariance / benchmark_variance

            return beta

        except Exception as e:
            logger.error(f"Error calculating beta: {e}", exc_info=True)
            return 1.0  # Neutral beta

    def calculate_alpha(
        self,
        portfolio_returns: Union[np.ndarray, pd.Series, List[float]],
        benchmark_returns: Union[np.ndarray, pd.Series, List[float]],
        risk_free_rate: float = None,
        periods_per_year: int = 252
    ) -> float:
        """
        Calculate Jensen's alpha.

        Args:
            portfolio_returns: Portfolio returns
            benchmark_returns: Benchmark returns
            risk_free_rate: Annual risk-free rate
            periods_per_year: Number of periods per year

        Returns:
            Alpha (annualized excess return)
        """
        try:
            portfolio_returns = self._validate_returns(portfolio_returns)
            benchmark_returns = self._validate_returns(benchmark_returns)

            rf_rate = risk_free_rate if risk_free_rate is not None else self.risk_free_rate

            # Calculate beta
            beta = self.calculate_beta(portfolio_returns, benchmark_returns)

            # Annualized returns
            portfolio_return = np.mean(portfolio_returns) * periods_per_year
            benchmark_return = np.mean(benchmark_returns) * periods_per_year

            # Jensen's alpha
            alpha = portfolio_return - (rf_rate + beta * (benchmark_return - rf_rate))

            return alpha

        except Exception as e:
            logger.error(f"Error calculating alpha: {e}", exc_info=True)
            return 0.0

    def calculate_correlation(
        self,
        returns1: Union[np.ndarray, pd.Series, List[float]],
        returns2: Union[np.ndarray, pd.Series, List[float]]
    ) -> float:
        """
        Calculate correlation between two return series.

        Args:
            returns1: First return series
            returns2: Second return series

        Returns:
            Correlation coefficient
        """
        try:
            returns1 = self._validate_returns(returns1)
            returns2 = self._validate_returns(returns2)

            if len(returns1) != len(returns2):
                min_len = min(len(returns1), len(returns2))
                returns1 = returns1[-min_len:]
                returns2 = returns2[-min_len:]

            correlation = np.corrcoef(returns1, returns2)[0, 1]

            return correlation

        except Exception as e:
            logger.error(f"Error calculating correlation: {e}", exc_info=True)
            return 0.0

    def calculate_correlation_matrix(
        self,
        returns_dict: Dict[str, Union[np.ndarray, pd.Series]],
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Calculate correlation matrix for multiple assets.

        Args:
            returns_dict: Dictionary of {symbol: returns}
            use_cache: Use cached result if available

        Returns:
            Correlation matrix DataFrame
        """
        try:
            # Check cache
            cache_key = frozenset(returns_dict.keys())
            if use_cache and cache_key in self._correlation_matrix_cache:
                if datetime.now() - self._last_cache_update < self._cache_ttl:
                    return self._correlation_matrix_cache[cache_key]

            # Convert to DataFrame
            returns_df = pd.DataFrame(returns_dict)

            # Calculate correlation matrix
            corr_matrix = returns_df.corr()

            # Update cache
            self._correlation_matrix_cache[cache_key] = corr_matrix
            self._last_cache_update = datetime.now()

            return corr_matrix

        except Exception as e:
            logger.error(f"Error calculating correlation matrix: {e}", exc_info=True)
            return pd.DataFrame()

    def calculate_covariance_matrix(
        self,
        returns_dict: Dict[str, Union[np.ndarray, pd.Series]],
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Calculate covariance matrix for multiple assets.

        Args:
            returns_dict: Dictionary of {symbol: returns}
            use_cache: Use cached result if available

        Returns:
            Covariance matrix DataFrame
        """
        try:
            # Check cache
            cache_key = frozenset(returns_dict.keys())
            if use_cache and cache_key in self._covariance_matrix_cache:
                if datetime.now() - self._last_cache_update < self._cache_ttl:
                    return self._covariance_matrix_cache[cache_key]

            # Convert to DataFrame
            returns_df = pd.DataFrame(returns_dict)

            # Calculate covariance matrix
            cov_matrix = returns_df.cov()

            # Update cache
            self._covariance_matrix_cache[cache_key] = cov_matrix
            self._last_cache_update = datetime.now()

            return cov_matrix

        except Exception as e:
            logger.error(f"Error calculating covariance matrix: {e}", exc_info=True)
            return pd.DataFrame()

    def calculate_portfolio_volatility(
        self,
        weights: Dict[str, float],
        returns_dict: Dict[str, Union[np.ndarray, pd.Series]],
        periods_per_year: int = 252
    ) -> float:
        """
        Calculate portfolio volatility (standard deviation).

        Args:
            weights: Dictionary of {symbol: weight}
            returns_dict: Dictionary of {symbol: returns}
            periods_per_year: Number of periods per year

        Returns:
            Annualized portfolio volatility
        """
        try:
            # Get covariance matrix
            cov_matrix = self.calculate_covariance_matrix(returns_dict)

            # Convert weights to array in same order as covariance matrix
            symbols = list(cov_matrix.columns)
            weight_array = np.array([weights.get(s, 0.0) for s in symbols])

            # Portfolio variance: w' * Cov * w
            portfolio_variance = np.dot(weight_array.T, np.dot(cov_matrix.values, weight_array))

            # Annualized volatility
            portfolio_vol = np.sqrt(portfolio_variance) * np.sqrt(periods_per_year)

            return portfolio_vol

        except Exception as e:
            logger.error(f"Error calculating portfolio volatility: {e}", exc_info=True)
            return 0.0

    def run_stress_test(
        self,
        positions: Dict[str, Dict[str, float]],
        scenario: StressScenario,
        custom_shocks: Dict[str, float] = None
    ) -> StressTestResult:
        """
        Run stress test scenario on portfolio.

        Args:
            positions: Dictionary of {symbol: {'value': value, 'returns': returns}}
            scenario: Stress test scenario type
            custom_shocks: Custom shock values for positions

        Returns:
            StressTestResult object
        """
        try:
            if scenario == StressScenario.MARKET_CRASH:
                shocks = self._get_market_crash_shocks(positions)
                scenario_name = "Market Crash (-30%)"
            elif scenario == StressScenario.VOLATILITY_SPIKE:
                shocks = self._get_volatility_spike_shocks(positions)
                scenario_name = "Volatility Spike (3x)"
            elif scenario == StressScenario.CORRELATION_BREAKDOWN:
                shocks = self._get_correlation_breakdown_shocks(positions)
                scenario_name = "Correlation Breakdown"
            elif scenario == StressScenario.LIQUIDITY_CRISIS:
                shocks = self._get_liquidity_crisis_shocks(positions)
                scenario_name = "Liquidity Crisis"
            elif scenario == StressScenario.SECTOR_SHOCK:
                shocks = self._get_sector_shock_shocks(positions)
                scenario_name = "Sector Shock (-50%)"
            elif scenario == StressScenario.CUSTOM:
                shocks = custom_shocks or {}
                scenario_name = "Custom Stress Test"
            else:
                raise ValueError(f"Unknown scenario: {scenario}")

            # Calculate expected losses
            total_loss = 0.0
            affected_positions = []

            for symbol, shock in shocks.items():
                if symbol in positions:
                    position_value = positions[symbol].get('value', 0.0)
                    loss = position_value * shock
                    total_loss += loss
                    affected_positions.append(symbol)

            # Calculate portfolio value
            portfolio_value = sum(p.get('value', 0.0) for p in positions.values())
            loss_pct = (total_loss / portfolio_value * 100) if portfolio_value > 0 else 0.0

            # Calculate VaR increase (simplified)
            var_increase = abs(total_loss) * 1.5

            # Calculate volatility increase
            vol_increase = 2.0 if scenario == StressScenario.VOLATILITY_SPIKE else 1.3

            # Calculate severity score (0-10)
            severity = min(10.0, abs(loss_pct) / 10)

            result = StressTestResult(
                scenario_name=scenario_name,
                scenario_type=scenario,
                expected_loss=total_loss,
                expected_loss_pct=loss_pct,
                var_increase=var_increase,
                volatility_increase=vol_increase,
                correlation_change=0.2,  # Simplified
                affected_positions=affected_positions,
                severity_score=severity,
                timestamp=datetime.now()
            )

            logger.info(f"Stress test completed: {scenario_name}, Loss: {loss_pct:.2f}%")

            return result

        except Exception as e:
            logger.error(f"Error running stress test: {e}", exc_info=True)
            return None

    def _get_market_crash_shocks(self, positions: Dict) -> Dict[str, float]:
        """Generate market crash shocks (-30% across board)"""
        return {symbol: -0.30 for symbol in positions.keys()}

    def _get_volatility_spike_shocks(self, positions: Dict) -> Dict[str, float]:
        """Generate volatility spike shocks (random with high variance)"""
        np.random.seed(42)
        return {symbol: np.random.normal(-0.15, 0.25) for symbol in positions.keys()}

    def _get_correlation_breakdown_shocks(self, positions: Dict) -> Dict[str, float]:
        """Generate correlation breakdown shocks (divergent movements)"""
        np.random.seed(42)
        shocks = {}
        for i, symbol in enumerate(positions.keys()):
            # Alternate between large positive and negative shocks
            shocks[symbol] = 0.20 if i % 2 == 0 else -0.20
        return shocks

    def _get_liquidity_crisis_shocks(self, positions: Dict) -> Dict[str, float]:
        """Generate liquidity crisis shocks (-20% with bid-ask widening)"""
        return {symbol: -0.20 for symbol in positions.keys()}

    def _get_sector_shock_shocks(self, positions: Dict) -> Dict[str, float]:
        """Generate sector-specific shocks"""
        # Simplified: apply -50% to first half of positions
        shocks = {}
        symbols = list(positions.keys())
        mid_point = len(symbols) // 2

        for i, symbol in enumerate(symbols):
            shocks[symbol] = -0.50 if i < mid_point else -0.05

        return shocks

    def calculate_comprehensive_metrics(
        self,
        portfolio_value: float,
        returns: Union[np.ndarray, pd.Series],
        benchmark_returns: Union[np.ndarray, pd.Series] = None,
        portfolio_values: Union[np.ndarray, pd.Series] = None
    ) -> RiskMetrics:
        """
        Calculate comprehensive risk metrics for portfolio.

        Args:
            portfolio_value: Current portfolio value
            returns: Portfolio returns
            benchmark_returns: Benchmark returns (optional)
            portfolio_values: Historical portfolio values (optional)

        Returns:
            RiskMetrics object with all calculated metrics
        """
        try:
            returns = self._validate_returns(returns)

            # Calculate VaR
            var_95 = self.calculate_var(returns, VaRMethod.HISTORICAL, 0.95, portfolio_value)
            var_99 = self.calculate_var(returns, VaRMethod.HISTORICAL, 0.99, portfolio_value)

            # Calculate CVaR
            cvar_95 = self.calculate_cvar(returns, 0.95, portfolio_value)
            cvar_99 = self.calculate_cvar(returns, 0.99, portfolio_value)

            # Calculate drawdowns
            if portfolio_values is not None:
                max_dd, current_dd, _, _ = self.calculate_maximum_drawdown(portfolio_values)
            else:
                max_dd, current_dd = 0.0, 0.0

            # Calculate ratios
            sharpe = self.calculate_sharpe_ratio(returns)
            sortino = self.calculate_sortino_ratio(returns)
            calmar = self.calculate_calmar_ratio(returns, portfolio_values)

            # Calculate volatility
            volatility = np.std(returns) * np.sqrt(252)

            # Calculate Greeks (if benchmark provided)
            if benchmark_returns is not None:
                benchmark_returns = self._validate_returns(benchmark_returns)
                beta = self.calculate_beta(returns, benchmark_returns)
                alpha = self.calculate_alpha(returns, benchmark_returns)
                correlation = self.calculate_correlation(returns, benchmark_returns)
            else:
                beta, alpha, correlation = 0.0, 0.0, 0.0

            metrics = RiskMetrics(
                timestamp=datetime.now(),
                portfolio_value=portfolio_value,
                var_95=var_95,
                var_99=var_99,
                cvar_95=cvar_95,
                cvar_99=cvar_99,
                max_drawdown=max_dd,
                current_drawdown=current_dd,
                sharpe_ratio=sharpe,
                sortino_ratio=sortino,
                calmar_ratio=calmar,
                volatility=volatility,
                beta=beta,
                alpha=alpha,
                correlation_to_benchmark=correlation,
                var_method=VaRMethod.HISTORICAL.value,
                confidence_level=0.95
            )

            logger.info(f"Comprehensive metrics calculated: VaR95={var_95:.2f}, "
                       f"Sharpe={sharpe:.2f}, MaxDD={max_dd:.2%}")

            return metrics

        except Exception as e:
            logger.error(f"Error calculating comprehensive metrics: {e}", exc_info=True)
            return None

    def _validate_returns(self, returns: Union[np.ndarray, pd.Series, List[float]]) -> np.ndarray:
        """Validate and convert returns to numpy array"""
        if isinstance(returns, pd.Series):
            returns = returns.values
        elif isinstance(returns, list):
            returns = np.array(returns)

        # Remove NaN values
        returns = returns[~np.isnan(returns)]

        # Remove infinite values
        returns = returns[~np.isinf(returns)]

        return returns

    def clear_cache(self):
        """Clear correlation and covariance matrix caches"""
        self._correlation_matrix_cache.clear()
        self._covariance_matrix_cache.clear()
        logger.info("Risk calculator caches cleared")

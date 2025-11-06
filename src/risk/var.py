"""
Value at Risk (VaR) and Expected Shortfall (ES) calculations.

Multiple methodologies: Historical, Parametric, Monte Carlo.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
import pandas as pd
import numpy as np
from loguru import logger
from scipy import stats


class VaRMethod(Enum):
    """VaR calculation methods."""
    HISTORICAL = "historical"
    PARAMETRIC = "parametric"
    MONTE_CARLO = "monte_carlo"
    CORNISH_FISHER = "cornish_fisher"


@dataclass
class VaRResult:
    """
    VaR calculation result.
    
    Attributes:
        var_95: 95% Value at Risk
        var_99: 99% Value at Risk
        var_99_5: 99.5% Value at Risk
        expected_shortfall_95: ES at 95%
        expected_shortfall_99: ES at 99%
        method: Calculation method used
        timestamp: Calculation time
        lookback_days: Days of history used
    """
    var_95: float
    var_99: float
    var_99_5: float
    expected_shortfall_95: float
    expected_shortfall_99: float
    method: VaRMethod
    timestamp: datetime
    lookback_days: int


class VaRCalculator:
    """
    VaR calculator with multiple methodologies.
    """
    
    def __init__(
        self,
        method: VaRMethod = VaRMethod.HISTORICAL,
        confidence_levels: List[float] = None,
        lookback_days: int = 252,
        monte_carlo_simulations: int = 10000
    ) -> None:
        """Initialize VaR calculator."""
        self.method = method
        self.confidence_levels = confidence_levels or [0.95, 0.99, 0.995]
        self.lookback_days = lookback_days
        self.monte_carlo_simulations = monte_carlo_simulations
        
        logger.info(f"Initialized VaRCalculator: method={method.value}")
    
    def calculate(
        self,
        returns: pd.Series,
        portfolio_value: float
    ) -> VaRResult:
        """Calculate VaR using configured method."""
        if self.method == VaRMethod.HISTORICAL:
            return self._historical_var(returns, portfolio_value)
        elif self.method == VaRMethod.PARAMETRIC:
            return self._parametric_var(returns, portfolio_value)
        elif self.method == VaRMethod.MONTE_CARLO:
            return self._monte_carlo_var(returns, portfolio_value)
        elif self.method == VaRMethod.CORNISH_FISHER:
            return self._cornish_fisher_var(returns, portfolio_value)
        else:
            raise ValueError(f"Unknown VaR method: {self.method}")
    
    def _historical_var(
        self,
        returns: pd.Series,
        portfolio_value: float
    ) -> VaRResult:
        """Historical simulation VaR."""
        returns_data = returns.tail(self.lookback_days)
        
        var_95 = returns_data.quantile(0.05) * portfolio_value
        var_99 = returns_data.quantile(0.01) * portfolio_value
        var_99_5 = returns_data.quantile(0.005) * portfolio_value
        
        # Expected Shortfall
        es_95 = returns_data[returns_data <= returns_data.quantile(0.05)].mean() * portfolio_value
        es_99 = returns_data[returns_data <= returns_data.quantile(0.01)].mean() * portfolio_value
        
        return VaRResult(
            var_95=var_95,
            var_99=var_99,
            var_99_5=var_99_5,
            expected_shortfall_95=es_95,
            expected_shortfall_99=es_99,
            method=VaRMethod.HISTORICAL,
            timestamp=datetime.now(),
            lookback_days=len(returns_data)
        )
    
    def _parametric_var(
        self,
        returns: pd.Series,
        portfolio_value: float
    ) -> VaRResult:
        """Parametric VaR (assumes normal distribution)."""
        returns_data = returns.tail(self.lookback_days)
        
        mean = returns_data.mean()
        std = returns_data.std()
        
        # VaR = mean + z * std
        var_95 = (mean + stats.norm.ppf(0.05) * std) * portfolio_value
        var_99 = (mean + stats.norm.ppf(0.01) * std) * portfolio_value
        var_99_5 = (mean + stats.norm.ppf(0.005) * std) * portfolio_value
        
        # Expected Shortfall (analytical)
        es_95 = (mean - std * stats.norm.pdf(stats.norm.ppf(0.05)) / 0.05) * portfolio_value
        es_99 = (mean - std * stats.norm.pdf(stats.norm.ppf(0.01)) / 0.01) * portfolio_value
        
        return VaRResult(
            var_95=var_95,
            var_99=var_99,
            var_99_5=var_99_5,
            expected_shortfall_95=es_95,
            expected_shortfall_99=es_99,
            method=VaRMethod.PARAMETRIC,
            timestamp=datetime.now(),
            lookback_days=len(returns_data)
        )
    
    def _monte_carlo_var(
        self,
        returns: pd.Series,
        portfolio_value: float
    ) -> VaRResult:
        """Monte Carlo simulation VaR."""
        returns_data = returns.tail(self.lookback_days)
        
        mean = returns_data.mean()
        std = returns_data.std()
        
        # Generate simulations
        simulated_returns = np.random.normal(
            mean, std, self.monte_carlo_simulations
        )
        
        # Calculate VaR
        var_95 = np.percentile(simulated_returns, 5) * portfolio_value
        var_99 = np.percentile(simulated_returns, 1) * portfolio_value
        var_99_5 = np.percentile(simulated_returns, 0.5) * portfolio_value
        
        # Expected Shortfall
        es_95 = simulated_returns[simulated_returns <= np.percentile(simulated_returns, 5)].mean() * portfolio_value
        es_99 = simulated_returns[simulated_returns <= np.percentile(simulated_returns, 1)].mean() * portfolio_value
        
        return VaRResult(
            var_95=var_95,
            var_99=var_99,
            var_99_5=var_99_5,
            expected_shortfall_95=es_95,
            expected_shortfall_99=es_99,
            method=VaRMethod.MONTE_CARLO,
            timestamp=datetime.now(),
            lookback_days=len(returns_data)
        )
    
    def _cornish_fisher_var(
        self,
        returns: pd.Series,
        portfolio_value: float
    ) -> VaRResult:
        """Cornish-Fisher expansion VaR (accounts for skewness/kurtosis)."""
        returns_data = returns.tail(self.lookback_days)
        
        mean = returns_data.mean()
        std = returns_data.std()
        skew = returns_data.skew()
        kurt = returns_data.kurtosis()
        
        # Cornish-Fisher quantile
        def cf_quantile(alpha):
            z = stats.norm.ppf(alpha)
            z_cf = z + (z**2 - 1) * skew / 6 + \
                   (z**3 - 3*z) * kurt / 24 - \
                   (2*z**3 - 5*z) * skew**2 / 36
            return mean + z_cf * std
        
        var_95 = cf_quantile(0.05) * portfolio_value
        var_99 = cf_quantile(0.01) * portfolio_value
        var_99_5 = cf_quantile(0.005) * portfolio_value
        
        # Use historical ES (CF doesn't have analytical ES)
        es_95 = returns_data[returns_data <= returns_data.quantile(0.05)].mean() * portfolio_value
        es_99 = returns_data[returns_data <= returns_data.quantile(0.01)].mean() * portfolio_value
        
        return VaRResult(
            var_95=var_95,
            var_99=var_99,
            var_99_5=var_99_5,
            expected_shortfall_95=es_95,
            expected_shortfall_99=es_99,
            method=VaRMethod.CORNISH_FISHER,
            timestamp=datetime.now(),
            lookback_days=len(returns_data)
        )


class ESCalculator:
    """Expected Shortfall (CVaR) calculator."""
    
    def __init__(self, confidence_level: float = 0.95):
        """Initialize ES calculator."""
        self.confidence_level = confidence_level
    
    def calculate(
        self,
        returns: pd.Series,
        portfolio_value: float
    ) -> float:
        """Calculate Expected Shortfall."""
        threshold = returns.quantile(1 - self.confidence_level)
        tail_returns = returns[returns <= threshold]
        
        if len(tail_returns) > 0:
            es = tail_returns.mean() * portfolio_value
        else:
            es = threshold * portfolio_value
        
        return es

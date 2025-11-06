"""
Stress testing framework for portfolio risk analysis.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List
import pandas as pd
import numpy as np
from loguru import logger


@dataclass
class StressTestScenario:
    """Stress test scenario definition."""
    name: str
    description: str
    market_shock: float  # Market return shock (e.g., -0.20 for -20%)
    volatility_multiplier: float = 1.0  # Vol multiplier
    correlation_shift: float = 0.0  # Correlation shift
    sector_shocks: Dict[str, float] = field(default_factory=dict)


@dataclass
class StressTestResult:
    """Stress test result."""
    scenario: StressTestScenario
    portfolio_loss: float
    portfolio_loss_pct: float
    position_losses: Dict[str, float]
    var_95_shocked: float
    timestamp: datetime


class StressTester:
    """
    Portfolio stress testing framework.
    
    Tests portfolio under extreme market scenarios.
    """
    
    def __init__(self):
        """Initialize stress tester."""
        self.scenarios = self._create_default_scenarios()
        logger.info("Initialized StressTester")
    
    def _create_default_scenarios(self) -> List[StressTestScenario]:
        """Create standard stress scenarios."""
        return [
            StressTestScenario(
                name="market_crash",
                description="2008-style market crash",
                market_shock=-0.30,
                volatility_multiplier=3.0,
                correlation_shift=0.3
            ),
            StressTestScenario(
                name="flash_crash",
                description="Flash crash (-10% intraday)",
                market_shock=-0.10,
                volatility_multiplier=5.0
            ),
            StressTestScenario(
                name="tech_selloff",
                description="Tech sector selloff",
                market_shock=-0.05,
                sector_shocks={'Technology': -0.25}
            ),
            StressTestScenario(
                name="volatility_spike",
                description="VIX spike to 60",
                market_shock=0.0,
                volatility_multiplier=4.0
            ),
            StressTestScenario(
                name="liquidity_crisis",
                description="Liquidity dry-up",
                market_shock=-0.15,
                volatility_multiplier=2.5,
                correlation_shift=0.5
            ),
        ]
    
    def run_stress_test(
        self,
        positions: Dict[str, Dict],
        portfolio_value: float,
        market_data: pd.DataFrame,
        scenario: StressTestScenario
    ) -> StressTestResult:
        """Run single stress test scenario."""
        position_losses = {}
        total_loss = 0.0
        
        for symbol, pos in positions.items():
            position_value = pos['value']
            beta = pos.get('beta', 1.0)
            sector = pos.get('sector', 'Unknown')
            
            # Calculate position shock
            shock = scenario.market_shock * beta
            
            # Add sector-specific shock
            if sector in scenario.sector_shocks:
                shock += scenario.sector_shocks[sector]
            
            # Calculate loss
            position_loss = position_value * shock
            position_losses[symbol] = position_loss
            total_loss += position_loss
        
        loss_pct = total_loss / portfolio_value if portfolio_value > 0 else 0
        
        # Estimate shocked VaR (simplified)
        var_95_shocked = total_loss * scenario.volatility_multiplier
        
        result = StressTestResult(
            scenario=scenario,
            portfolio_loss=total_loss,
            portfolio_loss_pct=loss_pct,
            position_losses=position_losses,
            var_95_shocked=var_95_shocked,
            timestamp=datetime.now()
        )
        
        logger.info(
            f"Stress test '{scenario.name}': "
            f"Loss={loss_pct:.2%}"
        )
        
        return result
    
    def run_all_scenarios(
        self,
        positions: Dict[str, Dict],
        portfolio_value: float,
        market_data: pd.DataFrame
    ) -> List[StressTestResult]:
        """Run all stress test scenarios."""
        results = []
        
        for scenario in self.scenarios:
            result = self.run_stress_test(
                positions, portfolio_value, market_data, scenario
            )
            results.append(result)
        
        return results
    
    def add_custom_scenario(self, scenario: StressTestScenario) -> None:
        """Add custom stress scenario."""
        self.scenarios.append(scenario)
        logger.info(f"Added stress scenario: {scenario.name}")


# Aliases for backward compatibility
StressTest = StressTester
StressScenario = StressTestScenario


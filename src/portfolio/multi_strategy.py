"""
Multi-strategy portfolio management framework.

Manages multiple trading strategies within a single portfolio.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from loguru import logger
import numpy as np
import pandas as pd


class AllocationMethod(Enum):
    """Portfolio allocation methods."""
    EQUAL_WEIGHT = "equal_weight"
    RISK_PARITY = "risk_parity"
    SHARPE_WEIGHTED = "sharpe_weighted"
    INVERSE_VOLATILITY = "inverse_volatility"
    CUSTOM = "custom"


@dataclass
class StrategyConfig:
    """Configuration for a trading strategy."""
    name: str
    description: str
    target_allocation: float  # Target weight (0-1)
    min_allocation: float = 0.0
    max_allocation: float = 1.0
    enabled: bool = True
    risk_budget: float | None = None  # Volatility budget
    performance_history: list[float] = field(default_factory=list)

    def __post_init__(self):
        """Validate configuration."""
        if not 0 <= self.target_allocation <= 1:
            raise ValueError(f"target_allocation must be in [0, 1], got {self.target_allocation}")
        if not 0 <= self.min_allocation <= self.max_allocation <= 1:
            raise ValueError("Invalid min/max allocation bounds")


class MultiStrategyPortfolio:
    """
    Multi-strategy portfolio manager.
    
    Manages capital allocation across multiple strategies with:
    - Dynamic reallocation based on performance
    - Risk budgeting
    - Strategy correlation monitoring
    - Performance attribution
    """

    def __init__(
        self,
        initial_capital: float,
        allocation_method: AllocationMethod = AllocationMethod.RISK_PARITY,
        rebalance_frequency: str = "monthly",  # 'daily', 'weekly', 'monthly'
        correlation_threshold: float = 0.7,  # Max correlation between strategies
        performance_window: int = 63,  # Days for performance evaluation
    ):
        """
        Initialize multi-strategy portfolio.
        
        Args:
            initial_capital: Initial portfolio capital
            allocation_method: Method for allocating capital
            rebalance_frequency: How often to rebalance
            correlation_threshold: Max allowed correlation
            performance_window: Window for performance metrics
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.allocation_method = allocation_method
        self.rebalance_frequency = rebalance_frequency
        self.correlation_threshold = correlation_threshold
        self.performance_window = performance_window

        # Strategy registry
        self.strategies: dict[str, StrategyConfig] = {}

        # Current allocations
        self.current_allocations: dict[str, float] = {}

        # Performance tracking
        self.strategy_returns: dict[str, list[float]] = {}
        self.portfolio_value_history: list[float] = [initial_capital]
        self.allocation_history: list[dict] = []

        logger.info(
            f"Initialized MultiStrategyPortfolio: "
            f"capital=${initial_capital:,.0f}, method={allocation_method.value}"
        )

    def add_strategy(self, config: StrategyConfig) -> None:
        """
        Add a trading strategy to the portfolio.
        
        Args:
            config: Strategy configuration
        """
        if config.name in self.strategies:
            logger.warning(f"Strategy {config.name} already exists, updating")

        self.strategies[config.name] = config
        self.strategy_returns[config.name] = []

        logger.info(f"Added strategy: {config.name} (target={config.target_allocation:.1%})")

    def remove_strategy(self, name: str) -> None:
        """Remove a strategy from the portfolio."""
        if name in self.strategies:
            del self.strategies[name]
            del self.strategy_returns[name]
            if name in self.current_allocations:
                del self.current_allocations[name]
            logger.info(f"Removed strategy: {name}")

    def calculate_allocations(
        self,
        strategy_metrics: dict[str, dict] | None = None
    ) -> dict[str, float]:
        """
        Calculate optimal capital allocation across strategies.
        
        Args:
            strategy_metrics: Optional dict of {strategy_name: {vol, sharpe, correlation}}
            
        Returns:
            Dict of {strategy_name: allocation_weight}
        """
        if len(self.strategies) == 0:
            return {}

        enabled_strategies = {
            name: config for name, config in self.strategies.items()
            if config.enabled
        }

        if len(enabled_strategies) == 0:
            logger.warning("No enabled strategies")
            return {}

        # Calculate allocations based on method
        if self.allocation_method == AllocationMethod.EQUAL_WEIGHT:
            allocations = self._equal_weight_allocation(enabled_strategies)

        elif self.allocation_method == AllocationMethod.RISK_PARITY:
            allocations = self._risk_parity_allocation(
                enabled_strategies, strategy_metrics
            )

        elif self.allocation_method == AllocationMethod.SHARPE_WEIGHTED:
            allocations = self._sharpe_weighted_allocation(
                enabled_strategies, strategy_metrics
            )

        elif self.allocation_method == AllocationMethod.INVERSE_VOLATILITY:
            allocations = self._inverse_volatility_allocation(
                enabled_strategies, strategy_metrics
            )

        else:  # CUSTOM
            allocations = {
                name: config.target_allocation
                for name, config in enabled_strategies.items()
            }

        # Apply constraints
        allocations = self._apply_constraints(allocations, enabled_strategies)

        # Normalize to sum to 1
        total = sum(allocations.values())
        if total > 0:
            allocations = {name: alloc / total for name, alloc in allocations.items()}

        self.current_allocations = allocations

        # Record allocation
        self.allocation_history.append({
            "timestamp": datetime.now(),
            "allocations": allocations.copy(),
            "portfolio_value": self.current_capital
        })

        logger.info(f"Calculated allocations: {allocations}")

        return allocations

    def _equal_weight_allocation(
        self,
        strategies: dict[str, StrategyConfig]
    ) -> dict[str, float]:
        """Equal weight allocation."""
        n = len(strategies)
        return dict.fromkeys(strategies, 1.0 / n)

    def _risk_parity_allocation(
        self,
        strategies: dict[str, StrategyConfig],
        metrics: dict[str, dict] | None
    ) -> dict[str, float]:
        """Risk parity allocation (equal risk contribution)."""
        if metrics is None:
            return self._equal_weight_allocation(strategies)

        # Get volatilities
        vols = {}
        for name in strategies:
            if name in metrics and "volatility" in metrics[name]:
                vols[name] = metrics[name]["volatility"]
            else:
                vols[name] = 0.15  # Default 15% vol

        # Inverse volatility weighting
        inv_vols = {name: 1.0 / vol if vol > 0 else 0 for name, vol in vols.items()}

        total_inv_vol = sum(inv_vols.values())
        if total_inv_vol > 0:
            weights = {name: inv / total_inv_vol for name, inv in inv_vols.items()}
        else:
            weights = self._equal_weight_allocation(strategies)

        return weights

    def _sharpe_weighted_allocation(
        self,
        strategies: dict[str, StrategyConfig],
        metrics: dict[str, dict] | None
    ) -> dict[str, float]:
        """Sharpe ratio weighted allocation."""
        if metrics is None:
            return self._equal_weight_allocation(strategies)

        # Get Sharpe ratios
        sharpes = {}
        for name in strategies:
            if name in metrics and "sharpe" in metrics[name]:
                sharpes[name] = max(metrics[name]["sharpe"], 0)  # Only positive
            else:
                sharpes[name] = 0

        total_sharpe = sum(sharpes.values())
        if total_sharpe > 0:
            weights = {name: sharpe / total_sharpe for name, sharpe in sharpes.items()}
        else:
            weights = self._equal_weight_allocation(strategies)

        return weights

    def _inverse_volatility_allocation(
        self,
        strategies: dict[str, StrategyConfig],
        metrics: dict[str, dict] | None
    ) -> dict[str, float]:
        """Inverse volatility allocation."""
        return self._risk_parity_allocation(strategies, metrics)

    def _apply_constraints(
        self,
        allocations: dict[str, float],
        strategies: dict[str, StrategyConfig]
    ) -> dict[str, float]:
        """Apply min/max allocation constraints."""
        constrained = {}

        for name, alloc in allocations.items():
            config = strategies[name]
            constrained[name] = np.clip(alloc, config.min_allocation, config.max_allocation)

        return constrained

    def update_returns(
        self,
        strategy_returns: dict[str, float]
    ) -> float:
        """
        Update portfolio with strategy returns.
        
        Args:
            strategy_returns: Dict of {strategy_name: period_return}
            
        Returns:
            Portfolio return for the period
        """
        portfolio_return = 0.0

        for name, ret in strategy_returns.items():
            if name in self.current_allocations:
                allocation = self.current_allocations[name]
                contribution = allocation * ret
                portfolio_return += contribution

                # Track strategy returns
                if name in self.strategy_returns:
                    self.strategy_returns[name].append(ret)

        # Update capital
        self.current_capital *= (1 + portfolio_return)
        self.portfolio_value_history.append(self.current_capital)

        logger.debug(
            f"Portfolio return: {portfolio_return:.4f}, "
            f"value: ${self.current_capital:,.0f}"
        )

        return portfolio_return

    def get_performance_attribution(
        self,
        periods: int = 252
    ) -> pd.DataFrame:
        """
        Calculate performance attribution by strategy.
        
        Args:
            periods: Number of periods to analyze
            
        Returns:
            DataFrame with attribution metrics
        """
        attribution_data = []

        for name, config in self.strategies.items():
            if name not in self.strategy_returns:
                continue

            returns = self.strategy_returns[name][-periods:]

            if len(returns) == 0:
                continue

            # Calculate metrics
            total_return = (1 + pd.Series(returns)).prod() - 1
            avg_return = np.mean(returns)
            volatility = np.std(returns) * np.sqrt(252)
            sharpe = np.sqrt(252) * avg_return / np.std(returns) if np.std(returns) > 0 else 0

            # Current allocation
            current_alloc = self.current_allocations.get(name, 0)

            # Contribution to portfolio
            contribution = current_alloc * avg_return

            attribution_data.append({
                "strategy": name,
                "allocation": current_alloc,
                "total_return": total_return,
                "avg_daily_return": avg_return,
                "volatility": volatility,
                "sharpe": sharpe,
                "contribution": contribution,
                "enabled": config.enabled
            })

        return pd.DataFrame(attribution_data)

    def get_strategy_correlations(
        self,
        periods: int = 63
    ) -> pd.DataFrame:
        """
        Calculate correlation matrix between strategies.
        
        Args:
            periods: Number of periods for correlation
            
        Returns:
            Correlation matrix
        """
        # Build returns DataFrame
        returns_dict = {}
        for name, returns in self.strategy_returns.items():
            if len(returns) >= periods:
                returns_dict[name] = returns[-periods:]

        if len(returns_dict) == 0:
            return pd.DataFrame()

        returns_df = pd.DataFrame(returns_dict)
        correlation_matrix = returns_df.corr()

        return correlation_matrix

    def check_correlation_violations(
        self
    ) -> list[dict]:
        """Check for strategies with high correlation."""
        correlations = self.get_strategy_correlations()

        if correlations.empty:
            return []

        violations = []

        # Check all pairs
        for i, strategy1 in enumerate(correlations.index):
            for j, strategy2 in enumerate(correlations.columns):
                if i >= j:  # Skip diagonal and lower triangle
                    continue

                corr = correlations.loc[strategy1, strategy2]

                if abs(corr) > self.correlation_threshold:
                    violations.append({
                        "strategy1": strategy1,
                        "strategy2": strategy2,
                        "correlation": corr,
                        "threshold": self.correlation_threshold
                    })

        if violations:
            logger.warning(f"Found {len(violations)} correlation violations")

        return violations

    def get_portfolio_metrics(self) -> dict:
        """Get overall portfolio metrics."""
        if len(self.portfolio_value_history) < 2:
            return {}

        # Calculate returns
        values = pd.Series(self.portfolio_value_history)
        returns = values.pct_change().dropna()

        # Metrics
        total_return = (values.iloc[-1] / values.iloc[0]) - 1
        cagr = (values.iloc[-1] / values.iloc[0]) ** (252 / len(returns)) - 1
        volatility = returns.std() * np.sqrt(252)
        sharpe = np.sqrt(252) * returns.mean() / returns.std() if returns.std() > 0 else 0

        # Drawdown
        running_max = values.cummax()
        drawdown = (values - running_max) / running_max
        max_drawdown = drawdown.min()

        return {
            "current_value": self.current_capital,
            "total_return": total_return,
            "cagr": cagr,
            "volatility": volatility,
            "sharpe": sharpe,
            "max_drawdown": max_drawdown,
            "num_strategies": len(self.strategies),
            "active_strategies": sum(1 for s in self.strategies.values() if s.enabled)
        }

    def rebalance_needed(self) -> bool:
        """Check if rebalancing is needed."""
        # Simple check: has allocation drifted significantly?
        if len(self.current_allocations) == 0:
            return True

        # Check drift from target
        max_drift = 0
        for name, config in self.strategies.items():
            if name in self.current_allocations:
                current = self.current_allocations[name]
                target = config.target_allocation
                drift = abs(current - target)
                max_drift = max(max_drift, drift)

        # Rebalance if drift > 5%
        return max_drift > 0.05

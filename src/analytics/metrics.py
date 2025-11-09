"""
Comprehensive performance metrics calculator.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class PerformanceStats:
    """Container for performance statistics."""
    # Returns
    total_return: float
    annual_return: float
    monthly_return: float
    daily_return: float

    # Risk
    volatility: float
    downside_volatility: float
    var_95: float
    cvar_95: float

    # Risk-adjusted returns
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    information_ratio: float
    omega_ratio: float

    # Drawdown
    max_drawdown: float
    avg_drawdown: float
    max_drawdown_duration: int
    recovery_time: int

    # Win/Loss
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float

    # Trading
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_trade_duration: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "Total Return": f"{self.total_return:.2%}",
            "Annual Return": f"{self.annual_return:.2%}",
            "Volatility": f"{self.volatility:.2%}",
            "Sharpe Ratio": f"{self.sharpe_ratio:.2f}",
            "Sortino Ratio": f"{self.sortino_ratio:.2f}",
            "Calmar Ratio": f"{self.calmar_ratio:.2f}",
            "Max Drawdown": f"{self.max_drawdown:.2%}",
            "Win Rate": f"{self.win_rate:.2%}",
            "Profit Factor": f"{self.profit_factor:.2f}",
            "Total Trades": self.total_trades
        }


class PerformanceMetrics:
    """
    Calculate comprehensive performance metrics.

    Provides a wide range of performance and risk metrics
    for strategy evaluation.
    """

    def __init__(
        self,
        returns: pd.Series,
        benchmark_returns: pd.Series | None = None,
        risk_free_rate: float = 0.02,
        periods_per_year: int = 252
    ):
        """
        Initialize performance metrics calculator.

        Args:
            returns: Strategy returns (daily)
            benchmark_returns: Benchmark returns for comparison
            risk_free_rate: Annual risk-free rate
            periods_per_year: Trading periods per year
        """
        self.returns = returns
        self.benchmark_returns = benchmark_returns
        self.risk_free_rate = risk_free_rate
        self.periods_per_year = periods_per_year

        # Ensure returns is a Series
        if isinstance(returns, np.ndarray):
            self.returns = pd.Series(returns)

        if benchmark_returns is not None and isinstance(benchmark_returns, np.ndarray):
            self.benchmark_returns = pd.Series(benchmark_returns)

    def calculate_all(self) -> PerformanceStats:
        """Calculate all performance metrics."""
        returns = self.returns.dropna()

        if len(returns) == 0:
            return self._empty_stats()

        return PerformanceStats(
            # Returns
            total_return=self.total_return(),
            annual_return=self.annualized_return(),
            monthly_return=self.monthly_return(),
            daily_return=self.daily_return(),

            # Risk
            volatility=self.volatility(),
            downside_volatility=self.downside_volatility(),
            var_95=self.value_at_risk(confidence=0.95),
            cvar_95=self.conditional_var(confidence=0.95),

            # Risk-adjusted
            sharpe_ratio=self.sharpe_ratio(),
            sortino_ratio=self.sortino_ratio(),
            calmar_ratio=self.calmar_ratio(),
            information_ratio=self.information_ratio(),
            omega_ratio=self.omega_ratio(),

            # Drawdown
            max_drawdown=self.max_drawdown(),
            avg_drawdown=self.avg_drawdown(),
            max_drawdown_duration=self.max_drawdown_duration(),
            recovery_time=self.recovery_time(),

            # Win/Loss
            win_rate=self.win_rate(),
            profit_factor=self.profit_factor(),
            avg_win=self.avg_win(),
            avg_loss=self.avg_loss(),
            largest_win=self.largest_win(),
            largest_loss=self.largest_loss(),

            # Trading
            total_trades=self.total_trades(),
            winning_trades=self.winning_trades(),
            losing_trades=self.losing_trades(),
            avg_trade_duration=0.0  # Would need trade data
        )

    # Return Metrics

    def total_return(self) -> float:
        """Calculate total return."""
        if len(self.returns) == 0:
            return 0.0
        return (1 + self.returns).prod() - 1

    def annualized_return(self) -> float:
        """Calculate annualized return."""
        if len(self.returns) == 0:
            return 0.0

        total_return = self.total_return()
        n_periods = len(self.returns)
        years = n_periods / self.periods_per_year

        if years <= 0:
            return 0.0

        return (1 + total_return) ** (1 / years) - 1

    def monthly_return(self) -> float:
        """Calculate average monthly return."""
        annual = self.annualized_return()
        return (1 + annual) ** (1/12) - 1

    def daily_return(self) -> float:
        """Calculate average daily return."""
        if len(self.returns) == 0:
            return 0.0
        return self.returns.mean()

    # Risk Metrics

    def volatility(self) -> float:
        """Calculate annualized volatility."""
        if len(self.returns) == 0:
            return 0.0
        return self.returns.std() * np.sqrt(self.periods_per_year)

    def downside_volatility(self, threshold: float = 0.0) -> float:
        """Calculate downside volatility (only negative returns)."""
        downside_returns = self.returns[self.returns < threshold]
        if len(downside_returns) == 0:
            return 0.0
        return downside_returns.std() * np.sqrt(self.periods_per_year)

    def value_at_risk(self, confidence: float = 0.95) -> float:
        """
        Calculate Value at Risk (VaR).

        Args:
            confidence: Confidence level (0.95 = 95%)

        Returns:
            VaR (negative value)
        """
        if len(self.returns) == 0:
            return 0.0
        return np.percentile(self.returns, (1 - confidence) * 100)

    def conditional_var(self, confidence: float = 0.95) -> float:
        """
        Calculate Conditional Value at Risk (CVaR/Expected Shortfall).

        Average loss beyond VaR threshold.
        """
        if len(self.returns) == 0:
            return 0.0

        var = self.value_at_risk(confidence)
        return self.returns[self.returns <= var].mean()

    # Risk-Adjusted Return Metrics

    def sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio."""
        if len(self.returns) == 0:
            return 0.0

        excess_returns = self.returns - self.risk_free_rate / self.periods_per_year
        std = excess_returns.std()

        if std == 0:
            return 0.0

        return (excess_returns.mean() / std) * np.sqrt(self.periods_per_year)

    def sortino_ratio(self, threshold: float = 0.0) -> float:
        """Calculate Sortino ratio (uses downside deviation)."""
        if len(self.returns) == 0:
            return 0.0

        excess_returns = self.returns - self.risk_free_rate / self.periods_per_year
        downside_std = self.downside_volatility(threshold) / np.sqrt(self.periods_per_year)

        if downside_std == 0:
            return 0.0

        return (excess_returns.mean() / downside_std) * np.sqrt(self.periods_per_year)

    def calmar_ratio(self) -> float:
        """Calculate Calmar ratio (return / max drawdown)."""
        annual_return = self.annualized_return()
        max_dd = abs(self.max_drawdown())

        if max_dd == 0:
            return 0.0

        return annual_return / max_dd

    def information_ratio(self) -> float:
        """Calculate Information ratio (vs benchmark)."""
        if self.benchmark_returns is None or len(self.benchmark_returns) == 0:
            return 0.0

        # Align returns
        active_returns = self.returns - self.benchmark_returns

        if len(active_returns) == 0:
            return 0.0

        tracking_error = active_returns.std()

        if tracking_error == 0:
            return 0.0

        return active_returns.mean() / tracking_error

    def omega_ratio(self, threshold: float = 0.0) -> float:
        """
        Calculate Omega ratio.

        Ratio of probability-weighted gains to losses.
        """
        if len(self.returns) == 0:
            return 0.0

        gains = self.returns[self.returns > threshold] - threshold
        losses = threshold - self.returns[self.returns < threshold]

        if len(losses) == 0 or losses.sum() == 0:
            return np.inf if len(gains) > 0 else 0.0

        return gains.sum() / losses.sum()

    # Drawdown Metrics

    def max_drawdown(self) -> float:
        """Calculate maximum drawdown."""
        if len(self.returns) == 0:
            return 0.0

        cumulative = (1 + self.returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max

        return drawdown.min()

    def avg_drawdown(self) -> float:
        """Calculate average drawdown."""
        if len(self.returns) == 0:
            return 0.0

        cumulative = (1 + self.returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max

        # Only count periods in drawdown
        in_drawdown = drawdown < 0

        if not in_drawdown.any():
            return 0.0

        return drawdown[in_drawdown].mean()

    def max_drawdown_duration(self) -> int:
        """Calculate maximum drawdown duration (days)."""
        if len(self.returns) == 0:
            return 0

        cumulative = (1 + self.returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max

        # Find drawdown periods
        in_drawdown = drawdown < 0
        drawdown_periods = []
        current_duration = 0

        for is_dd in in_drawdown:
            if is_dd:
                current_duration += 1
            else:
                if current_duration > 0:
                    drawdown_periods.append(current_duration)
                current_duration = 0

        if current_duration > 0:
            drawdown_periods.append(current_duration)

        return max(drawdown_periods) if drawdown_periods else 0

    def recovery_time(self) -> int:
        """Calculate average recovery time from drawdowns."""
        if len(self.returns) == 0:
            return 0

        cumulative = (1 + self.returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max

        # Find recovery periods
        recovery_times = []
        in_drawdown = False
        drawdown_start = 0

        for i, dd in enumerate(drawdown):
            if dd < 0 and not in_drawdown:
                in_drawdown = True
                drawdown_start = i
            elif dd >= 0 and in_drawdown:
                in_drawdown = False
                recovery_times.append(i - drawdown_start)

        return int(np.mean(recovery_times)) if recovery_times else 0

    # Win/Loss Metrics

    def win_rate(self) -> float:
        """Calculate win rate (% of positive returns)."""
        if len(self.returns) == 0:
            return 0.0

        winning_days = (self.returns > 0).sum()
        return winning_days / len(self.returns)

    def profit_factor(self) -> float:
        """Calculate profit factor (total wins / total losses)."""
        wins = self.returns[self.returns > 0].sum()
        losses = abs(self.returns[self.returns < 0].sum())

        if losses == 0:
            return np.inf if wins > 0 else 0.0

        return wins / losses

    def avg_win(self) -> float:
        """Calculate average winning return."""
        wins = self.returns[self.returns > 0]
        return wins.mean() if len(wins) > 0 else 0.0

    def avg_loss(self) -> float:
        """Calculate average losing return."""
        losses = self.returns[self.returns < 0]
        return losses.mean() if len(losses) > 0 else 0.0

    def largest_win(self) -> float:
        """Calculate largest single-day win."""
        return self.returns.max() if len(self.returns) > 0 else 0.0

    def largest_loss(self) -> float:
        """Calculate largest single-day loss."""
        return self.returns.min() if len(self.returns) > 0 else 0.0

    # Trading Metrics

    def total_trades(self) -> int:
        """Count total trading days."""
        return len(self.returns[self.returns != 0])

    def winning_trades(self) -> int:
        """Count winning days."""
        return (self.returns > 0).sum()

    def losing_trades(self) -> int:
        """Count losing days."""
        return (self.returns < 0).sum()

    def _empty_stats(self) -> PerformanceStats:
        """Return empty stats when no data available."""
        return PerformanceStats(
            total_return=0.0,
            annual_return=0.0,
            monthly_return=0.0,
            daily_return=0.0,
            volatility=0.0,
            downside_volatility=0.0,
            var_95=0.0,
            cvar_95=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            information_ratio=0.0,
            omega_ratio=0.0,
            max_drawdown=0.0,
            avg_drawdown=0.0,
            max_drawdown_duration=0,
            recovery_time=0,
            win_rate=0.0,
            profit_factor=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            largest_win=0.0,
            largest_loss=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            avg_trade_duration=0.0
        )

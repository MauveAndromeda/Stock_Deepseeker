"""
Real-time risk monitoring system.

Monitors portfolio risk metrics and triggers alerts.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from loguru import logger
import numpy as np
import pandas as pd


class RiskLevel(Enum):
    """Risk severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskMetrics:
    """
    Real-time portfolio risk metrics.

    Attributes:
        timestamp: Calculation timestamp
        portfolio_value: Total portfolio value
        daily_pnl: Daily P&L
        daily_return: Daily return percentage
        volatility: Annualized volatility
        beta: Market beta
        sharpe_ratio: Sharpe ratio
        max_drawdown: Maximum drawdown from peak
        var_95: 95% Value at Risk
        var_99: 99% Value at Risk
        expected_shortfall: Expected Shortfall (CVaR)
        leverage: Portfolio leverage
        concentration: Largest position weight
        num_positions: Number of positions
        long_exposure: Long exposure
        short_exposure: Short exposure
        net_exposure: Net exposure
        gross_exposure: Gross exposure
    """
    timestamp: datetime
    portfolio_value: float
    daily_pnl: float
    daily_return: float
    volatility: float
    beta: float
    sharpe_ratio: float
    max_drawdown: float
    var_95: float
    var_99: float
    expected_shortfall: float
    leverage: float
    concentration: float
    num_positions: int
    long_exposure: float
    short_exposure: float
    net_exposure: float
    gross_exposure: float
    metadata: dict = field(default_factory=dict)

    def get_risk_level(self) -> RiskLevel:
        """Determine overall risk level."""
        critical_count = 0

        # Check critical thresholds
        if abs(self.max_drawdown) > 0.20:  # 20% drawdown
            critical_count += 1
        if self.volatility > 0.40:  # 40% annualized vol
            critical_count += 1
        if abs(self.leverage) > 2.0:  # 2x leverage
            critical_count += 1
        if self.concentration > 0.30:  # 30% in single position
            critical_count += 1

        if critical_count >= 2:
            return RiskLevel.CRITICAL
        if critical_count == 1:
            return RiskLevel.HIGH
        if abs(self.max_drawdown) > 0.10 or self.volatility > 0.25:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW


class RiskMonitor:
    """
    Real-time risk monitoring system.

    Continuously monitors portfolio risk and triggers alerts
    when thresholds are breached.
    """

    def __init__(
        self,
        update_frequency: int = 60,  # Seconds between updates
        lookback_window: int = 252,  # Days for vol/correlation
        alert_callbacks: list[Callable] | None = None,
    ) -> None:
        """
        Initialize risk monitor.

        Args:
            update_frequency: Seconds between metric updates
            lookback_window: Days for historical calculations
            alert_callbacks: List of functions to call on alerts
        """
        self.update_frequency = update_frequency
        self.lookback_window = lookback_window
        self.alert_callbacks = alert_callbacks or []

        # Historical data
        self.metrics_history: list[RiskMetrics] = []
        self.returns_history: pd.Series = pd.Series(dtype=float)
        self.portfolio_values: pd.Series = pd.Series(dtype=float)

        # Current state
        self.current_metrics: RiskMetrics | None = None
        self.last_update: datetime | None = None

        # Alert tracking
        self.active_alerts: dict[str, dict] = {}

        logger.info("Initialized RiskMonitor")

    def update(
        self,
        portfolio_value: float,
        positions: dict[str, dict],  # symbol -> {quantity, price, value}
        market_data: pd.DataFrame,  # Recent price data
        benchmark_returns: pd.Series | None = None
    ) -> RiskMetrics:
        """
        Update risk metrics.

        Args:
            portfolio_value: Current portfolio value
            positions: Current positions
            market_data: Recent market data for calculations
            benchmark_returns: Benchmark returns for beta

        Returns:
            RiskMetrics with current risk measures
        """
        timestamp = datetime.now()

        # Calculate metrics
        metrics = self._calculate_metrics(
            timestamp,
            portfolio_value,
            positions,
            market_data,
            benchmark_returns
        )

        # Store metrics
        self.current_metrics = metrics
        self.metrics_history.append(metrics)
        self.last_update = timestamp

        # Update historical data
        self.portfolio_values[timestamp] = portfolio_value
        if len(self.portfolio_values) > 1:
            prev_value = self.portfolio_values.iloc[-2]
            daily_return = (portfolio_value - prev_value) / prev_value
            self.returns_history[timestamp] = daily_return

        # Check for alerts
        self._check_alerts(metrics)

        # Log summary
        risk_level = metrics.get_risk_level()
        logger.info(
            f"Risk Update [{risk_level.value.upper()}]: "
            f"Value=${portfolio_value:,.0f}, "
            f"DD={metrics.max_drawdown:.2%}, "
            f"Vol={metrics.volatility:.1%}"
        )

        return metrics

    def _calculate_metrics(
        self,
        timestamp: datetime,
        portfolio_value: float,
        positions: dict[str, dict],
        market_data: pd.DataFrame,
        benchmark_returns: pd.Series | None
    ) -> RiskMetrics:
        """Calculate current risk metrics."""
        # Daily P&L
        if len(self.portfolio_values) > 0:
            prev_value = self.portfolio_values.iloc[-1]
            daily_pnl = portfolio_value - prev_value
            daily_return = daily_pnl / prev_value if prev_value > 0 else 0
        else:
            daily_pnl = 0
            daily_return = 0

        # Volatility (annualized)
        if len(self.returns_history) >= 20:
            volatility = self.returns_history.tail(self.lookback_window).std() * np.sqrt(252)
        else:
            volatility = 0.0

        # Beta
        if benchmark_returns is not None and len(self.returns_history) >= 20:
            beta = self._calculate_beta(benchmark_returns)
        else:
            beta = 1.0

        # Sharpe ratio
        if len(self.returns_history) >= 20 and volatility > 0:
            mean_return = self.returns_history.tail(self.lookback_window).mean()
            sharpe_ratio = np.sqrt(252) * mean_return / volatility
        else:
            sharpe_ratio = 0.0

        # Maximum drawdown
        max_drawdown = self._calculate_max_drawdown()

        # VaR and ES
        var_95, var_99, expected_shortfall = self._calculate_var_es()

        # Position metrics
        long_exposure = sum(
            pos["value"] for pos in positions.values() if pos["value"] > 0
        )
        short_exposure = sum(
            abs(pos["value"]) for pos in positions.values() if pos["value"] < 0
        )
        net_exposure = long_exposure - short_exposure
        gross_exposure = long_exposure + short_exposure

        # Leverage
        if portfolio_value > 0:
            leverage = gross_exposure / portfolio_value
        else:
            leverage = 0.0

        # Concentration (largest position)
        if len(positions) > 0 and portfolio_value > 0:
            largest_position = max(abs(pos["value"]) for pos in positions.values())
            concentration = largest_position / portfolio_value
        else:
            concentration = 0.0

        return RiskMetrics(
            timestamp=timestamp,
            portfolio_value=portfolio_value,
            daily_pnl=daily_pnl,
            daily_return=daily_return,
            volatility=volatility,
            beta=beta,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            var_95=var_95,
            var_99=var_99,
            expected_shortfall=expected_shortfall,
            leverage=leverage,
            concentration=concentration,
            num_positions=len(positions),
            long_exposure=long_exposure,
            short_exposure=short_exposure,
            net_exposure=net_exposure,
            gross_exposure=gross_exposure,
        )

    def _calculate_beta(self, benchmark_returns: pd.Series) -> float:
        """Calculate portfolio beta."""
        # Align returns
        common_dates = self.returns_history.index.intersection(benchmark_returns.index)

        if len(common_dates) < 20:
            return 1.0

        portfolio_rets = self.returns_history.loc[common_dates].tail(self.lookback_window)
        benchmark_rets = benchmark_returns.loc[common_dates].tail(self.lookback_window)

        # Calculate beta = Cov(portfolio, benchmark) / Var(benchmark)
        covariance = portfolio_rets.cov(benchmark_rets)
        benchmark_var = benchmark_rets.var()

        if benchmark_var > 0:
            beta = covariance / benchmark_var
        else:
            beta = 1.0

        return beta

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from peak."""
        if len(self.portfolio_values) < 2:
            return 0.0

        # Calculate running maximum
        running_max = self.portfolio_values.cummax()

        # Calculate drawdown
        drawdown = (self.portfolio_values - running_max) / running_max

        return drawdown.min()

    def _calculate_var_es(self) -> tuple[float, float, float]:
        """Calculate Value at Risk and Expected Shortfall."""
        if len(self.returns_history) < 20:
            return 0.0, 0.0, 0.0

        returns = self.returns_history.tail(self.lookback_window)

        # VaR (historical simulation)
        var_95 = returns.quantile(0.05)  # 5th percentile
        var_99 = returns.quantile(0.01)  # 1st percentile

        # Expected Shortfall (CVaR) - mean of returns below VaR
        tail_returns = returns[returns <= var_95]
        if len(tail_returns) > 0:
            expected_shortfall = tail_returns.mean()
        else:
            expected_shortfall = var_95

        return var_95, var_99, expected_shortfall

    def _check_alerts(self, metrics: RiskMetrics) -> None:
        """Check for risk limit breaches and trigger alerts."""
        alerts = []

        # Drawdown alerts
        if abs(metrics.max_drawdown) > 0.20:
            alerts.append({
                "type": "drawdown",
                "severity": RiskLevel.CRITICAL,
                "message": f"Critical drawdown: {metrics.max_drawdown:.2%}",
                "value": metrics.max_drawdown,
            })
        elif abs(metrics.max_drawdown) > 0.15:
            alerts.append({
                "type": "drawdown",
                "severity": RiskLevel.HIGH,
                "message": f"High drawdown: {metrics.max_drawdown:.2%}",
                "value": metrics.max_drawdown,
            })

        # Volatility alerts
        if metrics.volatility > 0.40:
            alerts.append({
                "type": "volatility",
                "severity": RiskLevel.HIGH,
                "message": f"High volatility: {metrics.volatility:.1%}",
                "value": metrics.volatility,
            })

        # Leverage alerts
        if abs(metrics.leverage) > 2.0:
            alerts.append({
                "type": "leverage",
                "severity": RiskLevel.CRITICAL,
                "message": f"Excessive leverage: {metrics.leverage:.2f}x",
                "value": metrics.leverage,
            })
        elif abs(metrics.leverage) > 1.5:
            alerts.append({
                "type": "leverage",
                "severity": RiskLevel.HIGH,
                "message": f"High leverage: {metrics.leverage:.2f}x",
                "value": metrics.leverage,
            })

        # Concentration alerts
        if metrics.concentration > 0.30:
            alerts.append({
                "type": "concentration",
                "severity": RiskLevel.HIGH,
                "message": f"High concentration: {metrics.concentration:.1%}",
                "value": metrics.concentration,
            })

        # VaR alerts
        if abs(metrics.var_99) > 0.05:  # 5% daily VaR
            alerts.append({
                "type": "var",
                "severity": RiskLevel.HIGH,
                "message": f"High VaR(99%): {metrics.var_99:.2%}",
                "value": metrics.var_99,
            })

        # Trigger callbacks
        for alert in alerts:
            alert_key = f"{alert['type']}_{alert['severity'].value}"

            # Only trigger if not already active or severity increased
            if alert_key not in self.active_alerts or \
               self.active_alerts[alert_key]["severity"].value < alert["severity"].value:

                logger.warning(f"RISK ALERT: {alert['message']}")

                for callback in self.alert_callbacks:
                    try:
                        callback(alert, metrics)
                    except Exception as e:
                        logger.error(f"Alert callback failed: {e}")

                self.active_alerts[alert_key] = alert

        # Clear resolved alerts
        current_alert_keys = {f"{a['type']}_{a['severity'].value}" for a in alerts}
        resolved_keys = set(self.active_alerts.keys()) - current_alert_keys

        for key in resolved_keys:
            logger.info(f"Risk alert resolved: {self.active_alerts[key]['message']}")
            del self.active_alerts[key]

    def get_risk_report(self) -> dict:
        """Generate comprehensive risk report."""
        if self.current_metrics is None:
            return {}

        metrics = self.current_metrics
        risk_level = metrics.get_risk_level()

        report = {
            "timestamp": metrics.timestamp,
            "risk_level": risk_level.value,
            "portfolio": {
                "value": metrics.portfolio_value,
                "daily_pnl": metrics.daily_pnl,
                "daily_return": metrics.daily_return,
                "num_positions": metrics.num_positions,
            },
            "exposure": {
                "long": metrics.long_exposure,
                "short": metrics.short_exposure,
                "net": metrics.net_exposure,
                "gross": metrics.gross_exposure,
                "leverage": metrics.leverage,
            },
            "risk_metrics": {
                "volatility": metrics.volatility,
                "beta": metrics.beta,
                "sharpe_ratio": metrics.sharpe_ratio,
                "max_drawdown": metrics.max_drawdown,
                "concentration": metrics.concentration,
            },
            "var_metrics": {
                "var_95": metrics.var_95,
                "var_99": metrics.var_99,
                "expected_shortfall": metrics.expected_shortfall,
            },
            "active_alerts": list(self.active_alerts.values()),
        }

        return report

    def get_metrics_history(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None
    ) -> pd.DataFrame:
        """Get historical risk metrics as DataFrame."""
        if len(self.metrics_history) == 0:
            return pd.DataFrame()

        # Convert to DataFrame
        data = []
        for m in self.metrics_history:
            if start_date and m.timestamp < start_date:
                continue
            if end_date and m.timestamp > end_date:
                continue

            data.append({
                "timestamp": m.timestamp,
                "portfolio_value": m.portfolio_value,
                "daily_return": m.daily_return,
                "volatility": m.volatility,
                "sharpe_ratio": m.sharpe_ratio,
                "max_drawdown": m.max_drawdown,
                "leverage": m.leverage,
                "concentration": m.concentration,
                "var_95": m.var_95,
                "var_99": m.var_99,
            })

        return pd.DataFrame(data).set_index("timestamp")

    def reset(self) -> None:
        """Reset monitor state."""
        self.metrics_history.clear()
        self.returns_history = pd.Series(dtype=float)
        self.portfolio_values = pd.Series(dtype=float)
        self.current_metrics = None
        self.last_update = None
        self.active_alerts.clear()

        logger.info("RiskMonitor reset")

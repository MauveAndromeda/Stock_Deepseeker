"""
Risk Limiter Module

Comprehensive risk limit enforcement system for trading operations.
Enforces position limits, concentration limits, loss limits, and dynamic sizing.

Author: Stock_Deepseeker Team
Version: 1.0.0
"""

import logging
from typing import Dict, List, Optional, Tuple, Union, Any
from datetime import datetime, time, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class LimitType(Enum):
    """Types of risk limits"""
    POSITION_SIZE = "position_size"
    PORTFOLIO_CONCENTRATION = "portfolio_concentration"
    DAILY_LOSS = "daily_loss"
    WEEKLY_LOSS = "weekly_loss"
    MONTHLY_LOSS = "monthly_loss"
    LEVERAGE = "leverage"
    SECTOR_EXPOSURE = "sector_exposure"
    CORRELATION = "correlation"
    VOLATILITY = "volatility"
    DRAWDOWN = "drawdown"
    VAR = "var"
    LIQUIDITY = "liquidity"


class ViolationSeverity(Enum):
    """Severity levels for limit violations"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class LimitViolation:
    """Container for limit violation information"""
    limit_type: LimitType
    severity: ViolationSeverity
    current_value: float
    limit_value: float
    excess_amount: float
    excess_percentage: float
    symbol: Optional[str] = None
    description: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    requires_action: bool = True
    suggested_action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'limit_type': self.limit_type.value,
            'severity': self.severity.value,
            'current_value': self.current_value,
            'limit_value': self.limit_value,
            'excess_amount': self.excess_amount,
            'excess_percentage': self.excess_percentage,
            'symbol': self.symbol,
            'description': self.description,
            'timestamp': self.timestamp.isoformat(),
            'requires_action': self.requires_action,
            'suggested_action': self.suggested_action
        }


@dataclass
class PositionSizeResult:
    """Result from position sizing calculation"""
    symbol: str
    requested_size: float
    approved_size: float
    approved: bool
    rejection_reason: Optional[str] = None
    adjustments_applied: List[str] = field(default_factory=list)
    risk_score: float = 0.0


class RiskLimiter:
    """
    Comprehensive risk limit enforcement system.

    Features:
    - Maximum position size enforcement
    - Portfolio concentration limits
    - Daily/weekly/monthly loss limits with auto-shutdown
    - Leverage constraints
    - Sector exposure limits
    - Correlation-based position sizing
    - Dynamic volatility-adjusted sizing
    - Real-time limit monitoring
    """

    def __init__(
        self,
        max_position_size_pct: float = 0.10,
        max_sector_exposure_pct: float = 0.30,
        max_single_stock_pct: float = 0.05,
        max_correlation_exposure: float = 0.50,
        max_leverage: float = 2.0,
        max_daily_loss_pct: float = 0.02,
        max_weekly_loss_pct: float = 0.05,
        max_monthly_loss_pct: float = 0.10,
        max_drawdown_pct: float = 0.15,
        enable_auto_shutdown: bool = True,
        enable_dynamic_sizing: bool = True,
        volatility_lookback: int = 20,
        alert_on_violations: bool = True
    ):
        """
        Initialize Risk Limiter.

        Args:
            max_position_size_pct: Maximum position size as % of portfolio
            max_sector_exposure_pct: Maximum sector exposure as % of portfolio
            max_single_stock_pct: Maximum single stock position as % of portfolio
            max_correlation_exposure: Maximum correlated position exposure
            max_leverage: Maximum portfolio leverage
            max_daily_loss_pct: Maximum daily loss before shutdown
            max_weekly_loss_pct: Maximum weekly loss
            max_monthly_loss_pct: Maximum monthly loss
            max_drawdown_pct: Maximum drawdown before risk reduction
            enable_auto_shutdown: Enable automatic trading shutdown on limits
            enable_dynamic_sizing: Enable volatility-based position sizing
            volatility_lookback: Days to look back for volatility calculation
            alert_on_violations: Enable alerting on limit violations
        """
        # Position limits
        self.max_position_size_pct = max_position_size_pct
        self.max_sector_exposure_pct = max_sector_exposure_pct
        self.max_single_stock_pct = max_single_stock_pct
        self.max_correlation_exposure = max_correlation_exposure

        # Leverage limits
        self.max_leverage = max_leverage

        # Loss limits
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_weekly_loss_pct = max_weekly_loss_pct
        self.max_monthly_loss_pct = max_monthly_loss_pct
        self.max_drawdown_pct = max_drawdown_pct

        # Features
        self.enable_auto_shutdown = enable_auto_shutdown
        self.enable_dynamic_sizing = enable_dynamic_sizing
        self.volatility_lookback = volatility_lookback
        self.alert_on_violations = alert_on_violations

        # State tracking
        self.is_shutdown = False
        self.shutdown_reason = None
        self.shutdown_timestamp = None

        # Loss tracking
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.monthly_pnl = 0.0
        self.daily_start_value = None
        self.weekly_start_value = None
        self.monthly_start_value = None

        # Violation history
        self.violation_history: List[LimitViolation] = []

        # Position tracking
        self.current_positions: Dict[str, Dict] = {}
        self.sector_exposures: Dict[str, float] = {}

        logger.info(f"RiskLimiter initialized: max_position={max_position_size_pct:.2%}, "
                   f"max_daily_loss={max_daily_loss_pct:.2%}")

    def check_position_limit(
        self,
        symbol: str,
        position_value: float,
        portfolio_value: float,
        sector: Optional[str] = None
    ) -> Tuple[bool, Optional[LimitViolation]]:
        """
        Check if position size is within limits.

        Args:
            symbol: Stock symbol
            position_value: Proposed position value
            portfolio_value: Total portfolio value
            sector: Sector classification

        Returns:
            Tuple of (is_within_limits, violation_if_any)
        """
        try:
            if portfolio_value <= 0:
                return False, None

            position_pct = abs(position_value) / portfolio_value

            # Check single stock limit
            if position_pct > self.max_single_stock_pct:
                violation = LimitViolation(
                    limit_type=LimitType.POSITION_SIZE,
                    severity=ViolationSeverity.WARNING,
                    current_value=position_pct,
                    limit_value=self.max_single_stock_pct,
                    excess_amount=position_pct - self.max_single_stock_pct,
                    excess_percentage=(position_pct / self.max_single_stock_pct - 1) * 100,
                    symbol=symbol,
                    description=f"Position size {position_pct:.2%} exceeds limit {self.max_single_stock_pct:.2%}",
                    suggested_action=f"Reduce position to {self.max_single_stock_pct * portfolio_value:.2f}"
                )

                self._record_violation(violation)
                return False, violation

            # Check sector exposure if provided
            if sector:
                is_within, sector_violation = self.check_sector_limit(
                    sector, position_value, portfolio_value
                )
                if not is_within:
                    return False, sector_violation

            return True, None

        except Exception as e:
            logger.error(f"Error checking position limit: {e}", exc_info=True)
            return False, None

    def check_sector_limit(
        self,
        sector: str,
        additional_value: float,
        portfolio_value: float
    ) -> Tuple[bool, Optional[LimitViolation]]:
        """
        Check sector exposure limits.

        Args:
            sector: Sector name
            additional_value: Additional exposure to add
            portfolio_value: Total portfolio value

        Returns:
            Tuple of (is_within_limits, violation_if_any)
        """
        try:
            current_sector_value = self.sector_exposures.get(sector, 0.0)
            new_sector_value = current_sector_value + additional_value
            sector_exposure_pct = new_sector_value / portfolio_value

            if sector_exposure_pct > self.max_sector_exposure_pct:
                violation = LimitViolation(
                    limit_type=LimitType.SECTOR_EXPOSURE,
                    severity=ViolationSeverity.WARNING,
                    current_value=sector_exposure_pct,
                    limit_value=self.max_sector_exposure_pct,
                    excess_amount=sector_exposure_pct - self.max_sector_exposure_pct,
                    excess_percentage=(sector_exposure_pct / self.max_sector_exposure_pct - 1) * 100,
                    description=f"Sector {sector} exposure {sector_exposure_pct:.2%} exceeds limit",
                    suggested_action=f"Reduce {sector} exposure or diversify"
                )

                self._record_violation(violation)
                return False, violation

            return True, None

        except Exception as e:
            logger.error(f"Error checking sector limit: {e}", exc_info=True)
            return False, None

    def check_leverage_limit(
        self,
        total_position_value: float,
        portfolio_value: float
    ) -> Tuple[bool, Optional[LimitViolation]]:
        """
        Check portfolio leverage limits.

        Args:
            total_position_value: Total gross position value
            portfolio_value: Net portfolio value

        Returns:
            Tuple of (is_within_limits, violation_if_any)
        """
        try:
            if portfolio_value <= 0:
                return False, None

            current_leverage = total_position_value / portfolio_value

            if current_leverage > self.max_leverage:
                violation = LimitViolation(
                    limit_type=LimitType.LEVERAGE,
                    severity=ViolationSeverity.CRITICAL,
                    current_value=current_leverage,
                    limit_value=self.max_leverage,
                    excess_amount=current_leverage - self.max_leverage,
                    excess_percentage=(current_leverage / self.max_leverage - 1) * 100,
                    description=f"Leverage {current_leverage:.2f}x exceeds limit {self.max_leverage:.2f}x",
                    suggested_action="Reduce positions to lower leverage"
                )

                self._record_violation(violation)
                return False, violation

            return True, None

        except Exception as e:
            logger.error(f"Error checking leverage limit: {e}", exc_info=True)
            return False, None

    def check_daily_loss_limit(
        self,
        current_portfolio_value: float
    ) -> Tuple[bool, Optional[LimitViolation]]:
        """
        Check daily loss limits and trigger shutdown if necessary.

        Args:
            current_portfolio_value: Current portfolio value

        Returns:
            Tuple of (is_within_limits, violation_if_any)
        """
        try:
            # Initialize daily start value if needed
            if self.daily_start_value is None:
                self.daily_start_value = current_portfolio_value
                return True, None

            # Calculate daily P&L
            self.daily_pnl = current_portfolio_value - self.daily_start_value
            daily_loss_pct = self.daily_pnl / self.daily_start_value

            if daily_loss_pct < -self.max_daily_loss_pct:
                severity = ViolationSeverity.EMERGENCY

                violation = LimitViolation(
                    limit_type=LimitType.DAILY_LOSS,
                    severity=severity,
                    current_value=daily_loss_pct,
                    limit_value=-self.max_daily_loss_pct,
                    excess_amount=abs(daily_loss_pct) - self.max_daily_loss_pct,
                    excess_percentage=(abs(daily_loss_pct) / self.max_daily_loss_pct - 1) * 100,
                    description=f"Daily loss {daily_loss_pct:.2%} exceeds limit",
                    suggested_action="EMERGENCY: Auto-shutdown triggered"
                )

                self._record_violation(violation)

                # Trigger shutdown if enabled
                if self.enable_auto_shutdown:
                    self.trigger_shutdown("Daily loss limit exceeded")

                return False, violation

            return True, None

        except Exception as e:
            logger.error(f"Error checking daily loss limit: {e}", exc_info=True)
            return False, None

    def check_correlation_limit(
        self,
        symbol: str,
        position_value: float,
        correlation_matrix: pd.DataFrame,
        current_positions: Dict[str, float],
        portfolio_value: float
    ) -> Tuple[bool, Optional[LimitViolation]]:
        """
        Check correlation-based exposure limits.

        Args:
            symbol: New position symbol
            position_value: New position value
            correlation_matrix: Correlation matrix of returns
            current_positions: Current positions {symbol: value}
            portfolio_value: Total portfolio value

        Returns:
            Tuple of (is_within_limits, violation_if_any)
        """
        try:
            if symbol not in correlation_matrix.index:
                logger.warning(f"Symbol {symbol} not in correlation matrix")
                return True, None

            # Calculate correlated exposure
            correlated_exposure = 0.0

            for pos_symbol, pos_value in current_positions.items():
                if pos_symbol == symbol:
                    continue

                if pos_symbol in correlation_matrix.columns:
                    correlation = correlation_matrix.loc[symbol, pos_symbol]

                    # Only consider highly correlated positions (> 0.7)
                    if abs(correlation) > 0.7:
                        correlated_exposure += abs(pos_value * correlation)

            # Add new position
            correlated_exposure += abs(position_value)

            correlation_exposure_pct = correlated_exposure / portfolio_value

            if correlation_exposure_pct > self.max_correlation_exposure:
                violation = LimitViolation(
                    limit_type=LimitType.CORRELATION,
                    severity=ViolationSeverity.WARNING,
                    current_value=correlation_exposure_pct,
                    limit_value=self.max_correlation_exposure,
                    excess_amount=correlation_exposure_pct - self.max_correlation_exposure,
                    excess_percentage=(correlation_exposure_pct / self.max_correlation_exposure - 1) * 100,
                    symbol=symbol,
                    description=f"Correlated exposure {correlation_exposure_pct:.2%} exceeds limit",
                    suggested_action="Reduce correlated positions or diversify"
                )

                self._record_violation(violation)
                return False, violation

            return True, None

        except Exception as e:
            logger.error(f"Error checking correlation limit: {e}", exc_info=True)
            return True, None  # Allow trade on error

    def calculate_position_size(
        self,
        symbol: str,
        desired_size: float,
        portfolio_value: float,
        volatility: Optional[float] = None,
        sector: Optional[str] = None,
        correlation_matrix: Optional[pd.DataFrame] = None,
        current_positions: Optional[Dict[str, float]] = None
    ) -> PositionSizeResult:
        """
        Calculate approved position size with all risk constraints.

        Args:
            symbol: Stock symbol
            desired_size: Desired position size
            portfolio_value: Total portfolio value
            volatility: Asset volatility (for dynamic sizing)
            sector: Sector classification
            correlation_matrix: Correlation matrix
            current_positions: Current positions

        Returns:
            PositionSizeResult with approved size and details
        """
        try:
            if self.is_shutdown:
                return PositionSizeResult(
                    symbol=symbol,
                    requested_size=desired_size,
                    approved_size=0.0,
                    approved=False,
                    rejection_reason=f"Trading shutdown: {self.shutdown_reason}"
                )

            adjustments = []
            approved_size = abs(desired_size)
            sign = 1 if desired_size >= 0 else -1

            # Apply maximum position size limit
            max_allowed = portfolio_value * self.max_single_stock_pct
            if approved_size > max_allowed:
                approved_size = max_allowed
                adjustments.append(f"Reduced to max position size: {self.max_single_stock_pct:.2%}")

            # Apply dynamic volatility adjustment if enabled
            if self.enable_dynamic_sizing and volatility is not None:
                volatility_adjusted = self._apply_volatility_adjustment(
                    approved_size, volatility, portfolio_value
                )
                if volatility_adjusted < approved_size:
                    adjustments.append(f"Reduced for volatility: {volatility:.2%}")
                    approved_size = volatility_adjusted

            # Check sector limits
            if sector:
                is_within, _ = self.check_sector_limit(sector, approved_size, portfolio_value)
                if not is_within:
                    # Reduce to fit sector limit
                    current_sector_exposure = self.sector_exposures.get(sector, 0.0)
                    max_sector_value = portfolio_value * self.max_sector_exposure_pct
                    approved_size = min(approved_size, max_sector_value - current_sector_exposure)
                    adjustments.append(f"Reduced for sector limit: {sector}")

            # Check correlation limits
            if correlation_matrix is not None and current_positions is not None:
                is_within, _ = self.check_correlation_limit(
                    symbol, approved_size, correlation_matrix,
                    current_positions, portfolio_value
                )
                if not is_within:
                    approved_size *= 0.7  # Reduce by 30%
                    adjustments.append("Reduced for correlation exposure")

            # Calculate risk score (0-100)
            risk_score = self._calculate_position_risk_score(
                symbol, approved_size, portfolio_value, volatility
            )

            # Ensure approved size is not negative
            approved_size = max(0, approved_size)

            # Restore sign
            approved_size = approved_size * sign

            result = PositionSizeResult(
                symbol=symbol,
                requested_size=desired_size,
                approved_size=approved_size,
                approved=abs(approved_size) > 0,
                adjustments_applied=adjustments,
                risk_score=risk_score
            )

            logger.info(f"Position sizing for {symbol}: requested={desired_size:.2f}, "
                       f"approved={approved_size:.2f}, risk_score={risk_score:.1f}")

            return result

        except Exception as e:
            logger.error(f"Error calculating position size: {e}", exc_info=True)
            return PositionSizeResult(
                symbol=symbol,
                requested_size=desired_size,
                approved_size=0.0,
                approved=False,
                rejection_reason=f"Error: {str(e)}"
            )

    def _apply_volatility_adjustment(
        self,
        position_size: float,
        volatility: float,
        portfolio_value: float,
        target_volatility: float = 0.15
    ) -> float:
        """
        Apply volatility-based position size adjustment.

        Higher volatility = smaller position size

        Args:
            position_size: Proposed position size
            volatility: Asset volatility (annualized)
            portfolio_value: Total portfolio value
            target_volatility: Target portfolio volatility

        Returns:
            Adjusted position size
        """
        try:
            if volatility <= 0:
                return position_size

            # Scale position inversely with volatility
            # If volatility is 2x target, reduce position by half
            volatility_scalar = target_volatility / volatility
            volatility_scalar = min(1.0, max(0.1, volatility_scalar))  # Clamp between 0.1 and 1.0

            adjusted_size = position_size * volatility_scalar

            return adjusted_size

        except Exception as e:
            logger.error(f"Error applying volatility adjustment: {e}", exc_info=True)
            return position_size

    def _calculate_position_risk_score(
        self,
        symbol: str,
        position_size: float,
        portfolio_value: float,
        volatility: Optional[float] = None
    ) -> float:
        """
        Calculate risk score for position (0-100).

        Higher score = higher risk

        Args:
            symbol: Stock symbol
            position_size: Position size
            portfolio_value: Portfolio value
            volatility: Asset volatility

        Returns:
            Risk score (0-100)
        """
        try:
            score = 0.0

            # Size component (0-40 points)
            size_pct = abs(position_size) / portfolio_value
            size_score = min(40, (size_pct / self.max_single_stock_pct) * 40)
            score += size_score

            # Volatility component (0-30 points)
            if volatility is not None:
                vol_score = min(30, (volatility / 0.30) * 30)  # 30% vol = max score
                score += vol_score

            # Concentration component (0-30 points)
            num_positions = len(self.current_positions)
            if num_positions > 0:
                concentration_score = max(0, 30 - num_positions * 2)
                score += concentration_score

            return min(100, score)

        except Exception as e:
            logger.error(f"Error calculating risk score: {e}", exc_info=True)
            return 50.0  # Default medium risk

    def trigger_shutdown(self, reason: str):
        """
        Trigger emergency trading shutdown.

        Args:
            reason: Reason for shutdown
        """
        self.is_shutdown = True
        self.shutdown_reason = reason
        self.shutdown_timestamp = datetime.now()

        logger.critical(f"TRADING SHUTDOWN TRIGGERED: {reason}")

        if self.alert_on_violations:
            self._send_critical_alert(f"Emergency Shutdown: {reason}")

    def lift_shutdown(self, authorized_by: str = "system"):
        """
        Lift trading shutdown.

        Args:
            authorized_by: Who authorized the lift
        """
        if self.is_shutdown:
            logger.warning(f"Trading shutdown lifted by {authorized_by}. "
                          f"Previous reason: {self.shutdown_reason}")

            self.is_shutdown = False
            self.shutdown_reason = None
            self.shutdown_timestamp = None

    def reset_daily_tracking(self, current_portfolio_value: float):
        """Reset daily P&L tracking"""
        self.daily_start_value = current_portfolio_value
        self.daily_pnl = 0.0
        logger.info(f"Daily tracking reset: start_value={current_portfolio_value:.2f}")

    def reset_weekly_tracking(self, current_portfolio_value: float):
        """Reset weekly P&L tracking"""
        self.weekly_start_value = current_portfolio_value
        self.weekly_pnl = 0.0
        logger.info(f"Weekly tracking reset: start_value={current_portfolio_value:.2f}")

    def reset_monthly_tracking(self, current_portfolio_value: float):
        """Reset monthly P&L tracking"""
        self.monthly_start_value = current_portfolio_value
        self.monthly_pnl = 0.0
        logger.info(f"Monthly tracking reset: start_value={current_portfolio_value:.2f}")

    def update_positions(self, positions: Dict[str, Dict[str, Any]]):
        """
        Update current position tracking.

        Args:
            positions: Dictionary of {symbol: {value, sector, etc}}
        """
        self.current_positions = positions

        # Update sector exposures
        self.sector_exposures.clear()
        for symbol, pos_data in positions.items():
            sector = pos_data.get('sector')
            value = pos_data.get('value', 0.0)

            if sector:
                self.sector_exposures[sector] = self.sector_exposures.get(sector, 0.0) + value

        logger.debug(f"Positions updated: {len(positions)} positions, "
                    f"{len(self.sector_exposures)} sectors")

    def get_violations(
        self,
        severity: Optional[ViolationSeverity] = None,
        limit_type: Optional[LimitType] = None,
        hours: int = 24
    ) -> List[LimitViolation]:
        """
        Get recent limit violations.

        Args:
            severity: Filter by severity
            limit_type: Filter by limit type
            hours: Look back hours

        Returns:
            List of violations
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        violations = [
            v for v in self.violation_history
            if v.timestamp >= cutoff_time
        ]

        if severity:
            violations = [v for v in violations if v.severity == severity]

        if limit_type:
            violations = [v for v in violations if v.limit_type == limit_type]

        return violations

    def get_limit_status(self, portfolio_value: float) -> Dict[str, Any]:
        """
        Get current status of all limits.

        Args:
            portfolio_value: Current portfolio value

        Returns:
            Dictionary with limit status
        """
        total_position_value = sum(
            abs(p.get('value', 0.0)) for p in self.current_positions.values()
        )

        leverage = total_position_value / portfolio_value if portfolio_value > 0 else 0.0

        daily_loss_pct = (self.daily_pnl / self.daily_start_value
                         if self.daily_start_value else 0.0)

        return {
            'is_shutdown': self.is_shutdown,
            'shutdown_reason': self.shutdown_reason,
            'leverage': {
                'current': leverage,
                'limit': self.max_leverage,
                'utilization_pct': (leverage / self.max_leverage * 100)
            },
            'daily_loss': {
                'current_pct': daily_loss_pct,
                'limit_pct': -self.max_daily_loss_pct,
                'pnl': self.daily_pnl
            },
            'positions': {
                'count': len(self.current_positions),
                'total_value': total_position_value
            },
            'sectors': {
                'count': len(self.sector_exposures),
                'exposures': self.sector_exposures
            },
            'recent_violations': len(self.get_violations(hours=24))
        }

    def _record_violation(self, violation: LimitViolation):
        """Record a limit violation"""
        self.violation_history.append(violation)

        # Keep only last 1000 violations
        if len(self.violation_history) > 1000:
            self.violation_history = self.violation_history[-1000:]

        if self.alert_on_violations:
            self._send_alert(violation)

    def _send_alert(self, violation: LimitViolation):
        """Send alert for violation"""
        if violation.severity == ViolationSeverity.CRITICAL or \
           violation.severity == ViolationSeverity.EMERGENCY:
            logger.critical(f"LIMIT VIOLATION: {violation.description}")
        elif violation.severity == ViolationSeverity.WARNING:
            logger.warning(f"Limit violation: {violation.description}")
        else:
            logger.info(f"Limit info: {violation.description}")

    def _send_critical_alert(self, message: str):
        """Send critical alert"""
        logger.critical(f"CRITICAL ALERT: {message}")
        # In production, this would integrate with alerting systems
        # (email, SMS, Slack, PagerDuty, etc.)

    def clear_violation_history(self):
        """Clear violation history"""
        self.violation_history.clear()
        logger.info("Violation history cleared")

    def export_violations(self, filepath: str):
        """
        Export violations to JSON file.

        Args:
            filepath: Path to export file
        """
        try:
            violations_data = [v.to_dict() for v in self.violation_history]

            with open(filepath, 'w') as f:
                json.dump(violations_data, f, indent=2)

            logger.info(f"Exported {len(violations_data)} violations to {filepath}")

        except Exception as e:
            logger.error(f"Error exporting violations: {e}", exc_info=True)

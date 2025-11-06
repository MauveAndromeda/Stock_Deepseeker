"""
Risk limit system for portfolio risk control.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
import pandas as pd
from loguru import logger


class LimitType(Enum):
    """Risk limit types."""
    POSITION_SIZE = "position_size"
    LEVERAGE = "leverage"
    DRAWDOWN = "drawdown"
    VOLATILITY = "volatility"
    VAR = "var"
    CONCENTRATION = "concentration"
    EXPOSURE = "exposure"


class LimitSeverity(Enum):
    """Limit violation severity."""
    WARNING = "warning"
    BREACH = "breach"
    CRITICAL = "critical"


@dataclass
class RiskLimit:
    """Risk limit definition."""
    name: str
    limit_type: LimitType
    soft_limit: float  # Warning threshold
    hard_limit: float  # Breach threshold
    critical_limit: Optional[float] = None  # Critical threshold
    enabled: bool = True


@dataclass
class LimitViolation:
    """Limit violation event."""
    timestamp: datetime
    limit: RiskLimit
    current_value: float
    severity: LimitSeverity
    excess: float
    metadata: Dict = field(default_factory=dict)


class RiskLimitSystem:
    """
    Comprehensive risk limit monitoring and enforcement.
    """
    
    def __init__(self):
        """Initialize risk limit system."""
        self.limits: Dict[str, RiskLimit] = {}
        self.violation_history: List[LimitViolation] = []
        self._create_default_limits()
        
        logger.info("Initialized RiskLimitSystem")
    
    def _create_default_limits(self) -> None:
        """Create standard risk limits."""
        default_limits = [
            RiskLimit(
                name="max_single_position",
                limit_type=LimitType.POSITION_SIZE,
                soft_limit=0.15,  # 15% warning
                hard_limit=0.20,  # 20% breach
                critical_limit=0.30  # 30% critical
            ),
            RiskLimit(
                name="max_leverage",
                limit_type=LimitType.LEVERAGE,
                soft_limit=1.5,  # 1.5x warning
                hard_limit=2.0,  # 2x breach
                critical_limit=3.0  # 3x critical
            ),
            RiskLimit(
                name="max_drawdown",
                limit_type=LimitType.DRAWDOWN,
                soft_limit=-0.10,  # -10% warning
                hard_limit=-0.15,  # -15% breach
                critical_limit=-0.20  # -20% critical
            ),
            RiskLimit(
                name="max_volatility",
                limit_type=LimitType.VOLATILITY,
                soft_limit=0.25,  # 25% warning
                hard_limit=0.35,  # 35% breach
                critical_limit=0.50  # 50% critical
            ),
            RiskLimit(
                name="max_var_99",
                limit_type=LimitType.VAR,
                soft_limit=-0.03,  # -3% daily VaR warning
                hard_limit=-0.05,  # -5% breach
                critical_limit=-0.08  # -8% critical
            ),
        ]
        
        for limit in default_limits:
            self.limits[limit.name] = limit
    
    def add_limit(self, limit: RiskLimit) -> None:
        """Add custom risk limit."""
        self.limits[limit.name] = limit
        logger.info(f"Added risk limit: {limit.name}")
    
    def check_limits(self, metrics: Dict[str, float]) -> List[LimitViolation]:
        """Check all limits against current metrics."""
        violations = []
        
        for name, limit in self.limits.items():
            if not limit.enabled:
                continue
            
            # Map metric name to limit name
            metric_value = metrics.get(name)
            if metric_value is None:
                continue
            
            # Check violation
            violation = self._check_single_limit(limit, metric_value)
            
            if violation:
                violations.append(violation)
                self.violation_history.append(violation)
                
                logger.warning(
                    f"Risk limit violation: {limit.name} "
                    f"[{violation.severity.value.upper()}] "
                    f"Value={metric_value:.4f}, Limit={limit.hard_limit:.4f}"
                )
        
        return violations
    
    def _check_single_limit(
        self,
        limit: RiskLimit,
        value: float
    ) -> Optional[LimitViolation]:
        """Check single limit."""
        severity = None
        threshold = None
        
        # Determine severity
        if limit.critical_limit is not None:
            if (value > limit.critical_limit if limit.critical_limit > 0 
                else value < limit.critical_limit):
                severity = LimitSeverity.CRITICAL
                threshold = limit.critical_limit
        
        if severity is None:
            if (value > limit.hard_limit if limit.hard_limit > 0 
                else value < limit.hard_limit):
                severity = LimitSeverity.BREACH
                threshold = limit.hard_limit
        
        if severity is None:
            if (value > limit.soft_limit if limit.soft_limit > 0 
                else value < limit.soft_limit):
                severity = LimitSeverity.WARNING
                threshold = limit.soft_limit
        
        if severity is None:
            return None
        
        excess = abs(value - threshold)
        
        return LimitViolation(
            timestamp=datetime.now(),
            limit=limit,
            current_value=value,
            severity=severity,
            excess=excess
        )
    
    def get_limit_status(self) -> pd.DataFrame:
        """Get status of all limits."""
        status_data = []
        
        for name, limit in self.limits.items():
            status_data.append({
                'name': name,
                'type': limit.limit_type.value,
                'soft_limit': limit.soft_limit,
                'hard_limit': limit.hard_limit,
                'critical_limit': limit.critical_limit,
                'enabled': limit.enabled
            })
        
        return pd.DataFrame(status_data)
    
    def get_violation_history(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """Get violation history."""
        if len(self.violation_history) == 0:
            return pd.DataFrame()
        
        data = []
        for v in self.violation_history:
            if start_date and v.timestamp < start_date:
                continue
            if end_date and v.timestamp > end_date:
                continue
            
            data.append({
                'timestamp': v.timestamp,
                'limit_name': v.limit.name,
                'limit_type': v.limit.limit_type.value,
                'severity': v.severity.value,
                'value': v.current_value,
                'threshold': v.limit.hard_limit,
                'excess': v.excess
            })
        
        return pd.DataFrame(data)
    
    def reset_violations(self) -> None:
        """Clear violation history."""
        self.violation_history.clear()
        logger.info("Risk limit violations cleared")

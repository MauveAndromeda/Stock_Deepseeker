"""
Dynamic stop-loss management system.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional
from enum import Enum
import pandas as pd
from loguru import logger


class StopLossType(Enum):
    """Stop-loss types."""
    FIXED = "fixed"
    TRAILING = "trailing"
    VOLATILITY_BASED = "volatility_based"
    TIME_BASED = "time_based"


@dataclass
class StopLossConfig:
    """Stop-loss configuration."""
    type: StopLossType
    threshold: float  # Loss threshold (e.g., -0.05 for 5%)
    trailing_distance: Optional[float] = None  # For trailing stops
    volatility_multiplier: Optional[float] = None  # For vol-based stops
    time_horizon_days: Optional[int] = None  # For time-based stops


@dataclass
class StopLossEvent:
    """Stop-loss trigger event."""
    timestamp: datetime
    symbol: str
    entry_price: float
    current_price: float
    loss_amount: float
    loss_pct: float
    stop_type: StopLossType


class StopLossManager:
    """Dynamic stop-loss management."""
    
    def __init__(self, config: StopLossConfig):
        """Initialize stop-loss manager."""
        self.config = config
        self.position_stops: Dict[str, Dict] = {}
        logger.info(f"Initialized StopLossManager: {config.type.value}")
    
    def add_position(
        self,
        symbol: str,
        entry_price: float,
        entry_time: datetime
    ) -> None:
        """Add position with stop-loss."""
        self.position_stops[symbol] = {
            'entry_price': entry_price,
            'entry_time': entry_time,
            'stop_price': entry_price * (1 + self.config.threshold),
            'highest_price': entry_price,
        }
    
    def check_stops(
        self,
        current_prices: Dict[str, float],
        volatilities: Optional[Dict[str, float]] = None
    ) -> List[StopLossEvent]:
        """Check if any stops are hit."""
        events = []
        
        for symbol, stop_data in list(self.position_stops.items()):
            if symbol not in current_prices:
                continue
            
            current_price = current_prices[symbol]
            entry_price = stop_data['entry_price']
            
            # Update stop based on type
            if self.config.type == StopLossType.TRAILING:
                self._update_trailing_stop(symbol, current_price)
            elif self.config.type == StopLossType.VOLATILITY_BASED and volatilities:
                self._update_volatility_stop(symbol, current_price, volatilities.get(symbol, 0))
            
            # Check if stop hit
            stop_price = stop_data['stop_price']
            
            if current_price <= stop_price:
                loss_amount = current_price - entry_price
                loss_pct = loss_amount / entry_price
                
                event = StopLossEvent(
                    timestamp=datetime.now(),
                    symbol=symbol,
                    entry_price=entry_price,
                    current_price=current_price,
                    loss_amount=loss_amount,
                    loss_pct=loss_pct,
                    stop_type=self.config.type
                )
                
                events.append(event)
                logger.warning(f"Stop-loss triggered: {symbol} at {current_price:.2f}")
        
        return events
    
    def _update_trailing_stop(self, symbol: str, current_price: float) -> None:
        """Update trailing stop-loss."""
        stop_data = self.position_stops[symbol]
        
        # Update highest price
        if current_price > stop_data['highest_price']:
            stop_data['highest_price'] = current_price
            
            # Update stop price
            trail_distance = self.config.trailing_distance or abs(self.config.threshold)
            stop_data['stop_price'] = current_price * (1 - trail_distance)
    
    def _update_volatility_stop(
        self,
        symbol: str,
        current_price: float,
        volatility: float
    ) -> None:
        """Update volatility-based stop-loss."""
        multiplier = self.config.volatility_multiplier or 2.0
        stop_distance = volatility * multiplier
        
        self.position_stops[symbol]['stop_price'] = current_price * (1 - stop_distance)
    
    def remove_position(self, symbol: str) -> None:
        """Remove position from stop-loss tracking."""
        if symbol in self.position_stops:
            del self.position_stops[symbol]

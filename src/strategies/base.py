"""
Base strategy class.

All trading strategies should inherit from BaseStrategy.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class SignalType(Enum):
    """Signal types."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Signal:
    """Trading signal."""
    timestamp: datetime
    symbol: str
    signal_type: SignalType
    strength: float  # 0.0 to 1.0
    price: Optional[float] = None
    quantity: Optional[float] = None
    metadata: Dict = None


class BaseStrategy(ABC):
    """
    Base strategy class.
    
    All strategies must implement on_data() method.
    """
    
    def __init__(self, name: str = "BaseStrategy"):
        """Initialize strategy."""
        self.name = name
        self.positions = {}
        self.signals_history = []
    
    @abstractmethod
    def on_data(self, data: Dict) -> List[Signal]:
        """
        Process new market data and generate signals.
        
        Args:
            data: Dictionary with market data
        
        Returns:
            List of trading signals
        """
        pass
    
    def on_fill(self, fill):
        """Called when order is filled."""
        pass
    
    def on_order_update(self, order):
        """Called when order status changes."""
        pass
    
    def reset(self):
        """Reset strategy state."""
        self.positions = {}
        self.signals_history = []

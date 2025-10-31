"""
Base Strategy Class
Abstract base class for all trading strategies
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd
import numpy as np
from loguru import logger

@dataclass
class Position:
    """Represents a trading position"""
    symbol: str
    quantity: float
    entry_price: float
    entry_time: datetime
    current_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_type: str = "long"

    @property
    def unrealized_pnl(self) -> float:
        if self.position_type == "long":
            return (self.current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.current_price) * self.quantity

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.position_type == "long":
            return (self.current_price / self.entry_price - 1) * 100
        else:
            return (1 - self.current_price / self.entry_price) * 100

    def update_price(self, price: float):
        self.current_price = price

    def should_stop_loss(self) -> bool:
        if self.stop_loss is None:
            return False
        if self.position_type == "long":
            return self.current_price <= self.stop_loss
        else:
            return self.current_price >= self.stop_loss

    def should_take_profit(self) -> bool:
        if self.take_profit is None:
            return False
        if self.position_type == "long":
            return self.current_price >= self.take_profit
        else:
            return self.current_price <= self.take_profit

@dataclass
class Trade:
    """Represents a completed trade"""
    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    position_type: str
    pnl: float
    pnl_pct: float
    commission: float
    reason: str

@dataclass
class Signal:
    """Trading signal"""
    symbol: str
    timestamp: datetime
    action: str
    strength: float
    confidence: float
    metadata: Dict = field(default_factory=dict)

@dataclass
class StrategyConfig:
    """Strategy configuration"""
    name: str
    enabled: bool = True
    max_positions: int = 10
    max_position_size: float = 0.1
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.05
    trailing_stop_pct: Optional[float] = None
    min_holding_period: int = 1
    max_holding_period: Optional[int] = None
    allow_short: bool = False
    risk_per_trade: float = 0.01

class BaseStrategy(ABC):
    """Abstract base class for trading strategies"""

    def __init__(self, config: StrategyConfig):
        self.config = config
        self.positions: Dict[str, Position] = {}
        self.closed_trades: List[Trade] = []
        self.signals: List[Signal] = []
        self.total_pnl = 0.0
        self.win_count = 0
        self.loss_count = 0
        logger.info(f"Initialized strategy: {self.config.name}")

    @abstractmethod
    def analyze(self, data: pd.DataFrame, symbol: str) -> Signal:
        pass

    @abstractmethod
    def should_enter(self, data: pd.DataFrame, symbol: str) -> Tuple[bool, str]:
        pass

    @abstractmethod
    def should_exit(self, position: Position, data: pd.DataFrame) -> Tuple[bool, str]:
        pass

    def calculate_position_size(
        self, symbol: str, price: float, portfolio_value: float, volatility: Optional[float] = None
    ) -> float:
        max_position_value = portfolio_value * self.config.max_position_size
        risk_amount = portfolio_value * self.config.risk_per_trade
        stop_loss_distance = price * self.config.stop_loss_pct
        if stop_loss_distance > 0:
            risk_based_shares = risk_amount / stop_loss_distance
        else:
            risk_based_shares = float('inf')
        max_shares = max_position_value / price
        shares = min(risk_based_shares, max_shares)
        if volatility is not None and volatility > 0:
            vol_adjustment = 1 / (1 + volatility)
            shares *= vol_adjustment
        return int(shares)

    def open_position(
        self, symbol: str, price: float, quantity: float, 
        position_type: str = "long", timestamp: Optional[datetime] = None
    ) -> Position:
        if timestamp is None:
            timestamp = datetime.now()
        if position_type == "long":
            stop_loss = price * (1 - self.config.stop_loss_pct)
            take_profit = price * (1 + self.config.take_profit_pct)
        else:
            stop_loss = price * (1 + self.config.stop_loss_pct)
            take_profit = price * (1 - self.config.take_profit_pct)
        position = Position(
            symbol=symbol, quantity=quantity, entry_price=price,
            entry_time=timestamp, current_price=price,
            stop_loss=stop_loss, take_profit=take_profit,
            position_type=position_type
        )
        self.positions[symbol] = position
        logger.info(f"Opened {position_type} position: {symbol} @ ${price:.2f}, qty={quantity}")
        return position

    def close_position(
        self, symbol: str, price: float, reason: str = "signal",
        timestamp: Optional[datetime] = None, commission: float = 0.0
    ) -> Optional[Trade]:
        if symbol not in self.positions:
            return None
        if timestamp is None:
            timestamp = datetime.now()
        position = self.positions[symbol]
        if position.position_type == "long":
            pnl = (price - position.entry_price) * position.quantity
            pnl_pct = (price / position.entry_price - 1) * 100
        else:
            pnl = (position.entry_price - price) * position.quantity
            pnl_pct = (1 - price / position.entry_price) * 100
        pnl -= commission
        trade = Trade(
            symbol=symbol, entry_time=position.entry_time, exit_time=timestamp,
            entry_price=position.entry_price, exit_price=price,
            quantity=position.quantity, position_type=position.position_type,
            pnl=pnl, pnl_pct=pnl_pct, commission=commission, reason=reason
        )
        self.total_pnl += pnl
        if pnl > 0:
            self.win_count += 1
        else:
            self.loss_count += 1
        self.closed_trades.append(trade)
        del self.positions[symbol]
        logger.info(f"Closed position: {symbol} @ ${price:.2f}, P&L=${pnl:.2f}")
        return trade

    def get_performance_metrics(self) -> Dict:
        if not self.closed_trades:
            return {"total_trades": 0, "total_pnl": 0.0, "win_rate": 0.0}
        total_trades = len(self.closed_trades)
        winning_trades = [t for t in self.closed_trades if t.pnl > 0]
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        return {
            "total_trades": total_trades,
            "total_pnl": self.total_pnl,
            "win_rate": win_rate,
            "open_positions": len(self.positions)
        }

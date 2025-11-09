"""
Portfolio Manager v2 - Enhanced position tracking and P&L calculation.

Features:
- Real-time position tracking
- Accurate P&L calculation
- Commission and slippage tracking
- Risk metrics
- Trade history
"""

from dataclasses import dataclass
from datetime import datetime

from loguru import logger
import numpy as np
import pandas as pd

from src.backtest.events import FillEvent


@dataclass
class Position:
    """
    Represents a position in a single security.

    Attributes:
        symbol: Stock symbol
        quantity: Number of shares (positive=long, negative=short)
        avg_cost: Average cost basis per share
        last_price: Most recent market price
        unrealized_pnl: Unrealized profit/loss
        realized_pnl: Realized profit/loss from closed trades
    """
    symbol: str
    quantity: float = 0.0
    avg_cost: float = 0.0
    last_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    @property
    def market_value(self) -> float:
        """Current market value of position."""
        return self.quantity * self.last_price

    @property
    def cost_basis(self) -> float:
        """Total cost basis."""
        return self.quantity * self.avg_cost

    @property
    def total_pnl(self) -> float:
        """Total P&L (realized + unrealized)."""
        return self.realized_pnl + self.unrealized_pnl

    def update_price(self, price: float) -> None:
        """
        Update market price and recalculate unrealized P&L.

        Args:
            price: New market price
        """
        self.last_price = price
        self.unrealized_pnl = (price - self.avg_cost) * self.quantity


@dataclass
class Trade:
    """
    Represents a completed trade.

    Attributes:
        timestamp: Trade execution time
        symbol: Stock symbol
        quantity: Number of shares
        price: Execution price
        commission: Commission paid
        slippage: Slippage cost
        direction: 'BUY' or 'SELL'
        pnl: Profit/loss (for sells)
    """
    timestamp: datetime
    symbol: str
    quantity: float
    price: float
    commission: float
    slippage: float
    direction: str
    pnl: float = 0.0


class PortfolioV2:
    """
    Portfolio manager with enhanced tracking and analytics.

    Tracks:
    - Cash balance
    - Positions (long and short)
    - Trade history
    - Equity curve
    - Performance metrics
    """

    def __init__(
        self,
        initial_capital: float,
        commission_rate: float = 0.001,
        slippage_rate: float = 0.0005
    ) -> None:
        """
        Initialize portfolio.

        Args:
            initial_capital: Starting cash
            commission_rate: Commission as decimal (e.g., 0.001 = 0.1%)
            slippage_rate: Slippage as decimal
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate

        # Positions
        self.positions: dict[str, Position] = {}

        # History
        self.trades: list[Trade] = []
        self.equity_history: list[dict] = []

        # Statistics
        self.total_commission_paid = 0.0
        self.total_slippage_paid = 0.0

        logger.info(f"Initialized portfolio with ${initial_capital:,.2f}")

    @property
    def positions_value(self) -> float:
        """Total value of all positions."""
        return sum(pos.market_value for pos in self.positions.values())

    @property
    def total_value(self) -> float:
        """Total portfolio value (cash + positions)."""
        return self.cash + self.positions_value

    @property
    def total_return(self) -> float:
        """Total return as decimal."""
        return (self.total_value - self.initial_capital) / self.initial_capital

    def get_position(self, symbol: str) -> Position | None:
        """
        Get position for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Position or None if not held
        """
        return self.positions.get(symbol)

    def update_fill(self, fill: FillEvent) -> None:
        """
        Update portfolio with a fill event.

        Args:
            fill: Fill event
        """
        symbol = fill.symbol
        quantity = fill.quantity if fill.direction == "BUY" else -fill.quantity
        price = fill.fill_price

        # Get or create position
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol, last_price=price)

        position = self.positions[symbol]

        # Calculate realized P&L for closing trades
        realized_pnl = 0.0
        if (position.quantity > 0 and quantity < 0) or (position.quantity < 0 and quantity > 0):
            # Closing trade
            closed_quantity = min(abs(quantity), abs(position.quantity))
            realized_pnl = closed_quantity * (price - position.avg_cost)
            if position.quantity < 0:
                realized_pnl = -realized_pnl
            position.realized_pnl += realized_pnl

        # Update position
        old_quantity = position.quantity
        new_quantity = old_quantity + quantity

        if new_quantity == 0:
            # Position closed
            position.quantity = 0
            position.avg_cost = 0
            position.unrealized_pnl = 0
        elif (old_quantity >= 0 and quantity > 0) or (old_quantity <= 0 and quantity < 0):
            # Adding to position
            total_cost = abs(old_quantity) * position.avg_cost + abs(quantity) * price
            position.avg_cost = total_cost / abs(new_quantity)
            position.quantity = new_quantity
        else:
            # Reducing position
            position.quantity = new_quantity

        position.last_price = price
        position.unrealized_pnl = (price - position.avg_cost) * position.quantity

        # Update cash
        trade_value = quantity * price
        total_cost = trade_value + fill.commission + fill.slippage
        self.cash -= total_cost

        # Update statistics
        self.total_commission_paid += fill.commission
        self.total_slippage_paid += fill.slippage

        # Record trade
        trade = Trade(
            timestamp=fill.timestamp,
            symbol=symbol,
            quantity=abs(quantity),
            price=price,
            commission=fill.commission,
            slippage=fill.slippage,
            direction=fill.direction,
            pnl=realized_pnl
        )
        self.trades.append(trade)

        logger.debug(
            f"Fill: {fill.direction} {abs(quantity)} {symbol} @ ${price:.2f}, "
            f"P&L: ${realized_pnl:.2f}"
        )

    def update_prices(self, date: datetime, prices: dict[str, float]) -> None:
        """
        Update positions with latest prices.

        Args:
            date: Current date
            prices: Dict of symbol -> price
        """
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].update_price(price)

        # Record equity point
        self.equity_history.append({
            "date": date,
            "cash": self.cash,
            "positions_value": self.positions_value,
            "total_value": self.total_value,
            "total_return": self.total_return,
        })

    def get_all_positions(self) -> dict[str, Position]:
        """Get all positions."""
        return {
            symbol: pos for symbol, pos in self.positions.items()
            if pos.quantity != 0
        }

    def get_trade_history(self) -> list[Trade]:
        """Get trade history."""
        return self.trades.copy()

    def get_equity_curve(self) -> pd.DataFrame:
        """
        Get equity curve as DataFrame.

        Returns:
            DataFrame with equity history
        """
        if not self.equity_history:
            return pd.DataFrame()

        df = pd.DataFrame(self.equity_history)
        df.set_index("date", inplace=True)
        return df

    def close_all_positions(self, date: datetime) -> None:
        """
        Close all positions at market prices.

        Args:
            date: Closing date
        """
        for symbol, position in list(self.positions.items()):
            if position.quantity != 0:
                # Create synthetic fill to close position
                fill = FillEvent(
                    timestamp=date,
                    symbol=symbol,
                    quantity=abs(position.quantity),
                    fill_price=position.last_price,
                    commission=0.0,  # No commission on forced close
                    slippage=0.0,
                    direction="SELL" if position.quantity > 0 else "BUY"
                )
                self.update_fill(fill)

        logger.info(f"Closed all positions on {date.date()}")

    def get_performance_stats(self) -> dict:
        """
        Calculate performance statistics.

        Returns:
            Dict with performance metrics
        """
        if not self.equity_history:
            return {}

        df = self.get_equity_curve()

        returns = df["total_value"].pct_change().dropna()

        stats = {
            "total_return": self.total_return,
            "total_trades": len(self.trades),
            "total_commission": self.total_commission_paid,
            "total_slippage": self.total_slippage_paid,
            "final_value": self.total_value,
        }

        if len(returns) > 0:
            stats.update({
                "sharpe_ratio": np.sqrt(252) * returns.mean() / returns.std() if returns.std() > 0 else 0,
                "max_drawdown": self._calculate_max_drawdown(df["total_value"]),
                "winning_trades": sum(1 for t in self.trades if t.pnl > 0),
                "losing_trades": sum(1 for t in self.trades if t.pnl < 0),
            })

            if stats["total_trades"] > 0:
                stats["win_rate"] = stats["winning_trades"] / stats["total_trades"]

        return stats

    def _calculate_max_drawdown(self, equity: pd.Series) -> float:
        """Calculate maximum drawdown."""
        cummax = equity.cummax()
        drawdown = (equity - cummax) / cummax
        return drawdown.min()

"""
Trade-level analytics and analysis.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


@dataclass
class Trade:
    """Individual trade record."""
    symbol: str
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    quantity: float
    side: str  # 'long' or 'short'
    pnl: float
    pnl_pct: float
    holding_period: timedelta
    commission: float = 0.0
    slippage: float = 0.0

    @property
    def is_winner(self) -> bool:
        """Check if trade was profitable."""
        return self.pnl > 0

    def __repr__(self) -> str:
        return (
            f"Trade({self.symbol}, {self.side}, "
            f"P&L={self.pnl:.2f} ({self.pnl_pct:.2%}), "
            f"hold={self.holding_period.days}d)"
        )


@dataclass
class TradeStats:
    """Aggregated trade statistics."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float

    total_pnl: float
    avg_pnl: float
    avg_win: float
    avg_loss: float

    largest_win: float
    largest_loss: float

    profit_factor: float
    expectancy: float

    avg_holding_period: float
    avg_win_holding: float
    avg_loss_holding: float

    consecutive_wins: int
    consecutive_losses: int
    max_consecutive_wins: int
    max_consecutive_losses: int

    total_commission: float
    total_slippage: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "Total Trades": self.total_trades,
            "Win Rate": f"{self.win_rate:.2%}",
            "Total P&L": f"${self.total_pnl:,.2f}",
            "Avg P&L": f"${self.avg_pnl:,.2f}",
            "Profit Factor": f"{self.profit_factor:.2f}",
            "Expectancy": f"${self.expectancy:,.2f}",
            "Avg Holding": f"{self.avg_holding_period:.1f} days",
            "Max Consecutive Wins": self.max_consecutive_wins,
            "Max Consecutive Losses": self.max_consecutive_losses
        }


class TradeAnalyzer:
    """
    Analyze individual trades and trading patterns.

    Provides detailed trade-level analytics including:
    - Trade statistics
    - Win/loss analysis
    - Holding period analysis
    - Trade clustering
    - Performance by time of day, day of week, etc.
    """

    def __init__(self):
        """Initialize trade analyzer."""
        self.trades: list[Trade] = []

    def add_trade(self, trade: Trade) -> None:
        """Add a trade to the analyzer."""
        self.trades.append(trade)

    def add_trades(self, trades: list[Trade]) -> None:
        """Add multiple trades."""
        self.trades.extend(trades)

    def calculate_stats(self) -> TradeStats:
        """Calculate comprehensive trade statistics."""
        if len(self.trades) == 0:
            return self._empty_stats()

        winners = [t for t in self.trades if t.is_winner]
        losers = [t for t in self.trades if not t.is_winner]

        # Basic counts
        total_trades = len(self.trades)
        winning_trades = len(winners)
        losing_trades = len(losers)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        # P&L metrics
        total_pnl = sum(t.pnl for t in self.trades)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0.0

        total_wins = sum(t.pnl for t in winners)
        total_losses = abs(sum(t.pnl for t in losers))

        avg_win = total_wins / winning_trades if winning_trades > 0 else 0.0
        avg_loss = -total_losses / losing_trades if losing_trades > 0 else 0.0

        largest_win = max((t.pnl for t in self.trades), default=0.0)
        largest_loss = min((t.pnl for t in self.trades), default=0.0)

        profit_factor = total_wins / total_losses if total_losses > 0 else 0.0
        expectancy = avg_pnl

        # Holding period
        avg_holding = np.mean([t.holding_period.total_seconds() / 86400 for t in self.trades])
        avg_win_holding = np.mean(
            [t.holding_period.total_seconds() / 86400 for t in winners]
        ) if winners else 0.0
        avg_loss_holding = np.mean(
            [t.holding_period.total_seconds() / 86400 for t in losers]
        ) if losers else 0.0

        # Consecutive wins/losses
        streaks = self._calculate_streaks()

        # Costs
        total_commission = sum(t.commission for t in self.trades)
        total_slippage = sum(t.slippage for t in self.trades)

        return TradeStats(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_pnl=avg_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            profit_factor=profit_factor,
            expectancy=expectancy,
            avg_holding_period=avg_holding,
            avg_win_holding=avg_win_holding,
            avg_loss_holding=avg_loss_holding,
            consecutive_wins=streaks["current_wins"],
            consecutive_losses=streaks["current_losses"],
            max_consecutive_wins=streaks["max_wins"],
            max_consecutive_losses=streaks["max_losses"],
            total_commission=total_commission,
            total_slippage=total_slippage
        )

    def analyze_by_symbol(self) -> dict[str, TradeStats]:
        """Calculate statistics grouped by symbol."""
        by_symbol = defaultdict(list)

        for trade in self.trades:
            by_symbol[trade.symbol].append(trade)

        results = {}
        for symbol, trades in by_symbol.items():
            analyzer = TradeAnalyzer()
            analyzer.trades = trades
            results[symbol] = analyzer.calculate_stats()

        return results

    def analyze_by_side(self) -> dict[str, TradeStats]:
        """Calculate statistics grouped by side (long/short)."""
        by_side = defaultdict(list)

        for trade in self.trades:
            by_side[trade.side].append(trade)

        results = {}
        for side, trades in by_side.items():
            analyzer = TradeAnalyzer()
            analyzer.trades = trades
            results[side] = analyzer.calculate_stats()

        return results

    def analyze_by_holding_period(
        self,
        buckets: list[tuple[int, int]] = [(0, 1), (1, 5), (5, 20), (20, 100)]
    ) -> dict[str, TradeStats]:
        """
        Calculate statistics grouped by holding period.

        Args:
            buckets: List of (min_days, max_days) tuples

        Returns:
            Dictionary mapping bucket name to stats
        """
        by_period = defaultdict(list)

        for trade in self.trades:
            days = trade.holding_period.days

            for min_days, max_days in buckets:
                if min_days <= days < max_days:
                    bucket_name = f"{min_days}-{max_days} days"
                    by_period[bucket_name].append(trade)
                    break

        results = {}
        for period, trades in by_period.items():
            analyzer = TradeAnalyzer()
            analyzer.trades = trades
            results[period] = analyzer.calculate_stats()

        return results

    def analyze_by_time(self) -> dict[str, dict]:
        """Analyze performance by time patterns."""
        by_hour = defaultdict(list)
        by_day_of_week = defaultdict(list)
        by_month = defaultdict(list)

        for trade in self.trades:
            # Hour of entry
            hour = trade.entry_date.hour
            by_hour[hour].append(trade.pnl)

            # Day of week
            day_name = trade.entry_date.strftime("%A")
            by_day_of_week[day_name].append(trade.pnl)

            # Month
            month_name = trade.entry_date.strftime("%B")
            by_month[month_name].append(trade.pnl)

        return {
            "by_hour": {h: np.mean(pnls) for h, pnls in by_hour.items()},
            "by_day_of_week": {d: np.mean(pnls) for d, pnls in by_day_of_week.items()},
            "by_month": {m: np.mean(pnls) for m, pnls in by_month.items()}
        }

    def get_trade_distribution(self, bins: int = 20) -> tuple[np.ndarray, np.ndarray]:
        """
        Get distribution of trade P&L.

        Args:
            bins: Number of histogram bins

        Returns:
            Tuple of (bin_edges, frequencies)
        """
        if len(self.trades) == 0:
            return np.array([]), np.array([])

        pnls = [t.pnl_pct for t in self.trades]
        hist, bin_edges = np.histogram(pnls, bins=bins)

        return bin_edges, hist

    def get_equity_curve(self, starting_capital: float = 100000) -> pd.Series:
        """
        Calculate equity curve from trades.

        Args:
            starting_capital: Starting capital

        Returns:
            Series with cumulative equity
        """
        if len(self.trades) == 0:
            return pd.Series([starting_capital])

        # Sort trades by exit date
        sorted_trades = sorted(self.trades, key=lambda t: t.exit_date)

        equity = [starting_capital]
        dates = [sorted_trades[0].entry_date]

        for trade in sorted_trades:
            equity.append(equity[-1] + trade.pnl)
            dates.append(trade.exit_date)

        return pd.Series(equity, index=dates)

    def find_best_worst_trades(self, n: int = 10) -> tuple[list[Trade], list[Trade]]:
        """
        Find best and worst trades.

        Args:
            n: Number of trades to return

        Returns:
            Tuple of (best_trades, worst_trades)
        """
        sorted_by_pnl = sorted(self.trades, key=lambda t: t.pnl, reverse=True)

        best = sorted_by_pnl[:n]
        worst = sorted_by_pnl[-n:]

        return best, worst

    def _calculate_streaks(self) -> dict[str, int]:
        """Calculate winning/losing streaks."""
        if len(self.trades) == 0:
            return {
                "current_wins": 0,
                "current_losses": 0,
                "max_wins": 0,
                "max_losses": 0
            }

        current_wins = 0
        current_losses = 0
        max_wins = 0
        max_losses = 0

        for trade in self.trades:
            if trade.is_winner:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)

        return {
            "current_wins": current_wins,
            "current_losses": current_losses,
            "max_wins": max_wins,
            "max_losses": max_losses
        }

    def _empty_stats(self) -> TradeStats:
        """Return empty stats."""
        return TradeStats(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_pnl=0.0,
            avg_pnl=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            largest_win=0.0,
            largest_loss=0.0,
            profit_factor=0.0,
            expectancy=0.0,
            avg_holding_period=0.0,
            avg_win_holding=0.0,
            avg_loss_holding=0.0,
            consecutive_wins=0,
            consecutive_losses=0,
            max_consecutive_wins=0,
            max_consecutive_losses=0,
            total_commission=0.0,
            total_slippage=0.0
        )

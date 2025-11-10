"""Lightweight portfolio implementation for compatibility tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from src.backtest.events import FillEvent, OrderSide


@dataclass
class Position:
    """Represents a single security holding."""

    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0
    last_price: float = 0.0

    def market_value(self, price: float | None = None) -> float:
        reference_price = price if price is not None else (self.last_price or self.avg_price)
        return self.quantity * reference_price


class Portfolio:
    """Simplified portfolio used by the comprehensive backtest tests."""

    def __init__(self, initial_capital: float) -> None:
        self.initial_capital = float(initial_capital)
        self.current_cash = float(initial_capital)
        self.realized_pnl = 0.0
        self.positions: Dict[str, Position] = {}

    # ------------------------------------------------------------------
    # Fill processing
    # ------------------------------------------------------------------
    def process_fill(self, fill: FillEvent) -> None:
        """Update portfolio state from an executed trade."""

        position = self.positions.setdefault(fill.symbol, Position(symbol=fill.symbol))

        quantity = float(fill.quantity)
        price = float(fill.price)
        total_trade_value = quantity * price
        trading_costs = float(fill.commission) + float(fill.slippage)

        if fill.side == OrderSide.BUY:
            # Update weighted average price for the position
            new_quantity = position.quantity + quantity
            if new_quantity > 0:
                previous_cost = position.quantity * position.avg_price
                position.avg_price = (previous_cost + total_trade_value) / new_quantity
            else:
                position.avg_price = price

            position.quantity = new_quantity
            self.current_cash -= total_trade_value + trading_costs

        else:  # SELL
            sell_quantity = quantity

            # Realized P&L from the portion being closed
            realized = (price - position.avg_price) * sell_quantity
            self.realized_pnl += realized - trading_costs

            position.quantity -= sell_quantity
            if abs(position.quantity) < 1e-9:
                position.quantity = 0.0
                position.avg_price = 0.0

            self.current_cash += total_trade_value - trading_costs

        position.last_price = price

    # ------------------------------------------------------------------
    # Valuation helpers
    # ------------------------------------------------------------------
    def get_total_value(self, current_prices: dict[str, float] | None = None) -> float:
        """Calculate total portfolio value given optional market prices."""

        total_value = self.current_cash

        price_lookup = current_prices or {}

        for symbol, position in self.positions.items():
            market_price = price_lookup.get(symbol)
            if market_price is not None:
                position.last_price = market_price
            total_value += position.market_value(price_lookup.get(symbol))

        return total_value


__all__ = ["Portfolio", "Position"]


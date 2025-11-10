"""Compatibility backtest engine used by the test-suite."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Iterable

import pandas as pd

from src.backtest.events import (
    Event,
    EventType,
    MarketEvent,
    OrderEvent,
    OrderSide,
    OrderType,
    SignalEvent,
)
from src.backtest.execution import ExecutionHandler
from src.backtest.portfolio import Portfolio
from src.core.performance import PerformanceAnalyzer


@dataclass
class BacktestResult:
    """Container for backtest outputs."""

    equity_curve: pd.Series
    returns: pd.Series
    total_return: float
    sharpe_ratio: float
    max_drawdown: float


class BacktestEngine:
    """Minimal event-driven backtest engine compatible with unit tests."""

    def __init__(
        self,
        initial_capital: float,
        start_date: datetime,
        end_date: datetime,
        *,
        commission: float = 0.001,
        slippage: float = 0.0005
    ) -> None:
        self.initial_capital = float(initial_capital)
        self.start_date = start_date
        self.end_date = end_date

        self.commission_rate = commission
        self.slippage_rate = slippage

        self.portfolio = Portfolio(initial_capital)
        self.execution = ExecutionHandler(commission=commission, slippage=slippage)
        self.performance = PerformanceAnalyzer()

        self.event_queue: Deque[Event] = deque()
        self.latest_prices: dict[str, float] = {}
        self.equity_points: list[tuple[datetime, float]] = []

        self.current_time: datetime | None = None
        self.results: BacktestResult | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self, strategy: object, market_data: pd.DataFrame) -> BacktestResult:
        """Execute the backtest over the provided market data."""

        # Reset state for each run
        self.portfolio = Portfolio(self.initial_capital)
        self.execution = ExecutionHandler(
            commission=self.commission_rate,
            slippage=self.slippage_rate,
        )
        self.event_queue.clear()
        self.latest_prices.clear()
        self.equity_points.clear()
        self.current_time = None

        if market_data is None or market_data.empty:
            empty_series = pd.Series(dtype=float)
            self.results = BacktestResult(
                equity_curve=empty_series,
                returns=empty_series,
                total_return=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
            )
            return self.results

        for market_event in self._iterate_market_events(market_data):
            self.event_queue.append(market_event)
            self._process_next_event(strategy)

        result = self._finalize_results()
        self.results = result
        return result

    # ------------------------------------------------------------------
    # Event processing
    # ------------------------------------------------------------------
    def _process_next_event(self, strategy: object) -> None:
        if not self.event_queue:
            return

        event = self.event_queue.popleft()
        self.current_time = event.timestamp

        if event.type == EventType.MARKET:
            self._handle_market_event(event, strategy)

    def _handle_market_event(self, event: MarketEvent, strategy: object) -> None:
        symbol = event.symbol
        execution_price = self._extract_price(event)
        if symbol is not None and execution_price is not None:
            self.latest_prices[symbol] = execution_price

        signal_events: Iterable[SignalEvent] = []
        if hasattr(strategy, "on_market_data"):
            signal = strategy.on_market_data(event)
            if signal is None:
                signal_events = []
            elif isinstance(signal, Iterable) and not isinstance(signal, SignalEvent):
                signal_events = signal
            else:
                signal_events = [signal]

        for signal_event in signal_events:
            orders = self._generate_orders(strategy, signal_event)
            for order in orders:
                fill = self.execution.execute_order(order, execution_price)
                if fill is not None:
                    self.portfolio.process_fill(fill)

        if symbol is not None and execution_price is not None:
            total_value = self.portfolio.get_total_value(self.latest_prices)
            self.equity_points.append((event.timestamp, total_value))

    def _generate_orders(
        self,
        strategy: object,
        signal: SignalEvent
    ) -> Iterable[OrderEvent]:
        if hasattr(strategy, "generate_orders"):
            orders = strategy.generate_orders(signal, self.portfolio)
            if orders is None:
                return []
            return orders

        side = OrderSide.BUY if signal.signal_type.upper() == "BUY" else OrderSide.SELL
        return [
            OrderEvent(
                timestamp=signal.timestamp,
                symbol=signal.symbol,
                order_type=OrderType.MARKET,
                quantity=1,
                side=side,
            )
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _extract_price(self, event: MarketEvent) -> float | None:
        if not event.data:
            return None
        for key in ("close", "price", "last", "adjusted_close"):
            if key in event.data:
                return float(event.data[key])
        return None

    def _iterate_market_events(
        self,
        market_data: pd.DataFrame
    ) -> Iterable[MarketEvent]:
        df = market_data.copy()

        if df.index.nlevels == 2:
            df = df.sort_index()
            for (timestamp, symbol), row in df.iterrows():
                if not (self.start_date <= timestamp <= self.end_date):
                    continue
                yield MarketEvent(timestamp=timestamp, symbol=symbol, data=row.to_dict())
        else:
            if "symbol" in df.columns:
                df = df.sort_values(by=[df.index.name or "date", "symbol"])
            else:
                df = df.sort_index()

            for idx, row in df.iterrows():
                timestamp = idx if isinstance(idx, datetime) else row.get("date")
                if timestamp is None:
                    continue
                if not isinstance(timestamp, datetime):
                    timestamp = pd.to_datetime(timestamp).to_pydatetime()
                if not (self.start_date <= timestamp <= self.end_date):
                    continue
                symbol = row.get("symbol")
                yield MarketEvent(timestamp=timestamp, symbol=symbol, data=row.to_dict())

    def _finalize_results(self) -> BacktestResult:
        if not self.equity_points:
            empty = pd.Series(dtype=float)
            return BacktestResult(
                equity_curve=empty,
                returns=empty,
                total_return=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
            )

        times, values = zip(*self.equity_points)
        equity_curve = pd.Series(values, index=pd.DatetimeIndex(times), name="equity")

        returns = equity_curve.pct_change().dropna()

        total_return = self.performance.calculate_total_return(returns)
        sharpe_ratio = self.performance.calculate_sharpe_ratio(returns)
        max_drawdown = self.performance.calculate_max_drawdown(returns)

        return BacktestResult(
            equity_curve=equity_curve,
            returns=returns,
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
        )


__all__ = ["BacktestEngine", "BacktestResult"]


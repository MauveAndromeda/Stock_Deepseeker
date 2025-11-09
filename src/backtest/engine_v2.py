"""
Backtest Engine v2 - No Lookahead Bias.

Strictly enforces no lookahead bias through:
1. Event-driven architecture with strict time ordering
2. Automatic signal shift (T signal -> T+1 execution)
3. Realistic market simulation
4. Proper data alignment
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from loguru import logger
import numpy as np
import pandas as pd

from src.backtest.events import (
    Event,
    EventType,
    FillEvent,
    MarketEvent,
    OrderEvent,
    SignalEvent,
)
from src.backtest.execution import ExecutionHandler
from src.backtest.portfolio_v2 import PortfolioV2
from src.data.providers.base import PriceData


class BacktestPhase(Enum):
    """Phases of backtest execution."""
    INITIALIZATION = "initialization"
    DATA_LOADING = "data_loading"
    WARMUP = "warmup"              # Build initial factor history
    TRADING = "trading"             # Active trading
    FINALIZATION = "finalization"   # Close all positions
    COMPLETED = "completed"


@dataclass
class BacktestConfig:
    """
    Configuration for backtest engine.

    Attributes:
        start_date: Backtest start date
        end_date: Backtest end date
        initial_capital: Starting capital
        warmup_period: Days for factor calculation warmup
        commission: Commission rate (as decimal)
        slippage: Slippage (as decimal)
        trade_on_close: Whether to trade on close prices
        allow_fractional_shares: Whether to allow fractional shares
        min_order_value: Minimum order value
        max_position_size: Maximum position size (as decimal of portfolio)
        enable_short_selling: Whether to allow short selling
        margin_requirement: Margin requirement for shorts
    """
    start_date: datetime
    end_date: datetime
    initial_capital: float = 100000.0
    warmup_period: int = 252  # 1 year of trading days
    commission: float = 0.001  # 0.1%
    slippage: float = 0.0005   # 0.05%
    trade_on_close: bool = True
    allow_fractional_shares: bool = False
    min_order_value: float = 100.0
    max_position_size: float = 0.2  # 20% max
    enable_short_selling: bool = False
    margin_requirement: float = 0.5  # 50% for shorts


class Strategy(ABC):
    """
    Abstract base class for trading strategies.

    All strategies must implement generate_signals method.
    """

    def __init__(self, name: str) -> None:
        """
        Initialize strategy.

        Args:
            name: Strategy name
        """
        self.name = name
        self.signals_generated = 0

    @abstractmethod
    def generate_signals(
        self,
        date: datetime,
        data: dict[str, pd.DataFrame],
        portfolio: "PortfolioV2"
    ) -> list[SignalEvent]:
        """
        Generate trading signals.

        IMPORTANT: This method is called with data available UP TO AND INCLUDING
        the current date. The signals will be executed on the NEXT trading day.
        This automatically prevents lookahead bias.

        Args:
            date: Current date (signal generation date)
            data: Historical data available up to this date
            portfolio: Current portfolio state

        Returns:
            List of signal events
        """

    def on_market_open(self, date: datetime, portfolio: "PortfolioV2") -> None:
        """
        Called at market open.

        Args:
            date: Current date
            portfolio: Portfolio state
        """

    def on_market_close(self, date: datetime, portfolio: "PortfolioV2") -> None:
        """
        Called at market close.

        Args:
            date: Current date
            portfolio: Portfolio state
        """


class BacktestEngineV2:
    """
    Event-driven backtest engine with strict no-lookahead bias.

    Key features:
    1. Event queue with strict time ordering
    2. Automatic signal delay (T signal -> T+1 execution)
    3. Realistic execution simulation
    4. Proper handling of market open/close
    5. Data alignment validation
    """

    def __init__(self, config: BacktestConfig) -> None:
        """
        Initialize backtest engine.

        Args:
            config: Backtest configuration
        """
        self.config = config
        self.current_date: datetime | None = None
        self.phase = BacktestPhase.INITIALIZATION

        # Event queue (sorted by time)
        self.events: list[Event] = []

        # Data storage
        self.price_data: dict[str, pd.DataFrame] = {}
        self.trading_calendar: list[datetime] = []

        # Components
        self.portfolio: PortfolioV2 | None = None
        self.execution: ExecutionHandler | None = None
        self.strategy: Strategy | None = None

        # Signals awaiting execution
        self.pending_signals: list[SignalEvent] = []

        # Statistics
        self.stats = {
            "total_events": 0,
            "market_events": 0,
            "signal_events": 0,
            "order_events": 0,
            "fill_events": 0,
            "rejected_orders": 0,
        }

        logger.info(f"Initialized BacktestEngineV2: {config.start_date.date()} to {config.end_date.date()}")

    def load_data(self, price_data: dict[str, PriceData]) -> None:
        """
        Load price data for backtest.

        Args:
            price_data: Dict mapping symbols to PriceData objects

        Raises:
            ValueError: If data is invalid or has lookahead issues
        """
        logger.info(f"Loading data for {len(price_data)} symbols")

        self.price_data = {}

        for symbol, pdata in price_data.items():
            df = pdata.data.copy()

            # Ensure datetime index
            if not isinstance(df.index, pd.DatetimeIndex):
                raise ValueError(f"Data for {symbol} must have DatetimeIndex")

            # Ensure timezone-naive
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            # Filter to backtest date range (including warmup)
            warmup_start = self.config.start_date - timedelta(days=self.config.warmup_period)
            df = df[(df.index >= warmup_start) & (df.index <= self.config.end_date)]

            if df.empty:
                logger.warning(f"No data for {symbol} in backtest range")
                continue

            # Normalize column names
            df.columns = df.columns.str.lower()

            # Validate required columns
            required = ["open", "high", "low", "close", "volume"]
            missing = set(required) - set(df.columns)
            if missing:
                raise ValueError(f"Missing columns for {symbol}: {missing}")

            self.price_data[symbol] = df

            logger.debug(f"Loaded {len(df)} rows for {symbol}")

        # Build trading calendar from union of all dates
        all_dates = set()
        for df in self.price_data.values():
            all_dates.update(df.index)

        self.trading_calendar = sorted(all_dates)
        logger.info(f"Trading calendar: {len(self.trading_calendar)} dates")

        self.phase = BacktestPhase.DATA_LOADING

    def set_strategy(self, strategy: Strategy) -> None:
        """
        Set trading strategy.

        Args:
            strategy: Strategy instance
        """
        self.strategy = strategy
        logger.info(f"Set strategy: {strategy.name}")

    def _get_available_data(self, date: datetime) -> dict[str, pd.DataFrame]:
        """
        Get data available up to (and including) a specific date.

        This is crucial for preventing lookahead bias.

        Args:
            date: Current date

        Returns:
            Dict of data available up to this date
        """
        available_data = {}

        for symbol, df in self.price_data.items():
            # Only include data up to and including current date
            mask = df.index <= date
            available_data[symbol] = df[mask].copy()

        return available_data

    def _create_market_event(self, date: datetime) -> MarketEvent:
        """
        Create market event for a trading day.

        Args:
            date: Trading date

        Returns:
            MarketEvent
        """
        return MarketEvent(timestamp=date, data={
            "date": date,
            "symbols": list(self.price_data.keys())
        })

    def _process_market_event(self, event: MarketEvent) -> None:
        """
        Process market event.

        1. Update portfolio with latest prices
        2. Execute pending orders from previous day
        3. Generate new signals for next day

        Args:
            event: Market event
        """
        self.stats["market_events"] += 1
        date = event.timestamp

        logger.debug(f"Processing market event: {date.date()}")

        # Call strategy market open hook
        if self.strategy:
            self.strategy.on_market_open(date, self.portfolio)

        # Execute pending orders from previous day's signals
        # This is KEY to preventing lookahead bias:
        # Signals generated on day T are executed on day T+1
        if self.pending_signals:
            logger.debug(f"Executing {len(self.pending_signals)} pending signals")

            for signal in self.pending_signals:
                # Convert signal to order
                order = self._signal_to_order(signal, date)
                if order:
                    self.events.append(order)

            self.pending_signals.clear()

        # Update portfolio with current prices
        current_prices = {}
        for symbol, df in self.price_data.items():
            if date in df.index:
                # Use close price for valuation
                current_prices[symbol] = df.loc[date, "close"]

        if self.portfolio:
            self.portfolio.update_prices(date, current_prices)

        # Generate signals for NEXT day
        # These will be executed tomorrow
        if self.strategy and self.phase == BacktestPhase.TRADING:
            available_data = self._get_available_data(date)
            signals = self.strategy.generate_signals(date, available_data, self.portfolio)

            if signals:
                logger.debug(f"Generated {len(signals)} signals for next day")
                self.pending_signals.extend(signals)
                self.stats["signal_events"] += len(signals)

        # Call strategy market close hook
        if self.strategy:
            self.strategy.on_market_close(date, self.portfolio)

    def _signal_to_order(
        self,
        signal: SignalEvent,
        execution_date: datetime
    ) -> OrderEvent | None:
        """
        Convert signal to order with risk checks.

        Args:
            signal: Signal event
            execution_date: Date when order will be executed

        Returns:
            OrderEvent or None if rejected
        """
        # Get current price for the symbol
        if signal.symbol not in self.price_data:
            logger.warning(f"No data for {signal.symbol}, rejecting order")
            return None

        df = self.price_data[signal.symbol]
        if execution_date not in df.index:
            logger.warning(f"No price data for {signal.symbol} on {execution_date.date()}")
            return None

        # Use open price for execution (assuming trade at open)
        # Or close price if trade_on_close=True
        if self.config.trade_on_close:
            execution_price = df.loc[execution_date, "close"]
        else:
            execution_price = df.loc[execution_date, "open"]

        # Calculate order quantity
        quantity = self._calculate_order_quantity(signal, execution_price)

        if quantity == 0:
            logger.debug(f"Zero quantity for {signal.symbol}, skipping")
            return None

        # Create order event
        order = OrderEvent(
            timestamp=execution_date,
            symbol=signal.symbol,
            order_type="MARKET",
            quantity=quantity,
            direction="BUY" if quantity > 0 else "SELL",
            price=execution_price,
        )

        self.stats["order_events"] += 1
        return order

    def _calculate_order_quantity(
        self,
        signal: SignalEvent,
        price: float
    ) -> int:
        """
        Calculate order quantity based on signal and portfolio constraints.

        Args:
            signal: Signal event
            price: Execution price

        Returns:
            Order quantity (positive for buy, negative for sell)
        """
        if not self.portfolio:
            return 0

        # Get current position
        current_position = self.portfolio.get_position(signal.symbol)

        # Calculate target position
        if signal.signal_type == "LONG":
            target_value = self.portfolio.total_value * signal.strength
        elif signal.signal_type == "SHORT":
            if not self.config.enable_short_selling:
                return 0
            target_value = -self.portfolio.total_value * signal.strength
        elif signal.signal_type == "EXIT":
            target_value = 0
        else:
            return 0

        # Apply max position size constraint
        max_value = self.portfolio.total_value * self.config.max_position_size
        target_value = np.clip(target_value, -max_value, max_value)

        # Calculate shares needed
        target_shares = target_value / price if price > 0 else 0
        current_shares = current_position.quantity if current_position else 0

        # Order quantity is the difference
        quantity = target_shares - current_shares

        # Round to integer shares if needed
        if not self.config.allow_fractional_shares:
            quantity = int(quantity)

        return quantity

    def run(self) -> dict[str, Any]:
        """
        Run the backtest.

        Returns:
            Dict with backtest results and statistics
        """
        if not self.strategy:
            raise ValueError("Strategy not set")

        if not self.price_data:
            raise ValueError("No price data loaded")

        # Initialize components
        self.portfolio = PortfolioV2(
            initial_capital=self.config.initial_capital,
            commission_rate=self.config.commission,
            slippage_rate=self.config.slippage,
        )

        self.execution = ExecutionHandler(
            portfolio=self.portfolio,
            price_data=self.price_data,
            config=self.config,
        )

        # Run phases
        self._run_warmup()
        self._run_trading()
        self._run_finalization()

        # Collect results
        results = self._collect_results()

        self.phase = BacktestPhase.COMPLETED
        logger.info("Backtest completed successfully")

        return results

    def _run_warmup(self) -> None:
        """Run warmup period to build factor history."""
        self.phase = BacktestPhase.WARMUP

        warmup_start = self.config.start_date - timedelta(days=self.config.warmup_period)
        warmup_dates = [d for d in self.trading_calendar if warmup_start <= d < self.config.start_date]

        logger.info(f"Warmup period: {len(warmup_dates)} days")

        for date in warmup_dates:
            self.current_date = date
            # Just update data, don't trade
            available_data = self._get_available_data(date)
            # Strategy can use this to build factor history
            if self.strategy and hasattr(self.strategy, "on_warmup"):
                self.strategy.on_warmup(date, available_data)

    def _run_trading(self) -> None:
        """Run main trading period."""
        self.phase = BacktestPhase.TRADING

        trading_dates = [
            d for d in self.trading_calendar
            if self.config.start_date <= d <= self.config.end_date
        ]

        logger.info(f"Trading period: {len(trading_dates)} days")

        for date in trading_dates:
            self.current_date = date

            # Create market event
            market_event = self._create_market_event(date)
            self.events.append(market_event)

            # Process all events for this date
            while self.events:
                event = self.events.pop(0)
                self.stats["total_events"] += 1

                if event.event_type == EventType.MARKET:
                    self._process_market_event(event)
                elif event.event_type == EventType.ORDER:
                    self._process_order_event(event)
                elif event.event_type == EventType.FILL:
                    self._process_fill_event(event)

            # Log progress
            if date.day == 1 or date == trading_dates[-1]:
                logger.info(
                    f"Progress: {date.date()} - "
                    f"Portfolio value: ${self.portfolio.total_value:,.2f}"
                )

    def _run_finalization(self) -> None:
        """Close all positions and finalize backtest."""
        self.phase = BacktestPhase.FINALIZATION

        logger.info("Finalizing backtest: closing all positions")

        # Close all positions at final prices
        if self.portfolio:
            self.portfolio.close_all_positions(self.current_date)

    def _process_order_event(self, event: OrderEvent) -> None:
        """
        Process order event through execution handler.

        Args:
            event: Order event
        """
        if not self.execution:
            return

        fill_event = self.execution.execute_order(event)

        if fill_event:
            self.events.append(fill_event)
        else:
            self.stats["rejected_orders"] += 1

    def _process_fill_event(self, event: FillEvent) -> None:
        """
        Process fill event by updating portfolio.

        Args:
            event: Fill event
        """
        if not self.portfolio:
            return

        self.portfolio.update_fill(event)
        self.stats["fill_events"] += 1

    def _collect_results(self) -> dict[str, Any]:
        """
        Collect backtest results.

        Returns:
            Dict with all results and statistics
        """
        if not self.portfolio:
            return {}

        results = {
            "config": self.config,
            "statistics": self.stats,
            "portfolio": {
                "final_value": self.portfolio.total_value,
                "total_return": (
                    (self.portfolio.total_value - self.config.initial_capital)
                    / self.config.initial_capital
                ),
                "positions": self.portfolio.get_all_positions(),
                "trades": self.portfolio.get_trade_history(),
            },
            "equity_curve": self.portfolio.get_equity_curve(),
            "strategy": self.strategy.name if self.strategy else None,
        }

        return results


# Example usage will be in a separate file

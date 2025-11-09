"""
Base classes for corporate action processing.

Defines interfaces and common functionality for handling corporate actions
like splits, dividends, mergers, etc.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger
import pandas as pd


class CorporateActionType(Enum):
    """Types of corporate actions."""
    SPLIT = "split"
    REVERSE_SPLIT = "reverse_split"
    DIVIDEND = "dividend"
    SPECIAL_DIVIDEND = "special_dividend"
    STOCK_DIVIDEND = "stock_dividend"
    RIGHTS_OFFERING = "rights_offering"
    SPIN_OFF = "spin_off"
    MERGER = "merger"
    ACQUISITION = "acquisition"
    DELISTING = "delisting"
    SYMBOL_CHANGE = "symbol_change"
    NAME_CHANGE = "name_change"


class AdjustmentMethod(Enum):
    """Price adjustment methods."""
    FORWARD = "forward"      # Adjust historical prices forward from split date
    BACKWARD = "backward"    # Adjust historical prices backward from today
    NONE = "none"           # No adjustment


@dataclass
class CorporateActionEvent:
    """
    Represents a corporate action event.

    Attributes:
        symbol: Stock symbol
        action_type: Type of corporate action
        ex_date: Ex-date (date when action takes effect)
        record_date: Record date (shareholders of record)
        payment_date: Payment date (for dividends)
        announcement_date: When action was announced
        ratio: Numerical ratio (e.g., 2.0 for 2-for-1 split)
        value: Monetary value (e.g., dividend amount)
        currency: Currency for monetary values
        new_symbol: New symbol (for symbol changes)
        details: Additional details
        source: Data source
        validated: Whether event has been validated
    """
    symbol: str
    action_type: CorporateActionType
    ex_date: datetime
    record_date: datetime | None = None
    payment_date: datetime | None = None
    announcement_date: datetime | None = None
    ratio: float | None = None
    value: float | None = None
    currency: str = "USD"
    new_symbol: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"
    validated: bool = False

    def __post_init__(self) -> None:
        """Validate corporate action event."""
        # Ensure ex_date is datetime
        if not isinstance(self.ex_date, datetime):
            raise ValueError("ex_date must be datetime")

        # Validate based on action type
        if self.action_type in [CorporateActionType.SPLIT, CorporateActionType.REVERSE_SPLIT]:
            if self.ratio is None or self.ratio <= 0:
                raise ValueError(f"{self.action_type.value} requires positive ratio")

        elif self.action_type in [CorporateActionType.DIVIDEND, CorporateActionType.SPECIAL_DIVIDEND]:
            if self.value is None or self.value <= 0:
                raise ValueError(f"{self.action_type.value} requires positive value")

        elif self.action_type == CorporateActionType.SYMBOL_CHANGE:
            if not self.new_symbol:
                raise ValueError("SYMBOL_CHANGE requires new_symbol")

    def __str__(self) -> str:
        """String representation."""
        if self.action_type in [CorporateActionType.SPLIT, CorporateActionType.REVERSE_SPLIT]:
            return f"{self.symbol} {self.action_type.value} {self.ratio}:1 on {self.ex_date.date()}"
        if self.action_type in [CorporateActionType.DIVIDEND, CorporateActionType.SPECIAL_DIVIDEND]:
            return f"{self.symbol} {self.action_type.value} ${self.value} on {self.ex_date.date()}"
        return f"{self.symbol} {self.action_type.value} on {self.ex_date.date()}"


class CorporateActionProcessor(ABC):
    """
    Abstract base class for corporate action processors.

    Each processor handles a specific type of corporate action.
    """

    def __init__(self) -> None:
        """Initialize processor."""
        self.events: list[CorporateActionEvent] = []
        self.adjustment_cache: dict[str, pd.DataFrame] = {}

    @abstractmethod
    def process_event(
        self,
        event: CorporateActionEvent,
        price_data: pd.DataFrame,
        method: AdjustmentMethod = AdjustmentMethod.BACKWARD
    ) -> pd.DataFrame:
        """
        Process a corporate action event and adjust prices.

        Args:
            event: Corporate action event
            price_data: Historical price data
            method: Adjustment method

        Returns:
            Adjusted price data
        """

    @abstractmethod
    def validate_event(self, event: CorporateActionEvent) -> tuple[bool, str | None]:
        """
        Validate a corporate action event.

        Args:
            event: Corporate action event

        Returns:
            Tuple of (is_valid, error_message)
        """

    def add_event(self, event: CorporateActionEvent) -> None:
        """
        Add a corporate action event.

        Args:
            event: Corporate action event

        Raises:
            ValueError: If event is invalid
        """
        is_valid, error = self.validate_event(event)
        if not is_valid:
            raise ValueError(f"Invalid corporate action: {error}")

        event.validated = True
        self.events.append(event)
        logger.info(f"Added corporate action: {event}")

    def get_events(
        self,
        symbol: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        action_type: CorporateActionType | None = None
    ) -> list[CorporateActionEvent]:
        """
        Get filtered corporate action events.

        Args:
            symbol: Filter by symbol
            start_date: Filter by start date
            end_date: Filter by end date
            action_type: Filter by action type

        Returns:
            List of filtered events
        """
        filtered_events = self.events

        if symbol:
            filtered_events = [e for e in filtered_events if e.symbol == symbol]

        if start_date:
            filtered_events = [e for e in filtered_events if e.ex_date >= start_date]

        if end_date:
            filtered_events = [e for e in filtered_events if e.ex_date <= end_date]

        if action_type:
            filtered_events = [e for e in filtered_events if e.action_type == action_type]

        return sorted(filtered_events, key=lambda x: x.ex_date)

    def clear_cache(self) -> None:
        """Clear adjustment cache."""
        self.adjustment_cache.clear()

    def get_adjustment_factor(
        self,
        event: CorporateActionEvent,
        date: datetime
    ) -> float:
        """
        Calculate adjustment factor for a given date.

        Args:
            event: Corporate action event
            date: Date for which to calculate factor

        Returns:
            Adjustment factor (1.0 = no adjustment)
        """
        # To be implemented by subclasses
        return 1.0


class CorporateActionDatabase:
    """
    Database for storing and retrieving corporate actions.

    Maintains a historical record of all corporate actions.
    """

    def __init__(self) -> None:
        """Initialize database."""
        self.events: dict[str, list[CorporateActionEvent]] = {}
        self.processors: dict[CorporateActionType, CorporateActionProcessor] = {}

    def add_event(self, event: CorporateActionEvent) -> None:
        """
        Add event to database.

        Args:
            event: Corporate action event
        """
        if event.symbol not in self.events:
            self.events[event.symbol] = []

        self.events[event.symbol].append(event)
        logger.debug(f"Added to database: {event}")

    def get_events(
        self,
        symbol: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        action_types: list[CorporateActionType] | None = None
    ) -> list[CorporateActionEvent]:
        """
        Get events for a symbol.

        Args:
            symbol: Stock symbol
            start_date: Filter by start date
            end_date: Filter by end date
            action_types: Filter by action types

        Returns:
            List of events
        """
        if symbol not in self.events:
            return []

        events = self.events[symbol]

        if start_date:
            events = [e for e in events if e.ex_date >= start_date]

        if end_date:
            events = [e for e in events if e.ex_date <= end_date]

        if action_types:
            events = [e for e in events if e.action_type in action_types]

        return sorted(events, key=lambda x: x.ex_date)

    def register_processor(
        self,
        action_type: CorporateActionType,
        processor: CorporateActionProcessor
    ) -> None:
        """
        Register a processor for an action type.

        Args:
            action_type: Type of corporate action
            processor: Processor instance
        """
        self.processors[action_type] = processor
        logger.info(f"Registered processor for {action_type.value}")

    def adjust_prices(
        self,
        symbol: str,
        price_data: pd.DataFrame,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        method: AdjustmentMethod = AdjustmentMethod.BACKWARD
    ) -> pd.DataFrame:
        """
        Adjust prices for all relevant corporate actions.

        Args:
            symbol: Stock symbol
            price_data: Historical price data
            start_date: Start date for adjustment
            end_date: End date for adjustment
            method: Adjustment method

        Returns:
            Adjusted price data
        """
        events = self.get_events(symbol, start_date, end_date)

        if not events:
            logger.debug(f"No corporate actions found for {symbol}")
            return price_data.copy()

        adjusted_data = price_data.copy()

        # Apply adjustments for each event
        for event in events:
            processor = self.processors.get(event.action_type)
            if processor:
                try:
                    adjusted_data = processor.process_event(event, adjusted_data, method)
                    logger.debug(f"Applied {event.action_type.value} adjustment for {symbol}")
                except Exception as e:
                    logger.error(f"Failed to process {event}: {e}")
                    continue
            else:
                logger.warning(f"No processor registered for {event.action_type.value}")

        return adjusted_data

    def export_to_dataframe(self, symbol: str | None = None) -> pd.DataFrame:
        """
        Export events to DataFrame.

        Args:
            symbol: Optional symbol filter

        Returns:
            DataFrame with all events
        """
        events_list = []

        symbols = [symbol] if symbol else self.events.keys()

        for sym in symbols:
            for event in self.events.get(sym, []):
                events_list.append({
                    "symbol": event.symbol,
                    "action_type": event.action_type.value,
                    "ex_date": event.ex_date,
                    "record_date": event.record_date,
                    "payment_date": event.payment_date,
                    "announcement_date": event.announcement_date,
                    "ratio": event.ratio,
                    "value": event.value,
                    "currency": event.currency,
                    "new_symbol": event.new_symbol,
                    "source": event.source,
                    "validated": event.validated,
                })

        return pd.DataFrame(events_list)

    def import_from_dataframe(self, df: pd.DataFrame) -> int:
        """
        Import events from DataFrame.

        Args:
            df: DataFrame with corporate action events

        Returns:
            Number of events imported
        """
        count = 0

        for _, row in df.iterrows():
            try:
                event = CorporateActionEvent(
                    symbol=row["symbol"],
                    action_type=CorporateActionType(row["action_type"]),
                    ex_date=pd.to_datetime(row["ex_date"]).to_pydatetime(),
                    record_date=pd.to_datetime(row.get("record_date")).to_pydatetime() if pd.notna(row.get("record_date")) else None,
                    payment_date=pd.to_datetime(row.get("payment_date")).to_pydatetime() if pd.notna(row.get("payment_date")) else None,
                    announcement_date=pd.to_datetime(row.get("announcement_date")).to_pydatetime() if pd.notna(row.get("announcement_date")) else None,
                    ratio=row.get("ratio") if pd.notna(row.get("ratio")) else None,
                    value=row.get("value") if pd.notna(row.get("value")) else None,
                    currency=row.get("currency", "USD"),
                    new_symbol=row.get("new_symbol") if pd.notna(row.get("new_symbol")) else None,
                    source=row.get("source", "import"),
                )
                self.add_event(event)
                count += 1
            except Exception as e:
                logger.error(f"Failed to import row: {e}")
                continue

        logger.info(f"Imported {count} corporate action events")
        return count

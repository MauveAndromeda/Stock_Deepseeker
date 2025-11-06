"""
Unified price adjustment system.

Combines all corporate action adjustments into a single interface.
"""

from datetime import datetime
from typing import List, Optional, Dict
import pandas as pd
from loguru import logger

from src.data.corporate_actions.base import (
    CorporateActionDatabase,
    CorporateActionEvent,
    CorporateActionType,
    AdjustmentMethod,
)
from src.data.corporate_actions.splits import SplitAdjuster
from src.data.corporate_actions.dividends import DividendProcessor


class PriceAdjuster:
    """
    Unified price adjustment system.

    Coordinates all corporate action processors to produce fully adjusted prices.
    """

    def __init__(
        self,
        adjust_for_splits: bool = True,
        adjust_for_dividends: bool = True,
        reinvest_dividends: bool = False,
        dividend_tax_rate: float = 0.0
    ) -> None:
        """
        Initialize price adjuster.

        Args:
            adjust_for_splits: Whether to adjust for splits
            adjust_for_dividends: Whether to adjust for dividends
            reinvest_dividends: Whether to simulate dividend reinvestment
            dividend_tax_rate: Tax rate on dividends
        """
        self.adjust_for_splits = adjust_for_splits
        self.adjust_for_dividends = adjust_for_dividends

        # Initialize database and processors
        self.database = CorporateActionDatabase()

        # Register processors
        if adjust_for_splits:
            split_adjuster = SplitAdjuster()
            self.database.register_processor(CorporateActionType.SPLIT, split_adjuster)
            self.database.register_processor(
                CorporateActionType.REVERSE_SPLIT,
                split_adjuster
            )

        if adjust_for_dividends:
            dividend_processor = DividendProcessor(
                reinvest_dividends=reinvest_dividends,
                tax_rate=dividend_tax_rate
            )
            self.database.register_processor(
                CorporateActionType.DIVIDEND,
                dividend_processor
            )
            self.database.register_processor(
                CorporateActionType.SPECIAL_DIVIDEND,
                dividend_processor
            )

    def add_events(self, events: List[CorporateActionEvent]) -> None:
        """
        Add corporate action events.

        Args:
            events: List of corporate action events
        """
        for event in events:
            self.database.add_event(event)
            logger.debug(f"Added event: {event}")

    def add_event(self, event: CorporateActionEvent) -> None:
        """
        Add a single corporate action event.

        Args:
            event: Corporate action event
        """
        self.database.add_event(event)

    def adjust_prices(
        self,
        symbol: str,
        price_data: pd.DataFrame,
        method: AdjustmentMethod = AdjustmentMethod.BACKWARD
    ) -> pd.DataFrame:
        """
        Apply all relevant corporate action adjustments.

        Args:
            symbol: Stock symbol
            price_data: Historical price data
            method: Adjustment method

        Returns:
            Fully adjusted price data
        """
        if price_data.empty:
            return price_data

        # Get date range from price data
        start_date = price_data.index.min().to_pydatetime()
        end_date = price_data.index.max().to_pydatetime()

        # Adjust prices using database
        adjusted_data = self.database.adjust_prices(
            symbol=symbol,
            price_data=price_data,
            start_date=start_date,
            end_date=end_date,
            method=method
        )

        return adjusted_data

    def get_adjustment_factors(
        self,
        symbol: str,
        dates: pd.DatetimeIndex
    ) -> pd.Series:
        """
        Calculate cumulative adjustment factors for specific dates.

        Args:
            symbol: Stock symbol
            dates: Dates for which to calculate factors

        Returns:
            Series of adjustment factors (1.0 = no adjustment)
        """
        factors = pd.Series(1.0, index=dates)

        # Get all events for this symbol
        events = self.database.get_events(symbol)

        for date in dates:
            cumulative_factor = 1.0

            # Calculate cumulative effect of all events before this date
            for event in events:
                if event.ex_date > date.to_pydatetime():
                    continue

                # Get processor for this event type
                processor = self.database.processors.get(event.action_type)
                if processor and hasattr(processor, 'get_adjustment_factor'):
                    factor = processor.get_adjustment_factor(event, date.to_pydatetime())
                    cumulative_factor *= factor

            factors[date] = cumulative_factor

        return factors

    def get_events_summary(self, symbol: str) -> Dict[str, any]:
        """
        Get summary of all corporate actions for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Summary dict with counts and details
        """
        events = self.database.get_events(symbol)

        summary = {
            'total_events': len(events),
            'by_type': {},
            'date_range': None,
            'events': []
        }

        if not events:
            return summary

        # Count by type
        for event in events:
            action_type = event.action_type.value
            summary['by_type'][action_type] = summary['by_type'].get(action_type, 0) + 1

        # Date range
        sorted_events = sorted(events, key=lambda x: x.ex_date)
        summary['date_range'] = (
            sorted_events[0].ex_date.date(),
            sorted_events[-1].ex_date.date()
        )

        # Event details
        for event in sorted_events:
            summary['events'].append({
                'date': event.ex_date.date(),
                'type': event.action_type.value,
                'ratio': event.ratio,
                'value': event.value,
            })

        return summary

    def export_events(self, symbol: Optional[str] = None) -> pd.DataFrame:
        """
        Export events to DataFrame.

        Args:
            symbol: Optional symbol filter

        Returns:
            DataFrame with all events
        """
        return self.database.export_to_dataframe(symbol)

    def import_events(self, df: pd.DataFrame) -> int:
        """
        Import events from DataFrame.

        Args:
            df: DataFrame with corporate action events

        Returns:
            Number of events imported
        """
        return self.database.import_from_dataframe(df)


def create_fully_adjusted_prices(
    price_data: pd.DataFrame,
    corporate_actions: List[CorporateActionEvent],
    symbol: str,
    method: AdjustmentMethod = AdjustmentMethod.BACKWARD
) -> pd.DataFrame:
    """
    Convenience function to create fully adjusted prices.

    Args:
        price_data: Raw price data
        corporate_actions: List of corporate actions
        symbol: Stock symbol
        method: Adjustment method

    Returns:
        Fully adjusted price data
    """
    adjuster = PriceAdjuster()
    adjuster.add_events(corporate_actions)
    return adjuster.adjust_prices(symbol, price_data, method)


# Example usage
if __name__ == "__main__":
    # Create sample data
    dates = pd.date_range('2020-01-01', '2023-12-31', freq='B')
    data = pd.DataFrame({
        'open': 100.0,
        'high': 105.0,
        'low': 95.0,
        'close': 100.0,
        'volume': 1000000,
    }, index=dates)

    # Create events
    events = [
        # 2-for-1 split in 2021
        CorporateActionEvent(
            symbol='TEST',
            action_type=CorporateActionType.SPLIT,
            ex_date=datetime(2021, 6, 1),
            ratio=2.0,
            source='manual',
        ),
        # Quarterly dividends in 2022
        CorporateActionEvent(
            symbol='TEST',
            action_type=CorporateActionType.DIVIDEND,
            ex_date=datetime(2022, 3, 15),
            value=1.00,
            source='manual',
        ),
        CorporateActionEvent(
            symbol='TEST',
            action_type=CorporateActionType.DIVIDEND,
            ex_date=datetime(2022, 6, 15),
            value=1.00,
            source='manual',
        ),
        # Special dividend in 2023
        CorporateActionEvent(
            symbol='TEST',
            action_type=CorporateActionType.SPECIAL_DIVIDEND,
            ex_date=datetime(2023, 1, 15),
            value=5.00,
            source='manual',
        ),
    ]

    # Create adjuster
    adjuster = PriceAdjuster(
        adjust_for_splits=True,
        adjust_for_dividends=True,
        reinvest_dividends=False,
        dividend_tax_rate=0.15
    )

    # Add events
    adjuster.add_events(events)

    # Adjust prices
    adjusted = adjuster.adjust_prices('TEST', data, AdjustmentMethod.BACKWARD)

    # Print summary
    print("Corporate Actions Summary:")
    summary = adjuster.get_events_summary('TEST')
    print(f"  Total events: {summary['total_events']}")
    print(f"  By type: {summary['by_type']}")
    print(f"  Date range: {summary['date_range']}")

    # Compare prices
    print("\nPrice comparison (selected dates):")
    for date in ['2020-12-31', '2021-12-31', '2022-12-31', '2023-12-31']:
        try:
            orig = data.loc[date, 'close']
            adj = adjusted.loc[date, 'close']
            print(f"  {date}: Original=${orig:.2f}, Adjusted=${adj:.2f}")
        except KeyError:
            pass

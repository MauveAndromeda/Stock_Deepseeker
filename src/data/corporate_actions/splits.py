"""
Stock split adjustment processor.

Handles forward and reverse splits with proper price and volume adjustments.
"""

from datetime import datetime

from loguru import logger
import pandas as pd

from src.data.corporate_actions.base import (
    AdjustmentMethod,
    CorporateActionEvent,
    CorporateActionProcessor,
    CorporateActionType,
)


class SplitAdjuster(CorporateActionProcessor):
    """
    Processes stock splits and reverse splits.

    Handles:
    - Forward splits (e.g., 2-for-1)
    - Reverse splits (e.g., 1-for-10)
    - Price adjustments
    - Volume adjustments
    """

    def __init__(self) -> None:
        """Initialize split adjuster."""
        super().__init__()

    def validate_event(self, event: CorporateActionEvent) -> tuple[bool, str | None]:
        """
        Validate split event.

        Args:
            event: Corporate action event

        Returns:
            Tuple of (is_valid, error_message)
        """
        if event.action_type not in [
            CorporateActionType.SPLIT,
            CorporateActionType.REVERSE_SPLIT
        ]:
            return False, f"Invalid action type: {event.action_type}"

        if event.ratio is None or event.ratio <= 0:
            return False, "Split ratio must be positive"

        # Check for suspicious ratios
        if event.ratio > 100:
            logger.warning(f"Very large split ratio: {event.ratio}")

        if event.ratio < 0.01:
            logger.warning(f"Very small split ratio: {event.ratio}")

        return True, None

    def process_event(
        self,
        event: CorporateActionEvent,
        price_data: pd.DataFrame,
        method: AdjustmentMethod = AdjustmentMethod.BACKWARD
    ) -> pd.DataFrame:
        """
        Adjust prices for stock split.

        Args:
            event: Split event
            price_data: Historical price data
            method: Adjustment method

        Returns:
            Adjusted price data

        Raises:
            ValueError: If event is invalid or data is incompatible
        """
        is_valid, error = self.validate_event(event)
        if not is_valid:
            raise ValueError(f"Invalid split event: {error}")

        if price_data.empty:
            return price_data

        # Make a copy to avoid modifying original
        adjusted_data = price_data.copy()

        # Determine split factor
        if event.action_type == CorporateActionType.SPLIT:
            # Forward split (e.g., 2-for-1 means ratio=2.0)
            split_factor = event.ratio
        else:
            # Reverse split (e.g., 1-for-10 means ratio=0.1)
            split_factor = event.ratio

        # Find the split date in the data
        split_date = event.ex_date
        if split_date.tzinfo is not None:
            split_date = split_date.replace(tzinfo=None)

        # Apply adjustment based on method
        if method == AdjustmentMethod.BACKWARD:
            # Adjust all prices BEFORE the split date
            mask = adjusted_data.index < split_date

            if mask.any():
                # Adjust prices (divide by split factor)
                price_columns = ["open", "high", "low", "close"]
                for col in price_columns:
                    if col in adjusted_data.columns:
                        adjusted_data.loc[mask, col] = adjusted_data.loc[mask, col] / split_factor

                # Adjust volume (multiply by split factor)
                if "volume" in adjusted_data.columns:
                    adjusted_data.loc[mask, "volume"] = adjusted_data.loc[mask, "volume"] * split_factor

                logger.info(
                    f"Applied backward split adjustment for {event.symbol}: "
                    f"ratio={split_factor:.4f}, affected {mask.sum()} rows"
                )

        elif method == AdjustmentMethod.FORWARD:
            # Adjust all prices AFTER the split date
            mask = adjusted_data.index >= split_date

            if mask.any():
                # Adjust prices (multiply by split factor)
                price_columns = ["open", "high", "low", "close"]
                for col in price_columns:
                    if col in adjusted_data.columns:
                        adjusted_data.loc[mask, col] = adjusted_data.loc[mask, col] * split_factor

                # Adjust volume (divide by split factor)
                if "volume" in adjusted_data.columns:
                    adjusted_data.loc[mask, "volume"] = adjusted_data.loc[mask, "volume"] / split_factor

                logger.info(
                    f"Applied forward split adjustment for {event.symbol}: "
                    f"ratio={split_factor:.4f}, affected {mask.sum()} rows"
                )

        else:
            # No adjustment
            logger.debug(f"No adjustment applied for {event.symbol}")

        return adjusted_data

    def calculate_cumulative_factor(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> float:
        """
        Calculate cumulative split factor over a date range.

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date

        Returns:
            Cumulative split factor
        """
        events = [
            e for e in self.events
            if e.symbol == symbol
            and start_date <= e.ex_date <= end_date
        ]

        cumulative_factor = 1.0

        for event in sorted(events, key=lambda x: x.ex_date):
            if event.action_type in (CorporateActionType.SPLIT, CorporateActionType.REVERSE_SPLIT):
                cumulative_factor *= event.ratio

        return cumulative_factor

    def get_split_history(self, symbol: str) -> pd.DataFrame:
        """
        Get split history for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            DataFrame with split history
        """
        events = [
            e for e in self.events
            if e.symbol == symbol
            and e.action_type in [
                CorporateActionType.SPLIT,
                CorporateActionType.REVERSE_SPLIT
            ]
        ]

        if not events:
            return pd.DataFrame()

        data = []
        for event in sorted(events, key=lambda x: x.ex_date):
            data.append({
                "ex_date": event.ex_date,
                "type": event.action_type.value,
                "ratio": event.ratio,
                "description": self._describe_split(event),
            })

        return pd.DataFrame(data)

    def _describe_split(self, event: CorporateActionEvent) -> str:
        """
        Create human-readable description of split.

        Args:
            event: Split event

        Returns:
            Description string
        """
        ratio = event.ratio

        if event.action_type == CorporateActionType.SPLIT:
            # Forward split
            if ratio == int(ratio):
                return f"{int(ratio)}-for-1 split"
            return f"{ratio:.2f}-for-1 split"
        # Reverse split
        if 1/ratio == int(1/ratio):
            return f"1-for-{int(1/ratio)} reverse split"
        return f"1-for-{1/ratio:.2f} reverse split"

    def detect_splits_from_prices(
        self,
        price_data: pd.DataFrame,
        threshold: float = 0.4
    ) -> list[tuple[datetime, float]]:
        """
        Detect potential splits from price data.

        Useful for finding unrecorded splits.

        Args:
            price_data: Historical price data
            threshold: Minimum price change ratio to consider (default 40%)

        Returns:
            List of (date, ratio) tuples for potential splits
        """
        if len(price_data) < 2:
            return []

        # Calculate daily price ratios
        price_ratios = price_data["close"].pct_change()

        # Find large drops (potential forward splits)
        forward_splits = price_ratios[price_ratios < -threshold]

        # Find large jumps (potential reverse splits)
        reverse_splits = price_ratios[price_ratios > threshold]

        detected_splits = []

        for date, ratio in forward_splits.items():
            # Convert percentage drop to split ratio
            # -50% drop suggests 2-for-1 split
            split_ratio = 1 / (1 + ratio)
            detected_splits.append((date.to_pydatetime(), split_ratio))

        for date, ratio in reverse_splits.items():
            # Convert percentage jump to reverse split ratio
            split_ratio = 1 + ratio
            detected_splits.append((date.to_pydatetime(), split_ratio))

        return sorted(detected_splits, key=lambda x: x[0])


# Example usage
if __name__ == "__main__":
    # Create sample data
    dates = pd.date_range("2023-01-01", "2023-12-31", freq="B")
    data = pd.DataFrame({
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 100.0,
        "volume": 1000000,
    }, index=dates)

    # Create split event (2-for-1 split on July 1)
    split_event = CorporateActionEvent(
        symbol="TEST",
        action_type=CorporateActionType.SPLIT,
        ex_date=datetime(2023, 7, 1),
        ratio=2.0,  # 2-for-1 split
        source="manual",
    )

    # Process split
    adjuster = SplitAdjuster()
    adjuster.add_event(split_event)
    adjusted = adjuster.process_event(split_event, data, AdjustmentMethod.BACKWARD)

    # Check results
    print("Original close price (June 30):", data.loc["2023-06-30", "close"])
    print("Adjusted close price (June 30):", adjusted.loc["2023-06-30", "close"])
    print("Close price (July 3):", adjusted.loc["2023-07-03", "close"])

    # Should be 50.0 before split, 100.0 after split (in backward adjustment)

"""
Dividend processing and adjustment.

Handles cash dividends, special dividends, and dividend reinvestment.
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


class DividendProcessor(CorporateActionProcessor):
    """
    Processes dividend payments and adjusts prices accordingly.

    Handles:
    - Cash dividends
    - Special dividends
    - Stock dividends
    - Dividend reinvestment (DRIP)
    - Tax adjustments
    """

    def __init__(self, reinvest_dividends: bool = False, tax_rate: float = 0.0) -> None:
        """
        Initialize dividend processor.

        Args:
            reinvest_dividends: Whether to simulate dividend reinvestment
            tax_rate: Tax rate on dividends (0.0 to 1.0)
        """
        super().__init__()
        self.reinvest_dividends = reinvest_dividends
        self.tax_rate = tax_rate

    def validate_event(self, event: CorporateActionEvent) -> tuple[bool, str | None]:
        """
        Validate dividend event.

        Args:
            event: Corporate action event

        Returns:
            Tuple of (is_valid, error_message)
        """
        if event.action_type not in [
            CorporateActionType.DIVIDEND,
            CorporateActionType.SPECIAL_DIVIDEND,
            CorporateActionType.STOCK_DIVIDEND,
        ]:
            return False, f"Invalid action type: {event.action_type}"

        if event.value is None or event.value <= 0:
            return False, "Dividend value must be positive"

        # Check for suspicious dividend amounts
        if event.value > 1000:
            logger.warning(f"Very large dividend amount: ${event.value}")

        return True, None

    def process_event(
        self,
        event: CorporateActionEvent,
        price_data: pd.DataFrame,
        method: AdjustmentMethod = AdjustmentMethod.BACKWARD
    ) -> pd.DataFrame:
        """
        Adjust prices for dividend.

        Args:
            event: Dividend event
            price_data: Historical price data
            method: Adjustment method

        Returns:
            Adjusted price data

        Raises:
            ValueError: If event is invalid
        """
        is_valid, error = self.validate_event(event)
        if not is_valid:
            raise ValueError(f"Invalid dividend event: {error}")

        if price_data.empty:
            return price_data

        adjusted_data = price_data.copy()

        # Get ex-dividend date
        ex_date = event.ex_date
        if ex_date.tzinfo is not None:
            ex_date = ex_date.replace(tzinfo=None)

        # Calculate dividend amount (after tax if applicable)
        dividend_amount = event.value * (1 - self.tax_rate)

        if method == AdjustmentMethod.BACKWARD:
            # Adjust all prices BEFORE the ex-dividend date
            mask = adjusted_data.index < ex_date

            if mask.any():
                # Get price on ex-dividend date for calculating adjustment factor
                # If ex-date data exists, use it; otherwise use last available price
                try:
                    ref_price = adjusted_data.loc[
                        adjusted_data.index >= ex_date, "close"
                    ].iloc[0]
                except (IndexError, KeyError):
                    ref_price = adjusted_data["close"].iloc[-1]

                # Calculate adjustment factor
                # Factor = (Price - Dividend) / Price
                adjustment_factor = (ref_price - dividend_amount) / ref_price

                if adjustment_factor <= 0:
                    logger.warning(
                        f"Dividend amount (${dividend_amount:.2f}) exceeds price "
                        f"(${ref_price:.2f}), adjustment may be incorrect"
                    )
                    adjustment_factor = 0.01  # Minimum factor

                # Adjust prices
                price_columns = ["open", "high", "low", "close"]
                for col in price_columns:
                    if col in adjusted_data.columns:
                        adjusted_data.loc[mask, col] = (
                            adjusted_data.loc[mask, col] * adjustment_factor
                        )

                logger.info(
                    f"Applied dividend adjustment for {event.symbol}: "
                    f"amount=${dividend_amount:.4f}, factor={adjustment_factor:.6f}, "
                    f"affected {mask.sum()} rows"
                )

        elif method == AdjustmentMethod.FORWARD:
            # Adjust all prices AFTER the ex-dividend date
            mask = adjusted_data.index >= ex_date

            if mask.any():
                # Get price just before ex-dividend date
                try:
                    ref_price = adjusted_data.loc[
                        adjusted_data.index < ex_date, "close"
                    ].iloc[-1]
                except (IndexError, KeyError):
                    ref_price = adjusted_data["close"].iloc[0]

                # Calculate adjustment factor
                # Factor = Price / (Price - Dividend)
                adjustment_factor = ref_price / (ref_price - dividend_amount)

                # Adjust prices
                price_columns = ["open", "high", "low", "close"]
                for col in price_columns:
                    if col in adjusted_data.columns:
                        adjusted_data.loc[mask, col] = (
                            adjusted_data.loc[mask, col] * adjustment_factor
                        )

                logger.info(
                    f"Applied forward dividend adjustment for {event.symbol}: "
                    f"amount=${dividend_amount:.4f}, factor={adjustment_factor:.6f}, "
                    f"affected {mask.sum()} rows"
                )

        return adjusted_data

    def calculate_total_dividends(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        shares: float = 1.0
    ) -> dict[str, float]:
        """
        Calculate total dividends received over a period.

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            shares: Number of shares held

        Returns:
            Dict with dividend statistics
        """
        events = [
            e for e in self.events
            if e.symbol == symbol
            and start_date <= e.ex_date <= end_date
            and e.action_type in [
                CorporateActionType.DIVIDEND,
                CorporateActionType.SPECIAL_DIVIDEND,
            ]
        ]

        if not events:
            return {
                "total_gross": 0.0,
                "total_net": 0.0,
                "total_tax": 0.0,
                "count": 0,
                "average": 0.0,
            }

        total_gross = sum(e.value for e in events) * shares
        total_tax = total_gross * self.tax_rate
        total_net = total_gross - total_tax

        return {
            "total_gross": total_gross,
            "total_net": total_net,
            "total_tax": total_tax,
            "count": len(events),
            "average": total_gross / len(events) if events else 0.0,
        }

    def simulate_drip(
        self,
        price_data: pd.DataFrame,
        initial_shares: float = 1.0
    ) -> pd.DataFrame:
        """
        Simulate dividend reinvestment plan (DRIP).

        Args:
            price_data: Historical price data
            initial_shares: Initial number of shares

        Returns:
            DataFrame with shares_held column added
        """
        if not self.reinvest_dividends:
            logger.warning("DRIP simulation requires reinvest_dividends=True")
            return price_data

        result = price_data.copy()
        result["shares_held"] = initial_shares

        # Get dividends for this symbol
        # (Assuming events are already filtered by symbol)
        for event in sorted(self.events, key=lambda x: x.ex_date):
            if event.action_type not in [
                CorporateActionType.DIVIDEND,
                CorporateActionType.SPECIAL_DIVIDEND,
            ]:
                continue

            ex_date = event.ex_date
            if ex_date.tzinfo is not None:
                ex_date = ex_date.replace(tzinfo=None)

            # Find closest price data
            mask = result.index >= ex_date
            if not mask.any():
                continue

            # Get price on reinvestment date (assume payment date = ex-date for simplicity)
            reinvest_price = result.loc[mask, "close"].iloc[0]

            # Get current shares
            prev_mask = result.index < ex_date
            if prev_mask.any():
                current_shares = result.loc[prev_mask, "shares_held"].iloc[-1]
            else:
                current_shares = initial_shares

            # Calculate dividend received
            dividend_received = event.value * current_shares * (1 - self.tax_rate)

            # Calculate additional shares purchased
            additional_shares = dividend_received / reinvest_price

            # Update shares held after reinvestment
            result.loc[mask, "shares_held"] = current_shares + additional_shares

            logger.debug(
                f"DRIP: {event.ex_date.date()} - "
                f"dividend=${dividend_received:.2f}, "
                f"price=${reinvest_price:.2f}, "
                f"new shares={additional_shares:.4f}"
            )

        # Fill forward shares held
        result["shares_held"] = result["shares_held"].fillna(method="ffill")

        return result

    def get_dividend_yield(
        self,
        symbol: str,
        current_price: float,
        lookback_months: int = 12
    ) -> float:
        """
        Calculate trailing dividend yield.

        Args:
            symbol: Stock symbol
            current_price: Current stock price
            lookback_months: Months to look back

        Returns:
            Annualized dividend yield (as decimal, e.g., 0.03 = 3%)
        """
        from datetime import timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_months * 30)

        stats = self.calculate_total_dividends(symbol, start_date, end_date, shares=1.0)

        if stats["count"] == 0 or current_price <= 0:
            return 0.0

        # Annualize the dividend
        annual_dividend = stats["total_gross"] * (12 / lookback_months)

        # Calculate yield
        yield_pct = annual_dividend / current_price

        return yield_pct

    def get_dividend_history(self, symbol: str) -> pd.DataFrame:
        """
        Get dividend payment history.

        Args:
            symbol: Stock symbol

        Returns:
            DataFrame with dividend history
        """
        events = [
            e for e in self.events
            if e.symbol == symbol
            and e.action_type in [
                CorporateActionType.DIVIDEND,
                CorporateActionType.SPECIAL_DIVIDEND,
                CorporateActionType.STOCK_DIVIDEND,
            ]
        ]

        if not events:
            return pd.DataFrame()

        data = []
        for event in sorted(events, key=lambda x: x.ex_date):
            data.append({
                "ex_date": event.ex_date,
                "payment_date": event.payment_date,
                "type": event.action_type.value,
                "amount": event.value,
                "currency": event.currency,
            })

        return pd.DataFrame(data)


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

    # Create dividend events
    dividend_events = [
        CorporateActionEvent(
            symbol="TEST",
            action_type=CorporateActionType.DIVIDEND,
            ex_date=datetime(2023, 3, 15),
            payment_date=datetime(2023, 3, 30),
            value=1.50,  # $1.50 per share
            source="manual",
        ),
        CorporateActionEvent(
            symbol="TEST",
            action_type=CorporateActionType.DIVIDEND,
            ex_date=datetime(2023, 6, 15),
            payment_date=datetime(2023, 6, 30),
            value=1.50,
            source="manual",
        ),
    ]

    # Process dividends
    processor = DividendProcessor(tax_rate=0.15)
    for event in dividend_events:
        processor.add_event(event)

    adjusted = data.copy()
    for event in dividend_events:
        adjusted = processor.process_event(event, adjusted, AdjustmentMethod.BACKWARD)

    # Check results
    print("Dividend history:")
    print(processor.get_dividend_history("TEST"))

    print("\nTotal dividends:")
    print(processor.calculate_total_dividends(
        "TEST",
        datetime(2023, 1, 1),
        datetime(2023, 12, 31)
    ))

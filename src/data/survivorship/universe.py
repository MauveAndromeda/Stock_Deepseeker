"""
Point-in-time universe management.

Handles dynamic universe construction without survivorship bias.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from loguru import logger
import pandas as pd


class DelistingReason(Enum):
    """Reasons for delisting."""
    BANKRUPTCY = "bankruptcy"
    MERGER = "merger"
    ACQUISITION = "acquisition"
    GOING_PRIVATE = "going_private"
    REGULATORY = "regulatory"
    VOLUNTARY = "voluntary"
    INSUFFICIENT_VALUE = "insufficient_value"
    INSUFFICIENT_LIQUIDITY = "insufficient_liquidity"
    UNKNOWN = "unknown"


@dataclass
class UniverseConstituent:
    """
    Represents a stock in the universe at a point in time.

    Attributes:
        symbol: Stock symbol
        name: Company name
        list_date: Date when stock was listed
        delist_date: Date when stock was delisted (None if still listed)
        delist_reason: Reason for delisting
        sector: Company sector
        industry: Company industry
        market_cap: Market capitalization (at entry)
        metadata: Additional metadata
    """
    symbol: str
    name: str
    list_date: datetime
    delist_date: datetime | None = None
    delist_reason: DelistingReason | None = None
    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = None
    metadata: dict[str, any] = field(default_factory=dict)

    def is_active(self, date: datetime) -> bool:
        """
        Check if constituent is active on a given date.

        Args:
            date: Date to check

        Returns:
            True if active on that date
        """
        if date < self.list_date:
            return False

        return not (self.delist_date is not None and date >= self.delist_date)

    def get_final_return(self) -> float | None:
        """
        Get final return for delisted stock.

        Returns:
            Final return (may be -1.0 for bankruptcy, or positive for merger)
        """
        if self.delist_date is None:
            return None

        if self.delist_reason == DelistingReason.BANKRUPTCY:
            return -1.0  # Total loss

        # For other reasons, return from metadata if available
        return self.metadata.get("final_return", 0.0)


@dataclass
class PointInTimeUniverse:
    """
    Universe snapshot at a specific point in time.

    Attributes:
        date: Snapshot date
        constituents: Set of active symbols
        metadata: Additional metadata about the universe
    """
    date: datetime
    constituents: set[str]
    metadata: dict[str, any] = field(default_factory=dict)

    def __len__(self) -> int:
        """Return number of constituents."""
        return len(self.constituents)

    def __contains__(self, symbol: str) -> bool:
        """Check if symbol is in universe."""
        return symbol in self.constituents

    def to_list(self) -> list[str]:
        """Return constituents as sorted list."""
        return sorted(self.constituents)


class UniverseManager:
    """
    Manages dynamic universe construction with survivorship bias handling.

    Features:
    - Point-in-time queries (no lookahead)
    - Tracks listing and delisting dates
    - Handles symbol changes
    - Computes delisting returns
    """

    def __init__(self) -> None:
        """Initialize universe manager."""
        self.constituents: dict[str, UniverseConstituent] = {}
        self.symbol_history: dict[str, list[str]] = {}  # old_symbol -> [new_symbols]

        # Cache for performance
        self._universe_cache: dict[datetime, PointInTimeUniverse] = {}

    def add_constituent(self, constituent: UniverseConstituent) -> None:
        """
        Add a constituent to the universe.

        Args:
            constituent: Universe constituent
        """
        self.constituents[constituent.symbol] = constituent
        logger.debug(f"Added constituent: {constituent.symbol}")

    def add_constituents(self, constituents: list[UniverseConstituent]) -> None:
        """
        Add multiple constituents.

        Args:
            constituents: List of constituents
        """
        for constituent in constituents:
            self.add_constituent(constituent)

    def delist(
        self,
        symbol: str,
        delist_date: datetime,
        reason: DelistingReason,
        final_return: float | None = None
    ) -> None:
        """
        Mark a stock as delisted.

        Args:
            symbol: Stock symbol
            delist_date: Delisting date
            reason: Reason for delisting
            final_return: Final return (for partial loss/gain)
        """
        if symbol not in self.constituents:
            logger.warning(f"Cannot delist unknown symbol: {symbol}")
            return

        constituent = self.constituents[symbol]
        constituent.delist_date = delist_date
        constituent.delist_reason = reason

        if final_return is not None:
            constituent.metadata["final_return"] = final_return

        logger.info(
            f"Delisted {symbol} on {delist_date.date()}: {reason.value}"
        )

        # Clear cache as universe has changed
        self._universe_cache.clear()

    def add_symbol_change(self, old_symbol: str, new_symbol: str, change_date: datetime) -> None:
        """
        Record a symbol change.

        Args:
            old_symbol: Old symbol
            new_symbol: New symbol
            change_date: Date of change
        """
        if old_symbol not in self.symbol_history:
            self.symbol_history[old_symbol] = []

        self.symbol_history[old_symbol].append(new_symbol)
        logger.info(f"Symbol change: {old_symbol} -> {new_symbol} on {change_date.date()}")

    def get_universe_at(
        self,
        date: datetime,
        min_market_cap: float | None = None,
        sectors: list[str] | None = None,
        use_cache: bool = True
    ) -> PointInTimeUniverse:
        """
        Get universe constituents at a specific date (no lookahead).

        Args:
            date: Query date
            min_market_cap: Minimum market cap filter
            sectors: Sector filter
            use_cache: Whether to use cache

        Returns:
            Point-in-time universe
        """
        # Check cache
        cache_key = date
        if use_cache and cache_key in self._universe_cache:
            cached = self._universe_cache[cache_key]

            # Apply filters to cached universe if needed
            if min_market_cap is None and sectors is None:
                return cached

        # Build universe from scratch
        active_symbols = set()

        for symbol, constituent in self.constituents.items():
            if not constituent.is_active(date):
                continue

            # Apply filters
            if min_market_cap and (
                constituent.market_cap is None or
                constituent.market_cap < min_market_cap
            ):
                continue

            if sectors and constituent.sector not in sectors:
                continue

            active_symbols.add(symbol)

        universe = PointInTimeUniverse(
            date=date,
            constituents=active_symbols,
            metadata={
                "min_market_cap": min_market_cap,
                "sectors": sectors,
            }
        )

        # Cache if no filters applied
        if min_market_cap is None and sectors is None:
            self._universe_cache[cache_key] = universe

        logger.debug(
            f"Universe at {date.date()}: {len(universe)} constituents"
        )

        return universe

    def get_universe_changes(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> dict[str, dict[str, list[str]]]:
        """
        Get universe changes over a date range.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Dict with 'additions' and 'removals' lists per date
        """
        changes: dict[str, dict[str, list[str]]] = {}

        # Track universe at start
        prev_universe = self.get_universe_at(start_date)

        # Check each day
        current_date = start_date + timedelta(days=1)
        while current_date <= end_date:
            curr_universe = self.get_universe_at(current_date)

            # Find additions and removals
            additions = curr_universe.constituents - prev_universe.constituents
            removals = prev_universe.constituents - curr_universe.constituents

            if additions or removals:
                changes[current_date.isoformat()] = {
                    "additions": sorted(additions),
                    "removals": sorted(removals),
                }

            prev_universe = curr_universe
            current_date += timedelta(days=1)

        return changes

    def get_delisted_stocks(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        reason: DelistingReason | None = None
    ) -> list[UniverseConstituent]:
        """
        Get delisted stocks in a date range.

        Args:
            start_date: Start date filter
            end_date: End date filter
            reason: Delisting reason filter

        Returns:
            List of delisted constituents
        """
        delisted = []

        for constituent in self.constituents.values():
            if constituent.delist_date is None:
                continue

            # Apply date filters
            if start_date and constituent.delist_date < start_date:
                continue

            if end_date and constituent.delist_date > end_date:
                continue

            # Apply reason filter
            if reason and constituent.delist_reason != reason:
                continue

            delisted.append(constituent)

        return sorted(delisted, key=lambda x: x.delist_date)

    def get_survivorship_rate(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> dict[str, any]:
        """
        Calculate survivorship statistics.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Dict with survivorship metrics
        """
        start_universe = self.get_universe_at(start_date)
        end_universe = self.get_universe_at(end_date)

        # Find stocks that existed at start
        start_symbols = start_universe.constituents

        # Find how many survived to end
        survived = start_symbols & end_universe.constituents
        delisted = start_symbols - end_universe.constituents

        survival_rate = len(survived) / len(start_symbols) if start_symbols else 0.0

        # Calculate delisting reasons
        delist_reasons = {}
        for symbol in delisted:
            if symbol in self.constituents:
                reason = self.constituents[symbol].delist_reason
                if reason:
                    reason_str = reason.value
                    delist_reasons[reason_str] = delist_reasons.get(reason_str, 0) + 1

        return {
            "start_count": len(start_symbols),
            "end_count": len(survived),
            "delisted_count": len(delisted),
            "survival_rate": survival_rate,
            "delisting_reasons": delist_reasons,
            "delisted_symbols": sorted(delisted),
        }

    def export_to_dataframe(self) -> pd.DataFrame:
        """
        Export all constituents to DataFrame.

        Returns:
            DataFrame with all constituent data
        """
        data = []

        for constituent in self.constituents.values():
            data.append({
                "symbol": constituent.symbol,
                "name": constituent.name,
                "list_date": constituent.list_date,
                "delist_date": constituent.delist_date,
                "delist_reason": constituent.delist_reason.value if constituent.delist_reason else None,
                "sector": constituent.sector,
                "industry": constituent.industry,
                "market_cap": constituent.market_cap,
            })

        return pd.DataFrame(data)

    def import_from_dataframe(self, df: pd.DataFrame) -> int:
        """
        Import constituents from DataFrame.

        Args:
            df: DataFrame with constituent data

        Returns:
            Number of constituents imported
        """
        count = 0

        for _, row in df.iterrows():
            try:
                constituent = UniverseConstituent(
                    symbol=row["symbol"],
                    name=row["name"],
                    list_date=pd.to_datetime(row["list_date"]).to_pydatetime(),
                    delist_date=pd.to_datetime(row["delist_date"]).to_pydatetime() if pd.notna(row.get("delist_date")) else None,
                    delist_reason=DelistingReason(row["delist_reason"]) if pd.notna(row.get("delist_reason")) else None,
                    sector=row.get("sector"),
                    industry=row.get("industry"),
                    market_cap=row.get("market_cap"),
                )
                self.add_constituent(constituent)
                count += 1
            except Exception as e:
                logger.error(f"Failed to import row: {e}")
                continue

        logger.info(f"Imported {count} constituents")
        return count


# Example usage
if __name__ == "__main__":
    manager = UniverseManager()

    # Add some constituents
    manager.add_constituent(UniverseConstituent(
        symbol="AAPL",
        name="Apple Inc.",
        list_date=datetime(1980, 12, 12),
        sector="Technology",
        market_cap=3000000000000,
    ))

    manager.add_constituent(UniverseConstituent(
        symbol="LEHMAN",  # Example: Lehman Brothers
        name="Lehman Brothers",
        list_date=datetime(1994, 5, 26),
        delist_date=datetime(2008, 9, 15),
        delist_reason=DelistingReason.BANKRUPTCY,
        sector="Financials",
        market_cap=60000000000,
    ))

    # Get universe at different dates
    universe_2007 = manager.get_universe_at(datetime(2007, 1, 1))
    universe_2009 = manager.get_universe_at(datetime(2009, 1, 1))

    print(f"Universe 2007: {universe_2007.to_list()}")
    print(f"Universe 2009: {universe_2009.to_list()}")

    # Survivorship statistics
    stats = manager.get_survivorship_rate(
        datetime(2007, 1, 1),
        datetime(2009, 1, 1)
    )
    print(f"\nSurvivorship stats: {stats}")

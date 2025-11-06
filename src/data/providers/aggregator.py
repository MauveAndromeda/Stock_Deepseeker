"""
Multi-source data aggregator.

Combines multiple data providers for robustness and data quality.
Implements failover, data validation, and quality scoring.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from loguru import logger

from src.data.providers.base import (
    CorporateAction,
    DataFetchError,
    DataProvider,
    DataValidationError,
    FundamentalData,
    PriceData,
)


class DataQualityMetrics:
    """Data quality metrics for validation."""

    @staticmethod
    def calculate_completeness(data: pd.DataFrame) -> float:
        """Calculate data completeness (% of non-null values)."""
        return 1.0 - (data.isnull().sum().sum() / (data.shape[0] * data.shape[1]))

    @staticmethod
    def calculate_consistency(data: pd.DataFrame) -> float:
        """
        Calculate data consistency.

        Checks for:
        - High >= Low
        - Close within (Low, High)
        - Open within (Low, High)
        - No negative prices
        """
        violations = 0
        total_checks = 0

        # Check high >= low
        violations += (data['high'] < data['low']).sum()
        total_checks += len(data)

        # Check close within range
        violations += ((data['close'] < data['low']) | (data['close'] > data['high'])).sum()
        total_checks += len(data)

        # Check open within range
        violations += ((data['open'] < data['low']) | (data['open'] > data['high'])).sum()
        total_checks += len(data)

        # Check no negative prices
        for col in ['open', 'high', 'low', 'close']:
            violations += (data[col] < 0).sum()
            total_checks += len(data)

        return 1.0 - (violations / max(total_checks, 1))

    @staticmethod
    def calculate_continuity(data: pd.DataFrame, expected_freq: str = 'B') -> float:
        """
        Calculate data continuity (no large gaps).

        Args:
            data: Price data
            expected_freq: Expected frequency ('B' for business days)

        Returns:
            Continuity score (0-1)
        """
        if len(data) < 2:
            return 1.0

        # Create expected date range
        expected_dates = pd.date_range(
            start=data.index[0],
            end=data.index[-1],
            freq=expected_freq
        )

        # Calculate coverage
        coverage = len(data) / len(expected_dates)
        return min(coverage, 1.0)

    @staticmethod
    def calculate_quality_score(data: pd.DataFrame) -> float:
        """
        Calculate overall quality score.

        Returns:
            Quality score (0-1)
        """
        completeness = DataQualityMetrics.calculate_completeness(data)
        consistency = DataQualityMetrics.calculate_consistency(data)
        continuity = DataQualityMetrics.calculate_continuity(data)

        # Weighted average
        return 0.4 * completeness + 0.4 * consistency + 0.2 * continuity


class MultiSourceAggregator:
    """
    Aggregates data from multiple providers with failover and quality checks.

    Features:
    - Automatic failover to backup providers
    - Data quality validation and scoring
    - Conflict resolution when data differs
    - Caching for performance
    """

    def __init__(
        self,
        providers: List[DataProvider],
        quality_threshold: float = 0.85,
        enable_validation: bool = True
    ) -> None:
        """
        Initialize multi-source aggregator.

        Args:
            providers: List of data providers (in priority order)
            quality_threshold: Minimum acceptable quality score
            enable_validation: Whether to validate data quality
        """
        if not providers:
            raise ValueError("At least one provider is required")

        self.providers = providers
        self.quality_threshold = quality_threshold
        self.enable_validation = enable_validation

        # Statistics
        self.fetch_stats: Dict[str, Any] = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'provider_usage': {i: 0 for i in range(len(providers))},
            'quality_scores': [],
        }

    def get_historical_prices(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        adjusted: bool = True,
        **kwargs: Any
    ) -> PriceData:
        """
        Fetch historical prices with fallback to multiple providers.

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            adjusted: Whether to adjust for splits/dividends
            **kwargs: Additional parameters

        Returns:
            PriceData from the best available source

        Raises:
            DataFetchError: If all providers fail
        """
        self.fetch_stats['total_requests'] += 1

        errors = []

        for idx, provider in enumerate(self.providers):
            try:
                logger.debug(f"Trying provider {idx}: {type(provider).__name__}")

                # Fetch data
                price_data = provider.get_historical_prices(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    adjusted=adjusted,
                    **kwargs
                )

                # Validate quality
                if self.enable_validation:
                    quality_score = DataQualityMetrics.calculate_quality_score(
                        price_data.data
                    )
                    self.fetch_stats['quality_scores'].append(quality_score)

                    if quality_score < self.quality_threshold:
                        logger.warning(
                            f"Data quality too low ({quality_score:.2f}) from "
                            f"{type(provider).__name__}, trying next provider"
                        )
                        continue

                    # Add quality score to metadata
                    price_data.metadata['quality_score'] = quality_score

                # Success!
                self.fetch_stats['successful_requests'] += 1
                self.fetch_stats['provider_usage'][idx] += 1

                logger.info(
                    f"Successfully fetched {symbol} from {type(provider).__name__} "
                    f"(quality: {price_data.metadata.get('quality_score', 'N/A')})"
                )

                return price_data

            except (DataFetchError, DataValidationError) as e:
                logger.warning(
                    f"Provider {idx} ({type(provider).__name__}) failed: {e}"
                )
                errors.append((idx, str(e)))
                continue

        # All providers failed
        self.fetch_stats['failed_requests'] += 1
        error_msg = f"All providers failed for {symbol}. Errors: {errors}"
        logger.error(error_msg)
        raise DataFetchError(error_msg)

    def get_multiple_symbols(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        adjusted: bool = True,
        **kwargs: Any
    ) -> Dict[str, PriceData]:
        """
        Fetch data for multiple symbols efficiently.

        Args:
            symbols: List of symbols
            start_date: Start date
            end_date: End date
            adjusted: Whether to adjust for splits/dividends
            **kwargs: Additional parameters

        Returns:
            Dict mapping symbols to PriceData objects
        """
        results = {}

        for symbol in symbols:
            try:
                data = self.get_historical_prices(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    adjusted=adjusted,
                    **kwargs
                )
                results[symbol] = data
            except DataFetchError as e:
                logger.error(f"Failed to fetch {symbol}: {e}")
                continue

        return results

    def get_fundamentals(
        self,
        symbol: str,
        report_date: Optional[datetime] = None,
        **kwargs: Any
    ) -> FundamentalData:
        """
        Fetch fundamentals with fallback.

        Args:
            symbol: Stock symbol
            report_date: Specific report date
            **kwargs: Additional parameters

        Returns:
            FundamentalData from the best available source

        Raises:
            DataFetchError: If all providers fail
        """
        errors = []

        for idx, provider in enumerate(self.providers):
            try:
                fundamental_data = provider.get_fundamentals(
                    symbol=symbol,
                    report_date=report_date,
                    **kwargs
                )

                logger.info(
                    f"Successfully fetched fundamentals for {symbol} from "
                    f"{type(provider).__name__}"
                )

                return fundamental_data

            except DataFetchError as e:
                logger.warning(
                    f"Provider {idx} ({type(provider).__name__}) failed: {e}"
                )
                errors.append((idx, str(e)))
                continue

        # All providers failed
        error_msg = f"All providers failed for {symbol} fundamentals. Errors: {errors}"
        logger.error(error_msg)
        raise DataFetchError(error_msg)

    def get_corporate_actions(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any
    ) -> List[CorporateAction]:
        """
        Fetch corporate actions with fallback.

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            **kwargs: Additional parameters

        Returns:
            List of CorporateAction objects

        Raises:
            DataFetchError: If all providers fail
        """
        errors = []

        for idx, provider in enumerate(self.providers):
            try:
                actions = provider.get_corporate_actions(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    **kwargs
                )

                logger.info(
                    f"Successfully fetched {len(actions)} corporate actions for {symbol} "
                    f"from {type(provider).__name__}"
                )

                return actions

            except DataFetchError as e:
                logger.warning(
                    f"Provider {idx} ({type(provider).__name__}) failed: {e}"
                )
                errors.append((idx, str(e)))
                continue

        # All providers failed
        error_msg = f"All providers failed for {symbol} actions. Errors: {errors}"
        logger.error(error_msg)
        raise DataFetchError(error_msg)

    def merge_price_data(
        self,
        primary: PriceData,
        secondary: PriceData,
        strategy: str = 'primary_preferred'
    ) -> PriceData:
        """
        Merge price data from two sources.

        Args:
            primary: Primary data source
            secondary: Secondary data source
            strategy: Merge strategy ('primary_preferred', 'highest_quality', 'average')

        Returns:
            Merged PriceData

        Raises:
            ValueError: If strategy is invalid
        """
        if strategy == 'primary_preferred':
            # Use primary, fill gaps with secondary
            merged = primary.data.combine_first(secondary.data)

        elif strategy == 'highest_quality':
            # Use data with better quality score
            primary_quality = primary.metadata.get('quality_score', 0)
            secondary_quality = secondary.metadata.get('quality_score', 0)

            if primary_quality >= secondary_quality:
                merged = primary.data.combine_first(secondary.data)
            else:
                merged = secondary.data.combine_first(primary.data)

        elif strategy == 'average':
            # Average the two sources (for overlapping dates)
            merged = (primary.data + secondary.data) / 2
            merged = merged.combine_first(primary.data).combine_first(secondary.data)

        else:
            raise ValueError(f"Invalid merge strategy: {strategy}")

        return PriceData(
            symbol=primary.symbol,
            data=merged,
            start_date=min(primary.start_date, secondary.start_date),
            end_date=max(primary.end_date, secondary.end_date),
            adjusted=primary.adjusted,
            provider=primary.provider,
            metadata={
                'merged': True,
                'primary_provider': type(primary.provider).__name__,
                'secondary_provider': type(secondary.provider).__name__,
                'merge_strategy': strategy,
            }
        )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get aggregator statistics.

        Returns:
            Dict with usage statistics
        """
        stats = self.fetch_stats.copy()

        # Calculate additional metrics
        if stats['total_requests'] > 0:
            stats['success_rate'] = (
                stats['successful_requests'] / stats['total_requests']
            )

        if stats['quality_scores']:
            stats['avg_quality_score'] = np.mean(stats['quality_scores'])
            stats['min_quality_score'] = np.min(stats['quality_scores'])
            stats['max_quality_score'] = np.max(stats['quality_scores'])

        return stats

    def reset_statistics(self) -> None:
        """Reset statistics counters."""
        self.fetch_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'provider_usage': {i: 0 for i in range(len(self.providers))},
            'quality_scores': [],
        }


# Example usage
if __name__ == "__main__":
    from src.data.providers.yahoo import YahooFinanceProvider

    # Create aggregator with Yahoo as primary (add more providers in production)
    aggregator = MultiSourceAggregator(
        providers=[
            YahooFinanceProvider(),
            # PolygonProvider(api_key="..."),  # Add when implemented
            # AlpacaProvider(api_key="..."),    # Add when implemented
        ],
        quality_threshold=0.85
    )

    # Fetch data
    try:
        data = aggregator.get_historical_prices(
            symbol="AAPL",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31)
        )
        print(f"Fetched {len(data.data)} rows for {data.symbol}")
        print(f"Quality score: {data.metadata.get('quality_score', 'N/A')}")

        # Print statistics
        stats = aggregator.get_statistics()
        print(f"\nAggregator Statistics:")
        print(f"  Success rate: {stats.get('success_rate', 0):.2%}")
        print(f"  Avg quality: {stats.get('avg_quality_score', 0):.2f}")

    except DataFetchError as e:
        print(f"Failed to fetch data: {e}")

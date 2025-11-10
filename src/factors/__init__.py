"""
High-performance factor computation engine.

Uses vectorized operations for fast factor calculation across large universes.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from loguru import logger
import numpy as np
import pandas as pd


class FactorCategory(Enum):
    """Factor categories."""
    MOMENTUM = "momentum"
    VALUE = "value"
    QUALITY = "quality"
    VOLATILITY = "volatility"
    LIQUIDITY = "liquidity"
    GROWTH = "growth"
    SENTIMENT = "sentiment"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    ALTERNATIVE = "alternative"


@dataclass
class FactorMetadata:
    """
    Metadata for a factor.

    Attributes:
        name: Factor name
        category: Factor category
        description: Factor description
        formula: Mathematical formula
        data_requirements: Required data fields
        lookback_period: Lookback period in days
        update_frequency: How often factor updates (daily, weekly, etc.)
        normalization: Whether factor should be normalized
    """
    name: str
    category: FactorCategory
    description: str
    formula: str
    data_requirements: list[str]
    lookback_period: int
    update_frequency: str = "daily"
    normalization: bool = True


class Factor(ABC):
    """
    Abstract base class for all factors.

    All factors must implement the calculate method.
    """

    def __init__(self, metadata: FactorMetadata) -> None:
        """
        Initialize factor.

        Args:
            metadata: Factor metadata
        """
        self.metadata = metadata

    @abstractmethod
    def calculate(
        self,
        data: pd.DataFrame,
        universe: list[str] | None = None
    ) -> pd.Series:
        """
        Calculate factor values.

        Args:
            data: Price/volume data with MultiIndex (date, symbol)
            universe: Optional universe filter

        Returns:
            Series of factor values indexed by (date, symbol)
        """

    def validate_data(self, data: pd.DataFrame) -> bool:
        """
        Validate that required data is present.

        Args:
            data: Input data

        Returns:
            True if valid
        """
        required = set(self.metadata.data_requirements)
        available = set(data.columns.str.lower())
        missing = required - available

        if missing:
            logger.warning(
                f"Missing required columns for {self.metadata.name}: {missing}"
            )
            return False

        return True

    def normalize(
        self,
        values: pd.Series,
        method: str = "zscore",
        winsorize: float = 0.05
    ) -> pd.Series:
        """
        Normalize factor values.

        Args:
            values: Factor values
            method: Normalization method ('zscore', 'rank', 'minmax')
            winsorize: Winsorization percentile (e.g., 0.05 for 5%)

        Returns:
            Normalized values
        """
        if method == "zscore":
            # Z-score normalization
            if winsorize > 0:
                # Winsorize before normalizing
                lower = values.quantile(winsorize)
                upper = values.quantile(1 - winsorize)
                values = values.clip(lower, upper)

            mean = values.mean()
            std = values.std()
            if std > 0:
                return (values - mean) / std
            return values - mean

        if method == "rank":
            # Rank normalization (0 to 1)
            return values.rank(pct=True)

        if method == "minmax":
            # Min-max normalization (0 to 1)
            min_val = values.min()
            max_val = values.max()
            if max_val > min_val:
                return (values - min_val) / (max_val - min_val)
            return values * 0

        raise ValueError(f"Unknown normalization method: {method}")


class VectorizedFactorEngine:
    """
    High-performance vectorized factor calculation engine.

    Features:
    - Batch calculation across universe
    - Parallel processing
    - Caching
    - Incremental updates
    """

    def __init__(
        self,
        factors: list[Factor] | None = None,
        enable_cache: bool = True
    ) -> None:
        """
        Initialize factor engine.

        Args:
            factors: List of factors to compute
            enable_cache: Whether to enable caching
        """
        self.factors: dict[str, Factor] = {}
        if factors:
            for factor in factors:
                self.register_factor(factor)

        self.enable_cache = enable_cache
        self._cache: dict[str, pd.Series] = {}

        # Statistics
        self.stats = {
            "calculations": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        if not factors:
            self._register_default_factors()

    def _register_default_factors(self) -> None:
        """Register a handful of commonly used factors for convenience."""
        try:
            from .momentum import PriceMomentum
        except Exception:  # pragma: no cover - optional dependency chain
            return

        default_factors: dict[str, Factor] = {
            "momentum_12m": PriceMomentum(lookback=252, skip=21),
        }

        for alias, factor in default_factors.items():
            if factor.metadata.name not in self.factors:
                self.register_factor(factor)
            self.factors.setdefault(alias, factor)

    def register_factor(self, factor: Factor) -> None:
        """
        Register a factor.

        Args:
            factor: Factor instance
        """
        self.factors[factor.metadata.name] = factor
        logger.debug(f"Registered factor: {factor.metadata.name}")

    def calculate_factor(
        self,
        factor_name: str,
        data: pd.DataFrame,
        universe: list[str] | None = None,
        use_cache: bool = True
    ) -> pd.Series:
        """
        Calculate a single factor.

        Args:
            factor_name: Name of factor to calculate
            data: Price/volume data
            universe: Optional universe filter
            use_cache: Whether to use cache

        Returns:
            Factor values
        """
        if factor_name not in self.factors:
            raise ValueError(f"Unknown factor: {factor_name}")

        factor = self.factors[factor_name]

        # Check cache
        cache_key = self._get_cache_key(factor_name, data, universe)
        if use_cache and self.enable_cache and cache_key in self._cache:
            self.stats["cache_hits"] += 1
            logger.debug(f"Cache hit: {factor_name}")
            return self._cache[cache_key]

        self.stats["cache_misses"] += 1
        self.stats["calculations"] += 1

        # Validate data
        if not factor.validate_data(data):
            logger.error(f"Invalid data for factor: {factor_name}")
            return pd.Series(dtype=float)

        # Calculate factor
        logger.debug(f"Calculating factor: {factor_name}")
        values = factor.calculate(data, universe)

        # Normalize if requested
        if factor.metadata.normalization:
            values = factor.normalize(values)

        # Cache result
        if self.enable_cache:
            self._cache[cache_key] = values

        return values

    def calculate_all_factors(
        self,
        data: pd.DataFrame,
        universe: list[str] | None = None,
        categories: list[FactorCategory] | None = None
    ) -> pd.DataFrame:
        """
        Calculate all registered factors.

        Args:
            data: Price/volume data
            universe: Optional universe filter
            categories: Optional category filter

        Returns:
            DataFrame with factor values (columns = factors)
        """
        results = {}

        factors_to_calc = self.factors.values()
        if categories:
            factors_to_calc = [
                f for f in factors_to_calc
                if f.metadata.category in categories
            ]

        for factor in factors_to_calc:
            try:
                values = self.calculate_factor(
                    factor.metadata.name,
                    data,
                    universe
                )
                results[factor.metadata.name] = values
            except Exception as e:
                logger.error(f"Failed to calculate {factor.metadata.name}: {e}")
                continue

        return pd.DataFrame(results)

    def calculate_factor_panel(
        self,
        data: dict[str, pd.DataFrame],
        factor_names: list[str],
        rebalance_dates: list[datetime]
    ) -> pd.DataFrame:
        """
        Calculate factor panel over time.

        Args:
            data: Dict of symbol -> price data
            factor_names: Factors to calculate
            rebalance_dates: Dates to calculate factors

        Returns:
            DataFrame with MultiIndex (date, symbol) and factor columns
        """
        results = []

        for date in rebalance_dates:
            # Filter data up to this date
            filtered_data = {}
            for symbol, df in data.items():
                mask = df.index <= date
                if mask.any():
                    filtered_data[symbol] = df[mask]

            if not filtered_data:
                continue

            # Stack data for vectorized calculation
            stacked_data = self._stack_data(filtered_data, date)

            # Calculate factors
            for factor_name in factor_names:
                try:
                    values = self.calculate_factor(
                        factor_name,
                        stacked_data,
                        use_cache=False  # Don't cache panel calculations
                    )

                    for symbol in filtered_data:
                        if symbol in values.index:
                            results.append({
                                "date": date,
                                "symbol": symbol,
                                "factor": factor_name,
                                "value": values[symbol]
                            })
                except Exception as e:
                    logger.error(
                        f"Failed to calculate {factor_name} on {date}: {e}"
                    )
                    continue

        if not results:
            return pd.DataFrame()

        df = pd.DataFrame(results)
        df = df.pivot_table(
            index=["date", "symbol"],
            columns="factor",
            values="value"
        )

        return df

    def _stack_data(
        self,
        data: dict[str, pd.DataFrame],
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Stack data from multiple symbols into single DataFrame.

        Args:
            data: Dict of symbol -> data
            end_date: End date for data

        Returns:
            Stacked DataFrame
        """
        dfs = []

        for symbol, df in data.items():
            df = df.copy()
            df["symbol"] = symbol
            dfs.append(df)

        if not dfs:
            return pd.DataFrame()

        stacked = pd.concat(dfs, axis=0)
        stacked = stacked.reset_index()
        stacked = stacked.set_index(["date", "symbol"])

        return stacked

    def _get_cache_key(
        self,
        factor_name: str,
        data: pd.DataFrame,
        universe: list[str] | None
    ) -> str:
        """Generate cache key."""
        data_hash = hash(tuple(data.index))
        universe_hash = hash(tuple(sorted(universe))) if universe else 0
        return f"{factor_name}_{data_hash}_{universe_hash}"

    def clear_cache(self) -> None:
        """Clear factor cache."""
        self._cache.clear()
        logger.info("Factor cache cleared")

    def get_statistics(self) -> dict[str, Any]:
        """
        Get engine statistics.

        Returns:
            Dict with statistics
        """
        total_requests = self.stats["cache_hits"] + self.stats["cache_misses"]
        hit_rate = (
            self.stats["cache_hits"] / total_requests
            if total_requests > 0 else 0
        )

        return {
            "registered_factors": len(self.factors),
            "total_calculations": self.stats["calculations"],
            "cache_size": len(self._cache),
            "cache_hit_rate": hit_rate,
            **self.stats
        }

    def list_factors(
        self,
        category: FactorCategory | None = None
    ) -> list[FactorMetadata]:
        """
        List registered factors.

        Args:
            category: Optional category filter

        Returns:
            List of factor metadata
        """
        factors = self.factors.values()

        if category:
            factors = [f for f in factors if f.metadata.category == category]

        return [f.metadata for f in factors]


# Example momentum factor
class MomentumFactor(Factor):
    """
    Simple price momentum factor.

    Returns = (Price_t - Price_t-n) / Price_t-n
    """

    def __init__(self, lookback: int = 20) -> None:
        """
        Initialize momentum factor.

        Args:
            lookback: Lookback period in days
        """
        metadata = FactorMetadata(
            name=f"momentum_{lookback}d",
            category=FactorCategory.MOMENTUM,
            description=f"{lookback}-day price momentum",
            formula=f"(close_t - close_t-{lookback}) / close_t-{lookback}",
            data_requirements=["close"],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: list[str] | None = None
    ) -> pd.Series:
        """Calculate momentum."""
        closes = data["close"]

        # Calculate returns
        returns = closes.pct_change(periods=self.lookback)

        # Filter universe if provided
        if universe:
            returns = returns[returns.index.get_level_values("symbol").isin(universe)]

        return returns.fillna(0)


# Example usage
if __name__ == "__main__":
    # Create engine
    engine = VectorizedFactorEngine()

    # Register factors
    engine.register_factor(MomentumFactor(lookback=20))
    engine.register_factor(MomentumFactor(lookback=60))

    # Create sample data
    dates = pd.date_range("2023-01-01", "2023-12-31", freq="B")
    symbols = ["AAPL", "MSFT", "GOOGL"]

    data_list = []
    for symbol in symbols:
        for date in dates:
            data_list.append({
                "date": date,
                "symbol": symbol,
                "close": 100 * (1 + np.random.randn() * 0.02).cumprod()[0]
            })

    data = pd.DataFrame(data_list)
    data = data.set_index(["date", "symbol"])

    # Calculate all factors
    factors = engine.calculate_all_factors(data)
    print(factors.head())

    # Get statistics
    print("\nEngine Statistics:")
    print(engine.get_statistics())

"""
Growth factors.

Growth metrics based on earnings, revenue, and fundamental trends.
"""

from typing import Optional, List
import pandas as pd
import numpy as np
from loguru import logger

from src.factors import Factor, FactorMetadata, FactorCategory


class RevenueGrowth(Factor):
    """
    Revenue growth rate.

    Formula: (Revenue_t - Revenue_t-n) / Revenue_t-n
    Higher growth = better
    """

    def __init__(self, lookback: int = 252) -> None:
        """
        Initialize revenue growth factor.

        Args:
            lookback: Lookback period (252 = YoY)
        """
        metadata = FactorMetadata(
            name=f"revenue_growth_{lookback}d",
            category=FactorCategory.GROWTH,
            description=f"{lookback}-day revenue growth rate",
            formula=f"(Revenue_t - Revenue_t-{lookback}) / Revenue_t-{lookback}",
            data_requirements=['revenue'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate revenue growth."""
        if 'revenue' not in data.columns:
            logger.warning("Missing revenue data for growth calculation")
            return pd.Series(dtype=float)

        revenue = data['revenue'].unstack(fill_value=np.nan)

        # Calculate TTM revenue
        revenue_ttm = revenue.rolling(window=4, min_periods=4).sum()

        # Calculate growth rate
        revenue_old = revenue_ttm.shift(periods=4)  # YoY comparison
        growth = (revenue_ttm - revenue_old) / revenue_old

        result = growth.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class EarningsGrowth(Factor):
    """
    Earnings growth rate.

    Formula: (Earnings_t - Earnings_t-n) / Earnings_t-n
    Higher growth = better
    """

    def __init__(self, lookback: int = 252) -> None:
        """
        Initialize earnings growth factor.

        Args:
            lookback: Lookback period (252 = YoY)
        """
        metadata = FactorMetadata(
            name=f"earnings_growth_{lookback}d",
            category=FactorCategory.GROWTH,
            description=f"{lookback}-day earnings growth rate",
            formula=f"(Earnings_t - Earnings_t-{lookback}) / Earnings_t-{lookback}",
            data_requirements=['net_income'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate earnings growth."""
        if 'net_income' not in data.columns:
            logger.warning("Missing earnings data for growth calculation")
            return pd.Series(dtype=float)

        earnings = data['net_income'].unstack(fill_value=np.nan)

        # Calculate TTM earnings
        earnings_ttm = earnings.rolling(window=4, min_periods=4).sum()

        # Calculate growth rate
        earnings_old = earnings_ttm.shift(periods=4)  # YoY comparison
        growth = (earnings_ttm - earnings_old) / earnings_old.abs()

        result = growth.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class EPSGrowth(Factor):
    """
    Earnings Per Share growth rate.

    Formula: (EPS_t - EPS_t-n) / EPS_t-n
    Higher growth = better
    """

    def __init__(self, lookback: int = 252) -> None:
        """
        Initialize EPS growth factor.

        Args:
            lookback: Lookback period (252 = YoY)
        """
        metadata = FactorMetadata(
            name=f"eps_growth_{lookback}d",
            category=FactorCategory.GROWTH,
            description=f"{lookback}-day EPS growth rate",
            formula=f"(EPS_t - EPS_t-{lookback}) / EPS_t-{lookback}",
            data_requirements=['eps'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate EPS growth."""
        if 'eps' not in data.columns:
            logger.warning("Missing EPS data for growth calculation")
            return pd.Series(dtype=float)

        eps = data['eps'].unstack(fill_value=np.nan)

        # Calculate TTM EPS
        eps_ttm = eps.rolling(window=4, min_periods=4).sum()

        # Calculate growth rate
        eps_old = eps_ttm.shift(periods=4)  # YoY comparison
        growth = (eps_ttm - eps_old) / eps_old.abs()

        result = growth.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class BookValueGrowth(Factor):
    """
    Book value growth rate.

    Formula: (Book Value_t - Book Value_t-n) / Book Value_t-n
    Higher growth = better asset accumulation
    """

    def __init__(self, lookback: int = 252) -> None:
        """
        Initialize book value growth factor.

        Args:
            lookback: Lookback period
        """
        metadata = FactorMetadata(
            name=f"book_value_growth_{lookback}d",
            category=FactorCategory.GROWTH,
            description=f"{lookback}-day book value growth rate",
            formula=f"(BV_t - BV_t-{lookback}) / BV_t-{lookback}",
            data_requirements=['book_value'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate book value growth."""
        if 'book_value' not in data.columns:
            logger.warning("Missing book value data for growth calculation")
            return pd.Series(dtype=float)

        book_value = data['book_value'].unstack(fill_value=np.nan)

        # Calculate growth rate
        book_value_old = book_value.shift(periods=4)  # YoY comparison
        growth = (book_value - book_value_old) / book_value_old

        result = growth.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class CashFlowGrowth(Factor):
    """
    Operating cash flow growth rate.

    Formula: (OCF_t - OCF_t-n) / OCF_t-n
    Higher growth = better cash generation
    """

    def __init__(self, lookback: int = 252, use_free_cash_flow: bool = False) -> None:
        """
        Initialize cash flow growth factor.

        Args:
            lookback: Lookback period
            use_free_cash_flow: Use FCF instead of OCF
        """
        cf_type = "free_cash_flow" if use_free_cash_flow else "operating_cash_flow"
        metadata = FactorMetadata(
            name=f"{'fcf' if use_free_cash_flow else 'ocf'}_growth_{lookback}d",
            category=FactorCategory.GROWTH,
            description=f"{lookback}-day {'FCF' if use_free_cash_flow else 'OCF'} growth rate",
            formula=f"(CF_t - CF_t-{lookback}) / CF_t-{lookback}",
            data_requirements=[cf_type],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback
        self.cf_column = cf_type

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate cash flow growth."""
        if self.cf_column not in data.columns:
            logger.warning(f"Missing {self.cf_column} data for growth calculation")
            return pd.Series(dtype=float)

        cash_flow = data[self.cf_column].unstack(fill_value=np.nan)

        # Calculate TTM cash flow
        cf_ttm = cash_flow.rolling(window=4, min_periods=4).sum()

        # Calculate growth rate
        cf_old = cf_ttm.shift(periods=4)  # YoY comparison
        growth = (cf_ttm - cf_old) / cf_old.abs()

        result = growth.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class ROEGrowth(Factor):
    """
    Return on Equity growth trend.

    Formula: ROE_t - ROE_t-n
    Improving ROE = quality improvement
    """

    def __init__(self, lookback: int = 252) -> None:
        """
        Initialize ROE growth factor.

        Args:
            lookback: Lookback period
        """
        metadata = FactorMetadata(
            name=f"roe_growth_{lookback}d",
            category=FactorCategory.GROWTH,
            description=f"{lookback}-day ROE improvement",
            formula=f"ROE_t - ROE_t-{lookback}",
            data_requirements=['roe'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate ROE growth."""
        if 'roe' not in data.columns:
            logger.warning("Missing ROE data for growth calculation")
            return pd.Series(dtype=float)

        roe = data['roe'].unstack(fill_value=np.nan)

        # Calculate change in ROE
        roe_old = roe.shift(periods=4)  # YoY comparison
        roe_change = roe - roe_old

        result = roe_change.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class MarginExpansion(Factor):
    """
    Operating margin expansion.

    Formula: Operating Margin_t - Operating Margin_t-n
    Expanding margins = improving efficiency
    """

    def __init__(self, lookback: int = 252) -> None:
        """
        Initialize margin expansion factor.

        Args:
            lookback: Lookback period
        """
        metadata = FactorMetadata(
            name=f"margin_expansion_{lookback}d",
            category=FactorCategory.GROWTH,
            description=f"{lookback}-day operating margin expansion",
            formula=f"OpMargin_t - OpMargin_t-{lookback}",
            data_requirements=['operating_margin'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate margin expansion."""
        if 'operating_margin' not in data.columns:
            logger.warning("Missing operating margin data for expansion calculation")
            return pd.Series(dtype=float)

        margin = data['operating_margin'].unstack(fill_value=np.nan)

        # Calculate change in margin
        margin_old = margin.shift(periods=4)  # YoY comparison
        margin_change = margin - margin_old

        result = margin_change.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class SalesAcceleration(Factor):
    """
    Sales growth acceleration.

    Measures whether sales growth is accelerating or decelerating.
    """

    def __init__(self, short_period: int = 63, long_period: int = 252) -> None:
        """
        Initialize sales acceleration factor.

        Args:
            short_period: Short growth period
            long_period: Long growth period
        """
        metadata = FactorMetadata(
            name=f"sales_acceleration_{short_period}_{long_period}d",
            category=FactorCategory.GROWTH,
            description="Sales growth acceleration",
            formula=f"Growth_{short_period}d - Growth_{long_period}d",
            data_requirements=['revenue'],
            lookback_period=long_period,
        )
        super().__init__(metadata)
        self.short_period = short_period
        self.long_period = long_period

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate sales acceleration."""
        if 'revenue' not in data.columns:
            logger.warning("Missing revenue data for acceleration calculation")
            return pd.Series(dtype=float)

        revenue = data['revenue'].unstack(fill_value=np.nan)

        # Calculate TTM revenue
        revenue_ttm = revenue.rolling(window=4, min_periods=4).sum()

        # Short-term growth
        short_growth = revenue_ttm.pct_change(periods=1)  # QoQ

        # Long-term growth
        long_growth = revenue_ttm.pct_change(periods=4)  # YoY

        # Acceleration = short - long
        acceleration = short_growth - long_growth

        result = acceleration.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class EarningsAcceleration(Factor):
    """
    Earnings growth acceleration.

    Measures whether earnings growth is accelerating.
    """

    def __init__(self, short_period: int = 63, long_period: int = 252) -> None:
        """
        Initialize earnings acceleration factor.

        Args:
            short_period: Short growth period
            long_period: Long growth period
        """
        metadata = FactorMetadata(
            name=f"earnings_acceleration_{short_period}_{long_period}d",
            category=FactorCategory.GROWTH,
            description="Earnings growth acceleration",
            formula=f"Growth_{short_period}d - Growth_{long_period}d",
            data_requirements=['net_income'],
            lookback_period=long_period,
        )
        super().__init__(metadata)
        self.short_period = short_period
        self.long_period = long_period

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate earnings acceleration."""
        if 'net_income' not in data.columns:
            logger.warning("Missing earnings data for acceleration calculation")
            return pd.Series(dtype=float)

        earnings = data['net_income'].unstack(fill_value=np.nan)

        # Calculate TTM earnings
        earnings_ttm = earnings.rolling(window=4, min_periods=4).sum()

        # Short-term growth
        short_growth = earnings_ttm.pct_change(periods=1)  # QoQ

        # Long-term growth
        long_growth = earnings_ttm.pct_change(periods=4)  # YoY

        # Acceleration = short - long
        acceleration = short_growth - long_growth

        result = acceleration.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class AssetGrowth(Factor):
    """
    Total assets growth rate.

    Formula: (Assets_t - Assets_t-n) / Assets_t-n
    Higher growth = business expansion
    """

    def __init__(self, lookback: int = 252) -> None:
        """
        Initialize asset growth factor.

        Args:
            lookback: Lookback period
        """
        metadata = FactorMetadata(
            name=f"asset_growth_{lookback}d",
            category=FactorCategory.GROWTH,
            description=f"{lookback}-day total assets growth rate",
            formula=f"(Assets_t - Assets_t-{lookback}) / Assets_t-{lookback}",
            data_requirements=['total_assets'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate asset growth."""
        if 'total_assets' not in data.columns:
            logger.warning("Missing total assets data for growth calculation")
            return pd.Series(dtype=float)

        assets = data['total_assets'].unstack(fill_value=np.nan)

        # Calculate growth rate
        assets_old = assets.shift(periods=4)  # YoY comparison
        growth = (assets - assets_old) / assets_old

        result = growth.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class SustainableGrowthRate(Factor):
    """
    Sustainable growth rate.

    Formula: ROE * (1 - Dividend Payout Ratio)
    Maximum growth rate without external financing
    """

    def __init__(self) -> None:
        """Initialize sustainable growth rate factor."""
        metadata = FactorMetadata(
            name="sustainable_growth_rate",
            category=FactorCategory.GROWTH,
            description="Sustainable growth rate (ROE * retention ratio)",
            formula="ROE * (1 - Dividend Payout Ratio)",
            data_requirements=['roe', 'dividend_payout_ratio'],
            lookback_period=1,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate sustainable growth rate."""
        if 'roe' not in data.columns:
            logger.warning("Missing ROE data for SGR calculation")
            return pd.Series(dtype=float)

        roe = data['roe'].unstack(fill_value=np.nan)

        # Get dividend payout ratio
        if 'dividend_payout_ratio' in data.columns:
            payout = data['dividend_payout_ratio'].unstack(fill_value=np.nan)
        else:
            # Assume 30% payout if not available
            payout = 0.30

        # Calculate sustainable growth rate
        sgr = roe * (1 - payout)

        result = sgr.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


# Factory function to create all growth factors
def create_growth_factors() -> List[Factor]:
    """
    Create standard set of growth factors.

    Returns:
        List of growth factors
    """
    return [
        # Core growth metrics
        RevenueGrowth(lookback=252),
        EarningsGrowth(lookback=252),
        EPSGrowth(lookback=252),
        BookValueGrowth(lookback=252),
        CashFlowGrowth(lookback=252, use_free_cash_flow=False),
        CashFlowGrowth(lookback=252, use_free_cash_flow=True),

        # Quality improvement
        ROEGrowth(lookback=252),
        MarginExpansion(lookback=252),

        # Growth momentum
        SalesAcceleration(short_period=63, long_period=252),
        EarningsAcceleration(short_period=63, long_period=252),

        # Balance sheet
        AssetGrowth(lookback=252),

        # Theoretical
        SustainableGrowthRate(),
    ]

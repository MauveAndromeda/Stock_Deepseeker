"""
Value factors.

Traditional and modern value factors for cross-sectional ranking.
"""

from typing import Optional, List
import pandas as pd
import numpy as np
from loguru import logger

from src.factors import Factor, FactorMetadata, FactorCategory


class PriceToBook(Factor):
    """
    Price-to-Book ratio factor.

    Formula: Market Cap / Book Value of Equity
    Lower P/B = more value
    """

    def __init__(self) -> None:
        """Initialize P/B factor."""
        metadata = FactorMetadata(
            name="price_to_book",
            category=FactorCategory.VALUE,
            description="Price-to-Book ratio (inverted for value signal)",
            formula="Book Value / Market Cap (inverted P/B)",
            data_requirements=['close', 'shares_outstanding', 'book_value'],
            lookback_period=1,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate inverted P/B ratio."""
        # Get market cap
        if 'market_cap' in data.columns:
            market_cap = data['market_cap'].unstack(fill_value=np.nan)
        else:
            # Calculate from price and shares
            closes = data['close'].unstack(fill_value=np.nan)
            if 'shares_outstanding' in data.columns:
                shares = data['shares_outstanding'].unstack(fill_value=np.nan)
                market_cap = closes * shares
            else:
                logger.warning("Missing market cap or shares data for P/B calculation")
                return pd.Series(dtype=float)

        # Get book value
        if 'book_value' not in data.columns:
            logger.warning("Missing book value data for P/B calculation")
            return pd.Series(dtype=float)

        book_value = data['book_value'].unstack(fill_value=np.nan)

        # Calculate B/P (inverted P/B for value signal)
        # Higher B/P = lower P/B = more value
        bp_ratio = book_value / market_cap

        result = bp_ratio.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class PriceToEarnings(Factor):
    """
    Price-to-Earnings ratio factor.

    Formula: Market Cap / Net Income (TTM)
    Lower P/E = more value
    """

    def __init__(self, use_forward: bool = False) -> None:
        """
        Initialize P/E factor.

        Args:
            use_forward: Use forward P/E if available
        """
        metadata = FactorMetadata(
            name=f"price_to_earnings{'_forward' if use_forward else ''}",
            category=FactorCategory.VALUE,
            description=f"Price-to-Earnings ratio ({'forward' if use_forward else 'trailing'}, inverted)",
            formula="Earnings / Market Cap (inverted P/E)",
            data_requirements=['close', 'earnings', 'market_cap'],
            lookback_period=252,  # Use TTM earnings
        )
        super().__init__(metadata)
        self.use_forward = use_forward

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate inverted P/E ratio."""
        # Get market cap
        if 'market_cap' in data.columns:
            market_cap = data['market_cap'].unstack(fill_value=np.nan)
        else:
            closes = data['close'].unstack(fill_value=np.nan)
            if 'shares_outstanding' in data.columns:
                shares = data['shares_outstanding'].unstack(fill_value=np.nan)
                market_cap = closes * shares
            else:
                logger.warning("Missing market cap data for P/E calculation")
                return pd.Series(dtype=float)

        # Get earnings
        earnings_col = 'forward_earnings' if self.use_forward else 'earnings'
        if earnings_col not in data.columns:
            logger.warning(f"Missing {earnings_col} data for P/E calculation")
            return pd.Series(dtype=float)

        earnings = data[earnings_col].unstack(fill_value=np.nan)

        # Calculate TTM earnings if not forward
        if not self.use_forward:
            earnings = earnings.rolling(window=4, min_periods=4).sum()

        # Calculate E/P (inverted P/E for value signal)
        # Higher E/P = lower P/E = more value
        ep_ratio = earnings / market_cap

        result = ep_ratio.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class PriceToSales(Factor):
    """
    Price-to-Sales ratio factor.

    Formula: Market Cap / Revenue (TTM)
    Lower P/S = more value
    """

    def __init__(self) -> None:
        """Initialize P/S factor."""
        metadata = FactorMetadata(
            name="price_to_sales",
            category=FactorCategory.VALUE,
            description="Price-to-Sales ratio (inverted for value signal)",
            formula="Revenue / Market Cap (inverted P/S)",
            data_requirements=['close', 'revenue', 'market_cap'],
            lookback_period=252,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate inverted P/S ratio."""
        # Get market cap
        if 'market_cap' in data.columns:
            market_cap = data['market_cap'].unstack(fill_value=np.nan)
        else:
            closes = data['close'].unstack(fill_value=np.nan)
            if 'shares_outstanding' in data.columns:
                shares = data['shares_outstanding'].unstack(fill_value=np.nan)
                market_cap = closes * shares
            else:
                logger.warning("Missing market cap data for P/S calculation")
                return pd.Series(dtype=float)

        # Get revenue
        if 'revenue' not in data.columns:
            logger.warning("Missing revenue data for P/S calculation")
            return pd.Series(dtype=float)

        revenue = data['revenue'].unstack(fill_value=np.nan)

        # Calculate TTM revenue
        revenue_ttm = revenue.rolling(window=4, min_periods=4).sum()

        # Calculate S/P (inverted P/S for value signal)
        sp_ratio = revenue_ttm / market_cap

        result = sp_ratio.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class PriceToCashFlow(Factor):
    """
    Price-to-Cash-Flow ratio factor.

    Formula: Market Cap / Operating Cash Flow (TTM)
    Lower P/CF = more value
    """

    def __init__(self, use_free_cash_flow: bool = False) -> None:
        """
        Initialize P/CF factor.

        Args:
            use_free_cash_flow: Use FCF instead of OCF
        """
        cf_type = "free_cash_flow" if use_free_cash_flow else "operating_cash_flow"
        metadata = FactorMetadata(
            name=f"price_to_{'fcf' if use_free_cash_flow else 'ocf'}",
            category=FactorCategory.VALUE,
            description=f"Price-to-{'Free' if use_free_cash_flow else 'Operating'} Cash Flow ratio (inverted)",
            formula=f"{cf_type.replace('_', ' ').title()} / Market Cap",
            data_requirements=['close', cf_type, 'market_cap'],
            lookback_period=252,
        )
        super().__init__(metadata)
        self.cf_column = cf_type
        self.use_free_cash_flow = use_free_cash_flow

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate inverted P/CF ratio."""
        # Get market cap
        if 'market_cap' in data.columns:
            market_cap = data['market_cap'].unstack(fill_value=np.nan)
        else:
            closes = data['close'].unstack(fill_value=np.nan)
            if 'shares_outstanding' in data.columns:
                shares = data['shares_outstanding'].unstack(fill_value=np.nan)
                market_cap = closes * shares
            else:
                logger.warning("Missing market cap data for P/CF calculation")
                return pd.Series(dtype=float)

        # Get cash flow
        if self.cf_column not in data.columns:
            logger.warning(f"Missing {self.cf_column} data for P/CF calculation")
            return pd.Series(dtype=float)

        cash_flow = data[self.cf_column].unstack(fill_value=np.nan)

        # Calculate TTM cash flow
        cf_ttm = cash_flow.rolling(window=4, min_periods=4).sum()

        # Calculate CF/P (inverted P/CF for value signal)
        cfp_ratio = cf_ttm / market_cap

        result = cfp_ratio.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class EVToEBITDA(Factor):
    """
    Enterprise Value to EBITDA ratio factor.

    Formula: (Market Cap + Debt - Cash) / EBITDA (TTM)
    Lower EV/EBITDA = more value
    """

    def __init__(self) -> None:
        """Initialize EV/EBITDA factor."""
        metadata = FactorMetadata(
            name="ev_to_ebitda",
            category=FactorCategory.VALUE,
            description="Enterprise Value to EBITDA ratio (inverted)",
            formula="EBITDA / (Market Cap + Debt - Cash)",
            data_requirements=['close', 'ebitda', 'total_debt', 'cash', 'market_cap'],
            lookback_period=252,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate inverted EV/EBITDA ratio."""
        # Get market cap
        if 'market_cap' in data.columns:
            market_cap = data['market_cap'].unstack(fill_value=np.nan)
        else:
            closes = data['close'].unstack(fill_value=np.nan)
            if 'shares_outstanding' in data.columns:
                shares = data['shares_outstanding'].unstack(fill_value=np.nan)
                market_cap = closes * shares
            else:
                logger.warning("Missing market cap data for EV/EBITDA calculation")
                return pd.Series(dtype=float)

        # Get debt and cash
        if 'total_debt' not in data.columns or 'cash' not in data.columns:
            logger.warning("Missing debt or cash data for EV/EBITDA calculation")
            return pd.Series(dtype=float)

        debt = data['total_debt'].unstack(fill_value=np.nan)
        cash = data['cash'].unstack(fill_value=np.nan)

        # Calculate Enterprise Value
        enterprise_value = market_cap + debt - cash

        # Get EBITDA
        if 'ebitda' not in data.columns:
            logger.warning("Missing EBITDA data for EV/EBITDA calculation")
            return pd.Series(dtype=float)

        ebitda = data['ebitda'].unstack(fill_value=np.nan)

        # Calculate TTM EBITDA
        ebitda_ttm = ebitda.rolling(window=4, min_periods=4).sum()

        # Calculate EBITDA/EV (inverted EV/EBITDA for value signal)
        ratio = ebitda_ttm / enterprise_value

        result = ratio.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class EVToSales(Factor):
    """
    Enterprise Value to Sales ratio factor.

    Formula: (Market Cap + Debt - Cash) / Revenue (TTM)
    Lower EV/Sales = more value
    """

    def __init__(self) -> None:
        """Initialize EV/Sales factor."""
        metadata = FactorMetadata(
            name="ev_to_sales",
            category=FactorCategory.VALUE,
            description="Enterprise Value to Sales ratio (inverted)",
            formula="Revenue / (Market Cap + Debt - Cash)",
            data_requirements=['close', 'revenue', 'total_debt', 'cash', 'market_cap'],
            lookback_period=252,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate inverted EV/Sales ratio."""
        # Get market cap
        if 'market_cap' in data.columns:
            market_cap = data['market_cap'].unstack(fill_value=np.nan)
        else:
            closes = data['close'].unstack(fill_value=np.nan)
            if 'shares_outstanding' in data.columns:
                shares = data['shares_outstanding'].unstack(fill_value=np.nan)
                market_cap = closes * shares
            else:
                logger.warning("Missing market cap data for EV/Sales calculation")
                return pd.Series(dtype=float)

        # Get debt and cash
        if 'total_debt' not in data.columns or 'cash' not in data.columns:
            logger.warning("Missing debt or cash data for EV/Sales calculation")
            return pd.Series(dtype=float)

        debt = data['total_debt'].unstack(fill_value=np.nan)
        cash = data['cash'].unstack(fill_value=np.nan)

        # Calculate Enterprise Value
        enterprise_value = market_cap + debt - cash

        # Get revenue
        if 'revenue' not in data.columns:
            logger.warning("Missing revenue data for EV/Sales calculation")
            return pd.Series(dtype=float)

        revenue = data['revenue'].unstack(fill_value=np.nan)

        # Calculate TTM revenue
        revenue_ttm = revenue.rolling(window=4, min_periods=4).sum()

        # Calculate Sales/EV (inverted EV/Sales for value signal)
        ratio = revenue_ttm / enterprise_value

        result = ratio.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class DividendYield(Factor):
    """
    Dividend Yield factor.

    Formula: Annual Dividends per Share / Price
    Higher dividend yield = more value
    """

    def __init__(self, lookback: int = 252) -> None:
        """
        Initialize dividend yield factor.

        Args:
            lookback: Lookback period for calculating annual dividends
        """
        metadata = FactorMetadata(
            name=f"dividend_yield_{lookback}d",
            category=FactorCategory.VALUE,
            description=f"{lookback}-day trailing dividend yield",
            formula="Sum of dividends over period / Current Price",
            data_requirements=['close', 'dividends'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate dividend yield."""
        closes = data['close'].unstack(fill_value=np.nan)

        # Get dividends
        if 'dividends' not in data.columns:
            logger.warning("Missing dividends data for dividend yield calculation")
            return pd.Series(dtype=float)

        dividends = data['dividends'].unstack(fill_value=np.nan)

        # Calculate trailing annual dividends
        annual_dividends = dividends.rolling(window=self.lookback).sum()

        # Calculate dividend yield
        div_yield = annual_dividends / closes

        result = div_yield.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class EarningsYield(Factor):
    """
    Earnings Yield factor.

    Formula: Earnings per Share (TTM) / Price
    Higher earnings yield = more value
    Inverse of P/E ratio
    """

    def __init__(self) -> None:
        """Initialize earnings yield factor."""
        metadata = FactorMetadata(
            name="earnings_yield",
            category=FactorCategory.VALUE,
            description="Trailing twelve month earnings yield",
            formula="TTM EPS / Current Price",
            data_requirements=['close', 'earnings', 'shares_outstanding'],
            lookback_period=252,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate earnings yield."""
        closes = data['close'].unstack(fill_value=np.nan)

        # Get earnings
        if 'earnings' not in data.columns:
            logger.warning("Missing earnings data for earnings yield calculation")
            return pd.Series(dtype=float)

        earnings = data['earnings'].unstack(fill_value=np.nan)

        # Calculate TTM earnings
        earnings_ttm = earnings.rolling(window=4, min_periods=4).sum()

        # Get shares outstanding
        if 'shares_outstanding' in data.columns:
            shares = data['shares_outstanding'].unstack(fill_value=np.nan)
            # Calculate EPS
            eps = earnings_ttm / shares
        else:
            # Use earnings directly if shares not available
            eps = earnings_ttm

        # Calculate earnings yield
        earnings_yield = eps / closes

        result = earnings_yield.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class FreeCashFlowYield(Factor):
    """
    Free Cash Flow Yield factor.

    Formula: Free Cash Flow per Share (TTM) / Price
    Higher FCF yield = more value
    """

    def __init__(self) -> None:
        """Initialize FCF yield factor."""
        metadata = FactorMetadata(
            name="fcf_yield",
            category=FactorCategory.VALUE,
            description="Trailing twelve month free cash flow yield",
            formula="TTM FCF per Share / Current Price",
            data_requirements=['close', 'free_cash_flow', 'shares_outstanding'],
            lookback_period=252,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate FCF yield."""
        closes = data['close'].unstack(fill_value=np.nan)

        # Get free cash flow
        if 'free_cash_flow' not in data.columns:
            logger.warning("Missing free cash flow data for FCF yield calculation")
            return pd.Series(dtype=float)

        fcf = data['free_cash_flow'].unstack(fill_value=np.nan)

        # Calculate TTM FCF
        fcf_ttm = fcf.rolling(window=4, min_periods=4).sum()

        # Get shares outstanding
        if 'shares_outstanding' in data.columns:
            shares = data['shares_outstanding'].unstack(fill_value=np.nan)
            # Calculate FCF per share
            fcf_per_share = fcf_ttm / shares
        else:
            # Use FCF directly if shares not available
            fcf_per_share = fcf_ttm

        # Calculate FCF yield
        fcf_yield = fcf_per_share / closes

        result = fcf_yield.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class BookToMarket(Factor):
    """
    Book-to-Market ratio factor (classic Fama-French value factor).

    Formula: Book Value / Market Cap
    Higher B/M = more value
    Same as inverted P/B but named differently for academic consistency
    """

    def __init__(self) -> None:
        """Initialize B/M factor."""
        metadata = FactorMetadata(
            name="book_to_market",
            category=FactorCategory.VALUE,
            description="Book-to-Market ratio (Fama-French HML factor)",
            formula="Book Value of Equity / Market Cap",
            data_requirements=['close', 'book_value', 'shares_outstanding'],
            lookback_period=1,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate B/M ratio."""
        # Get market cap
        if 'market_cap' in data.columns:
            market_cap = data['market_cap'].unstack(fill_value=np.nan)
        else:
            closes = data['close'].unstack(fill_value=np.nan)
            if 'shares_outstanding' in data.columns:
                shares = data['shares_outstanding'].unstack(fill_value=np.nan)
                market_cap = closes * shares
            else:
                logger.warning("Missing market cap data for B/M calculation")
                return pd.Series(dtype=float)

        # Get book value
        if 'book_value' not in data.columns:
            logger.warning("Missing book value data for B/M calculation")
            return pd.Series(dtype=float)

        book_value = data['book_value'].unstack(fill_value=np.nan)

        # Calculate B/M ratio
        bm_ratio = book_value / market_cap

        result = bm_ratio.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class SalesToPrice(Factor):
    """
    Sales-to-Price ratio (inverted P/S).

    Formula: Revenue (TTM) / Market Cap
    Higher S/P = more value
    """

    def __init__(self) -> None:
        """Initialize S/P factor."""
        metadata = FactorMetadata(
            name="sales_to_price",
            category=FactorCategory.VALUE,
            description="Sales-to-Price ratio (inverted P/S)",
            formula="TTM Revenue / Market Cap",
            data_requirements=['close', 'revenue', 'market_cap'],
            lookback_period=252,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate S/P ratio."""
        # Get market cap
        if 'market_cap' in data.columns:
            market_cap = data['market_cap'].unstack(fill_value=np.nan)
        else:
            closes = data['close'].unstack(fill_value=np.nan)
            if 'shares_outstanding' in data.columns:
                shares = data['shares_outstanding'].unstack(fill_value=np.nan)
                market_cap = closes * shares
            else:
                logger.warning("Missing market cap data for S/P calculation")
                return pd.Series(dtype=float)

        # Get revenue
        if 'revenue' not in data.columns:
            logger.warning("Missing revenue data for S/P calculation")
            return pd.Series(dtype=float)

        revenue = data['revenue'].unstack(fill_value=np.nan)

        # Calculate TTM revenue
        revenue_ttm = revenue.rolling(window=4, min_periods=4).sum()

        # Calculate S/P ratio
        sp_ratio = revenue_ttm / market_cap

        result = sp_ratio.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class AssetTurnover(Factor):
    """
    Asset Turnover ratio (value/efficiency hybrid).

    Formula: Revenue (TTM) / Total Assets
    Higher asset turnover = better capital efficiency
    """

    def __init__(self) -> None:
        """Initialize asset turnover factor."""
        metadata = FactorMetadata(
            name="asset_turnover",
            category=FactorCategory.VALUE,
            description="Asset turnover ratio (capital efficiency)",
            formula="TTM Revenue / Total Assets",
            data_requirements=['revenue', 'total_assets'],
            lookback_period=252,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate asset turnover."""
        # Get revenue
        if 'revenue' not in data.columns:
            logger.warning("Missing revenue data for asset turnover calculation")
            return pd.Series(dtype=float)

        revenue = data['revenue'].unstack(fill_value=np.nan)

        # Calculate TTM revenue
        revenue_ttm = revenue.rolling(window=4, min_periods=4).sum()

        # Get total assets
        if 'total_assets' not in data.columns:
            logger.warning("Missing total assets data for asset turnover calculation")
            return pd.Series(dtype=float)

        assets = data['total_assets'].unstack(fill_value=np.nan)

        # Calculate asset turnover
        turnover = revenue_ttm / assets

        result = turnover.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


# Factory function to create all value factors
def create_value_factors() -> List[Factor]:
    """
    Create standard set of value factors.

    Returns:
        List of value factors
    """
    return [
        # Classic value ratios
        PriceToBook(),
        PriceToEarnings(use_forward=False),
        PriceToEarnings(use_forward=True),
        PriceToSales(),
        PriceToCashFlow(use_free_cash_flow=False),
        PriceToCashFlow(use_free_cash_flow=True),

        # Enterprise value ratios
        EVToEBITDA(),
        EVToSales(),

        # Yield factors
        DividendYield(lookback=252),
        EarningsYield(),
        FreeCashFlowYield(),

        # Academic factors
        BookToMarket(),  # Fama-French HML
        SalesToPrice(),

        # Efficiency
        AssetTurnover(),
    ]

"""
Quality factors.

Fundamental quality metrics for identifying financially strong companies.
"""

from typing import Optional, List
import pandas as pd
import numpy as np
from loguru import logger

from src.factors import Factor, FactorMetadata, FactorCategory


class ReturnOnEquity(Factor):
    """
    Return on Equity (ROE) factor.

    Formula: Net Income / Shareholders' Equity
    Higher ROE = better quality
    """

    def __init__(self, lookback: int = 252) -> None:
        """
        Initialize ROE factor.

        Args:
            lookback: Lookback period for TTM calculation
        """
        metadata = FactorMetadata(
            name=f"roe_{lookback}d",
            category=FactorCategory.QUALITY,
            description=f"Return on Equity (TTM, {lookback} days)",
            formula="TTM Net Income / Average Shareholders' Equity",
            data_requirements=['net_income', 'shareholders_equity'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate ROE."""
        # Get net income
        if 'net_income' not in data.columns:
            logger.warning("Missing net income data for ROE calculation")
            return pd.Series(dtype=float)

        net_income = data['net_income'].unstack(fill_value=np.nan)

        # Calculate TTM net income
        net_income_ttm = net_income.rolling(window=4, min_periods=4).sum()

        # Get shareholders' equity
        if 'shareholders_equity' not in data.columns:
            logger.warning("Missing shareholders equity data for ROE calculation")
            return pd.Series(dtype=float)

        equity = data['shareholders_equity'].unstack(fill_value=np.nan)

        # Use average equity over period
        avg_equity = equity.rolling(window=2, min_periods=2).mean()

        # Calculate ROE
        roe = net_income_ttm / avg_equity

        result = roe.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class ReturnOnAssets(Factor):
    """
    Return on Assets (ROA) factor.

    Formula: Net Income / Total Assets
    Higher ROA = better quality
    """

    def __init__(self, lookback: int = 252) -> None:
        """
        Initialize ROA factor.

        Args:
            lookback: Lookback period for TTM calculation
        """
        metadata = FactorMetadata(
            name=f"roa_{lookback}d",
            category=FactorCategory.QUALITY,
            description=f"Return on Assets (TTM, {lookback} days)",
            formula="TTM Net Income / Average Total Assets",
            data_requirements=['net_income', 'total_assets'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate ROA."""
        # Get net income
        if 'net_income' not in data.columns:
            logger.warning("Missing net income data for ROA calculation")
            return pd.Series(dtype=float)

        net_income = data['net_income'].unstack(fill_value=np.nan)

        # Calculate TTM net income
        net_income_ttm = net_income.rolling(window=4, min_periods=4).sum()

        # Get total assets
        if 'total_assets' not in data.columns:
            logger.warning("Missing total assets data for ROA calculation")
            return pd.Series(dtype=float)

        assets = data['total_assets'].unstack(fill_value=np.nan)

        # Use average assets over period
        avg_assets = assets.rolling(window=2, min_periods=2).mean()

        # Calculate ROA
        roa = net_income_ttm / avg_assets

        result = roa.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class ReturnOnInvestedCapital(Factor):
    """
    Return on Invested Capital (ROIC) factor.

    Formula: NOPAT / Invested Capital
    Higher ROIC = better quality
    """

    def __init__(self, lookback: int = 252) -> None:
        """
        Initialize ROIC factor.

        Args:
            lookback: Lookback period for TTM calculation
        """
        metadata = FactorMetadata(
            name=f"roic_{lookback}d",
            category=FactorCategory.QUALITY,
            description=f"Return on Invested Capital (TTM, {lookback} days)",
            formula="NOPAT / (Total Assets - Current Liabilities)",
            data_requirements=['operating_income', 'tax_rate', 'total_assets', 'current_liabilities'],
            lookback_period=lookback,
        )
        super().__init__(metadata)
        self.lookback = lookback

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate ROIC."""
        # Get operating income
        if 'operating_income' not in data.columns:
            logger.warning("Missing operating income data for ROIC calculation")
            return pd.Series(dtype=float)

        operating_income = data['operating_income'].unstack(fill_value=np.nan)

        # Calculate TTM operating income
        operating_income_ttm = operating_income.rolling(window=4, min_periods=4).sum()

        # Calculate NOPAT (Net Operating Profit After Tax)
        if 'tax_rate' in data.columns:
            tax_rate = data['tax_rate'].unstack(fill_value=np.nan)
        else:
            # Assume 21% corporate tax rate if not available
            tax_rate = 0.21

        nopat = operating_income_ttm * (1 - tax_rate)

        # Get total assets and current liabilities
        if 'total_assets' not in data.columns or 'current_liabilities' not in data.columns:
            logger.warning("Missing balance sheet data for ROIC calculation")
            return pd.Series(dtype=float)

        assets = data['total_assets'].unstack(fill_value=np.nan)
        current_liabilities = data['current_liabilities'].unstack(fill_value=np.nan)

        # Calculate invested capital
        invested_capital = assets - current_liabilities

        # Use average invested capital
        avg_invested_capital = invested_capital.rolling(window=2, min_periods=2).mean()

        # Calculate ROIC
        roic = nopat / avg_invested_capital

        result = roic.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class GrossProfitMargin(Factor):
    """
    Gross Profit Margin factor.

    Formula: (Revenue - COGS) / Revenue
    Higher margin = better quality
    """

    def __init__(self) -> None:
        """Initialize gross margin factor."""
        metadata = FactorMetadata(
            name="gross_profit_margin",
            category=FactorCategory.QUALITY,
            description="Gross profit margin (TTM)",
            formula="(TTM Revenue - TTM COGS) / TTM Revenue",
            data_requirements=['revenue', 'cost_of_revenue'],
            lookback_period=252,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate gross profit margin."""
        # Get revenue
        if 'revenue' not in data.columns:
            logger.warning("Missing revenue data for margin calculation")
            return pd.Series(dtype=float)

        revenue = data['revenue'].unstack(fill_value=np.nan)
        revenue_ttm = revenue.rolling(window=4, min_periods=4).sum()

        # Get COGS
        if 'cost_of_revenue' not in data.columns:
            logger.warning("Missing cost of revenue data for margin calculation")
            return pd.Series(dtype=float)

        cogs = data['cost_of_revenue'].unstack(fill_value=np.nan)
        cogs_ttm = cogs.rolling(window=4, min_periods=4).sum()

        # Calculate gross margin
        gross_margin = (revenue_ttm - cogs_ttm) / revenue_ttm

        result = gross_margin.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class OperatingMargin(Factor):
    """
    Operating Profit Margin factor.

    Formula: Operating Income / Revenue
    Higher margin = better quality
    """

    def __init__(self) -> None:
        """Initialize operating margin factor."""
        metadata = FactorMetadata(
            name="operating_margin",
            category=FactorCategory.QUALITY,
            description="Operating profit margin (TTM)",
            formula="TTM Operating Income / TTM Revenue",
            data_requirements=['operating_income', 'revenue'],
            lookback_period=252,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate operating margin."""
        # Get operating income
        if 'operating_income' not in data.columns:
            logger.warning("Missing operating income data for margin calculation")
            return pd.Series(dtype=float)

        operating_income = data['operating_income'].unstack(fill_value=np.nan)
        operating_income_ttm = operating_income.rolling(window=4, min_periods=4).sum()

        # Get revenue
        if 'revenue' not in data.columns:
            logger.warning("Missing revenue data for margin calculation")
            return pd.Series(dtype=float)

        revenue = data['revenue'].unstack(fill_value=np.nan)
        revenue_ttm = revenue.rolling(window=4, min_periods=4).sum()

        # Calculate operating margin
        operating_margin = operating_income_ttm / revenue_ttm

        result = operating_margin.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class NetProfitMargin(Factor):
    """
    Net Profit Margin factor.

    Formula: Net Income / Revenue
    Higher margin = better quality
    """

    def __init__(self) -> None:
        """Initialize net margin factor."""
        metadata = FactorMetadata(
            name="net_profit_margin",
            category=FactorCategory.QUALITY,
            description="Net profit margin (TTM)",
            formula="TTM Net Income / TTM Revenue",
            data_requirements=['net_income', 'revenue'],
            lookback_period=252,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate net profit margin."""
        # Get net income
        if 'net_income' not in data.columns:
            logger.warning("Missing net income data for margin calculation")
            return pd.Series(dtype=float)

        net_income = data['net_income'].unstack(fill_value=np.nan)
        net_income_ttm = net_income.rolling(window=4, min_periods=4).sum()

        # Get revenue
        if 'revenue' not in data.columns:
            logger.warning("Missing revenue data for margin calculation")
            return pd.Series(dtype=float)

        revenue = data['revenue'].unstack(fill_value=np.nan)
        revenue_ttm = revenue.rolling(window=4, min_periods=4).sum()

        # Calculate net margin
        net_margin = net_income_ttm / revenue_ttm

        result = net_margin.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class CurrentRatio(Factor):
    """
    Current Ratio (liquidity) factor.

    Formula: Current Assets / Current Liabilities
    Higher ratio = better liquidity
    """

    def __init__(self) -> None:
        """Initialize current ratio factor."""
        metadata = FactorMetadata(
            name="current_ratio",
            category=FactorCategory.QUALITY,
            description="Current ratio (liquidity measure)",
            formula="Current Assets / Current Liabilities",
            data_requirements=['current_assets', 'current_liabilities'],
            lookback_period=1,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate current ratio."""
        # Get current assets
        if 'current_assets' not in data.columns:
            logger.warning("Missing current assets data for current ratio calculation")
            return pd.Series(dtype=float)

        current_assets = data['current_assets'].unstack(fill_value=np.nan)

        # Get current liabilities
        if 'current_liabilities' not in data.columns:
            logger.warning("Missing current liabilities data for current ratio calculation")
            return pd.Series(dtype=float)

        current_liabilities = data['current_liabilities'].unstack(fill_value=np.nan)

        # Calculate current ratio
        current_ratio = current_assets / current_liabilities

        result = current_ratio.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class QuickRatio(Factor):
    """
    Quick Ratio (acid test) factor.

    Formula: (Current Assets - Inventory) / Current Liabilities
    Higher ratio = better liquidity
    """

    def __init__(self) -> None:
        """Initialize quick ratio factor."""
        metadata = FactorMetadata(
            name="quick_ratio",
            category=FactorCategory.QUALITY,
            description="Quick ratio (acid test for liquidity)",
            formula="(Current Assets - Inventory) / Current Liabilities",
            data_requirements=['current_assets', 'inventory', 'current_liabilities'],
            lookback_period=1,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate quick ratio."""
        # Get current assets
        if 'current_assets' not in data.columns:
            logger.warning("Missing current assets data for quick ratio calculation")
            return pd.Series(dtype=float)

        current_assets = data['current_assets'].unstack(fill_value=np.nan)

        # Get inventory
        if 'inventory' not in data.columns:
            logger.warning("Missing inventory data for quick ratio calculation")
            return pd.Series(dtype=float)

        inventory = data['inventory'].unstack(fill_value=np.nan)

        # Get current liabilities
        if 'current_liabilities' not in data.columns:
            logger.warning("Missing current liabilities data for quick ratio calculation")
            return pd.Series(dtype=float)

        current_liabilities = data['current_liabilities'].unstack(fill_value=np.nan)

        # Calculate quick ratio
        quick_ratio = (current_assets - inventory) / current_liabilities

        result = quick_ratio.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class DebtToEquity(Factor):
    """
    Debt-to-Equity ratio factor.

    Formula: Total Debt / Shareholders' Equity
    Lower ratio = better quality (less leverage)
    """

    def __init__(self) -> None:
        """Initialize D/E ratio factor."""
        metadata = FactorMetadata(
            name="debt_to_equity",
            category=FactorCategory.QUALITY,
            description="Debt-to-Equity ratio (inverted for quality signal)",
            formula="-1 * (Total Debt / Shareholders' Equity)",
            data_requirements=['total_debt', 'shareholders_equity'],
            lookback_period=1,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate inverted D/E ratio."""
        # Get total debt
        if 'total_debt' not in data.columns:
            logger.warning("Missing total debt data for D/E calculation")
            return pd.Series(dtype=float)

        debt = data['total_debt'].unstack(fill_value=np.nan)

        # Get shareholders' equity
        if 'shareholders_equity' not in data.columns:
            logger.warning("Missing shareholders equity data for D/E calculation")
            return pd.Series(dtype=float)

        equity = data['shareholders_equity'].unstack(fill_value=np.nan)

        # Calculate D/E ratio and invert (lower debt = higher quality)
        de_ratio = -(debt / equity)

        result = de_ratio.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class InterestCoverage(Factor):
    """
    Interest Coverage ratio factor.

    Formula: EBIT / Interest Expense
    Higher coverage = better quality
    """

    def __init__(self) -> None:
        """Initialize interest coverage factor."""
        metadata = FactorMetadata(
            name="interest_coverage",
            category=FactorCategory.QUALITY,
            description="Interest coverage ratio (EBIT / Interest Expense)",
            formula="TTM EBIT / TTM Interest Expense",
            data_requirements=['ebit', 'interest_expense'],
            lookback_period=252,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate interest coverage."""
        # Get EBIT
        if 'ebit' not in data.columns:
            logger.warning("Missing EBIT data for interest coverage calculation")
            return pd.Series(dtype=float)

        ebit = data['ebit'].unstack(fill_value=np.nan)
        ebit_ttm = ebit.rolling(window=4, min_periods=4).sum()

        # Get interest expense
        if 'interest_expense' not in data.columns:
            logger.warning("Missing interest expense data for interest coverage calculation")
            return pd.Series(dtype=float)

        interest = data['interest_expense'].unstack(fill_value=np.nan)
        interest_ttm = interest.rolling(window=4, min_periods=4).sum()

        # Calculate interest coverage
        coverage = ebit_ttm / interest_ttm

        result = coverage.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class AccrualsRatio(Factor):
    """
    Accruals Ratio (earnings quality) factor.

    Formula: (Net Income - Operating Cash Flow) / Total Assets
    Lower accruals = better earnings quality
    """

    def __init__(self) -> None:
        """Initialize accruals ratio factor."""
        metadata = FactorMetadata(
            name="accruals_ratio",
            category=FactorCategory.QUALITY,
            description="Accruals ratio (inverted for quality signal)",
            formula="-1 * (Net Income - OCF) / Total Assets",
            data_requirements=['net_income', 'operating_cash_flow', 'total_assets'],
            lookback_period=252,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate inverted accruals ratio."""
        # Get net income
        if 'net_income' not in data.columns:
            logger.warning("Missing net income data for accruals calculation")
            return pd.Series(dtype=float)

        net_income = data['net_income'].unstack(fill_value=np.nan)
        net_income_ttm = net_income.rolling(window=4, min_periods=4).sum()

        # Get operating cash flow
        if 'operating_cash_flow' not in data.columns:
            logger.warning("Missing operating cash flow data for accruals calculation")
            return pd.Series(dtype=float)

        ocf = data['operating_cash_flow'].unstack(fill_value=np.nan)
        ocf_ttm = ocf.rolling(window=4, min_periods=4).sum()

        # Get total assets
        if 'total_assets' not in data.columns:
            logger.warning("Missing total assets data for accruals calculation")
            return pd.Series(dtype=float)

        assets = data['total_assets'].unstack(fill_value=np.nan)

        # Calculate accruals and invert (lower accruals = higher quality)
        accruals = -((net_income_ttm - ocf_ttm) / assets)

        result = accruals.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class AssetQuality(Factor):
    """
    Asset Quality factor.

    Formula: (Cash + Receivables + Inventory) / Total Assets
    Higher ratio = better asset quality
    """

    def __init__(self) -> None:
        """Initialize asset quality factor."""
        metadata = FactorMetadata(
            name="asset_quality",
            category=FactorCategory.QUALITY,
            description="Asset quality (proportion of liquid assets)",
            formula="(Cash + Receivables + Inventory) / Total Assets",
            data_requirements=['cash', 'receivables', 'inventory', 'total_assets'],
            lookback_period=1,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate asset quality."""
        # Get components
        if 'cash' not in data.columns:
            logger.warning("Missing cash data for asset quality calculation")
            return pd.Series(dtype=float)

        cash = data['cash'].unstack(fill_value=np.nan)

        # Receivables (optional)
        if 'receivables' in data.columns:
            receivables = data['receivables'].unstack(fill_value=np.nan)
        else:
            receivables = 0

        # Inventory (optional)
        if 'inventory' in data.columns:
            inventory = data['inventory'].unstack(fill_value=np.nan)
        else:
            inventory = 0

        # Get total assets
        if 'total_assets' not in data.columns:
            logger.warning("Missing total assets data for asset quality calculation")
            return pd.Series(dtype=float)

        assets = data['total_assets'].unstack(fill_value=np.nan)

        # Calculate asset quality
        quality = (cash + receivables + inventory) / assets

        result = quality.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


class PiotroskiFScore(Factor):
    """
    Piotroski F-Score (composite quality factor).

    Nine-point score based on:
    - Profitability (4 points)
    - Leverage/Liquidity (3 points)
    - Operating Efficiency (2 points)

    Higher score = better quality
    """

    def __init__(self) -> None:
        """Initialize Piotroski F-Score factor."""
        metadata = FactorMetadata(
            name="piotroski_fscore",
            category=FactorCategory.QUALITY,
            description="Piotroski F-Score (9-point quality composite)",
            formula="Sum of 9 binary signals",
            data_requirements=[
                'net_income', 'operating_cash_flow', 'roa', 'total_debt',
                'current_ratio', 'shares_outstanding', 'gross_margin', 'asset_turnover'
            ],
            lookback_period=252,
        )
        super().__init__(metadata)

    def calculate(
        self,
        data: pd.DataFrame,
        universe: Optional[List[str]] = None
    ) -> pd.Series:
        """Calculate Piotroski F-Score."""
        score = pd.DataFrame(0, index=data.index, columns=data['close'].unstack().columns)

        # Profitability signals
        # 1. Positive net income
        if 'net_income' in data.columns:
            net_income = data['net_income'].unstack(fill_value=np.nan)
            score += (net_income > 0).astype(int)

        # 2. Positive operating cash flow
        if 'operating_cash_flow' in data.columns:
            ocf = data['operating_cash_flow'].unstack(fill_value=np.nan)
            score += (ocf > 0).astype(int)

        # 3. Increasing ROA
        if 'roa' in data.columns:
            roa = data['roa'].unstack(fill_value=np.nan)
            roa_change = roa.diff(periods=4)  # YoY change
            score += (roa_change > 0).astype(int)

        # 4. Cash flow > Net income (quality of earnings)
        if 'operating_cash_flow' in data.columns and 'net_income' in data.columns:
            score += (ocf > net_income).astype(int)

        # Leverage/Liquidity signals
        # 5. Decreasing debt
        if 'total_debt' in data.columns:
            debt = data['total_debt'].unstack(fill_value=np.nan)
            debt_change = debt.diff(periods=4)
            score += (debt_change < 0).astype(int)

        # 6. Increasing current ratio
        if 'current_ratio' in data.columns:
            current_ratio = data['current_ratio'].unstack(fill_value=np.nan)
            cr_change = current_ratio.diff(periods=4)
            score += (cr_change > 0).astype(int)

        # 7. No new shares issued
        if 'shares_outstanding' in data.columns:
            shares = data['shares_outstanding'].unstack(fill_value=np.nan)
            shares_change = shares.diff(periods=4)
            score += (shares_change <= 0).astype(int)

        # Operating Efficiency signals
        # 8. Increasing gross margin
        if 'gross_margin' in data.columns:
            margin = data['gross_margin'].unstack(fill_value=np.nan)
            margin_change = margin.diff(periods=4)
            score += (margin_change > 0).astype(int)

        # 9. Increasing asset turnover
        if 'asset_turnover' in data.columns:
            turnover = data['asset_turnover'].unstack(fill_value=np.nan)
            turnover_change = turnover.diff(periods=4)
            score += (turnover_change > 0).astype(int)

        result = score.stack()

        if universe:
            result = result[result.index.get_level_values(1).isin(universe)]

        return result.replace([np.inf, -np.inf], np.nan).fillna(0)


# Factory function to create all quality factors
def create_quality_factors() -> List[Factor]:
    """
    Create standard set of quality factors.

    Returns:
        List of quality factors
    """
    return [
        # Profitability
        ReturnOnEquity(lookback=252),
        ReturnOnAssets(lookback=252),
        ReturnOnInvestedCapital(lookback=252),

        # Margins
        GrossProfitMargin(),
        OperatingMargin(),
        NetProfitMargin(),

        # Liquidity
        CurrentRatio(),
        QuickRatio(),

        # Leverage
        DebtToEquity(),
        InterestCoverage(),

        # Earnings quality
        AccrualsRatio(),
        AssetQuality(),

        # Composite
        PiotroskiFScore(),
    ]


# Aliases for backward compatibility and convenience
ROE = ReturnOnEquity
ROA = ReturnOnAssets
ROIC = ReturnOnInvestedCapital
GrossMargin = GrossProfitMargin
NetMargin = NetProfitMargin

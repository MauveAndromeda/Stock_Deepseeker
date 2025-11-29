"""
Yahoo Finance data provider implementation.

Provides access to Yahoo Finance data with proper error handling.
"""

from datetime import datetime
from typing import Any

from loguru import logger
import pandas as pd
import yfinance as yf

from src.data.providers.base import (
    CorporateAction,
    DataFetchError,
    DataProvider,
    DataProviderType,
    FundamentalData,
    PriceData,
)


class YahooFinanceProvider(DataProvider):
    """Yahoo Finance data provider."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize Yahoo Finance provider."""
        super().__init__(api_key=None, **kwargs)  # Yahoo doesn't need API key
        self.provider_type = DataProviderType.YAHOO_FINANCE

    def get_historical_prices(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        adjusted: bool = True,
        **kwargs: Any
    ) -> PriceData:
        """
        Fetch historical price data from Yahoo Finance.

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            adjusted: Whether to use adjusted prices
            **kwargs: Additional parameters

        Returns:
            PriceData object

        Raises:
            DataFetchError: If fetching fails
            DataValidationError: If validation fails
        """
        try:
            ticker = yf.Ticker(symbol)

            # Fetch data
            df = ticker.history(
                start=start_date,
                end=end_date,
                auto_adjust=adjusted,
                actions=True,
            )

            if df.empty:
                raise DataFetchError(f"No data available for {symbol}")

            # Normalize column names
            df.columns = df.columns.str.lower()

            # Ensure timezone-naive index
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            return PriceData(
                symbol=symbol,
                data=df,
                start_date=df.index[0].to_pydatetime(),
                end_date=df.index[-1].to_pydatetime(),
                adjusted=adjusted,
                provider=self.provider_type,
                metadata={
                    "source": "yahoo_finance",
                    "interval": kwargs.get("interval", "1d"),
                }
            )

        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
            raise DataFetchError(f"Yahoo Finance fetch failed: {e}") from e

    def get_fundamentals(
        self,
        symbol: str,
        report_date: datetime | None = None,
        **kwargs: Any
    ) -> FundamentalData:
        """
        Fetch fundamental data from Yahoo Finance.

        Args:
            symbol: Stock symbol
            report_date: Specific report date (None for latest)
            **kwargs: Additional parameters

        Returns:
            FundamentalData object

        Raises:
            DataFetchError: If fetching fails
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Extract key fundamental metrics
            fundamentals = {
                # Valuation
                "market_cap": info.get("marketCap"),
                "enterprise_value": info.get("enterpriseValue"),
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "peg_ratio": info.get("pegRatio"),
                "price_to_book": info.get("priceToBook"),
                "price_to_sales": info.get("priceToSalesTrailing12Months"),
                "ev_to_revenue": info.get("enterpriseToRevenue"),
                "ev_to_ebitda": info.get("enterpriseToEbitda"),

                # Profitability
                "profit_margin": info.get("profitMargins"),
                "operating_margin": info.get("operatingMargins"),
                "gross_margin": info.get("grossMargins"),
                "roe": info.get("returnOnEquity"),
                "roa": info.get("returnOnAssets"),
                "roic": info.get("returnOnCapital"),

                # Financial Health
                "debt_to_equity": info.get("debtToEquity"),
                "current_ratio": info.get("currentRatio"),
                "quick_ratio": info.get("quickRatio"),
                "total_cash": info.get("totalCash"),
                "total_debt": info.get("totalDebt"),
                "free_cash_flow": info.get("freeCashflow"),

                # Growth
                "revenue_growth": info.get("revenueGrowth"),
                "earnings_growth": info.get("earningsGrowth"),
                "revenue_per_share": info.get("revenuePerShare"),
                "eps": info.get("trailingEps"),
                "forward_eps": info.get("forwardEps"),

                # Dividends
                "dividend_rate": info.get("dividendRate"),
                "dividend_yield": info.get("dividendYield"),
                "payout_ratio": info.get("payoutRatio"),

                # Other
                "shares_outstanding": info.get("sharesOutstanding"),
                "float_shares": info.get("floatShares"),
                "beta": info.get("beta"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),

                # Company info
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "country": info.get("country"),
            }

            # Remove None values
            fundamentals = {k: v for k, v in fundamentals.items() if v is not None}

            # Use current date as report date if not specified
            if report_date is None:
                report_date = datetime.now()

            return FundamentalData(
                symbol=symbol,
                data=fundamentals,
                report_date=report_date,
                period_type="quarterly",  # Yahoo provides latest available
                provider=self.provider_type,
            )

        except Exception as e:
            logger.error(f"Failed to fetch fundamentals for {symbol}: {e}")
            raise DataFetchError(f"Yahoo Finance fundamentals fetch failed: {e}") from e

    def get_corporate_actions(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any
    ) -> list[CorporateAction]:
        """
        Fetch corporate actions from Yahoo Finance.

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            **kwargs: Additional parameters

        Returns:
            List of CorporateAction objects

        Raises:
            DataFetchError: If fetching fails
        """
        try:
            ticker = yf.Ticker(symbol)

            # Fetch actions (dividends and splits)
            actions = ticker.actions

            if actions.empty:
                return []

            # Filter by date range
            actions = actions[(actions.index >= start_date) & (actions.index <= end_date)]

            corporate_actions = []

            # Process dividends
            if "Dividends" in actions.columns:
                dividends = actions[actions["Dividends"] > 0]["Dividends"]
                for date, value in dividends.items():
                    corporate_actions.append(CorporateAction(
                        symbol=symbol,
                        action_type="dividend",
                        ex_date=date.to_pydatetime(),
                        value=float(value),
                        currency="USD",
                        metadata={"source": "yahoo_finance"}
                    ))

            # Process splits
            if "Stock Splits" in actions.columns:
                splits = actions[actions["Stock Splits"] > 0]["Stock Splits"]
                for date, value in splits.items():
                    corporate_actions.append(CorporateAction(
                        symbol=symbol,
                        action_type="split",
                        ex_date=date.to_pydatetime(),
                        value=float(value),
                        metadata={"source": "yahoo_finance"}
                    ))

            return sorted(corporate_actions, key=lambda x: x.ex_date)

        except Exception as e:
            logger.error(f"Failed to fetch corporate actions for {symbol}: {e}")
            raise DataFetchError(f"Yahoo Finance actions fetch failed: {e}") from e

    def search_symbols(
        self,
        query: str,
        limit: int = 10,
        **kwargs: Any
    ) -> list[dict[str, Any]]:
        """
        Search for symbols using Yahoo Finance.

        Note: Yahoo Finance doesn't have a direct search API,
        so this is a simplified implementation.

        Args:
            query: Search query
            limit: Maximum results
            **kwargs: Additional parameters

        Returns:
            List of symbol information dicts

        Raises:
            DataFetchError: If search fails
        """
        try:
            # This is a simplified implementation
            # In production, you might want to use yfinance's search
            # or maintain a symbol database

            results = []

            # Try to fetch info for the query as a direct symbol
            try:
                ticker = yf.Ticker(query.upper())
                info = ticker.info

                if info.get("symbol"):
                    results.append({
                        "symbol": info.get("symbol"),
                        "name": info.get("longName", ""),
                        "exchange": info.get("exchange", ""),
                        "type": info.get("quoteType", ""),
                        "sector": info.get("sector", ""),
                        "industry": info.get("industry", ""),
                    })
            except (KeyError, TypeError, AttributeError):
                pass

            return results[:limit]

        except Exception as e:
            logger.error(f"Failed to search symbols for query '{query}': {e}")
            raise DataFetchError(f"Yahoo Finance search failed: {e}") from e

    def is_available(self) -> bool:
        """
        Check if Yahoo Finance is available.

        Returns:
            True if provider is operational
        """
        try:
            # Try to fetch a simple quote
            ticker = yf.Ticker("SPY")
            info = ticker.info
            return bool(info.get("symbol"))
        except (OSError, ConnectionError, TimeoutError, KeyError):
            return False

    def get_option_chain(
        self,
        symbol: str,
        expiration: datetime | None = None
    ) -> dict[str, pd.DataFrame]:
        """
        Get option chain data.

        Args:
            symbol: Stock symbol
            expiration: Expiration date (None for nearest)

        Returns:
            Dict with 'calls' and 'puts' DataFrames

        Raises:
            DataFetchError: If fetching fails
        """
        try:
            ticker = yf.Ticker(symbol)

            if expiration is None:
                # Get nearest expiration
                expirations = ticker.options
                if not expirations:
                    raise DataFetchError(f"No options available for {symbol}")
                expiration_str = expirations[0]
            else:
                expiration_str = expiration.strftime("%Y-%m-%d")

            opt = ticker.option_chain(expiration_str)

            return {
                "calls": opt.calls,
                "puts": opt.puts,
                "expiration": expiration_str,
            }

        except Exception as e:
            logger.error(f"Failed to fetch option chain for {symbol}: {e}")
            raise DataFetchError(f"Yahoo Finance options fetch failed: {e}") from e

    def get_earnings_calendar(
        self,
        symbol: str
    ) -> pd.DataFrame:
        """
        Get earnings calendar.

        Args:
            symbol: Stock symbol

        Returns:
            DataFrame with earnings dates and estimates

        Raises:
            DataFetchError: If fetching fails
        """
        try:
            ticker = yf.Ticker(symbol)
            calendar = ticker.calendar

            if calendar is None or len(calendar) == 0:
                raise DataFetchError(f"No earnings calendar for {symbol}")

            return calendar

        except Exception as e:
            logger.error(f"Failed to fetch earnings calendar for {symbol}: {e}")
            raise DataFetchError(f"Yahoo Finance calendar fetch failed: {e}") from e

    def get_recommendations(
        self,
        symbol: str
    ) -> pd.DataFrame:
        """
        Get analyst recommendations.

        Args:
            symbol: Stock symbol

        Returns:
            DataFrame with analyst recommendations

        Raises:
            DataFetchError: If fetching fails
        """
        try:
            ticker = yf.Ticker(symbol)
            recommendations = ticker.recommendations

            if recommendations is None or len(recommendations) == 0:
                raise DataFetchError(f"No recommendations for {symbol}")

            return recommendations

        except Exception as e:
            logger.error(f"Failed to fetch recommendations for {symbol}: {e}")
            raise DataFetchError(f"Yahoo Finance recommendations fetch failed: {e}") from e

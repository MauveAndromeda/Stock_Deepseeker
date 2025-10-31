"""
Technical Indicators Module

This module provides a comprehensive collection of technical indicators for stock analysis,
including trend, momentum, volatility, volume, and support/resistance indicators.

Author: Stock Deepseeker Team
Date: 2025-10-30
"""

import logging
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """
    A comprehensive class for calculating technical indicators on OHLCV stock data.

    This class provides methods for calculating various categories of technical indicators:
    - Trend indicators (SMA, EMA, MACD, ADX, Parabolic SAR)
    - Momentum indicators (RSI, Stochastic, Williams %R, ROC, CCI)
    - Volatility indicators (Bollinger Bands, ATR, Keltner Channels, Std Dev)
    - Volume indicators (OBV, CMF, MFI, VWAP, Volume Profile)
    - Support/Resistance (Pivot Points, Fibonacci levels, Price channels)

    All methods accept pandas DataFrames with OHLCV data and return DataFrames
    with indicator values added as new columns.
    """

    def __init__(self, validate_data: bool = True):
        """
        Initialize the TechnicalIndicators class.

        Args:
            validate_data: Whether to validate input data (default: True)
        """
        self.validate_data = validate_data
        logger.info("TechnicalIndicators initialized")

    def _validate_dataframe(self, df: pd.DataFrame, required_columns: List[str]) -> None:
        """
        Validate that the DataFrame contains required columns.

        Args:
            df: Input DataFrame
            required_columns: List of required column names

        Raises:
            ValueError: If required columns are missing
        """
        if not self.validate_data:
            return

        if df is None or df.empty:
            raise ValueError("DataFrame is None or empty")

        missing_columns = set(required_columns) - set(df.columns)
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

    def _handle_nan(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Handle NaN values in DataFrame.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with NaN values handled
        """
        return df.copy()

    # =====================================================================
    # TREND INDICATORS
    # =====================================================================

    def calculate_sma(
        self,
        df: pd.DataFrame,
        column: str = 'close',
        periods: List[int] = [20, 50, 200]
    ) -> pd.DataFrame:
        """
        Calculate Simple Moving Average (SMA).

        SMA is the unweighted mean of the previous n data points.

        Args:
            df: DataFrame with OHLCV data
            column: Column name to calculate SMA on (default: 'close')
            periods: List of periods for SMA calculation (default: [20, 50, 200])

        Returns:
            DataFrame with SMA columns added

        Example:
            >>> indicators = TechnicalIndicators()
            >>> df_with_sma = indicators.calculate_sma(df, periods=[20, 50])
        """
        try:
            self._validate_dataframe(df, [column])
            df_result = df.copy()

            for period in periods:
                col_name = f'sma_{period}'
                df_result[col_name] = df_result[column].rolling(window=period).mean()
                logger.debug(f"Calculated {col_name}")

            return df_result

        except Exception as e:
            logger.error(f"Error calculating SMA: {str(e)}")
            raise

    def calculate_ema(
        self,
        df: pd.DataFrame,
        column: str = 'close',
        periods: List[int] = [12, 26, 50]
    ) -> pd.DataFrame:
        """
        Calculate Exponential Moving Average (EMA).

        EMA gives more weight to recent prices, making it more responsive to new information.

        Args:
            df: DataFrame with OHLCV data
            column: Column name to calculate EMA on (default: 'close')
            periods: List of periods for EMA calculation (default: [12, 26, 50])

        Returns:
            DataFrame with EMA columns added
        """
        try:
            self._validate_dataframe(df, [column])
            df_result = df.copy()

            for period in periods:
                col_name = f'ema_{period}'
                df_result[col_name] = df_result[column].ewm(span=period, adjust=False).mean()
                logger.debug(f"Calculated {col_name}")

            return df_result

        except Exception as e:
            logger.error(f"Error calculating EMA: {str(e)}")
            raise

    def calculate_macd(
        self,
        df: pd.DataFrame,
        column: str = 'close',
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> pd.DataFrame:
        """
        Calculate Moving Average Convergence Divergence (MACD).

        MACD shows the relationship between two moving averages of a security's price.

        Args:
            df: DataFrame with OHLCV data
            column: Column name to calculate MACD on (default: 'close')
            fast_period: Fast EMA period (default: 12)
            slow_period: Slow EMA period (default: 26)
            signal_period: Signal line period (default: 9)

        Returns:
            DataFrame with MACD, signal line, and histogram columns added
        """
        try:
            self._validate_dataframe(df, [column])
            df_result = df.copy()

            # Calculate MACD line
            ema_fast = df_result[column].ewm(span=fast_period, adjust=False).mean()
            ema_slow = df_result[column].ewm(span=slow_period, adjust=False).mean()
            df_result['macd'] = ema_fast - ema_slow

            # Calculate signal line
            df_result['macd_signal'] = df_result['macd'].ewm(span=signal_period, adjust=False).mean()

            # Calculate histogram
            df_result['macd_histogram'] = df_result['macd'] - df_result['macd_signal']

            logger.debug("Calculated MACD")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating MACD: {str(e)}")
            raise

    def calculate_adx(
        self,
        df: pd.DataFrame,
        period: int = 14
    ) -> pd.DataFrame:
        """
        Calculate Average Directional Index (ADX).

        ADX measures the strength of a trend, regardless of direction.
        Values above 25 indicate a strong trend.

        Args:
            df: DataFrame with OHLCV data (requires high, low, close)
            period: Lookback period (default: 14)

        Returns:
            DataFrame with ADX, +DI, and -DI columns added
        """
        try:
            self._validate_dataframe(df, ['high', 'low', 'close'])
            df_result = df.copy()

            # Calculate True Range
            df_result['tr1'] = df_result['high'] - df_result['low']
            df_result['tr2'] = abs(df_result['high'] - df_result['close'].shift())
            df_result['tr3'] = abs(df_result['low'] - df_result['close'].shift())
            df_result['tr'] = df_result[['tr1', 'tr2', 'tr3']].max(axis=1)

            # Calculate directional movements
            df_result['dm_plus'] = np.where(
                (df_result['high'] - df_result['high'].shift()) > (df_result['low'].shift() - df_result['low']),
                np.maximum(df_result['high'] - df_result['high'].shift(), 0),
                0
            )
            df_result['dm_minus'] = np.where(
                (df_result['low'].shift() - df_result['low']) > (df_result['high'] - df_result['high'].shift()),
                np.maximum(df_result['low'].shift() - df_result['low'], 0),
                0
            )

            # Calculate smoothed TR and DM
            atr = df_result['tr'].rolling(window=period).mean()
            dm_plus_smooth = df_result['dm_plus'].rolling(window=period).mean()
            dm_minus_smooth = df_result['dm_minus'].rolling(window=period).mean()

            # Calculate directional indicators
            df_result['di_plus'] = 100 * (dm_plus_smooth / atr)
            df_result['di_minus'] = 100 * (dm_minus_smooth / atr)

            # Calculate DX and ADX
            df_result['dx'] = 100 * abs(df_result['di_plus'] - df_result['di_minus']) / (df_result['di_plus'] + df_result['di_minus'])
            df_result['adx'] = df_result['dx'].rolling(window=period).mean()

            # Clean up temporary columns
            df_result.drop(['tr1', 'tr2', 'tr3', 'tr', 'dm_plus', 'dm_minus', 'dx'], axis=1, inplace=True)

            logger.debug("Calculated ADX")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating ADX: {str(e)}")
            raise

    def calculate_parabolic_sar(
        self,
        df: pd.DataFrame,
        af_start: float = 0.02,
        af_increment: float = 0.02,
        af_max: float = 0.20
    ) -> pd.DataFrame:
        """
        Calculate Parabolic SAR (Stop and Reverse).

        Parabolic SAR provides potential entry and exit points.

        Args:
            df: DataFrame with OHLCV data (requires high, low)
            af_start: Initial acceleration factor (default: 0.02)
            af_increment: Acceleration factor increment (default: 0.02)
            af_max: Maximum acceleration factor (default: 0.20)

        Returns:
            DataFrame with PSAR column added
        """
        try:
            self._validate_dataframe(df, ['high', 'low', 'close'])
            df_result = df.copy()

            length = len(df_result)
            psar = np.zeros(length)
            psarbull = [None] * length
            psarbear = [None] * length
            bull = True
            af = af_start
            hp = df_result['high'].iloc[0]
            lp = df_result['low'].iloc[0]

            for i in range(1, length):
                if bull:
                    psar[i] = psar[i - 1] + af * (hp - psar[i - 1])
                else:
                    psar[i] = psar[i - 1] + af * (lp - psar[i - 1])

                reverse = False

                if bull:
                    if df_result['low'].iloc[i] < psar[i]:
                        bull = False
                        reverse = True
                        psar[i] = hp
                        lp = df_result['low'].iloc[i]
                        af = af_start
                else:
                    if df_result['high'].iloc[i] > psar[i]:
                        bull = True
                        reverse = True
                        psar[i] = lp
                        hp = df_result['high'].iloc[i]
                        af = af_start

                if not reverse:
                    if bull:
                        if df_result['high'].iloc[i] > hp:
                            hp = df_result['high'].iloc[i]
                            af = min(af + af_increment, af_max)
                        if df_result['low'].iloc[i - 1] < psar[i]:
                            psar[i] = df_result['low'].iloc[i - 1]
                        if df_result['low'].iloc[i - 2] < psar[i]:
                            psar[i] = df_result['low'].iloc[i - 2]
                    else:
                        if df_result['low'].iloc[i] < lp:
                            lp = df_result['low'].iloc[i]
                            af = min(af + af_increment, af_max)
                        if df_result['high'].iloc[i - 1] > psar[i]:
                            psar[i] = df_result['high'].iloc[i - 1]
                        if df_result['high'].iloc[i - 2] > psar[i]:
                            psar[i] = df_result['high'].iloc[i - 2]

                if bull:
                    psarbull[i] = psar[i]
                else:
                    psarbear[i] = psar[i]

            df_result['psar'] = psar
            df_result['psar_bull'] = psarbull
            df_result['psar_bear'] = psarbear

            logger.debug("Calculated Parabolic SAR")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating Parabolic SAR: {str(e)}")
            raise

    # =====================================================================
    # MOMENTUM INDICATORS
    # =====================================================================

    def calculate_rsi(
        self,
        df: pd.DataFrame,
        column: str = 'close',
        period: int = 14
    ) -> pd.DataFrame:
        """
        Calculate Relative Strength Index (RSI).

        RSI measures the magnitude of recent price changes to evaluate
        overbought or oversold conditions. Values above 70 indicate overbought,
        below 30 indicate oversold.

        Args:
            df: DataFrame with OHLCV data
            column: Column name to calculate RSI on (default: 'close')
            period: Lookback period (default: 14)

        Returns:
            DataFrame with RSI column added
        """
        try:
            self._validate_dataframe(df, [column])
            df_result = df.copy()

            # Calculate price changes
            delta = df_result[column].diff()

            # Separate gains and losses
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)

            # Calculate average gain and loss
            avg_gain = gain.rolling(window=period).mean()
            avg_loss = loss.rolling(window=period).mean()

            # Calculate RS and RSI
            rs = avg_gain / avg_loss
            df_result['rsi'] = 100 - (100 / (1 + rs))

            logger.debug("Calculated RSI")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating RSI: {str(e)}")
            raise

    def calculate_stochastic(
        self,
        df: pd.DataFrame,
        k_period: int = 14,
        d_period: int = 3,
        smooth_k: int = 3
    ) -> pd.DataFrame:
        """
        Calculate Stochastic Oscillator.

        Stochastic oscillator compares a closing price to its price range over a period.

        Args:
            df: DataFrame with OHLCV data (requires high, low, close)
            k_period: %K period (default: 14)
            d_period: %D period (default: 3)
            smooth_k: Smoothing period for %K (default: 3)

        Returns:
            DataFrame with %K and %D columns added
        """
        try:
            self._validate_dataframe(df, ['high', 'low', 'close'])
            df_result = df.copy()

            # Calculate %K
            low_min = df_result['low'].rolling(window=k_period).min()
            high_max = df_result['high'].rolling(window=k_period).max()

            df_result['stoch_k'] = 100 * (df_result['close'] - low_min) / (high_max - low_min)

            # Smooth %K if needed
            if smooth_k > 1:
                df_result['stoch_k'] = df_result['stoch_k'].rolling(window=smooth_k).mean()

            # Calculate %D (moving average of %K)
            df_result['stoch_d'] = df_result['stoch_k'].rolling(window=d_period).mean()

            logger.debug("Calculated Stochastic Oscillator")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating Stochastic: {str(e)}")
            raise

    def calculate_williams_r(
        self,
        df: pd.DataFrame,
        period: int = 14
    ) -> pd.DataFrame:
        """
        Calculate Williams %R.

        Williams %R is a momentum indicator that measures overbought/oversold levels.
        Values between -80 and -100 indicate oversold, -0 to -20 indicate overbought.

        Args:
            df: DataFrame with OHLCV data (requires high, low, close)
            period: Lookback period (default: 14)

        Returns:
            DataFrame with Williams %R column added
        """
        try:
            self._validate_dataframe(df, ['high', 'low', 'close'])
            df_result = df.copy()

            high_max = df_result['high'].rolling(window=period).max()
            low_min = df_result['low'].rolling(window=period).min()

            df_result['williams_r'] = -100 * (high_max - df_result['close']) / (high_max - low_min)

            logger.debug("Calculated Williams %R")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating Williams %R: {str(e)}")
            raise

    def calculate_roc(
        self,
        df: pd.DataFrame,
        column: str = 'close',
        period: int = 12
    ) -> pd.DataFrame:
        """
        Calculate Rate of Change (ROC).

        ROC measures the percentage change in price from one period to another.

        Args:
            df: DataFrame with OHLCV data
            column: Column name to calculate ROC on (default: 'close')
            period: Lookback period (default: 12)

        Returns:
            DataFrame with ROC column added
        """
        try:
            self._validate_dataframe(df, [column])
            df_result = df.copy()

            df_result['roc'] = ((df_result[column] - df_result[column].shift(period)) /
                                df_result[column].shift(period)) * 100

            logger.debug("Calculated ROC")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating ROC: {str(e)}")
            raise

    def calculate_cci(
        self,
        df: pd.DataFrame,
        period: int = 20,
        constant: float = 0.015
    ) -> pd.DataFrame:
        """
        Calculate Commodity Channel Index (CCI).

        CCI measures the current price level relative to an average price level.
        Values above +100 indicate overbought, below -100 indicate oversold.

        Args:
            df: DataFrame with OHLCV data (requires high, low, close)
            period: Lookback period (default: 20)
            constant: Scaling constant (default: 0.015)

        Returns:
            DataFrame with CCI column added
        """
        try:
            self._validate_dataframe(df, ['high', 'low', 'close'])
            df_result = df.copy()

            # Calculate typical price
            tp = (df_result['high'] + df_result['low'] + df_result['close']) / 3

            # Calculate SMA of typical price
            sma_tp = tp.rolling(window=period).mean()

            # Calculate mean absolute deviation
            mad = tp.rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean())

            # Calculate CCI
            df_result['cci'] = (tp - sma_tp) / (constant * mad)

            logger.debug("Calculated CCI")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating CCI: {str(e)}")
            raise

    # =====================================================================
    # VOLATILITY INDICATORS
    # =====================================================================

    def calculate_bollinger_bands(
        self,
        df: pd.DataFrame,
        column: str = 'close',
        period: int = 20,
        std_dev: float = 2.0
    ) -> pd.DataFrame:
        """
        Calculate Bollinger Bands.

        Bollinger Bands consist of a middle band (SMA) and two outer bands
        that are standard deviations away from the middle band.

        Args:
            df: DataFrame with OHLCV data
            column: Column name to calculate on (default: 'close')
            period: Period for middle band SMA (default: 20)
            std_dev: Number of standard deviations (default: 2.0)

        Returns:
            DataFrame with BB upper, middle, and lower bands added
        """
        try:
            self._validate_dataframe(df, [column])
            df_result = df.copy()

            # Calculate middle band (SMA)
            df_result['bb_middle'] = df_result[column].rolling(window=period).mean()

            # Calculate standard deviation
            rolling_std = df_result[column].rolling(window=period).std()

            # Calculate upper and lower bands
            df_result['bb_upper'] = df_result['bb_middle'] + (rolling_std * std_dev)
            df_result['bb_lower'] = df_result['bb_middle'] - (rolling_std * std_dev)

            # Calculate bandwidth and %B
            df_result['bb_bandwidth'] = (df_result['bb_upper'] - df_result['bb_lower']) / df_result['bb_middle']
            df_result['bb_percent'] = (df_result[column] - df_result['bb_lower']) / (df_result['bb_upper'] - df_result['bb_lower'])

            logger.debug("Calculated Bollinger Bands")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {str(e)}")
            raise

    def calculate_atr(
        self,
        df: pd.DataFrame,
        period: int = 14
    ) -> pd.DataFrame:
        """
        Calculate Average True Range (ATR).

        ATR measures market volatility by decomposing the entire range of an asset.

        Args:
            df: DataFrame with OHLCV data (requires high, low, close)
            period: Lookback period (default: 14)

        Returns:
            DataFrame with ATR column added
        """
        try:
            self._validate_dataframe(df, ['high', 'low', 'close'])
            df_result = df.copy()

            # Calculate True Range
            df_result['tr1'] = df_result['high'] - df_result['low']
            df_result['tr2'] = abs(df_result['high'] - df_result['close'].shift())
            df_result['tr3'] = abs(df_result['low'] - df_result['close'].shift())
            df_result['tr'] = df_result[['tr1', 'tr2', 'tr3']].max(axis=1)

            # Calculate ATR
            df_result['atr'] = df_result['tr'].rolling(window=period).mean()

            # Clean up temporary columns
            df_result.drop(['tr1', 'tr2', 'tr3', 'tr'], axis=1, inplace=True)

            logger.debug("Calculated ATR")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating ATR: {str(e)}")
            raise

    def calculate_keltner_channels(
        self,
        df: pd.DataFrame,
        ema_period: int = 20,
        atr_period: int = 10,
        multiplier: float = 2.0
    ) -> pd.DataFrame:
        """
        Calculate Keltner Channels.

        Keltner Channels use ATR to set channel distance from an EMA.

        Args:
            df: DataFrame with OHLCV data (requires high, low, close)
            ema_period: EMA period for middle line (default: 20)
            atr_period: ATR period (default: 10)
            multiplier: ATR multiplier for channel width (default: 2.0)

        Returns:
            DataFrame with Keltner Channel upper, middle, and lower bands added
        """
        try:
            self._validate_dataframe(df, ['high', 'low', 'close'])
            df_result = df.copy()

            # Calculate middle line (EMA)
            df_result['kc_middle'] = df_result['close'].ewm(span=ema_period, adjust=False).mean()

            # Calculate ATR
            df_result = self.calculate_atr(df_result, period=atr_period)

            # Calculate upper and lower channels
            df_result['kc_upper'] = df_result['kc_middle'] + (df_result['atr'] * multiplier)
            df_result['kc_lower'] = df_result['kc_middle'] - (df_result['atr'] * multiplier)

            logger.debug("Calculated Keltner Channels")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating Keltner Channels: {str(e)}")
            raise

    def calculate_standard_deviation(
        self,
        df: pd.DataFrame,
        column: str = 'close',
        period: int = 20
    ) -> pd.DataFrame:
        """
        Calculate Standard Deviation.

        Standard deviation measures the amount of variation in a set of values.

        Args:
            df: DataFrame with OHLCV data
            column: Column name to calculate on (default: 'close')
            period: Lookback period (default: 20)

        Returns:
            DataFrame with standard deviation column added
        """
        try:
            self._validate_dataframe(df, [column])
            df_result = df.copy()

            df_result['std_dev'] = df_result[column].rolling(window=period).std()

            logger.debug("Calculated Standard Deviation")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating Standard Deviation: {str(e)}")
            raise

    # =====================================================================
    # VOLUME INDICATORS
    # =====================================================================

    def calculate_obv(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate On-Balance Volume (OBV).

        OBV measures buying and selling pressure as a cumulative indicator.

        Args:
            df: DataFrame with OHLCV data (requires close, volume)

        Returns:
            DataFrame with OBV column added
        """
        try:
            self._validate_dataframe(df, ['close', 'volume'])
            df_result = df.copy()

            # Calculate OBV
            df_result['obv'] = (np.sign(df_result['close'].diff()) * df_result['volume']).fillna(0).cumsum()

            logger.debug("Calculated OBV")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating OBV: {str(e)}")
            raise

    def calculate_cmf(
        self,
        df: pd.DataFrame,
        period: int = 20
    ) -> pd.DataFrame:
        """
        Calculate Chaikin Money Flow (CMF).

        CMF measures the amount of Money Flow Volume over a specific period.

        Args:
            df: DataFrame with OHLCV data (requires high, low, close, volume)
            period: Lookback period (default: 20)

        Returns:
            DataFrame with CMF column added
        """
        try:
            self._validate_dataframe(df, ['high', 'low', 'close', 'volume'])
            df_result = df.copy()

            # Calculate Money Flow Multiplier
            mfm = ((df_result['close'] - df_result['low']) - (df_result['high'] - df_result['close'])) / \
                  (df_result['high'] - df_result['low'])
            mfm = mfm.fillna(0)

            # Calculate Money Flow Volume
            mfv = mfm * df_result['volume']

            # Calculate CMF
            df_result['cmf'] = mfv.rolling(window=period).sum() / df_result['volume'].rolling(window=period).sum()

            logger.debug("Calculated CMF")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating CMF: {str(e)}")
            raise

    def calculate_mfi(
        self,
        df: pd.DataFrame,
        period: int = 14
    ) -> pd.DataFrame:
        """
        Calculate Money Flow Index (MFI).

        MFI is a momentum indicator that uses price and volume to identify
        overbought or oversold conditions.

        Args:
            df: DataFrame with OHLCV data (requires high, low, close, volume)
            period: Lookback period (default: 14)

        Returns:
            DataFrame with MFI column added
        """
        try:
            self._validate_dataframe(df, ['high', 'low', 'close', 'volume'])
            df_result = df.copy()

            # Calculate typical price
            typical_price = (df_result['high'] + df_result['low'] + df_result['close']) / 3

            # Calculate raw money flow
            money_flow = typical_price * df_result['volume']

            # Calculate positive and negative money flow
            positive_flow = pd.Series(0.0, index=df_result.index)
            negative_flow = pd.Series(0.0, index=df_result.index)

            for i in range(1, len(df_result)):
                if typical_price.iloc[i] > typical_price.iloc[i-1]:
                    positive_flow.iloc[i] = money_flow.iloc[i]
                elif typical_price.iloc[i] < typical_price.iloc[i-1]:
                    negative_flow.iloc[i] = money_flow.iloc[i]

            # Calculate money flow ratio
            positive_mf = positive_flow.rolling(window=period).sum()
            negative_mf = negative_flow.rolling(window=period).sum()
            mfr = positive_mf / negative_mf

            # Calculate MFI
            df_result['mfi'] = 100 - (100 / (1 + mfr))

            logger.debug("Calculated MFI")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating MFI: {str(e)}")
            raise

    def calculate_vwap(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate Volume Weighted Average Price (VWAP).

        VWAP is the ratio of the value traded to total volume traded.

        Args:
            df: DataFrame with OHLCV data (requires high, low, close, volume)

        Returns:
            DataFrame with VWAP column added
        """
        try:
            self._validate_dataframe(df, ['high', 'low', 'close', 'volume'])
            df_result = df.copy()

            # Calculate typical price
            typical_price = (df_result['high'] + df_result['low'] + df_result['close']) / 3

            # Calculate VWAP
            df_result['vwap'] = (typical_price * df_result['volume']).cumsum() / df_result['volume'].cumsum()

            logger.debug("Calculated VWAP")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating VWAP: {str(e)}")
            raise

    def calculate_volume_profile(
        self,
        df: pd.DataFrame,
        num_bins: int = 20
    ) -> pd.DataFrame:
        """
        Calculate Volume Profile.

        Volume Profile shows traded volume at different price levels.

        Args:
            df: DataFrame with OHLCV data (requires high, low, close, volume)
            num_bins: Number of price bins (default: 20)

        Returns:
            DataFrame with volume profile column added
        """
        try:
            self._validate_dataframe(df, ['high', 'low', 'close', 'volume'])
            df_result = df.copy()

            # Calculate price bins
            price_min = df_result['low'].min()
            price_max = df_result['high'].max()
            bins = np.linspace(price_min, price_max, num_bins + 1)

            # Calculate typical price
            typical_price = (df_result['high'] + df_result['low'] + df_result['close']) / 3

            # Assign prices to bins
            df_result['price_bin'] = pd.cut(typical_price, bins=bins, labels=False, include_lowest=True)

            # Calculate volume for each bin
            volume_profile = df_result.groupby('price_bin')['volume'].sum()

            # Map back to dataframe
            df_result['volume_profile'] = df_result['price_bin'].map(volume_profile)

            # Calculate Point of Control (POC) - price level with highest volume
            poc_bin = volume_profile.idxmax()
            df_result['poc_price'] = (bins[int(poc_bin)] + bins[int(poc_bin) + 1]) / 2 if not np.isnan(poc_bin) else np.nan

            logger.debug("Calculated Volume Profile")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating Volume Profile: {str(e)}")
            raise

    # =====================================================================
    # SUPPORT/RESISTANCE INDICATORS
    # =====================================================================

    def calculate_pivot_points(
        self,
        df: pd.DataFrame,
        method: str = 'standard'
    ) -> pd.DataFrame:
        """
        Calculate Pivot Points.

        Pivot points are used to identify potential support and resistance levels.

        Args:
            df: DataFrame with OHLCV data (requires high, low, close)
            method: Calculation method - 'standard', 'fibonacci', 'woodie', 'camarilla' (default: 'standard')

        Returns:
            DataFrame with pivot point columns added
        """
        try:
            self._validate_dataframe(df, ['high', 'low', 'close'])
            df_result = df.copy()

            # Use previous period's high, low, close
            high = df_result['high'].shift(1)
            low = df_result['low'].shift(1)
            close = df_result['close'].shift(1)

            if method == 'standard':
                # Standard Pivot Points
                df_result['pivot'] = (high + low + close) / 3
                df_result['r1'] = 2 * df_result['pivot'] - low
                df_result['s1'] = 2 * df_result['pivot'] - high
                df_result['r2'] = df_result['pivot'] + (high - low)
                df_result['s2'] = df_result['pivot'] - (high - low)
                df_result['r3'] = high + 2 * (df_result['pivot'] - low)
                df_result['s3'] = low - 2 * (high - df_result['pivot'])

            elif method == 'fibonacci':
                # Fibonacci Pivot Points
                df_result['pivot'] = (high + low + close) / 3
                df_result['r1'] = df_result['pivot'] + 0.382 * (high - low)
                df_result['s1'] = df_result['pivot'] - 0.382 * (high - low)
                df_result['r2'] = df_result['pivot'] + 0.618 * (high - low)
                df_result['s2'] = df_result['pivot'] - 0.618 * (high - low)
                df_result['r3'] = df_result['pivot'] + 1.000 * (high - low)
                df_result['s3'] = df_result['pivot'] - 1.000 * (high - low)

            elif method == 'woodie':
                # Woodie Pivot Points
                df_result['pivot'] = (high + low + 2 * close) / 4
                df_result['r1'] = 2 * df_result['pivot'] - low
                df_result['s1'] = 2 * df_result['pivot'] - high
                df_result['r2'] = df_result['pivot'] + (high - low)
                df_result['s2'] = df_result['pivot'] - (high - low)

            elif method == 'camarilla':
                # Camarilla Pivot Points
                df_result['pivot'] = (high + low + close) / 3
                range_hl = high - low
                df_result['r1'] = close + range_hl * 1.1 / 12
                df_result['s1'] = close - range_hl * 1.1 / 12
                df_result['r2'] = close + range_hl * 1.1 / 6
                df_result['s2'] = close - range_hl * 1.1 / 6
                df_result['r3'] = close + range_hl * 1.1 / 4
                df_result['s3'] = close - range_hl * 1.1 / 4
                df_result['r4'] = close + range_hl * 1.1 / 2
                df_result['s4'] = close - range_hl * 1.1 / 2
            else:
                raise ValueError(f"Unknown pivot point method: {method}")

            logger.debug(f"Calculated {method} Pivot Points")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating Pivot Points: {str(e)}")
            raise

    def calculate_fibonacci_levels(
        self,
        df: pd.DataFrame,
        lookback: int = 50,
        direction: str = 'auto'
    ) -> pd.DataFrame:
        """
        Calculate Fibonacci Retracement Levels.

        Fibonacci levels are used to identify potential support and resistance.

        Args:
            df: DataFrame with OHLCV data (requires high, low)
            lookback: Period to find swing high/low (default: 50)
            direction: Trend direction - 'up', 'down', 'auto' (default: 'auto')

        Returns:
            DataFrame with Fibonacci level columns added
        """
        try:
            self._validate_dataframe(df, ['high', 'low', 'close'])
            df_result = df.copy()

            # Fibonacci ratios
            fib_ratios = {
                'fib_0': 0.0,
                'fib_236': 0.236,
                'fib_382': 0.382,
                'fib_50': 0.5,
                'fib_618': 0.618,
                'fib_786': 0.786,
                'fib_100': 1.0
            }

            # Rolling window to find swing high and low
            swing_high = df_result['high'].rolling(window=lookback).max()
            swing_low = df_result['low'].rolling(window=lookback).min()

            # Determine trend direction
            if direction == 'auto':
                # Use close price relative to mid-point
                mid_point = (swing_high + swing_low) / 2
                is_uptrend = df_result['close'] > mid_point
            elif direction == 'up':
                is_uptrend = True
            else:
                is_uptrend = False

            # Calculate Fibonacci levels
            price_range = swing_high - swing_low

            for name, ratio in fib_ratios.items():
                if isinstance(is_uptrend, bool):
                    # Single direction for all rows
                    if is_uptrend:
                        df_result[name] = swing_high - (price_range * ratio)
                    else:
                        df_result[name] = swing_low + (price_range * ratio)
                else:
                    # Dynamic direction per row
                    df_result[name] = np.where(
                        is_uptrend,
                        swing_high - (price_range * ratio),
                        swing_low + (price_range * ratio)
                    )

            logger.debug("Calculated Fibonacci Levels")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating Fibonacci Levels: {str(e)}")
            raise

    def calculate_price_channels(
        self,
        df: pd.DataFrame,
        period: int = 20
    ) -> pd.DataFrame:
        """
        Calculate Price Channels (Donchian Channels).

        Price channels show the highest high and lowest low over a period.

        Args:
            df: DataFrame with OHLCV data (requires high, low)
            period: Lookback period (default: 20)

        Returns:
            DataFrame with price channel columns added
        """
        try:
            self._validate_dataframe(df, ['high', 'low'])
            df_result = df.copy()

            # Calculate upper and lower channels
            df_result['channel_upper'] = df_result['high'].rolling(window=period).max()
            df_result['channel_lower'] = df_result['low'].rolling(window=period).min()
            df_result['channel_middle'] = (df_result['channel_upper'] + df_result['channel_lower']) / 2

            logger.debug("Calculated Price Channels")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating Price Channels: {str(e)}")
            raise

    # =====================================================================
    # UTILITY METHODS
    # =====================================================================

    def calculate_all_indicators(
        self,
        df: pd.DataFrame,
        indicator_config: Optional[Dict] = None
    ) -> pd.DataFrame:
        """
        Calculate all technical indicators at once.

        Args:
            df: DataFrame with OHLCV data
            indicator_config: Optional dictionary to customize indicator parameters

        Returns:
            DataFrame with all indicators added
        """
        try:
            logger.info("Calculating all technical indicators...")
            df_result = df.copy()

            # Trend indicators
            df_result = self.calculate_sma(df_result)
            df_result = self.calculate_ema(df_result)
            df_result = self.calculate_macd(df_result)
            df_result = self.calculate_adx(df_result)
            df_result = self.calculate_parabolic_sar(df_result)

            # Momentum indicators
            df_result = self.calculate_rsi(df_result)
            df_result = self.calculate_stochastic(df_result)
            df_result = self.calculate_williams_r(df_result)
            df_result = self.calculate_roc(df_result)
            df_result = self.calculate_cci(df_result)

            # Volatility indicators
            df_result = self.calculate_bollinger_bands(df_result)
            df_result = self.calculate_atr(df_result)
            df_result = self.calculate_keltner_channels(df_result)
            df_result = self.calculate_standard_deviation(df_result)

            # Volume indicators
            df_result = self.calculate_obv(df_result)
            df_result = self.calculate_cmf(df_result)
            df_result = self.calculate_mfi(df_result)
            df_result = self.calculate_vwap(df_result)
            df_result = self.calculate_volume_profile(df_result)

            # Support/Resistance indicators
            df_result = self.calculate_pivot_points(df_result)
            df_result = self.calculate_fibonacci_levels(df_result)
            df_result = self.calculate_price_channels(df_result)

            logger.info(f"All indicators calculated. Total columns: {len(df_result.columns)}")
            return df_result

        except Exception as e:
            logger.error(f"Error calculating all indicators: {str(e)}")
            raise

    def get_signals(
        self,
        df: pd.DataFrame,
        strategy: str = 'combined'
    ) -> pd.DataFrame:
        """
        Generate buy/sell signals from technical indicators.

        Args:
            df: DataFrame with calculated indicators
            strategy: Signal strategy - 'trend', 'momentum', 'volume', 'combined' (default: 'combined')

        Returns:
            DataFrame with signal columns added
        """
        try:
            logger.info(f"Generating {strategy} signals...")
            df_result = df.copy()

            # Initialize signal columns
            df_result['signal_trend'] = 0
            df_result['signal_momentum'] = 0
            df_result['signal_volume'] = 0
            df_result['signal_combined'] = 0

            # Trend signals
            if strategy in ['trend', 'combined']:
                # MACD crossover
                if 'macd' in df_result.columns and 'macd_signal' in df_result.columns:
                    macd_cross_up = (df_result['macd'] > df_result['macd_signal']) & \
                                   (df_result['macd'].shift(1) <= df_result['macd_signal'].shift(1))
                    macd_cross_down = (df_result['macd'] < df_result['macd_signal']) & \
                                     (df_result['macd'].shift(1) >= df_result['macd_signal'].shift(1))

                    df_result.loc[macd_cross_up, 'signal_trend'] += 1
                    df_result.loc[macd_cross_down, 'signal_trend'] -= 1

                # EMA crossover
                if 'ema_12' in df_result.columns and 'ema_26' in df_result.columns:
                    ema_cross_up = (df_result['ema_12'] > df_result['ema_26']) & \
                                  (df_result['ema_12'].shift(1) <= df_result['ema_26'].shift(1))
                    ema_cross_down = (df_result['ema_12'] < df_result['ema_26']) & \
                                    (df_result['ema_12'].shift(1) >= df_result['ema_26'].shift(1))

                    df_result.loc[ema_cross_up, 'signal_trend'] += 1
                    df_result.loc[ema_cross_down, 'signal_trend'] -= 1

                # ADX strength
                if 'adx' in df_result.columns:
                    strong_trend = df_result['adx'] > 25
                    if 'di_plus' in df_result.columns and 'di_minus' in df_result.columns:
                        df_result.loc[strong_trend & (df_result['di_plus'] > df_result['di_minus']), 'signal_trend'] += 1
                        df_result.loc[strong_trend & (df_result['di_plus'] < df_result['di_minus']), 'signal_trend'] -= 1

            # Momentum signals
            if strategy in ['momentum', 'combined']:
                # RSI oversold/overbought
                if 'rsi' in df_result.columns:
                    rsi_oversold = df_result['rsi'] < 30
                    rsi_overbought = df_result['rsi'] > 70

                    df_result.loc[rsi_oversold, 'signal_momentum'] += 1
                    df_result.loc[rsi_overbought, 'signal_momentum'] -= 1

                # Stochastic oversold/overbought
                if 'stoch_k' in df_result.columns:
                    stoch_oversold = df_result['stoch_k'] < 20
                    stoch_overbought = df_result['stoch_k'] > 80

                    df_result.loc[stoch_oversold, 'signal_momentum'] += 1
                    df_result.loc[stoch_overbought, 'signal_momentum'] -= 1

                # CCI extreme levels
                if 'cci' in df_result.columns:
                    cci_oversold = df_result['cci'] < -100
                    cci_overbought = df_result['cci'] > 100

                    df_result.loc[cci_oversold, 'signal_momentum'] += 1
                    df_result.loc[cci_overbought, 'signal_momentum'] -= 1

            # Volume signals
            if strategy in ['volume', 'combined']:
                # CMF positive/negative
                if 'cmf' in df_result.columns:
                    cmf_positive = df_result['cmf'] > 0.1
                    cmf_negative = df_result['cmf'] < -0.1

                    df_result.loc[cmf_positive, 'signal_volume'] += 1
                    df_result.loc[cmf_negative, 'signal_volume'] -= 1

                # MFI oversold/overbought
                if 'mfi' in df_result.columns:
                    mfi_oversold = df_result['mfi'] < 20
                    mfi_overbought = df_result['mfi'] > 80

                    df_result.loc[mfi_oversold, 'signal_volume'] += 1
                    df_result.loc[mfi_overbought, 'signal_volume'] -= 1

            # Combined signal
            if strategy == 'combined':
                df_result['signal_combined'] = df_result['signal_trend'] + \
                                               df_result['signal_momentum'] + \
                                               df_result['signal_volume']

            # Create final buy/sell signal
            if strategy == 'combined':
                df_result['signal'] = np.where(df_result['signal_combined'] >= 2, 1,
                                              np.where(df_result['signal_combined'] <= -2, -1, 0))
            else:
                signal_col = f'signal_{strategy}'
                df_result['signal'] = np.where(df_result[signal_col] >= 1, 1,
                                              np.where(df_result[signal_col] <= -1, -1, 0))

            logger.info("Signals generated successfully")
            return df_result

        except Exception as e:
            logger.error(f"Error generating signals: {str(e)}")
            raise

    def normalize_indicators(
        self,
        df: pd.DataFrame,
        method: str = 'minmax',
        exclude_columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Normalize indicator values for machine learning models.

        Args:
            df: DataFrame with calculated indicators
            method: Normalization method - 'minmax', 'zscore', 'robust' (default: 'minmax')
            exclude_columns: Columns to exclude from normalization

        Returns:
            DataFrame with normalized indicator values
        """
        try:
            logger.info(f"Normalizing indicators using {method} method...")
            df_result = df.copy()

            # Default columns to exclude
            if exclude_columns is None:
                exclude_columns = ['open', 'high', 'low', 'close', 'volume', 'date', 'timestamp']

            # Get indicator columns (all except OHLCV and excluded)
            indicator_cols = [col for col in df_result.columns
                            if col not in exclude_columns and
                            df_result[col].dtype in ['float64', 'int64']]

            for col in indicator_cols:
                if method == 'minmax':
                    # Min-Max normalization (0 to 1)
                    col_min = df_result[col].min()
                    col_max = df_result[col].max()
                    if col_max != col_min:
                        df_result[f'{col}_norm'] = (df_result[col] - col_min) / (col_max - col_min)
                    else:
                        df_result[f'{col}_norm'] = 0

                elif method == 'zscore':
                    # Z-score normalization (mean=0, std=1)
                    col_mean = df_result[col].mean()
                    col_std = df_result[col].std()
                    if col_std != 0:
                        df_result[f'{col}_norm'] = (df_result[col] - col_mean) / col_std
                    else:
                        df_result[f'{col}_norm'] = 0

                elif method == 'robust':
                    # Robust normalization using median and IQR
                    col_median = df_result[col].median()
                    q75, q25 = df_result[col].quantile([0.75, 0.25])
                    iqr = q75 - q25
                    if iqr != 0:
                        df_result[f'{col}_norm'] = (df_result[col] - col_median) / iqr
                    else:
                        df_result[f'{col}_norm'] = 0

                else:
                    raise ValueError(f"Unknown normalization method: {method}")

            logger.info(f"Normalized {len(indicator_cols)} indicators")
            return df_result

        except Exception as e:
            logger.error(f"Error normalizing indicators: {str(e)}")
            raise

    def get_indicator_summary(self, df: pd.DataFrame) -> Dict:
        """
        Get a summary of calculated indicators.

        Args:
            df: DataFrame with calculated indicators

        Returns:
            Dictionary containing indicator summary statistics
        """
        try:
            summary = {
                'total_columns': len(df.columns),
                'total_rows': len(df),
                'indicators': {},
                'missing_values': {}
            }

            # Categorize indicators
            categories = {
                'trend': ['sma', 'ema', 'macd', 'adx', 'psar'],
                'momentum': ['rsi', 'stoch', 'williams', 'roc', 'cci'],
                'volatility': ['bb_', 'atr', 'kc_', 'std_dev'],
                'volume': ['obv', 'cmf', 'mfi', 'vwap', 'volume_profile'],
                'support_resistance': ['pivot', 'fib_', 'channel', 's1', 's2', 's3', 'r1', 'r2', 'r3']
            }

            for category, prefixes in categories.items():
                category_cols = [col for col in df.columns
                               if any(col.startswith(prefix) or prefix in col for prefix in prefixes)]
                summary['indicators'][category] = {
                    'count': len(category_cols),
                    'columns': category_cols
                }

            # Calculate missing values
            for col in df.columns:
                missing_count = df[col].isna().sum()
                if missing_count > 0:
                    summary['missing_values'][col] = {
                        'count': int(missing_count),
                        'percentage': float(missing_count / len(df) * 100)
                    }

            logger.info("Generated indicator summary")
            return summary

        except Exception as e:
            logger.error(f"Error generating indicator summary: {str(e)}")
            raise


# Convenience function for quick indicator calculation
def calculate_indicators(
    df: pd.DataFrame,
    indicators: Union[str, List[str]] = 'all',
    **kwargs
) -> pd.DataFrame:
    """
    Convenience function to calculate technical indicators.

    Args:
        df: DataFrame with OHLCV data
        indicators: Indicator(s) to calculate - 'all' or list of indicator names
        **kwargs: Additional parameters for specific indicators

    Returns:
        DataFrame with calculated indicators

    Example:
        >>> df_with_indicators = calculate_indicators(df, indicators='all')
        >>> df_with_rsi = calculate_indicators(df, indicators=['rsi', 'macd'])
    """
    tech_ind = TechnicalIndicators()

    if indicators == 'all':
        return tech_ind.calculate_all_indicators(df)

    df_result = df.copy()

    indicator_map = {
        'sma': tech_ind.calculate_sma,
        'ema': tech_ind.calculate_ema,
        'macd': tech_ind.calculate_macd,
        'adx': tech_ind.calculate_adx,
        'psar': tech_ind.calculate_parabolic_sar,
        'rsi': tech_ind.calculate_rsi,
        'stochastic': tech_ind.calculate_stochastic,
        'williams_r': tech_ind.calculate_williams_r,
        'roc': tech_ind.calculate_roc,
        'cci': tech_ind.calculate_cci,
        'bollinger': tech_ind.calculate_bollinger_bands,
        'atr': tech_ind.calculate_atr,
        'keltner': tech_ind.calculate_keltner_channels,
        'std_dev': tech_ind.calculate_standard_deviation,
        'obv': tech_ind.calculate_obv,
        'cmf': tech_ind.calculate_cmf,
        'mfi': tech_ind.calculate_mfi,
        'vwap': tech_ind.calculate_vwap,
        'volume_profile': tech_ind.calculate_volume_profile,
        'pivot': tech_ind.calculate_pivot_points,
        'fibonacci': tech_ind.calculate_fibonacci_levels,
        'channels': tech_ind.calculate_price_channels
    }

    if isinstance(indicators, str):
        indicators = [indicators]

    for indicator in indicators:
        if indicator in indicator_map:
            df_result = indicator_map[indicator](df_result, **kwargs)
        else:
            logger.warning(f"Unknown indicator: {indicator}")

    return df_result

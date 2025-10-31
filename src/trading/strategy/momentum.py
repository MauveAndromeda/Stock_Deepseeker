"""
Momentum Strategy Module

This module implements various momentum-based trading strategies including:
- Trend Following Strategy
- Breakout Strategy
- Moving Average Crossover
- RSI Momentum Strategy

Momentum strategies capitalize on the tendency of assets to continue moving
in the same direction for some period of time.
"""

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from .base import BaseStrategy, Position, PositionSide, SignalType, StrategyConfig

logger = logging.getLogger(__name__)


class MomentumStrategy(BaseStrategy):
    """
    Base momentum strategy class

    Provides common momentum calculation methods and utilities
    that can be used by specific momentum strategies.
    """

    def __init__(self, config: StrategyConfig):
        """Initialize momentum strategy"""
        super().__init__(config)
        self.lookback_period = config.parameters.get('lookback_period', 20)
        self.momentum_threshold = config.parameters.get('momentum_threshold', 0.02)

    def calculate_momentum(self, data: pd.DataFrame, period: int = 20) -> pd.Series:
        """
        Calculate price momentum

        Args:
            data: Market data DataFrame
            period: Lookback period

        Returns:
            Momentum series
        """
        return data['close'].pct_change(period)

    def calculate_rate_of_change(self, data: pd.DataFrame, period: int = 20) -> pd.Series:
        """
        Calculate rate of change (ROC)

        Args:
            data: Market data DataFrame
            period: Lookback period

        Returns:
            ROC series
        """
        return ((data['close'] - data['close'].shift(period)) / data['close'].shift(period)) * 100

    def calculate_momentum_strength(self, data: pd.DataFrame, period: int = 20) -> float:
        """
        Calculate momentum strength using linear regression

        Args:
            data: Market data DataFrame
            period: Lookback period

        Returns:
            Momentum strength (R-squared value)
        """
        if len(data) < period:
            return 0.0

        prices = data['close'].iloc[-period:].values
        x = np.arange(len(prices))

        # Fit linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, prices)

        return r_value ** 2  # R-squared

    def analyze(self, data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """Analyze momentum indicators"""
        analysis = {
            'symbol': symbol,
            'momentum': self.calculate_momentum(data, self.lookback_period).iloc[-1],
            'roc': self.calculate_rate_of_change(data, self.lookback_period).iloc[-1],
            'strength': self.calculate_momentum_strength(data, self.lookback_period),
        }
        return analysis

    def generate_signals(self, data: pd.DataFrame, symbol: str) -> SignalType:
        """Generate momentum-based signals"""
        momentum = self.calculate_momentum(data, self.lookback_period).iloc[-1]

        if momentum > self.momentum_threshold:
            return SignalType.BUY
        elif momentum < -self.momentum_threshold:
            return SignalType.SELL
        else:
            return SignalType.HOLD

    def execute(self, signal: SignalType, data: pd.DataFrame, symbol: str) -> Optional[Position]:
        """Execute momentum signal"""
        current_price = data['close'].iloc[-1]

        # Check if we already have a position
        if symbol in self.positions:
            position = self.positions[symbol]
            # Close position if signal reversed
            if (signal == SignalType.SELL and position.side == PositionSide.LONG) or \
               (signal == SignalType.BUY and position.side == PositionSide.SHORT):
                self.close_position(symbol, current_price, reason="signal_reversal")
                return None
            return None

        # Open new position
        if signal == SignalType.BUY:
            quantity = self.calculate_position_size(current_price, symbol)
            return self.open_position(
                symbol=symbol,
                side=PositionSide.LONG,
                quantity=quantity,
                price=current_price
            )
        elif signal == SignalType.SELL:
            quantity = self.calculate_position_size(current_price, symbol)
            return self.open_position(
                symbol=symbol,
                side=PositionSide.SHORT,
                quantity=quantity,
                price=current_price
            )

        return None


class TrendFollowingStrategy(BaseStrategy):
    """
    Trend Following Strategy

    Identifies and follows market trends using multiple indicators including
    moving averages, ADX, and trend strength metrics.
    """

    def __init__(self, config: StrategyConfig):
        """Initialize trend following strategy"""
        super().__init__(config)
        self.fast_period = config.parameters.get('fast_period', 10)
        self.slow_period = config.parameters.get('slow_period', 50)
        self.adx_period = config.parameters.get('adx_period', 14)
        self.adx_threshold = config.parameters.get('adx_threshold', 25)
        self.trend_strength_threshold = config.parameters.get('trend_strength', 0.6)

    def calculate_adx(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Calculate Average Directional Index (ADX)

        Args:
            data: Market data DataFrame
            period: ADX period

        Returns:
            ADX series
        """
        high = data['high']
        low = data['low']
        close = data['close']

        # Calculate True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Calculate +DM and -DM
        high_diff = high.diff()
        low_diff = -low.diff()

        plus_dm = high_diff.copy()
        plus_dm[high_diff < 0] = 0
        plus_dm[high_diff < low_diff] = 0

        minus_dm = low_diff.copy()
        minus_dm[low_diff < 0] = 0
        minus_dm[low_diff < high_diff] = 0

        # Smooth values
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)

        # Calculate ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()

        return adx

    def calculate_trend_strength(self, data: pd.DataFrame, period: int = 20) -> float:
        """
        Calculate trend strength using linear regression slope

        Args:
            data: Market data DataFrame
            period: Lookback period

        Returns:
            Normalized trend strength (-1 to 1)
        """
        if len(data) < period:
            return 0.0

        prices = data['close'].iloc[-period:].values
        x = np.arange(len(prices))

        slope, intercept, r_value, p_value, std_err = stats.linregress(x, prices)

        # Normalize slope by price
        normalized_slope = slope / prices.mean()

        return normalized_slope

    def analyze(self, data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """Analyze trend indicators"""
        fast_ma = data['close'].rolling(window=self.fast_period).mean()
        slow_ma = data['close'].rolling(window=self.slow_period).mean()
        adx = self.calculate_adx(data, self.adx_period)
        trend_strength = self.calculate_trend_strength(data, self.slow_period)

        analysis = {
            'symbol': symbol,
            'fast_ma': fast_ma.iloc[-1],
            'slow_ma': slow_ma.iloc[-1],
            'adx': adx.iloc[-1],
            'trend_strength': trend_strength,
            'trend_direction': 'UP' if fast_ma.iloc[-1] > slow_ma.iloc[-1] else 'DOWN',
            'strong_trend': adx.iloc[-1] > self.adx_threshold,
        }

        return analysis

    def generate_signals(self, data: pd.DataFrame, symbol: str) -> SignalType:
        """Generate trend following signals"""
        fast_ma = data['close'].rolling(window=self.fast_period).mean()
        slow_ma = data['close'].rolling(window=self.slow_period).mean()
        adx = self.calculate_adx(data, self.adx_period)
        trend_strength = self.calculate_trend_strength(data, self.slow_period)

        # Check if we have enough data
        if fast_ma.isna().iloc[-1] or slow_ma.isna().iloc[-1] or adx.isna().iloc[-1]:
            return SignalType.HOLD

        # Strong uptrend
        if (fast_ma.iloc[-1] > slow_ma.iloc[-1] and
            adx.iloc[-1] > self.adx_threshold and
            trend_strength > self.trend_strength_threshold):
            return SignalType.STRONG_BUY

        # Uptrend
        elif fast_ma.iloc[-1] > slow_ma.iloc[-1]:
            return SignalType.BUY

        # Strong downtrend
        elif (fast_ma.iloc[-1] < slow_ma.iloc[-1] and
              adx.iloc[-1] > self.adx_threshold and
              trend_strength < -self.trend_strength_threshold):
            return SignalType.STRONG_SELL

        # Downtrend
        elif fast_ma.iloc[-1] < slow_ma.iloc[-1]:
            return SignalType.SELL

        return SignalType.HOLD

    def execute(self, signal: SignalType, data: pd.DataFrame, symbol: str) -> Optional[Position]:
        """Execute trend following signal"""
        current_price = data['close'].iloc[-1]

        # Close opposite positions
        if symbol in self.positions:
            position = self.positions[symbol]
            if (signal in [SignalType.SELL, SignalType.STRONG_SELL] and position.side == PositionSide.LONG) or \
               (signal in [SignalType.BUY, SignalType.STRONG_BUY] and position.side == PositionSide.SHORT):
                self.close_position(symbol, current_price, reason="trend_reversal")
            else:
                return None

        # Open new position
        quantity = self.calculate_position_size(current_price, symbol)

        if signal in [SignalType.BUY, SignalType.STRONG_BUY]:
            return self.open_position(
                symbol=symbol,
                side=PositionSide.LONG,
                quantity=quantity,
                price=current_price,
                metadata={'signal_strength': 'STRONG' if signal == SignalType.STRONG_BUY else 'NORMAL'}
            )
        elif signal in [SignalType.SELL, SignalType.STRONG_SELL]:
            return self.open_position(
                symbol=symbol,
                side=PositionSide.SHORT,
                quantity=quantity,
                price=current_price,
                metadata={'signal_strength': 'STRONG' if signal == SignalType.STRONG_SELL else 'NORMAL'}
            )

        return None


class BreakoutStrategy(BaseStrategy):
    """
    Breakout Strategy

    Identifies and trades price breakouts from consolidation ranges using
    support/resistance levels, volume confirmation, and volatility analysis.
    """

    def __init__(self, config: StrategyConfig):
        """Initialize breakout strategy"""
        super().__init__(config)
        self.lookback_period = config.parameters.get('lookback_period', 20)
        self.volume_threshold = config.parameters.get('volume_threshold', 1.5)
        self.breakout_threshold = config.parameters.get('breakout_threshold', 0.01)
        self.volatility_period = config.parameters.get('volatility_period', 14)

    def calculate_support_resistance(self, data: pd.DataFrame, period: int = 20) -> Tuple[float, float]:
        """
        Calculate support and resistance levels

        Args:
            data: Market data DataFrame
            period: Lookback period

        Returns:
            Tuple of (support, resistance)
        """
        recent_data = data.iloc[-period:]
        support = recent_data['low'].min()
        resistance = recent_data['high'].max()
        return support, resistance

    def calculate_average_volume(self, data: pd.DataFrame, period: int = 20) -> float:
        """Calculate average volume"""
        return data['volume'].rolling(window=period).mean().iloc[-1]

    def calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Calculate Average True Range (ATR)

        Args:
            data: Market data DataFrame
            period: ATR period

        Returns:
            ATR series
        """
        high = data['high']
        low = data['low']
        close = data['close']

        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()

        return atr

    def is_consolidation(self, data: pd.DataFrame, period: int = 20) -> bool:
        """
        Check if price is in consolidation

        Args:
            data: Market data DataFrame
            period: Lookback period

        Returns:
            True if in consolidation
        """
        recent_data = data.iloc[-period:]
        price_range = (recent_data['high'].max() - recent_data['low'].min()) / recent_data['close'].mean()
        return price_range < 0.1  # Less than 10% range

    def analyze(self, data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """Analyze breakout indicators"""
        support, resistance = self.calculate_support_resistance(data, self.lookback_period)
        current_price = data['close'].iloc[-1]
        current_volume = data['volume'].iloc[-1]
        avg_volume = self.calculate_average_volume(data, self.lookback_period)
        atr = self.calculate_atr(data, self.volatility_period).iloc[-1]
        in_consolidation = self.is_consolidation(data, self.lookback_period)

        analysis = {
            'symbol': symbol,
            'current_price': current_price,
            'support': support,
            'resistance': resistance,
            'volume_ratio': current_volume / avg_volume if avg_volume > 0 else 0,
            'atr': atr,
            'in_consolidation': in_consolidation,
            'distance_to_resistance': (resistance - current_price) / current_price,
            'distance_to_support': (current_price - support) / current_price,
        }

        return analysis

    def generate_signals(self, data: pd.DataFrame, symbol: str) -> SignalType:
        """Generate breakout signals"""
        support, resistance = self.calculate_support_resistance(data, self.lookback_period)
        current_price = data['close'].iloc[-1]
        current_volume = data['volume'].iloc[-1]
        avg_volume = self.calculate_average_volume(data, self.lookback_period)

        # Volume confirmation
        volume_confirmed = current_volume > (avg_volume * self.volume_threshold)

        # Upside breakout
        if current_price > resistance * (1 + self.breakout_threshold) and volume_confirmed:
            return SignalType.STRONG_BUY

        # Downside breakout
        elif current_price < support * (1 - self.breakout_threshold) and volume_confirmed:
            return SignalType.STRONG_SELL

        # Near resistance
        elif current_price > resistance * 0.99 and volume_confirmed:
            return SignalType.BUY

        # Near support
        elif current_price < support * 1.01 and volume_confirmed:
            return SignalType.SELL

        return SignalType.HOLD

    def execute(self, signal: SignalType, data: pd.DataFrame, symbol: str) -> Optional[Position]:
        """Execute breakout signal"""
        current_price = data['close'].iloc[-1]
        atr = self.calculate_atr(data, self.volatility_period).iloc[-1]

        # Close opposite positions
        if symbol in self.positions:
            position = self.positions[symbol]
            if (signal in [SignalType.SELL, SignalType.STRONG_SELL] and position.side == PositionSide.LONG) or \
               (signal in [SignalType.BUY, SignalType.STRONG_BUY] and position.side == PositionSide.SHORT):
                self.close_position(symbol, current_price, reason="breakout_reversal")
            else:
                return None

        # Open new position with ATR-based stops
        quantity = self.calculate_position_size(current_price, symbol)

        if signal in [SignalType.BUY, SignalType.STRONG_BUY]:
            stop_loss = current_price - (2 * atr)
            take_profit = current_price + (3 * atr)
            return self.open_position(
                symbol=symbol,
                side=PositionSide.LONG,
                quantity=quantity,
                price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                metadata={'breakout_type': 'upside', 'atr': atr}
            )
        elif signal in [SignalType.SELL, SignalType.STRONG_SELL]:
            stop_loss = current_price + (2 * atr)
            take_profit = current_price - (3 * atr)
            return self.open_position(
                symbol=symbol,
                side=PositionSide.SHORT,
                quantity=quantity,
                price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                metadata={'breakout_type': 'downside', 'atr': atr}
            )

        return None


class MovingAverageCrossover(BaseStrategy):
    """
    Moving Average Crossover Strategy

    Classic strategy that generates signals based on the crossover of
    fast and slow moving averages with multiple confirmation filters.
    """

    def __init__(self, config: StrategyConfig):
        """Initialize MA crossover strategy"""
        super().__init__(config)
        self.fast_period = config.parameters.get('fast_period', 20)
        self.slow_period = config.parameters.get('slow_period', 50)
        self.signal_period = config.parameters.get('signal_period', 9)
        self.ma_type = config.parameters.get('ma_type', 'ema')  # 'sma' or 'ema'

    def calculate_ma(self, data: pd.Series, period: int, ma_type: str = 'ema') -> pd.Series:
        """
        Calculate moving average

        Args:
            data: Price series
            period: MA period
            ma_type: Type of MA ('sma' or 'ema')

        Returns:
            Moving average series
        """
        if ma_type == 'sma':
            return data.rolling(window=period).mean()
        elif ma_type == 'ema':
            return data.ewm(span=period, adjust=False).mean()
        else:
            raise ValueError(f"Unknown MA type: {ma_type}")

    def calculate_macd(self, data: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate MACD indicator

        Args:
            data: Market data DataFrame

        Returns:
            Tuple of (MACD line, signal line, histogram)
        """
        ema_fast = data['close'].ewm(span=12, adjust=False).mean()
        ema_slow = data['close'].ewm(span=26, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    def detect_crossover(self, fast_ma: pd.Series, slow_ma: pd.Series) -> int:
        """
        Detect MA crossover

        Args:
            fast_ma: Fast moving average
            slow_ma: Slow moving average

        Returns:
            1 for bullish crossover, -1 for bearish crossover, 0 for no crossover
        """
        if len(fast_ma) < 2 or len(slow_ma) < 2:
            return 0

        # Current values
        fast_current = fast_ma.iloc[-1]
        slow_current = slow_ma.iloc[-1]

        # Previous values
        fast_prev = fast_ma.iloc[-2]
        slow_prev = slow_ma.iloc[-2]

        # Bullish crossover
        if fast_prev <= slow_prev and fast_current > slow_current:
            return 1

        # Bearish crossover
        elif fast_prev >= slow_prev and fast_current < slow_current:
            return -1

        return 0

    def analyze(self, data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """Analyze moving average indicators"""
        fast_ma = self.calculate_ma(data['close'], self.fast_period, self.ma_type)
        slow_ma = self.calculate_ma(data['close'], self.slow_period, self.ma_type)
        macd_line, signal_line, histogram = self.calculate_macd(data)
        crossover = self.detect_crossover(fast_ma, slow_ma)

        analysis = {
            'symbol': symbol,
            'fast_ma': fast_ma.iloc[-1],
            'slow_ma': slow_ma.iloc[-1],
            'current_price': data['close'].iloc[-1],
            'ma_distance': (fast_ma.iloc[-1] - slow_ma.iloc[-1]) / slow_ma.iloc[-1] * 100,
            'macd': macd_line.iloc[-1],
            'macd_signal': signal_line.iloc[-1],
            'macd_histogram': histogram.iloc[-1],
            'crossover': crossover,
        }

        return analysis

    def generate_signals(self, data: pd.DataFrame, symbol: str) -> SignalType:
        """Generate MA crossover signals"""
        fast_ma = self.calculate_ma(data['close'], self.fast_period, self.ma_type)
        slow_ma = self.calculate_ma(data['close'], self.slow_period, self.ma_type)
        macd_line, signal_line, histogram = self.calculate_macd(data)

        # Check for crossover
        crossover = self.detect_crossover(fast_ma, slow_ma)

        # MACD confirmation
        macd_bullish = macd_line.iloc[-1] > signal_line.iloc[-1]
        macd_bearish = macd_line.iloc[-1] < signal_line.iloc[-1]

        # Strong bullish signal (crossover + MACD confirmation)
        if crossover == 1 and macd_bullish:
            return SignalType.STRONG_BUY

        # Bullish signal (MA position)
        elif fast_ma.iloc[-1] > slow_ma.iloc[-1] and macd_bullish:
            return SignalType.BUY

        # Strong bearish signal (crossover + MACD confirmation)
        elif crossover == -1 and macd_bearish:
            return SignalType.STRONG_SELL

        # Bearish signal (MA position)
        elif fast_ma.iloc[-1] < slow_ma.iloc[-1] and macd_bearish:
            return SignalType.SELL

        return SignalType.HOLD

    def execute(self, signal: SignalType, data: pd.DataFrame, symbol: str) -> Optional[Position]:
        """Execute MA crossover signal"""
        current_price = data['close'].iloc[-1]

        # Close opposite positions
        if symbol in self.positions:
            position = self.positions[symbol]
            if (signal in [SignalType.SELL, SignalType.STRONG_SELL] and position.side == PositionSide.LONG) or \
               (signal in [SignalType.BUY, SignalType.STRONG_BUY] and position.side == PositionSide.SHORT):
                self.close_position(symbol, current_price, reason="ma_crossover")
            else:
                return None

        # Open new position
        quantity = self.calculate_position_size(current_price, symbol)

        if signal in [SignalType.BUY, SignalType.STRONG_BUY]:
            return self.open_position(
                symbol=symbol,
                side=PositionSide.LONG,
                quantity=quantity,
                price=current_price,
                metadata={'strategy': 'ma_crossover', 'signal_type': signal.name}
            )
        elif signal in [SignalType.SELL, SignalType.STRONG_SELL]:
            return self.open_position(
                symbol=symbol,
                side=PositionSide.SHORT,
                quantity=quantity,
                price=current_price,
                metadata={'strategy': 'ma_crossover', 'signal_type': signal.name}
            )

        return None


class RSIMomentumStrategy(BaseStrategy):
    """
    RSI Momentum Strategy

    Uses Relative Strength Index (RSI) combined with momentum indicators
    to identify overbought/oversold conditions and momentum shifts.
    """

    def __init__(self, config: StrategyConfig):
        """Initialize RSI momentum strategy"""
        super().__init__(config)
        self.rsi_period = config.parameters.get('rsi_period', 14)
        self.rsi_overbought = config.parameters.get('rsi_overbought', 70)
        self.rsi_oversold = config.parameters.get('rsi_oversold', 30)
        self.momentum_period = config.parameters.get('momentum_period', 10)

    def calculate_rsi(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index (RSI)

        Args:
            data: Market data DataFrame
            period: RSI period

        Returns:
            RSI series
        """
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def calculate_stochastic_rsi(self, data: pd.DataFrame, period: int = 14) -> Tuple[pd.Series, pd.Series]:
        """
        Calculate Stochastic RSI

        Args:
            data: Market data DataFrame
            period: Period

        Returns:
            Tuple of (Stochastic RSI, Signal line)
        """
        rsi = self.calculate_rsi(data, period)

        stoch_rsi = (rsi - rsi.rolling(window=period).min()) / \
                    (rsi.rolling(window=period).max() - rsi.rolling(window=period).min()) * 100

        signal = stoch_rsi.rolling(window=3).mean()

        return stoch_rsi, signal

    def detect_rsi_divergence(self, data: pd.DataFrame, rsi: pd.Series, lookback: int = 20) -> int:
        """
        Detect RSI divergence

        Args:
            data: Market data DataFrame
            rsi: RSI series
            lookback: Lookback period

        Returns:
            1 for bullish divergence, -1 for bearish divergence, 0 for no divergence
        """
        if len(data) < lookback:
            return 0

        price = data['close'].iloc[-lookback:]
        rsi_values = rsi.iloc[-lookback:]

        # Bullish divergence: price makes lower low, RSI makes higher low
        price_ll = price.iloc[-1] < price.iloc[0]
        rsi_hl = rsi_values.iloc[-1] > rsi_values.iloc[0]

        if price_ll and rsi_hl:
            return 1

        # Bearish divergence: price makes higher high, RSI makes lower high
        price_hh = price.iloc[-1] > price.iloc[0]
        rsi_lh = rsi_values.iloc[-1] < rsi_values.iloc[0]

        if price_hh and rsi_lh:
            return -1

        return 0

    def analyze(self, data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """Analyze RSI and momentum indicators"""
        rsi = self.calculate_rsi(data, self.rsi_period)
        stoch_rsi, stoch_signal = self.calculate_stochastic_rsi(data, self.rsi_period)
        divergence = self.detect_rsi_divergence(data, rsi, self.momentum_period)
        momentum = data['close'].pct_change(self.momentum_period).iloc[-1]

        analysis = {
            'symbol': symbol,
            'rsi': rsi.iloc[-1],
            'stoch_rsi': stoch_rsi.iloc[-1],
            'stoch_signal': stoch_signal.iloc[-1],
            'divergence': divergence,
            'momentum': momentum * 100,
            'overbought': rsi.iloc[-1] > self.rsi_overbought,
            'oversold': rsi.iloc[-1] < self.rsi_oversold,
        }

        return analysis

    def generate_signals(self, data: pd.DataFrame, symbol: str) -> SignalType:
        """Generate RSI momentum signals"""
        rsi = self.calculate_rsi(data, self.rsi_period)
        stoch_rsi, stoch_signal = self.calculate_stochastic_rsi(data, self.rsi_period)
        divergence = self.detect_rsi_divergence(data, rsi, self.momentum_period)

        current_rsi = rsi.iloc[-1]

        # Strong buy: oversold + bullish divergence
        if current_rsi < self.rsi_oversold and divergence == 1:
            return SignalType.STRONG_BUY

        # Buy: oversold or StochRSI bullish crossover
        elif current_rsi < self.rsi_oversold or \
             (stoch_rsi.iloc[-1] > stoch_signal.iloc[-1] and stoch_rsi.iloc[-1] < 20):
            return SignalType.BUY

        # Strong sell: overbought + bearish divergence
        elif current_rsi > self.rsi_overbought and divergence == -1:
            return SignalType.STRONG_SELL

        # Sell: overbought or StochRSI bearish crossover
        elif current_rsi > self.rsi_overbought or \
             (stoch_rsi.iloc[-1] < stoch_signal.iloc[-1] and stoch_rsi.iloc[-1] > 80):
            return SignalType.SELL

        return SignalType.HOLD

    def execute(self, signal: SignalType, data: pd.DataFrame, symbol: str) -> Optional[Position]:
        """Execute RSI momentum signal"""
        current_price = data['close'].iloc[-1]
        rsi = self.calculate_rsi(data, self.rsi_period).iloc[-1]

        # Close opposite positions
        if symbol in self.positions:
            position = self.positions[symbol]
            if (signal in [SignalType.SELL, SignalType.STRONG_SELL] and position.side == PositionSide.LONG) or \
               (signal in [SignalType.BUY, SignalType.STRONG_BUY] and position.side == PositionSide.SHORT):
                self.close_position(symbol, current_price, reason="rsi_signal")
            else:
                return None

        # Open new position
        quantity = self.calculate_position_size(current_price, symbol)

        if signal in [SignalType.BUY, SignalType.STRONG_BUY]:
            return self.open_position(
                symbol=symbol,
                side=PositionSide.LONG,
                quantity=quantity,
                price=current_price,
                metadata={'rsi': rsi, 'signal_type': signal.name}
            )
        elif signal in [SignalType.SELL, SignalType.STRONG_SELL]:
            return self.open_position(
                symbol=symbol,
                side=PositionSide.SHORT,
                quantity=quantity,
                price=current_price,
                metadata={'rsi': rsi, 'signal_type': signal.name}
            )

        return None

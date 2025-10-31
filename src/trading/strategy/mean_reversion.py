"""
Mean Reversion Strategy Module

This module implements various mean reversion trading strategies including:
- Bollinger Band Mean Reversion
- Statistical Arbitrage
- Pair Trading Strategy

Mean reversion strategies capitalize on the tendency of prices to revert
to their mean or average value after deviating from it.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LinearRegression

from .base import BaseStrategy, Position, PositionSide, SignalType, StrategyConfig

logger = logging.getLogger(__name__)


class BollingerMeanReversion(BaseStrategy):
    """
    Bollinger Band Mean Reversion Strategy

    Trades mean reversion using Bollinger Bands with additional filters
    including volume, RSI, and volatility analysis.
    """

    def __init__(self, config: StrategyConfig):
        """Initialize Bollinger Band mean reversion strategy"""
        super().__init__(config)
        self.bb_period = config.parameters.get('bb_period', 20)
        self.bb_std = config.parameters.get('bb_std', 2.0)
        self.rsi_period = config.parameters.get('rsi_period', 14)
        self.volume_threshold = config.parameters.get('volume_threshold', 1.2)
        self.reversion_threshold = config.parameters.get('reversion_threshold', 0.8)

    def calculate_bollinger_bands(
        self,
        data: pd.DataFrame,
        period: int = 20,
        std_dev: float = 2.0
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands

        Args:
            data: Market data DataFrame
            period: Moving average period
            std_dev: Number of standard deviations

        Returns:
            Tuple of (upper band, middle band, lower band)
        """
        middle_band = data['close'].rolling(window=period).mean()
        std = data['close'].rolling(window=period).std()
        upper_band = middle_band + (std * std_dev)
        lower_band = middle_band - (std * std_dev)

        return upper_band, middle_band, lower_band

    def calculate_bb_width(self, upper: pd.Series, lower: pd.Series, middle: pd.Series) -> pd.Series:
        """
        Calculate Bollinger Band width

        Args:
            upper: Upper band
            lower: Lower band
            middle: Middle band

        Returns:
            Normalized band width
        """
        return ((upper - lower) / middle) * 100

    def calculate_percent_b(self, price: pd.Series, upper: pd.Series, lower: pd.Series) -> pd.Series:
        """
        Calculate %B indicator (price position within bands)

        Args:
            price: Price series
            upper: Upper band
            lower: Lower band

        Returns:
            %B values
        """
        return (price - lower) / (upper - lower)

    def calculate_rsi(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def detect_squeeze(self, bb_width: pd.Series, lookback: int = 20) -> bool:
        """
        Detect Bollinger Band squeeze (low volatility period)

        Args:
            bb_width: Bollinger Band width series
            lookback: Lookback period

        Returns:
            True if in squeeze
        """
        if len(bb_width) < lookback:
            return False

        current_width = bb_width.iloc[-1]
        avg_width = bb_width.iloc[-lookback:].mean()

        return current_width < avg_width * 0.5

    def analyze(self, data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """Analyze Bollinger Band indicators"""
        upper, middle, lower = self.calculate_bollinger_bands(data, self.bb_period, self.bb_std)
        bb_width = self.calculate_bb_width(upper, lower, middle)
        percent_b = self.calculate_percent_b(data['close'], upper, lower)
        rsi = self.calculate_rsi(data, self.rsi_period)
        is_squeeze = self.detect_squeeze(bb_width)

        current_price = data['close'].iloc[-1]

        analysis = {
            'symbol': symbol,
            'current_price': current_price,
            'upper_band': upper.iloc[-1],
            'middle_band': middle.iloc[-1],
            'lower_band': lower.iloc[-1],
            'bb_width': bb_width.iloc[-1],
            'percent_b': percent_b.iloc[-1],
            'rsi': rsi.iloc[-1],
            'squeeze': is_squeeze,
            'above_upper': current_price > upper.iloc[-1],
            'below_lower': current_price < lower.iloc[-1],
        }

        return analysis

    def generate_signals(self, data: pd.DataFrame, symbol: str) -> SignalType:
        """Generate mean reversion signals"""
        upper, middle, lower = self.calculate_bollinger_bands(data, self.bb_period, self.bb_std)
        percent_b = self.calculate_percent_b(data['close'], upper, lower)
        rsi = self.calculate_rsi(data, self.rsi_period)

        current_price = data['close'].iloc[-1]
        current_percent_b = percent_b.iloc[-1]

        # Volume confirmation
        avg_volume = data['volume'].rolling(window=20).mean().iloc[-1]
        volume_confirmed = data['volume'].iloc[-1] > (avg_volume * self.volume_threshold)

        # Strong oversold (below lower band + low RSI)
        if current_price < lower.iloc[-1] and rsi.iloc[-1] < 30 and volume_confirmed:
            return SignalType.STRONG_BUY

        # Oversold (approaching lower band)
        elif current_percent_b < 0.2 and rsi.iloc[-1] < 40:
            return SignalType.BUY

        # Strong overbought (above upper band + high RSI)
        elif current_price > upper.iloc[-1] and rsi.iloc[-1] > 70 and volume_confirmed:
            return SignalType.STRONG_SELL

        # Overbought (approaching upper band)
        elif current_percent_b > 0.8 and rsi.iloc[-1] > 60:
            return SignalType.SELL

        return SignalType.HOLD

    def execute(self, signal: SignalType, data: pd.DataFrame, symbol: str) -> Optional[Position]:
        """Execute mean reversion signal"""
        current_price = data['close'].iloc[-1]
        upper, middle, lower = self.calculate_bollinger_bands(data, self.bb_period, self.bb_std)

        # Close positions when price reverts to mean
        if symbol in self.positions:
            position = self.positions[symbol]

            # Close long position when price reaches middle band
            if position.side == PositionSide.LONG and current_price >= middle.iloc[-1]:
                self.close_position(symbol, current_price, reason="mean_reversion")
                return None

            # Close short position when price reaches middle band
            elif position.side == PositionSide.SHORT and current_price <= middle.iloc[-1]:
                self.close_position(symbol, current_price, reason="mean_reversion")
                return None

            return None

        # Open new positions
        quantity = self.calculate_position_size(current_price, symbol)

        if signal in [SignalType.BUY, SignalType.STRONG_BUY]:
            # Target is middle band, stop is further below
            return self.open_position(
                symbol=symbol,
                side=PositionSide.LONG,
                quantity=quantity,
                price=current_price,
                stop_loss=current_price * 0.97,
                take_profit=middle.iloc[-1],
                metadata={'entry_percent_b': (current_price - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1])}
            )
        elif signal in [SignalType.SELL, SignalType.STRONG_SELL]:
            # Target is middle band, stop is further above
            return self.open_position(
                symbol=symbol,
                side=PositionSide.SHORT,
                quantity=quantity,
                price=current_price,
                stop_loss=current_price * 1.03,
                take_profit=middle.iloc[-1],
                metadata={'entry_percent_b': (current_price - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1])}
            )

        return None


class StatisticalArbitrage(BaseStrategy):
    """
    Statistical Arbitrage Strategy

    Uses statistical measures to identify and trade deviations from
    expected price relationships, including z-score analysis and
    cointegration-based approaches.
    """

    def __init__(self, config: StrategyConfig):
        """Initialize statistical arbitrage strategy"""
        super().__init__(config)
        self.lookback_period = config.parameters.get('lookback_period', 60)
        self.entry_threshold = config.parameters.get('entry_threshold', 2.0)
        self.exit_threshold = config.parameters.get('exit_threshold', 0.5)
        self.half_life = config.parameters.get('half_life', 10)

    def calculate_z_score(self, data: pd.Series, window: int = 20) -> pd.Series:
        """
        Calculate rolling z-score

        Args:
            data: Price series
            window: Rolling window

        Returns:
            Z-score series
        """
        mean = data.rolling(window=window).mean()
        std = data.rolling(window=window).std()
        z_score = (data - mean) / std

        return z_score

    def calculate_half_life(self, spread: pd.Series) -> float:
        """
        Calculate mean reversion half-life using Ornstein-Uhlenbeck process

        Args:
            spread: Spread series

        Returns:
            Half-life in periods
        """
        spread_lag = spread.shift(1)
        spread_diff = spread - spread_lag

        spread_lag = spread_lag.dropna()
        spread_diff = spread_diff.dropna()

        # Align indices
        spread_diff = spread_diff[spread_diff.index.isin(spread_lag.index)]
        spread_lag = spread_lag[spread_lag.index.isin(spread_diff.index)]

        # Fit AR(1) model
        model = LinearRegression()
        model.fit(spread_lag.values.reshape(-1, 1), spread_diff.values)

        theta = model.coef_[0]

        if theta >= 0:
            return float('inf')

        half_life = -np.log(2) / theta

        return half_life

    def calculate_hurst_exponent(self, prices: pd.Series, max_lag: int = 20) -> float:
        """
        Calculate Hurst exponent to measure mean reversion tendency

        Args:
            prices: Price series
            max_lag: Maximum lag to use

        Returns:
            Hurst exponent (< 0.5 indicates mean reversion)
        """
        lags = range(2, max_lag)
        tau = []

        for lag in lags:
            # Calculate standard deviation of differenced series
            pp = np.subtract(prices[lag:].values, prices[:-lag].values)
            tau.append(np.std(pp))

        # Linear fit to log-log plot
        reg = LinearRegression()
        reg.fit(np.log(lags).reshape(-1, 1), np.log(tau))

        hurst = reg.coef_[0]

        return hurst

    def calculate_spread_ratio(self, price1: pd.Series, price2: pd.Series) -> pd.Series:
        """
        Calculate spread ratio between two price series

        Args:
            price1: First price series
            price2: Second price series

        Returns:
            Spread ratio
        """
        return price1 / price2

    def analyze(self, data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """Analyze statistical arbitrage indicators"""
        prices = data['close']
        z_score = self.calculate_z_score(prices, self.lookback_period)
        half_life = self.calculate_half_life(prices.pct_change().dropna())
        hurst = self.calculate_hurst_exponent(prices)

        # Calculate normalized price
        normalized_price = (prices - prices.rolling(window=self.lookback_period).mean()) / \
                          prices.rolling(window=self.lookback_period).std()

        analysis = {
            'symbol': symbol,
            'current_price': prices.iloc[-1],
            'z_score': z_score.iloc[-1],
            'half_life': half_life,
            'hurst_exponent': hurst,
            'mean_reverting': hurst < 0.5,
            'normalized_price': normalized_price.iloc[-1],
            'mean': prices.rolling(window=self.lookback_period).mean().iloc[-1],
            'std': prices.rolling(window=self.lookback_period).std().iloc[-1],
        }

        return analysis

    def generate_signals(self, data: pd.DataFrame, symbol: str) -> SignalType:
        """Generate statistical arbitrage signals"""
        prices = data['close']
        z_score = self.calculate_z_score(prices, self.lookback_period)

        current_z = z_score.iloc[-1]

        # Check if mean reverting
        hurst = self.calculate_hurst_exponent(prices)

        if hurst >= 0.5:  # Not mean reverting
            return SignalType.HOLD

        # Strong buy signal (oversold)
        if current_z < -self.entry_threshold:
            return SignalType.STRONG_BUY

        # Buy signal
        elif current_z < -self.entry_threshold * 0.7:
            return SignalType.BUY

        # Strong sell signal (overbought)
        elif current_z > self.entry_threshold:
            return SignalType.STRONG_SELL

        # Sell signal
        elif current_z > self.entry_threshold * 0.7:
            return SignalType.SELL

        return SignalType.HOLD

    def execute(self, signal: SignalType, data: pd.DataFrame, symbol: str) -> Optional[Position]:
        """Execute statistical arbitrage signal"""
        current_price = data['close'].iloc[-1]
        z_score = self.calculate_z_score(data['close'], self.lookback_period).iloc[-1]

        # Close positions when z-score reverts
        if symbol in self.positions:
            position = self.positions[symbol]

            # Exit long when z-score crosses exit threshold
            if position.side == PositionSide.LONG and z_score > -self.exit_threshold:
                self.close_position(symbol, current_price, reason="z_score_reversion")
                return None

            # Exit short when z-score crosses exit threshold
            elif position.side == PositionSide.SHORT and z_score < self.exit_threshold:
                self.close_position(symbol, current_price, reason="z_score_reversion")
                return None

            return None

        # Open new positions
        quantity = self.calculate_position_size(current_price, symbol)

        if signal in [SignalType.BUY, SignalType.STRONG_BUY]:
            return self.open_position(
                symbol=symbol,
                side=PositionSide.LONG,
                quantity=quantity,
                price=current_price,
                metadata={'entry_z_score': z_score, 'half_life': self.half_life}
            )
        elif signal in [SignalType.SELL, SignalType.STRONG_SELL]:
            return self.open_position(
                symbol=symbol,
                side=PositionSide.SHORT,
                quantity=quantity,
                price=current_price,
                metadata={'entry_z_score': z_score, 'half_life': self.half_life}
            )

        return None


class PairTradingStrategy(BaseStrategy):
    """
    Pair Trading Strategy

    Identifies and trades cointegrated pairs of securities, taking advantage
    of temporary divergences in their price relationship.
    """

    def __init__(self, config: StrategyConfig):
        """Initialize pair trading strategy"""
        super().__init__(config)
        self.pair_symbols = config.parameters.get('pair_symbols', [])
        self.lookback_period = config.parameters.get('lookback_period', 60)
        self.entry_threshold = config.parameters.get('entry_threshold', 2.0)
        self.exit_threshold = config.parameters.get('exit_threshold', 0.5)
        self.cointegration_pvalue = config.parameters.get('cointegration_pvalue', 0.05)

        # Store hedge ratios for pairs
        self.hedge_ratios: Dict[str, float] = {}

    def test_cointegration(self, series1: pd.Series, series2: pd.Series) -> Tuple[bool, float, float]:
        """
        Test for cointegration between two series

        Args:
            series1: First price series
            series2: Second price series

        Returns:
            Tuple of (is_cointegrated, p_value, hedge_ratio)
        """
        # Fit linear regression
        model = LinearRegression()
        model.fit(series2.values.reshape(-1, 1), series1.values)
        hedge_ratio = model.coef_[0]

        # Calculate spread
        spread = series1 - hedge_ratio * series2

        # Test if spread is stationary (ADF test approximation)
        mean = spread.mean()
        std = spread.std()

        # Simple stationarity check using normalized spread
        normalized_spread = (spread - mean) / std

        # Check if spread oscillates around zero
        crosses = ((normalized_spread[:-1] * normalized_spread[1:]) < 0).sum()
        expected_crosses = len(spread) * 0.3  # Expect some mean crossing

        is_stationary = crosses > expected_crosses
        p_value = 1.0 - (crosses / expected_crosses) if expected_crosses > 0 else 1.0

        return is_stationary, p_value, hedge_ratio

    def calculate_spread(
        self,
        price1: pd.Series,
        price2: pd.Series,
        hedge_ratio: Optional[float] = None
    ) -> pd.Series:
        """
        Calculate spread between pair

        Args:
            price1: First price series
            price2: Second price series
            hedge_ratio: Hedge ratio (calculated if None)

        Returns:
            Spread series
        """
        if hedge_ratio is None:
            model = LinearRegression()
            model.fit(price2.values.reshape(-1, 1), price1.values)
            hedge_ratio = model.coef_[0]

        spread = price1 - hedge_ratio * price2

        return spread

    def calculate_spread_zscore(self, spread: pd.Series, window: int = 20) -> pd.Series:
        """Calculate z-score of spread"""
        mean = spread.rolling(window=window).mean()
        std = spread.rolling(window=window).std()
        z_score = (spread - mean) / std

        return z_score

    def find_cointegrated_pairs(self, market_data: Dict[str, pd.DataFrame]) -> List[Tuple[str, str, float]]:
        """
        Find cointegrated pairs from available symbols

        Args:
            market_data: Dictionary of symbol -> DataFrame

        Returns:
            List of (symbol1, symbol2, hedge_ratio) tuples
        """
        cointegrated_pairs = []
        symbols = list(market_data.keys())

        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                sym1, sym2 = symbols[i], symbols[j]

                # Get price series
                prices1 = market_data[sym1]['close']
                prices2 = market_data[sym2]['close']

                # Align series
                common_index = prices1.index.intersection(prices2.index)
                if len(common_index) < self.lookback_period:
                    continue

                prices1 = prices1[common_index]
                prices2 = prices2[common_index]

                # Test cointegration
                is_coint, p_value, hedge_ratio = self.test_cointegration(prices1, prices2)

                if is_coint and p_value < self.cointegration_pvalue:
                    cointegrated_pairs.append((sym1, sym2, hedge_ratio))
                    self.logger.info(f"Found cointegrated pair: {sym1}-{sym2}, hedge ratio: {hedge_ratio:.4f}")

        return cointegrated_pairs

    def analyze(self, data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """Analyze pair trading indicators"""
        # This method would analyze a specific pair
        # For simplicity, we'll analyze the first symbol against its pair

        if len(self.pair_symbols) < 2:
            return {'error': 'Need at least 2 symbols for pair trading'}

        # Placeholder analysis
        analysis = {
            'symbol': symbol,
            'pair_count': len(self.pair_symbols),
            'hedge_ratios': self.hedge_ratios,
        }

        return analysis

    def generate_signals_for_pair(
        self,
        data1: pd.DataFrame,
        data2: pd.DataFrame,
        symbol1: str,
        symbol2: str
    ) -> Tuple[SignalType, SignalType]:
        """
        Generate signals for a pair

        Args:
            data1: Data for first symbol
            data2: Data for second symbol
            symbol1: First symbol
            symbol2: Second symbol

        Returns:
            Tuple of signals for (symbol1, symbol2)
        """
        # Get prices
        prices1 = data1['close']
        prices2 = data2['close']

        # Calculate or retrieve hedge ratio
        pair_key = f"{symbol1}_{symbol2}"
        if pair_key not in self.hedge_ratios:
            _, _, hedge_ratio = self.test_cointegration(prices1, prices2)
            self.hedge_ratios[pair_key] = hedge_ratio
        else:
            hedge_ratio = self.hedge_ratios[pair_key]

        # Calculate spread and z-score
        spread = self.calculate_spread(prices1, prices2, hedge_ratio)
        z_score = self.calculate_spread_zscore(spread, self.lookback_period)

        current_z = z_score.iloc[-1]

        # Generate signals
        if current_z > self.entry_threshold:
            # Spread too high: short symbol1, long symbol2
            return SignalType.SELL, SignalType.BUY
        elif current_z < -self.entry_threshold:
            # Spread too low: long symbol1, short symbol2
            return SignalType.BUY, SignalType.SELL
        else:
            return SignalType.HOLD, SignalType.HOLD

    def generate_signals(self, data: pd.DataFrame, symbol: str) -> SignalType:
        """Generate pair trading signals (placeholder)"""
        # This is a simplified version
        # In practice, you'd need data for both symbols in the pair
        return SignalType.HOLD

    def execute_pair_trade(
        self,
        signal1: SignalType,
        signal2: SignalType,
        data1: pd.DataFrame,
        data2: pd.DataFrame,
        symbol1: str,
        symbol2: str
    ) -> Tuple[Optional[Position], Optional[Position]]:
        """
        Execute pair trade

        Args:
            signal1: Signal for first symbol
            signal2: Signal for second symbol
            data1: Data for first symbol
            data2: Data for second symbol
            symbol1: First symbol
            symbol2: Second symbol

        Returns:
            Tuple of positions
        """
        price1 = data1['close'].iloc[-1]
        price2 = data2['close'].iloc[-1]

        pair_key = f"{symbol1}_{symbol2}"
        hedge_ratio = self.hedge_ratios.get(pair_key, 1.0)

        # Calculate position sizes
        # Ensure positions are balanced according to hedge ratio
        total_allocation = self.config.capital * self.config.position_size
        position_value1 = total_allocation / (1 + hedge_ratio)
        position_value2 = total_allocation * hedge_ratio / (1 + hedge_ratio)

        quantity1 = position_value1 / price1
        quantity2 = position_value2 / price2

        pos1, pos2 = None, None

        # Execute trades
        if signal1 == SignalType.BUY and signal2 == SignalType.SELL:
            pos1 = self.open_position(
                symbol=symbol1,
                side=PositionSide.LONG,
                quantity=quantity1,
                price=price1,
                metadata={'pair': symbol2, 'hedge_ratio': hedge_ratio}
            )
            pos2 = self.open_position(
                symbol=symbol2,
                side=PositionSide.SHORT,
                quantity=quantity2,
                price=price2,
                metadata={'pair': symbol1, 'hedge_ratio': hedge_ratio}
            )
        elif signal1 == SignalType.SELL and signal2 == SignalType.BUY:
            pos1 = self.open_position(
                symbol=symbol1,
                side=PositionSide.SHORT,
                quantity=quantity1,
                price=price1,
                metadata={'pair': symbol2, 'hedge_ratio': hedge_ratio}
            )
            pos2 = self.open_position(
                symbol=symbol2,
                side=PositionSide.LONG,
                quantity=quantity2,
                price=price2,
                metadata={'pair': symbol1, 'hedge_ratio': hedge_ratio}
            )

        return pos1, pos2

    def execute(self, signal: SignalType, data: pd.DataFrame, symbol: str) -> Optional[Position]:
        """Execute signal (simplified version)"""
        # In practice, use execute_pair_trade instead
        return None

    def run_pair_strategy(self, market_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        Run pair trading strategy

        Args:
            market_data: Dictionary of symbol -> DataFrame

        Returns:
            Results dictionary
        """
        results = {
            'pairs_traded': [],
            'positions': {},
            'performance': {}
        }

        # Find cointegrated pairs
        pairs = self.find_cointegrated_pairs(market_data)

        # Trade each pair
        for sym1, sym2, hedge_ratio in pairs:
            if sym1 not in market_data or sym2 not in market_data:
                continue

            # Generate signals for pair
            signal1, signal2 = self.generate_signals_for_pair(
                market_data[sym1],
                market_data[sym2],
                sym1,
                sym2
            )

            # Execute trades if signals generated
            if signal1 != SignalType.HOLD and signal2 != SignalType.HOLD:
                pos1, pos2 = self.execute_pair_trade(
                    signal1, signal2,
                    market_data[sym1], market_data[sym2],
                    sym1, sym2
                )

                if pos1 and pos2:
                    results['pairs_traded'].append((sym1, sym2))
                    results['positions'][sym1] = pos1
                    results['positions'][sym2] = pos2

        results['performance'] = self.performance.get_summary()

        return results

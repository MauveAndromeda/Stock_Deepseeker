"""
Pairs trading strategy.

Statistical arbitrage between correlated asset pairs.
"""

import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime
from collections import deque

from src.strategies.base import BaseStrategy, Signal, SignalType


class PairsTradingStrategy(BaseStrategy):
    """
    Pairs trading strategy.
    
    Trades mean reversion in spread between two correlated assets.
    
    Parameters:
        pair: Tuple of (symbol1, symbol2)
        window: Lookback window for statistics
        entry_threshold: Z-score threshold for entry
        exit_threshold: Z-score threshold for exit
        hedge_ratio_window: Window for calculating hedge ratio
    """
    
    def __init__(
        self,
        pair: Tuple[str, str],
        window: int = 20,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5,
        hedge_ratio_window: int = 60
    ):
        """Initialize pairs trading strategy."""
        super().__init__(name="PairsTradingStrategy")
        
        self.pair = pair
        self.window = window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.hedge_ratio_window = hedge_ratio_window
        
        self.price_history = {pair[0]: deque(), pair[1]: deque()}
        self.spread_history = deque(maxlen=window)
        self.in_position = False
    
    def on_data(self, data: Dict) -> List[Signal]:
        """Generate pairs trading signals."""
        signals = []
        
        prices = data.get('prices', {})
        symbol1, symbol2 = self.pair
        
        if symbol1 not in prices or symbol2 not in prices:
            return signals
        
        price1 = prices[symbol1]
        price2 = prices[symbol2]
        
        # Update price history
        self.price_history[symbol1].append(price1)
        self.price_history[symbol2].append(price2)
        
        # Need enough history
        if len(self.price_history[symbol1]) < self.hedge_ratio_window:
            return signals
        
        # Calculate hedge ratio (beta)
        prices1 = np.array(list(self.price_history[symbol1])[-self.hedge_ratio_window:])
        prices2 = np.array(list(self.price_history[symbol2])[-self.hedge_ratio_window:])
        
        hedge_ratio = np.cov(prices1, prices2)[0, 1] / np.var(prices2)
        
        # Calculate spread
        spread = price1 - hedge_ratio * price2
        self.spread_history.append(spread)
        
        # Need full window
        if len(self.spread_history) < self.window:
            return signals
        
        # Calculate spread statistics
        spread_mean = np.mean(self.spread_history)
        spread_std = np.std(self.spread_history)
        
        if spread_std == 0:
            return signals
        
        # Calculate z-score
        z_score = (spread - spread_mean) / spread_std
        
        current_time = data.get('timestamp', datetime.now())
        
        # Entry signals
        if not self.in_position:
            if z_score > self.entry_threshold:
                # Spread too high - short spread (short symbol1, long symbol2)
                signals.append(Signal(
                    timestamp=current_time,
                    symbol=symbol1,
                    signal_type=SignalType.SELL,
                    strength=min(abs(z_score) / self.entry_threshold, 1.0),
                    metadata={'z_score': z_score, 'hedge_ratio': hedge_ratio}
                ))
                signals.append(Signal(
                    timestamp=current_time,
                    symbol=symbol2,
                    signal_type=SignalType.BUY,
                    strength=min(abs(z_score) / self.entry_threshold, 1.0),
                    quantity=hedge_ratio,
                    metadata={'z_score': z_score, 'hedge_ratio': hedge_ratio}
                ))
                self.in_position = True
            
            elif z_score < -self.entry_threshold:
                # Spread too low - long spread (long symbol1, short symbol2)
                signals.append(Signal(
                    timestamp=current_time,
                    symbol=symbol1,
                    signal_type=SignalType.BUY,
                    strength=min(abs(z_score) / self.entry_threshold, 1.0),
                    metadata={'z_score': z_score, 'hedge_ratio': hedge_ratio}
                ))
                signals.append(Signal(
                    timestamp=current_time,
                    symbol=symbol2,
                    signal_type=SignalType.SELL,
                    strength=min(abs(z_score) / self.entry_threshold, 1.0),
                    quantity=hedge_ratio,
                    metadata={'z_score': z_score, 'hedge_ratio': hedge_ratio}
                ))
                self.in_position = True
        
        # Exit signals
        elif abs(z_score) < self.exit_threshold:
            # Close positions
            if symbol1 in self.positions:
                signals.append(Signal(
                    timestamp=current_time,
                    symbol=symbol1,
                    signal_type=SignalType.SELL if self.positions[symbol1] > 0 else SignalType.BUY,
                    strength=1.0,
                    metadata={'z_score': z_score, 'reason': 'spread_reversion'}
                ))
            
            if symbol2 in self.positions:
                signals.append(Signal(
                    timestamp=current_time,
                    symbol=symbol2,
                    signal_type=SignalType.SELL if self.positions[symbol2] > 0 else SignalType.BUY,
                    strength=1.0,
                    metadata={'z_score': z_score, 'reason': 'spread_reversion'}
                ))
            
            self.in_position = False
        
        return signals

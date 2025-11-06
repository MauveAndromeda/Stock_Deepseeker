"""
Momentum trading strategy.

Buys assets with strong recent performance, sells weak performers.
"""

import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime

from src.strategies.base import BaseStrategy, Signal, SignalType


class MomentumStrategy(BaseStrategy):
    """
    Momentum trading strategy.
    
    Parameters:
        lookback: Number of periods for momentum calculation
        holding_period: Number of periods to hold position
        n_positions: Number of positions to hold
        rebalance_frequency: How often to rebalance (days)
    """
    
    def __init__(
        self,
        lookback: int = 252,
        holding_period: int = 21,
        n_positions: int = 20,
        rebalance_frequency: int = 21
    ):
        """Initialize momentum strategy."""
        super().__init__(name="MomentumStrategy")
        
        self.lookback = lookback
        self.holding_period = holding_period
        self.n_positions = n_positions
        self.rebalance_frequency = rebalance_frequency
        
        self.last_rebalance = None
        self.price_history = {}
    
    def on_data(self, data: Dict) -> List[Signal]:
        """Generate momentum signals."""
        signals = []
        
        current_time = data.get('timestamp', datetime.now())
        
        # Check if rebalance needed
        if self.last_rebalance:
            days_since_rebalance = (current_time - self.last_rebalance).days
            if days_since_rebalance < self.rebalance_frequency:
                return signals
        
        # Update price history
        for symbol, price in data.get('prices', {}).items():
            if symbol not in self.price_history:
                self.price_history[symbol] = []
            
            self.price_history[symbol].append(price)
            
            # Keep only lookback period
            if len(self.price_history[symbol]) > self.lookback:
                self.price_history[symbol].pop(0)
        
        # Calculate momentum for each symbol
        momentum_scores = {}
        
        for symbol, prices in self.price_history.items():
            if len(prices) >= self.lookback:
                # Simple momentum: return over lookback period
                momentum = (prices[-1] / prices[0]) - 1
                momentum_scores[symbol] = momentum
        
        if not momentum_scores:
            return signals
        
        # Rank by momentum
        ranked_symbols = sorted(
            momentum_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Generate buy signals for top N
        for symbol, score in ranked_symbols[:self.n_positions]:
            if score > 0:  # Only buy positive momentum
                signal = Signal(
                    timestamp=current_time,
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    strength=min(score, 1.0),
                    metadata={'momentum': score}
                )
                signals.append(signal)
        
        # Generate sell signals for positions not in top N
        current_positions = set(self.positions.keys())
        top_symbols = set(s[0] for s in ranked_symbols[:self.n_positions])
        
        for symbol in current_positions - top_symbols:
            signal = Signal(
                timestamp=current_time,
                symbol=symbol,
                signal_type=SignalType.SELL,
                strength=1.0,
                metadata={'reason': 'not_in_top_n'}
            )
            signals.append(signal)
        
        self.last_rebalance = current_time
        
        return signals

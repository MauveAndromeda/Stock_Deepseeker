"""
Signal Aggregator
Combines signals from multiple sources
"""

from typing import List, Dict, Optional
from datetime import datetime
import numpy as np
from loguru import logger

from src.trading.strategy.base import Signal

class SignalAggregator:
    """Aggregates signals from multiple sources"""

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Args:
            weights: Dict of source -> weight for aggregation
        """
        self.weights = weights or {
            'technical': 0.3,
            'momentum': 0.2,
            'volume': 0.15,
            'mean_reversion': 0.15,
            'sentiment': 0.1,
            'ml_model': 0.1
        }
        
        # Normalize weights
        total = sum(self.weights.values())
        self.weights = {k: v/total for k, v in self.weights.items()}
        
        logger.info(f"Signal aggregator initialized with weights: {self.weights}")

    def aggregate(self, signals: List[Signal]) -> Optional[Signal]:
        """
        Aggregate multiple signals into one
        
        Args:
            signals: List of signals to aggregate
            
        Returns:
            Aggregated signal or None
        """
        if not signals:
            return None
        
        # Group by symbol (should all be same)
        symbol = signals[0].symbol
        
        # Calculate weighted scores
        buy_score = 0.0
        sell_score = 0.0
        hold_score = 0.0
        total_weight = 0.0
        total_confidence = 0.0
        
        for signal in signals:
            source = signal.metadata.get('source', 'unknown')
            weight = self.weights.get(source, 0.1)
            
            if signal.action == 'buy':
                buy_score += signal.strength * weight * signal.confidence
            elif signal.action == 'sell':
                sell_score += signal.strength * weight * signal.confidence
            elif signal.action == 'hold':
                hold_score += signal.strength * weight * signal.confidence
            
            total_weight += weight
            total_confidence += signal.confidence
        
        # Normalize scores
        if total_weight > 0:
            buy_score /= total_weight
            sell_score /= total_weight
            hold_score /= total_weight
        
        # Determine final action
        max_score = max(buy_score, sell_score, hold_score)
        
        if buy_score == max_score:
            action = 'buy'
            strength = buy_score
        elif sell_score == max_score:
            action = 'sell'
            strength = sell_score
        else:
            action = 'hold'
            strength = hold_score
        
        # Average confidence
        avg_confidence = total_confidence / len(signals) if signals else 0.5
        
        aggregated = Signal(
            symbol=symbol,
            timestamp=datetime.now(),
            action=action,
            strength=min(strength, 1.0),
            confidence=avg_confidence,
            metadata={
                'source': 'aggregated',
                'num_signals': len(signals),
                'buy_score': buy_score,
                'sell_score': sell_score,
                'hold_score': hold_score
            }
        )
        
        return aggregated

    def aggregate_by_voting(self, signals: List[Signal]) -> Optional[Signal]:
        """
        Aggregate using voting method
        
        Each signal gets one vote weighted by confidence
        """
        if not signals:
            return None
        
        symbol = signals[0].symbol
        
        # Count votes
        buy_votes = sum(s.confidence for s in signals if s.action == 'buy')
        sell_votes = sum(s.confidence for s in signals if s.action == 'sell')
        hold_votes = sum(s.confidence for s in signals if s.action == 'hold')
        
        total_votes = buy_votes + sell_votes + hold_votes
        
        # Determine winner
        if buy_votes > sell_votes and buy_votes > hold_votes:
            action = 'buy'
            strength = buy_votes / total_votes if total_votes > 0 else 0
        elif sell_votes > buy_votes and sell_votes > hold_votes:
            action = 'sell'
            strength = sell_votes / total_votes if total_votes > 0 else 0
        else:
            action = 'hold'
            strength = hold_votes / total_votes if total_votes > 0 else 0
        
        # Calculate average confidence
        avg_confidence = np.mean([s.confidence for s in signals])
        
        aggregated = Signal(
            symbol=symbol,
            timestamp=datetime.now(),
            action=action,
            strength=strength,
            confidence=avg_confidence,
            metadata={
                'source': 'voting',
                'num_signals': len(signals),
                'buy_votes': buy_votes,
                'sell_votes': sell_votes,
                'hold_votes': hold_votes
            }
        )
        
        return aggregated

    def filter_strong_signals(
        self,
        signals: List[Signal],
        min_strength: float = 0.5,
        min_confidence: float = 0.6
    ) -> List[Signal]:
        """Filter signals by strength and confidence"""
        filtered = [
            s for s in signals
            if s.strength >= min_strength and s.confidence >= min_confidence
        ]
        
        logger.debug(f"Filtered {len(filtered)}/{len(signals)} strong signals")
        
        return filtered

    def get_consensus(self, signals: List[Signal]) -> str:
        """Get consensus action from signals"""
        if not signals:
            return 'hold'
        
        actions = [s.action for s in signals]
        
        # Count actions
        buy_count = actions.count('buy')
        sell_count = actions.count('sell')
        hold_count = actions.count('hold')
        
        # Return majority
        if buy_count > sell_count and buy_count > hold_count:
            return 'buy'
        elif sell_count > buy_count and sell_count > hold_count:
            return 'sell'
        else:
            return 'hold'

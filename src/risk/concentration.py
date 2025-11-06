"""
Position concentration management and auto-rebalancing.
"""

from dataclasses import dataclass
from typing import Dict, List
import pandas as pd
from loguru import logger


@dataclass
class ConcentrationLimits:
    """Concentration risk limits."""
    max_single_position: float = 0.20  # 20% max in single position
    max_sector_exposure: float = 0.40  # 40% max in single sector
    max_top_5_concentration: float = 0.60  # 60% max in top 5
    max_top_10_concentration: float = 0.80  # 80% max in top 10


class ConcentrationManager:
    """
    Manages position concentration and triggers rebalancing.
    """
    
    def __init__(self, limits: ConcentrationLimits):
        """Initialize concentration manager."""
        self.limits = limits
        logger.info("Initialized ConcentrationManager")
    
    def check_concentration(
        self,
        positions: Dict[str, Dict],  # symbol -> {value, sector}
        portfolio_value: float
    ) -> Dict:
        """Check concentration limits."""
        if portfolio_value == 0:
            return {'violations': [], 'metrics': {}}
        
        violations = []
        
        # Calculate position weights
        weights = {
            symbol: abs(pos['value']) / portfolio_value
            for symbol, pos in positions.items()
        }
        
        # Check single position limit
        max_position = max(weights.values()) if weights else 0
        if max_position > self.limits.max_single_position:
            violations.append({
                'type': 'single_position',
                'value': max_position,
                'limit': self.limits.max_single_position,
                'excess': max_position - self.limits.max_single_position
            })
        
        # Check sector exposure
        sector_exposure = {}
        for symbol, pos in positions.items():
            sector = pos.get('sector', 'Unknown')
            sector_exposure[sector] = sector_exposure.get(sector, 0) + weights[symbol]
        
        max_sector = max(sector_exposure.values()) if sector_exposure else 0
        if max_sector > self.limits.max_sector_exposure:
            violations.append({
                'type': 'sector_exposure',
                'value': max_sector,
                'limit': self.limits.max_sector_exposure,
                'excess': max_sector - self.limits.max_sector_exposure
            })
        
        # Check top N concentration
        sorted_weights = sorted(weights.values(), reverse=True)
        
        top_5 = sum(sorted_weights[:5]) if len(sorted_weights) >= 5 else sum(sorted_weights)
        if top_5 > self.limits.max_top_5_concentration:
            violations.append({
                'type': 'top_5_concentration',
                'value': top_5,
                'limit': self.limits.max_top_5_concentration,
                'excess': top_5 - self.limits.max_top_5_concentration
            })
        
        top_10 = sum(sorted_weights[:10]) if len(sorted_weights) >= 10 else sum(sorted_weights)
        if top_10 > self.limits.max_top_10_concentration:
            violations.append({
                'type': 'top_10_concentration',
                'value': top_10,
                'limit': self.limits.max_top_10_concentration,
                'excess': top_10 - self.limits.max_top_10_concentration
            })
        
        metrics = {
            'max_single_position': max_position,
            'max_sector_exposure': max_sector,
            'top_5_concentration': top_5,
            'top_10_concentration': top_10,
            'herfindahl_index': sum(w**2 for w in weights.values()),
        }
        
        return {'violations': violations, 'metrics': metrics}
    
    def generate_rebalance_trades(
        self,
        positions: Dict[str, Dict],
        portfolio_value: float
    ) -> List[Dict]:
        """Generate trades to reduce concentration."""
        result = self.check_concentration(positions, portfolio_value)
        
        if not result['violations']:
            return []
        
        trades = []
        
        # Simple rebalancing: reduce oversized positions
        weights = {
            symbol: abs(pos['value']) / portfolio_value
            for symbol, pos in positions.items()
        }
        
        for symbol, weight in weights.items():
            if weight > self.limits.max_single_position:
                target_weight = self.limits.max_single_position * 0.95  # 5% buffer
                reduce_amount = (weight - target_weight) * portfolio_value
                
                trades.append({
                    'symbol': symbol,
                    'action': 'reduce',
                    'amount': reduce_amount,
                    'reason': 'single_position_limit'
                })
        
        return trades

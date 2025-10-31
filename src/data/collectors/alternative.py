"""
Alternative Data Collector
Collects alternative data sources: options flow, dark pool, insider trading
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from loguru import logger

class AlternativeDataCollector:
    """Collects alternative/non-traditional data"""

    def __init__(self):
        logger.info("Alternative data collector initialized")

    def get_options_flow(self, symbol: str, days_back: int = 1) -> pd.DataFrame:
        """
        Get unusual options activity
        
        Args:
            symbol: Stock symbol
            days_back: Days to look back
            
        Returns:
            DataFrame with options flow data
        """
        # In production, integrate with options data provider
        # For now, return placeholder
        
        logger.debug(f"Fetching options flow for {symbol}")
        
        data = {
            'timestamp': [datetime.now() - timedelta(hours=i) for i in range(10)],
            'strike': np.random.randint(90, 110, 10),
            'expiration': [(datetime.now() + timedelta(days=30)).date()] * 10,
            'type': np.random.choice(['call', 'put'], 10),
            'volume': np.random.randint(100, 10000, 10),
            'open_interest': np.random.randint(500, 50000, 10),
            'premium': np.random.uniform(0.5, 10, 10),
            'unusual': np.random.choice([True, False], 10, p=[0.2, 0.8])
        }
        
        df = pd.DataFrame(data)
        return df

    def get_dark_pool_activity(self, symbol: str) -> Dict:
        """
        Get dark pool trading data
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dict with dark pool metrics
        """
        logger.debug(f"Fetching dark pool data for {symbol}")
        
        # Placeholder data
        return {
            'symbol': symbol,
            'dark_pool_volume': np.random.randint(100000, 1000000),
            'dark_pool_pct': np.random.uniform(0.1, 0.4),
            'avg_trade_size': np.random.randint(1000, 10000),
            'net_sentiment': np.random.choice(['bullish', 'bearish', 'neutral']),
            'timestamp': datetime.now()
        }

    def get_insider_trading(self, symbol: str, days_back: int = 30) -> pd.DataFrame:
        """
        Get insider trading activity
        
        Args:
            symbol: Stock symbol
            days_back: Days to look back
            
        Returns:
            DataFrame with insider transactions
        """
        logger.debug(f"Fetching insider trading for {symbol}")
        
        # Placeholder data
        data = {
            'date': pd.date_range(end=datetime.now(), periods=5, freq='W'),
            'insider': ['CEO', 'CFO', 'Director', 'VP', '10% Owner'],
            'transaction': np.random.choice(['Buy', 'Sell'], 5),
            'shares': np.random.randint(1000, 100000, 5),
            'price': np.random.uniform(90, 110, 5),
            'value': [0] * 5
        }
        
        df = pd.DataFrame(data)
        df['value'] = df['shares'] * df['price']
        
        return df

    def get_short_interest(self, symbol: str) -> Dict:
        """
        Get short interest data
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dict with short interest metrics
        """
        logger.debug(f"Fetching short interest for {symbol}")
        
        return {
            'symbol': symbol,
            'short_interest': np.random.randint(1000000, 10000000),
            'short_pct_float': np.random.uniform(0.02, 0.25),
            'days_to_cover': np.random.uniform(0.5, 10),
            'short_interest_change': np.random.uniform(-0.2, 0.2),
            'timestamp': datetime.now()
        }

    def get_institutional_ownership(self, symbol: str) -> pd.DataFrame:
        """
        Get institutional ownership data
        
        Args:
            symbol: Stock symbol
            
        Returns:
            DataFrame with institutional holders
        """
        logger.debug(f"Fetching institutional ownership for {symbol}")
        
        data = {
            'institution': ['Vanguard', 'BlackRock', 'StateStreet', 'Fidelity', 'JPMorgan'],
            'shares': np.random.randint(1000000, 50000000, 5),
            'pct_ownership': np.random.uniform(1, 10, 5),
            'change_pct': np.random.uniform(-0.1, 0.1, 5),
            'value_usd': [0] * 5
        }
        
        df = pd.DataFrame(data)
        df['value_usd'] = df['shares'] * 100  # Assume $100 stock price
        
        return df

    def get_social_media_mentions(self, symbol: str, platform: str = 'twitter') -> Dict:
        """
        Get social media mention statistics
        
        Args:
            symbol: Stock symbol  
            platform: Social media platform
            
        Returns:
            Dict with social metrics
        """
        logger.debug(f"Fetching social media mentions for {symbol} on {platform}")
        
        return {
            'symbol': symbol,
            'platform': platform,
            'mentions_24h': np.random.randint(100, 10000),
            'mentions_7d': np.random.randint(1000, 50000),
            'sentiment_score': np.random.uniform(-1, 1),
            'trending_rank': np.random.randint(1, 100),
            'top_keywords': ['earnings', 'moon', 'buy', 'calls', 'puts'][:np.random.randint(2, 5)],
            'timestamp': datetime.now()
        }

    def get_earnings_estimates(self, symbol: str) -> Dict:
        """
        Get analyst earnings estimates
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dict with earnings estimates
        """
        logger.debug(f"Fetching earnings estimates for {symbol}")
        
        return {
            'symbol': symbol,
            'next_earnings_date': (datetime.now() + timedelta(days=30)).date(),
            'eps_estimate': np.random.uniform(1, 5),
            'eps_actual_last': np.random.uniform(1, 5),
            'revenue_estimate': np.random.uniform(1e9, 10e9),
            'num_analysts': np.random.randint(10, 40),
            'upgrades_3m': np.random.randint(0, 5),
            'downgrades_3m': np.random.randint(0, 5),
            'price_target_avg': np.random.uniform(90, 120),
            'price_target_high': np.random.uniform(120, 150),
            'price_target_low': np.random.uniform(70, 90)
        }

    def calculate_alternative_score(self, symbol: str) -> float:
        """
        Calculate composite alternative data score
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Score from -1 (bearish) to 1 (bullish)
        """
        # Collect all alternative data
        options = self.get_options_flow(symbol)
        dark_pool = self.get_dark_pool_activity(symbol)
        insider = self.get_insider_trading(symbol)
        short_int = self.get_short_interest(symbol)
        social = self.get_social_media_mentions(symbol)
        
        # Calculate component scores
        scores = []
        
        # Options flow score
        if not options.empty:
            unusual_calls = len(options[(options['type'] == 'call') & (options['unusual'])])
            unusual_puts = len(options[(options['type'] == 'put') & (options['unusual'])])
            options_score = (unusual_calls - unusual_puts) / max(len(options), 1)
            scores.append(options_score * 0.2)
        
        # Dark pool sentiment
        if dark_pool['net_sentiment'] == 'bullish':
            scores.append(0.15)
        elif dark_pool['net_sentiment'] == 'bearish':
            scores.append(-0.15)
        
        # Insider trading
        if not insider.empty:
            insider_buys = insider[insider['transaction'] == 'Buy']['value'].sum()
            insider_sells = insider[insider['transaction'] == 'Sell']['value'].sum()
            if insider_buys + insider_sells > 0:
                insider_score = (insider_buys - insider_sells) / (insider_buys + insider_sells)
                scores.append(insider_score * 0.25)
        
        # Short interest (inverse - high short can be bullish for squeeze)
        if short_int['short_pct_float'] > 0.15:
            scores.append(0.1)  # Potential squeeze
        elif short_int['short_pct_float'] > 0.1:
            scores.append(-0.1)  # High short interest bearish
        
        # Social sentiment
        scores.append(social['sentiment_score'] * 0.15)
        
        # Average all scores
        final_score = np.mean(scores) if scores else 0
        
        logger.debug(f"Alternative score for {symbol}: {final_score:.3f}")
        
        return float(np.clip(final_score, -1, 1))

"""
Signal Generator
Generates trading signals from various sources
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger

from src.trading.strategy.base import Signal

class SignalGenerator:
    """Generates trading signals"""

    def __init__(self):
        self.signal_history = []
        logger.info("Signal generator initialized")

    def generate_technical_signal(
        self,
        data: pd.DataFrame,
        symbol: str
    ) -> Optional[Signal]:
        """Generate signal from technical indicators"""
        if data.empty or len(data) < 50:
            return None
        
        latest = data.iloc[-1]
        
        # Extract indicators
        rsi = latest.get('rsi_14', 50)
        macd = latest.get('macd', 0)
        macd_signal = latest.get('macd_signal', 0)
        sma_50 = latest.get('sma_50', latest['close'])
        sma_200 = latest.get('sma_200', latest['close'])
        
        # Decision logic
        score = 0.0
        
        # RSI component
        if rsi < 30:
            score += 0.3  # Oversold
        elif rsi > 70:
            score -= 0.3  # Overbought
        
        # MACD component
        if macd > macd_signal:
            score += 0.2
        else:
            score -= 0.2
        
        # Moving average component
        if latest['close'] > sma_50 > sma_200:
            score += 0.3  # Strong uptrend
        elif latest['close'] < sma_50 < sma_200:
            score -= 0.3  # Strong downtrend
        
        # Determine action
        if score > 0.4:
            action = "buy"
        elif score < -0.4:
            action = "sell"
        else:
            action = "hold"
        
        signal = Signal(
            symbol=symbol,
            timestamp=datetime.now(),
            action=action,
            strength=min(abs(score), 1.0),
            confidence=0.7,
            metadata={'source': 'technical', 'score': score}
        )
        
        self.signal_history.append(signal)
        return signal

    def generate_momentum_signal(
        self,
        data: pd.DataFrame,
        symbol: str,
        lookback: int = 20
    ) -> Optional[Signal]:
        """Generate momentum-based signal"""
        if data.empty or len(data) < lookback:
            return None
        
        # Calculate momentum
        recent_prices = data['close'].iloc[-lookback:]
        momentum = (recent_prices.iloc[-1] / recent_prices.iloc[0] - 1) * 100
        
        # Calculate trend strength
        returns = recent_prices.pct_change()
        positive_days = (returns > 0).sum()
        trend_consistency = positive_days / lookback
        
        # Decision
        if momentum > 5 and trend_consistency > 0.6:
            action = "buy"
            strength = min(momentum / 10, 1.0)
            confidence = trend_consistency
        elif momentum < -5 and trend_consistency < 0.4:
            action = "sell"
            strength = min(abs(momentum) / 10, 1.0)
            confidence = 1 - trend_consistency
        else:
            action = "hold"
            strength = 0.3
            confidence = 0.5
        
        signal = Signal(
            symbol=symbol,
            timestamp=datetime.now(),
            action=action,
            strength=strength,
            confidence=confidence,
            metadata={'source': 'momentum', 'momentum_pct': momentum}
        )
        
        return signal

    def generate_volume_signal(
        self,
        data: pd.DataFrame,
        symbol: str
    ) -> Optional[Signal]:
        """Generate volume-based signal"""
        if data.empty or len(data) < 20:
            return None
        
        latest = data.iloc[-1]
        
        # Calculate volume metrics
        avg_volume = data['volume'].rolling(20).mean().iloc[-1]
        volume_ratio = latest['volume'] / avg_volume if avg_volume > 0 else 1
        
        # Price change
        price_change = (latest['close'] / latest['open'] - 1) * 100
        
        # Signal logic
        if volume_ratio > 2.0 and price_change > 2:
            action = "buy"
            strength = min(volume_ratio / 3, 1.0)
        elif volume_ratio > 2.0 and price_change < -2:
            action = "sell"
            strength = min(volume_ratio / 3, 1.0)
        else:
            action = "hold"
            strength = 0.3
        
        signal = Signal(
            symbol=symbol,
            timestamp=datetime.now(),
            action=action,
            strength=strength,
            confidence=0.6,
            metadata={'source': 'volume', 'volume_ratio': volume_ratio}
        )
        
        return signal

    def generate_mean_reversion_signal(
        self,
        data: pd.DataFrame,
        symbol: str,
        window: int = 20,
        std_threshold: float = 2.0
    ) -> Optional[Signal]:
        """Generate mean reversion signal"""
        if data.empty or len(data) < window:
            return None
        
        latest = data.iloc[-1]
        
        # Calculate Bollinger Bands
        sma = data['close'].rolling(window).mean().iloc[-1]
        std = data['close'].rolling(window).std().iloc[-1]
        
        upper_band = sma + (std_threshold * std)
        lower_band = sma - (std_threshold * std)
        
        # Distance from bands
        distance_upper = (latest['close'] - upper_band) / std if std > 0 else 0
        distance_lower = (lower_band - latest['close']) / std if std > 0 else 0
        
        # Signal logic
        if latest['close'] < lower_band:
            action = "buy"  # Oversold, expect reversion
            strength = min(abs(distance_lower) / 2, 1.0)
        elif latest['close'] > upper_band:
            action = "sell"  # Overbought, expect reversion
            strength = min(abs(distance_upper) / 2, 1.0)
        else:
            action = "hold"
            strength = 0.3
        
        signal = Signal(
            symbol=symbol,
            timestamp=datetime.now(),
            action=action,
            strength=strength,
            confidence=0.65,
            metadata={
                'source': 'mean_reversion',
                'upper_band': upper_band,
                'lower_band': lower_band
            }
        )
        
        return signal

    def generate_sentiment_signal(
        self,
        symbol: str,
        sentiment_score: float,
        confidence: float = 0.6
    ) -> Signal:
        """Generate signal from sentiment analysis"""
        # Sentiment score expected to be -1 to 1
        if sentiment_score > 0.3:
            action = "buy"
            strength = min(sentiment_score, 1.0)
        elif sentiment_score < -0.3:
            action = "sell"
            strength = min(abs(sentiment_score), 1.0)
        else:
            action = "hold"
            strength = 0.3
        
        signal = Signal(
            symbol=symbol,
            timestamp=datetime.now(),
            action=action,
            strength=strength,
            confidence=confidence,
            metadata={'source': 'sentiment', 'sentiment_score': sentiment_score}
        )
        
        return signal

    def generate_ml_signal(
        self,
        symbol: str,
        prediction: float,
        confidence: float
    ) -> Signal:
        """Generate signal from ML model prediction"""
        # Prediction is price direction probability (-1 to 1)
        if prediction > 0.2:
            action = "buy"
            strength = min(prediction, 1.0)
        elif prediction < -0.2:
            action = "sell"
            strength = min(abs(prediction), 1.0)
        else:
            action = "hold"
            strength = abs(prediction)
        
        signal = Signal(
            symbol=symbol,
            timestamp=datetime.now(),
            action=action,
            strength=strength,
            confidence=confidence,
            metadata={'source': 'ml_model', 'prediction': prediction}
        )
        
        return signal

    def get_signal_history(self, symbol: Optional[str] = None) -> List[Signal]:
        """Get signal history"""
        if symbol is None:
            return self.signal_history
        
        return [s for s in self.signal_history if s.symbol == symbol]

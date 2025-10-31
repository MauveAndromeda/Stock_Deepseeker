"""
Market Regime Detector
Detects different market regimes (bull, bear, sideways, volatile)
"""

import numpy as np
import pandas as pd
from typing import List, Tuple, Optional
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from loguru import logger


class MarketRegimeDetector:
    """Detects market regime using Hidden Markov Models and clustering"""

    def __init__(self, n_regimes: int = 3):
        """
        Args:
            n_regimes: Number of market regimes to detect
        """
        self.n_regimes = n_regimes
        self.model = None
        self.scaler = StandardScaler()
        self.regime_labels = ['Bullish', 'Bearish', 'Sideways']
        logger.info(f"Market regime detector initialized with {n_regimes} regimes")

    def fit(self, data: pd.DataFrame):
        """
        Fit regime detector on historical data
        
        Args:
            data: DataFrame with OHLCV and features
        """
        # Extract features
        features = self._extract_features(data)
        
        # Normalize features
        features_scaled = self.scaler.fit_transform(features)
        
        # Fit Gaussian Mixture Model
        self.model = GaussianMixture(
            n_components=self.n_regimes,
            covariance_type='full',
            max_iter=100,
            random_state=42
        )
        
        self.model.fit(features_scaled)
        
        logger.info("Regime detector fitted")

    def predict(self, data: pd.DataFrame) -> np.ndarray:
        """
        Predict regime for data
        
        Args:
            data: DataFrame with market data
            
        Returns:
            Array of regime labels (0, 1, 2, ...)
        """
        if self.model is None:
            raise ValueError("Model must be fitted before prediction")
        
        features = self._extract_features(data)
        features_scaled = self.scaler.transform(features)
        
        regimes = self.model.predict(features_scaled)
        
        return regimes

    def predict_current_regime(self, data: pd.DataFrame) -> Tuple[int, str, float]:
        """
        Predict current market regime
        
        Args:
            data: Recent market data
            
        Returns:
            (regime_id, regime_name, confidence)
        """
        if self.model is None:
            # If not fitted, use heuristic
            return self._heuristic_regime(data)
        
        features = self._extract_features(data)
        features_scaled = self.scaler.transform(features)
        
        # Get regime and probabilities
        regime = self.model.predict(features_scaled)[-1]
        proba = self.model.predict_proba(features_scaled)[-1]
        
        confidence = proba[regime]
        regime_name = self.regime_labels[regime] if regime < len(self.regime_labels) else f"Regime{regime}"
        
        return regime, regime_name, confidence

    def _extract_features(self, data: pd.DataFrame) -> np.ndarray:
        """
        Extract features for regime detection
        
        Args:
            data: Market data DataFrame
            
        Returns:
            Feature array
        """
        features = []
        
        # Calculate returns
        if 'close' in data.columns:
            returns = data['close'].pct_change()
            
            # Return statistics
            features.append(returns.rolling(20).mean().fillna(0))
            features.append(returns.rolling(20).std().fillna(0))
            features.append(returns.rolling(20).skew().fillna(0))
            features.append(returns.rolling(20).kurt().fillna(0))
        
        # Volatility
        if 'high' in data.columns and 'low' in data.columns:
            volatility = (data['high'] - data['low']) / data['close']
            features.append(volatility.rolling(20).mean().fillna(0))
        
        # Volume
        if 'volume' in data.columns:
            volume_ma = data['volume'].rolling(20).mean()
            volume_ratio = data['volume'] / volume_ma
            features.append(volume_ratio.fillna(1))
        
        # Trend strength
        if 'close' in data.columns:
            sma_20 = data['close'].rolling(20).mean()
            sma_50 = data['close'].rolling(50).mean()
            trend = (sma_20 - sma_50) / sma_50
            features.append(trend.fillna(0))
        
        # Stack features
        feature_matrix = np.column_stack(features)
        
        return feature_matrix

    def _heuristic_regime(self, data: pd.DataFrame) -> Tuple[int, str, float]:
        """
        Heuristic regime detection (when model not fitted)
        
        Args:
            data: Market data
            
        Returns:
            (regime_id, regime_name, confidence)
        """
        # Calculate returns and volatility
        returns = data['close'].pct_change().dropna()
        
        mean_return = returns.tail(20).mean()
        volatility = returns.tail(20).std()
        
        # Regime logic
        if mean_return > 0.001 and volatility < 0.02:
            regime = 0  # Bullish
            regime_name = "Bullish"
            confidence = 0.7
        elif mean_return < -0.001 and volatility < 0.02:
            regime = 1  # Bearish
            regime_name = "Bearish"
            confidence = 0.7
        elif volatility > 0.03:
            regime = 3  # Volatile
            regime_name = "Volatile"
            confidence = 0.6
        else:
            regime = 2  # Sideways
            regime_name = "Sideways"
            confidence = 0.6
        
        return regime, regime_name, confidence

    def analyze_regime_transitions(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Analyze regime transitions
        
        Args:
            data: Historical data
            
        Returns:
            DataFrame with regime transitions
        """
        regimes = self.predict(data)
        
        # Find transitions
        transitions = []
        prev_regime = regimes[0]
        
        for i, regime in enumerate(regimes[1:], 1):
            if regime != prev_regime:
                transitions.append({
                    'date': data.index[i],
                    'from_regime': prev_regime,
                    'to_regime': regime,
                    'from_name': self.regime_labels[prev_regime] if prev_regime < len(self.regime_labels) else f"Regime{prev_regime}",
                    'to_name': self.regime_labels[regime] if regime < len(self.regime_labels) else f"Regime{regime}"
                })
                prev_regime = regime
        
        return pd.DataFrame(transitions)

    def get_regime_statistics(self, data: pd.DataFrame, regimes: np.ndarray) -> Dict:
        """
        Calculate statistics for each regime
        
        Args:
            data: Market data
            regimes: Regime assignments
            
        Returns:
            Dict of regime statistics
        """
        stats = {}
        
        for regime_id in range(self.n_regimes):
            mask = regimes == regime_id
            regime_data = data[mask]
            
            if len(regime_data) > 0:
                returns = regime_data['close'].pct_change().dropna()
                
                stats[regime_id] = {
                    'name': self.regime_labels[regime_id] if regime_id < len(self.regime_labels) else f"Regime{regime_id}",
                    'count': len(regime_data),
                    'avg_return': returns.mean(),
                    'volatility': returns.std(),
                    'sharpe': returns.mean() / returns.std() if returns.std() > 0 else 0,
                    'max_drawdown': self._calculate_max_dd(regime_data['close'].values)
                }
        
        return stats

    @staticmethod
    def _calculate_max_dd(equity: np.ndarray) -> float:
        """Calculate maximum drawdown"""
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max
        return abs(np.min(drawdown))

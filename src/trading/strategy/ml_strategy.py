"""
Machine Learning Strategy Module

This module implements ML-based trading strategies that leverage:
- Transformer model predictions
- SAC (Soft Actor-Critic) agent decisions
- Ensemble model predictions
- Feature importance tracking and analysis

These strategies integrate deep learning models with traditional trading logic
to generate sophisticated trading signals.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .base import BaseStrategy, Position, PositionSide, SignalType, StrategyConfig

logger = logging.getLogger(__name__)


class MLStrategy(BaseStrategy):
    """
    Base Machine Learning Strategy

    Provides common functionality for ML-based strategies including
    model integration, feature preparation, and prediction handling.
    """

    def __init__(self, config: StrategyConfig):
        """Initialize ML strategy"""
        super().__init__(config)
        self.model = None
        self.feature_columns = config.parameters.get('feature_columns', [])
        self.prediction_threshold = config.parameters.get('prediction_threshold', 0.6)
        self.confidence_threshold = config.parameters.get('confidence_threshold', 0.7)
        self.lookback_window = config.parameters.get('lookback_window', 30)

        # Feature importance tracking
        self.feature_importance: Dict[str, float] = {}
        self.prediction_history: List[Dict[str, Any]] = []

    def prepare_features(self, data: pd.DataFrame) -> np.ndarray:
        """
        Prepare features for ML model

        Args:
            data: Market data DataFrame

        Returns:
            Feature array
        """
        if not self.feature_columns:
            # Use basic OHLCV features
            features = data[['open', 'high', 'low', 'close', 'volume']].values
        else:
            # Use specified features
            features = data[self.feature_columns].values

        # Handle NaN values
        features = np.nan_to_num(features, nan=0.0)

        return features

    def calculate_prediction_confidence(self, prediction: np.ndarray) -> float:
        """
        Calculate confidence score for prediction

        Args:
            prediction: Model prediction (probabilities or values)

        Returns:
            Confidence score (0 to 1)
        """
        if len(prediction.shape) == 1:
            # Single value prediction
            return abs(prediction[0])
        else:
            # Probability distribution
            return float(np.max(prediction))

    def track_prediction(self, symbol: str, prediction: Any, actual: Optional[float] = None) -> None:
        """
        Track prediction for performance analysis

        Args:
            symbol: Trading symbol
            prediction: Model prediction
            actual: Actual outcome (if available)
        """
        record = {
            'symbol': symbol,
            'timestamp': pd.Timestamp.now(),
            'prediction': prediction,
            'actual': actual,
        }
        self.prediction_history.append(record)

        # Keep only recent history
        if len(self.prediction_history) > 1000:
            self.prediction_history = self.prediction_history[-1000:]

    def update_feature_importance(self, importance_dict: Dict[str, float]) -> None:
        """
        Update feature importance scores

        Args:
            importance_dict: Dictionary of feature -> importance score
        """
        # Exponential moving average of importance
        alpha = 0.1
        for feature, importance in importance_dict.items():
            if feature in self.feature_importance:
                self.feature_importance[feature] = \
                    alpha * importance + (1 - alpha) * self.feature_importance[feature]
            else:
                self.feature_importance[feature] = importance

    def get_top_features(self, n: int = 10) -> List[Tuple[str, float]]:
        """
        Get top N most important features

        Args:
            n: Number of features to return

        Returns:
            List of (feature, importance) tuples
        """
        sorted_features = sorted(
            self.feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_features[:n]

    def analyze(self, data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """Analyze using ML model"""
        features = self.prepare_features(data)

        analysis = {
            'symbol': symbol,
            'feature_shape': features.shape,
            'top_features': self.get_top_features(5),
            'prediction_count': len(self.prediction_history),
        }

        return analysis

    def generate_signals(self, data: pd.DataFrame, symbol: str) -> SignalType:
        """Generate ML-based signals (to be implemented by subclasses)"""
        return SignalType.HOLD

    def execute(self, signal: SignalType, data: pd.DataFrame, symbol: str) -> Optional[Position]:
        """Execute ML signal"""
        current_price = data['close'].iloc[-1]

        # Close opposite positions
        if symbol in self.positions:
            position = self.positions[symbol]
            if (signal in [SignalType.SELL, SignalType.STRONG_SELL] and position.side == PositionSide.LONG) or \
               (signal in [SignalType.BUY, SignalType.STRONG_BUY] and position.side == PositionSide.SHORT):
                self.close_position(symbol, current_price, reason="ml_signal_reversal")
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
                metadata={'strategy': 'ml', 'signal_type': signal.name}
            )
        elif signal in [SignalType.SELL, SignalType.STRONG_SELL]:
            return self.open_position(
                symbol=symbol,
                side=PositionSide.SHORT,
                quantity=quantity,
                price=current_price,
                metadata={'strategy': 'ml', 'signal_type': signal.name}
            )

        return None


class TransformerStrategy(MLStrategy):
    """
    Transformer-based Trading Strategy

    Uses Transformer model predictions to generate trading signals.
    Integrates with TimeSeriesTransformer for sequence prediction.
    """

    def __init__(self, config: StrategyConfig):
        """Initialize Transformer strategy"""
        super().__init__(config)
        self.model_path = config.parameters.get('model_path', None)
        self.sequence_length = config.parameters.get('sequence_length', 60)
        self.prediction_horizon = config.parameters.get('prediction_horizon', 5)
        self.attention_threshold = config.parameters.get('attention_threshold', 0.5)

        # Initialize Transformer model (placeholder)
        self._initialize_model()

    def _initialize_model(self) -> None:
        """Initialize Transformer model"""
        try:
            # In practice, load the actual Transformer model
            # from src.models import TransformerPredictor
            # self.model = TransformerPredictor.load(self.model_path)
            self.logger.info("Transformer model initialized")
        except Exception as e:
            self.logger.error(f"Error initializing Transformer model: {e}")
            self.model = None

    def prepare_sequence(self, data: pd.DataFrame) -> np.ndarray:
        """
        Prepare sequence data for Transformer

        Args:
            data: Market data DataFrame

        Returns:
            Sequence array of shape (sequence_length, features)
        """
        if len(data) < self.sequence_length:
            # Pad if necessary
            pad_length = self.sequence_length - len(data)
            padding = np.zeros((pad_length, len(self.feature_columns) or 5))
            features = self.prepare_features(data)
            sequence = np.vstack([padding, features])
        else:
            features = self.prepare_features(data.iloc[-self.sequence_length:])
            sequence = features

        return sequence

    def predict_future_prices(self, data: pd.DataFrame) -> np.ndarray:
        """
        Predict future prices using Transformer

        Args:
            data: Market data DataFrame

        Returns:
            Predicted prices array
        """
        if self.model is None:
            # Return simple trend-based prediction as fallback
            recent_prices = data['close'].iloc[-self.prediction_horizon:].values
            trend = np.polyfit(range(len(recent_prices)), recent_prices, 1)[0]
            predictions = recent_prices[-1] + trend * np.arange(1, self.prediction_horizon + 1)
            return predictions

        # Prepare sequence
        sequence = self.prepare_sequence(data)

        # Get prediction from Transformer
        # In practice: predictions = self.model.predict(sequence)
        # Placeholder: use simple linear extrapolation
        recent_prices = data['close'].iloc[-self.prediction_horizon:].values
        trend = np.polyfit(range(len(recent_prices)), recent_prices, 1)[0]
        predictions = recent_prices[-1] + trend * np.arange(1, self.prediction_horizon + 1)

        return predictions

    def analyze_attention_weights(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze attention weights to understand model focus

        Args:
            data: Market data DataFrame

        Returns:
            Attention analysis
        """
        # Placeholder for attention weight analysis
        # In practice, extract and analyze attention weights from model
        analysis = {
            'high_attention_periods': [],
            'attention_score': 0.0,
            'focused_features': [],
        }

        return analysis

    def analyze(self, data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """Analyze using Transformer model"""
        base_analysis = super().analyze(data, symbol)

        # Get predictions
        predictions = self.predict_future_prices(data)
        current_price = data['close'].iloc[-1]

        # Analyze attention
        attention_analysis = self.analyze_attention_weights(data)

        # Calculate expected return
        expected_return = (predictions[-1] - current_price) / current_price

        analysis = {
            **base_analysis,
            'predictions': predictions.tolist(),
            'expected_return': expected_return,
            'prediction_trend': 'UP' if predictions[-1] > current_price else 'DOWN',
            'attention_analysis': attention_analysis,
        }

        return analysis

    def generate_signals(self, data: pd.DataFrame, symbol: str) -> SignalType:
        """Generate signals using Transformer predictions"""
        # Get price predictions
        predictions = self.predict_future_prices(data)
        current_price = data['close'].iloc[-1]

        # Calculate expected return
        expected_return = (predictions[-1] - current_price) / current_price

        # Calculate prediction confidence (based on trend consistency)
        prediction_trend = np.diff(predictions)
        trend_consistency = np.sum(prediction_trend > 0) / len(prediction_trend)

        # Strong signals require high confidence
        if expected_return > self.prediction_threshold and trend_consistency > self.confidence_threshold:
            return SignalType.STRONG_BUY

        elif expected_return > self.prediction_threshold * 0.5 and trend_consistency > 0.5:
            return SignalType.BUY

        elif expected_return < -self.prediction_threshold and trend_consistency < (1 - self.confidence_threshold):
            return SignalType.STRONG_SELL

        elif expected_return < -self.prediction_threshold * 0.5 and trend_consistency < 0.5:
            return SignalType.SELL

        return SignalType.HOLD


class SACStrategy(MLStrategy):
    """
    Soft Actor-Critic (SAC) based Trading Strategy

    Uses reinforcement learning agent to make trading decisions.
    The SAC agent learns optimal trading policies through interaction.
    """

    def __init__(self, config: StrategyConfig):
        """Initialize SAC strategy"""
        super().__init__(config)
        self.agent = None
        self.environment = None
        self.state_dim = config.parameters.get('state_dim', 20)
        self.action_space = config.parameters.get('action_space', 3)  # Buy, Sell, Hold
        self.model_path = config.parameters.get('model_path', None)

        # Initialize SAC agent
        self._initialize_agent()

    def _initialize_agent(self) -> None:
        """Initialize SAC agent and environment"""
        try:
            # In practice, load the actual SAC agent
            # from src.models import SACTradingAgent, TradingEnvironment
            # self.agent = SACTradingAgent.load(self.model_path)
            # self.environment = TradingEnvironment(...)
            self.logger.info("SAC agent initialized")
        except Exception as e:
            self.logger.error(f"Error initializing SAC agent: {e}")
            self.agent = None

    def prepare_state(self, data: pd.DataFrame, position: Optional[Position] = None) -> np.ndarray:
        """
        Prepare state representation for SAC agent

        Args:
            data: Market data DataFrame
            position: Current position (if any)

        Returns:
            State array
        """
        # Basic state features
        state_features = []

        # Price features
        close_prices = data['close'].iloc[-self.lookback_window:].values
        normalized_prices = (close_prices - close_prices.mean()) / (close_prices.std() + 1e-8)
        state_features.extend(normalized_prices[-5:])  # Last 5 normalized prices

        # Technical indicators
        returns = data['close'].pct_change().iloc[-self.lookback_window:].values
        state_features.append(np.mean(returns))
        state_features.append(np.std(returns))

        # Volatility
        volatility = data['close'].rolling(window=20).std().iloc[-1]
        state_features.append(volatility / data['close'].iloc[-1])

        # Volume
        volume_ratio = data['volume'].iloc[-1] / data['volume'].rolling(window=20).mean().iloc[-1]
        state_features.append(volume_ratio)

        # Position information
        if position and position.side != PositionSide.FLAT:
            state_features.append(1.0 if position.side == PositionSide.LONG else -1.0)
            state_features.append(position.get_return() / 100)
        else:
            state_features.extend([0.0, 0.0])

        # Pad or trim to state_dim
        state = np.array(state_features)
        if len(state) < self.state_dim:
            state = np.pad(state, (0, self.state_dim - len(state)))
        else:
            state = state[:self.state_dim]

        return state

    def get_agent_action(self, state: np.ndarray) -> Tuple[int, float]:
        """
        Get action from SAC agent

        Args:
            state: Current state

        Returns:
            Tuple of (action, confidence)
        """
        if self.agent is None:
            # Fallback to simple rule-based action
            # 0: Hold, 1: Buy, 2: Sell
            return 0, 0.5

        # In practice: action, confidence = self.agent.select_action(state)
        # Placeholder: random action
        action = np.random.choice([0, 1, 2])
        confidence = np.random.random()

        return action, confidence

    def analyze(self, data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """Analyze using SAC agent"""
        base_analysis = super().analyze(data, symbol)

        # Prepare state
        position = self.positions.get(symbol, None)
        state = self.prepare_state(data, position)

        # Get agent action
        action, confidence = self.get_agent_action(state)

        action_map = {0: 'HOLD', 1: 'BUY', 2: 'SELL'}

        analysis = {
            **base_analysis,
            'state_shape': state.shape,
            'agent_action': action_map[action],
            'action_confidence': confidence,
            'position_status': position.side.value if position else 'FLAT',
        }

        return analysis

    def generate_signals(self, data: pd.DataFrame, symbol: str) -> SignalType:
        """Generate signals using SAC agent"""
        # Prepare state
        position = self.positions.get(symbol, None)
        state = self.prepare_state(data, position)

        # Get action from agent
        action, confidence = self.get_agent_action(state)

        # Map action to signal
        # Action 0: Hold, 1: Buy, 2: Sell

        if action == 1:  # Buy
            if confidence > self.confidence_threshold:
                return SignalType.STRONG_BUY
            else:
                return SignalType.BUY

        elif action == 2:  # Sell
            if confidence > self.confidence_threshold:
                return SignalType.STRONG_SELL
            else:
                return SignalType.SELL

        return SignalType.HOLD

    def update_agent(self, state: np.ndarray, action: int, reward: float, next_state: np.ndarray) -> None:
        """
        Update SAC agent with experience

        Args:
            state: Current state
            action: Action taken
            reward: Reward received
            next_state: Next state
        """
        if self.agent is None:
            return

        # In practice: self.agent.update(state, action, reward, next_state)
        pass


class EnsembleStrategy(MLStrategy):
    """
    Ensemble ML Strategy

    Combines predictions from multiple models (Transformer, SAC, etc.)
    to generate robust trading signals with voting or weighted averaging.
    """

    def __init__(self, config: StrategyConfig):
        """Initialize ensemble strategy"""
        super().__init__(config)
        self.models: List[MLStrategy] = []
        self.model_weights: List[float] = config.parameters.get('model_weights', [])
        self.voting_method = config.parameters.get('voting_method', 'weighted')  # 'majority' or 'weighted'
        self.min_agreement = config.parameters.get('min_agreement', 0.6)

        # Initialize sub-strategies
        self._initialize_models()

    def _initialize_models(self) -> None:
        """Initialize ensemble models"""
        # Create sub-strategies
        # In practice, initialize multiple ML strategies

        self.logger.info(f"Initialized ensemble with {len(self.models)} models")

        # Set equal weights if not specified
        if not self.model_weights or len(self.model_weights) != len(self.models):
            self.model_weights = [1.0 / len(self.models)] * len(self.models)

    def add_model(self, model: MLStrategy, weight: float = 1.0) -> None:
        """
        Add a model to the ensemble

        Args:
            model: ML strategy to add
            weight: Model weight
        """
        self.models.append(model)
        self.model_weights.append(weight)

        # Normalize weights
        total_weight = sum(self.model_weights)
        self.model_weights = [w / total_weight for w in self.model_weights]

    def get_ensemble_predictions(self, data: pd.DataFrame, symbol: str) -> List[Tuple[SignalType, float]]:
        """
        Get predictions from all models

        Args:
            data: Market data DataFrame
            symbol: Trading symbol

        Returns:
            List of (signal, confidence) tuples
        """
        predictions = []

        for model in self.models:
            try:
                signal = model.generate_signals(data, symbol)
                # Estimate confidence based on model's internal state
                confidence = 0.7  # Placeholder
                predictions.append((signal, confidence))
            except Exception as e:
                self.logger.error(f"Error getting prediction from {model.__class__.__name__}: {e}")
                predictions.append((SignalType.HOLD, 0.0))

        return predictions

    def majority_voting(self, predictions: List[Tuple[SignalType, float]]) -> SignalType:
        """
        Use majority voting to combine predictions

        Args:
            predictions: List of (signal, confidence) tuples

        Returns:
            Final signal
        """
        signal_counts = {}

        for signal, _ in predictions:
            signal_counts[signal] = signal_counts.get(signal, 0) + 1

        # Find majority signal
        max_count = max(signal_counts.values())
        majority_signals = [s for s, c in signal_counts.items() if c == max_count]

        # If tie, prefer HOLD
        if len(majority_signals) > 1:
            return SignalType.HOLD if SignalType.HOLD in majority_signals else majority_signals[0]

        return majority_signals[0]

    def weighted_voting(self, predictions: List[Tuple[SignalType, float]]) -> SignalType:
        """
        Use weighted voting to combine predictions

        Args:
            predictions: List of (signal, confidence) tuples

        Returns:
            Final signal
        """
        # Map signals to scores
        signal_scores = {
            SignalType.STRONG_BUY: 2.0,
            SignalType.BUY: 1.0,
            SignalType.HOLD: 0.0,
            SignalType.SELL: -1.0,
            SignalType.STRONG_SELL: -2.0,
        }

        # Calculate weighted score
        total_score = 0.0
        total_weight = 0.0

        for (signal, confidence), weight in zip(predictions, self.model_weights):
            score = signal_scores[signal]
            total_score += score * weight * confidence
            total_weight += weight * confidence

        # Normalize
        if total_weight > 0:
            final_score = total_score / total_weight
        else:
            final_score = 0.0

        # Map score back to signal
        if final_score >= 1.5:
            return SignalType.STRONG_BUY
        elif final_score >= 0.5:
            return SignalType.BUY
        elif final_score <= -1.5:
            return SignalType.STRONG_SELL
        elif final_score <= -0.5:
            return SignalType.SELL
        else:
            return SignalType.HOLD

    def calculate_agreement(self, predictions: List[Tuple[SignalType, float]]) -> float:
        """
        Calculate agreement level among models

        Args:
            predictions: List of (signal, confidence) tuples

        Returns:
            Agreement score (0 to 1)
        """
        if not predictions:
            return 0.0

        # Count same signals
        signal_counts = {}
        for signal, _ in predictions:
            signal_counts[signal] = signal_counts.get(signal, 0) + 1

        # Agreement is the proportion of models agreeing on most common signal
        max_count = max(signal_counts.values())
        agreement = max_count / len(predictions)

        return agreement

    def analyze(self, data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """Analyze using ensemble models"""
        base_analysis = super().analyze(data, symbol)

        # Get predictions from all models
        predictions = self.get_ensemble_predictions(data, symbol)

        # Calculate agreement
        agreement = self.calculate_agreement(predictions)

        # Get individual model signals
        model_signals = {
            f"model_{i}": signal.name
            for i, (signal, _) in enumerate(predictions)
        }

        analysis = {
            **base_analysis,
            'ensemble_size': len(self.models),
            'model_signals': model_signals,
            'agreement': agreement,
            'voting_method': self.voting_method,
        }

        return analysis

    def generate_signals(self, data: pd.DataFrame, symbol: str) -> SignalType:
        """Generate ensemble signals"""
        # Get predictions from all models
        predictions = self.get_ensemble_predictions(data, symbol)

        # Check agreement
        agreement = self.calculate_agreement(predictions)

        # If low agreement, default to HOLD
        if agreement < self.min_agreement:
            self.logger.info(f"Low model agreement ({agreement:.2f}) for {symbol}, defaulting to HOLD")
            return SignalType.HOLD

        # Combine predictions
        if self.voting_method == 'majority':
            signal = self.majority_voting(predictions)
        else:  # weighted
            signal = self.weighted_voting(predictions)

        return signal

    def update_model_weights(self, performance_scores: List[float]) -> None:
        """
        Update model weights based on performance

        Args:
            performance_scores: Performance score for each model
        """
        if len(performance_scores) != len(self.models):
            self.logger.warning("Performance scores length mismatch")
            return

        # Normalize scores to weights
        total_score = sum(performance_scores)
        if total_score > 0:
            self.model_weights = [score / total_score for score in performance_scores]
        else:
            # Equal weights if all scores are zero or negative
            self.model_weights = [1.0 / len(self.models)] * len(self.models)

        self.logger.info(f"Updated model weights: {self.model_weights}")

    def get_model_performance(self) -> Dict[str, float]:
        """
        Get performance metrics for each model

        Returns:
            Dictionary of model name -> performance score
        """
        performance = {}

        for i, model in enumerate(self.models):
            model_name = f"{model.__class__.__name__}_{i}"
            # Use model's performance metrics
            if hasattr(model, 'performance'):
                performance[model_name] = model.performance.total_return
            else:
                performance[model_name] = 0.0

        return performance

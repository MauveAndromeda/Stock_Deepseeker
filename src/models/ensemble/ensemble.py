"""
Ensemble Model
Combines predictions from multiple models
"""

import numpy as np
from typing import List, Dict, Optional
from loguru import logger


class EnsembleModel:
    """Ensemble of multiple models"""

    def __init__(self, models: List, weights: Optional[List[float]] = None):
        """
        Args:
            models: List of models
            weights: Optional weights for each model
        """
        self.models = models
        
        if weights is None:
            self.weights = [1.0 / len(models)] * len(models)
        else:
            total = sum(weights)
            self.weights = [w / total for w in weights]
        
        logger.info(f"Ensemble initialized with {len(models)} models")

    def predict(self, X):
        """Make ensemble prediction"""
        predictions = []
        
        for model in self.models:
            try:
                pred = model.predict(X)
                predictions.append(pred)
            except Exception as e:
                logger.error(f"Model prediction failed: {e}")
                continue
        
        if not predictions:
            return None
        
        # Weighted average
        weighted_pred = np.average(predictions, axis=0, weights=self.weights[:len(predictions)])
        
        return weighted_pred

    def predict_with_confidence(self, X):
        """Predict with confidence estimate"""
        predictions = []
        
        for model in self.models:
            pred = model.predict(X)
            predictions.append(pred)
        
        # Average prediction
        avg_pred = np.mean(predictions, axis=0)
        
        # Confidence based on agreement
        std_pred = np.std(predictions, axis=0)
        confidence = 1.0 / (1.0 + std_pred)
        
        return avg_pred, confidence

    def add_model(self, model, weight: float = 1.0):
        """Add a model to ensemble"""
        self.models.append(model)
        
        # Recalculate weights
        total = sum(self.weights) + weight
        self.weights.append(weight / total)
        self.weights = [w * total / (total) for w in self.weights[:-1]] + [weight / total]

    def remove_model(self, index: int):
        """Remove a model from ensemble"""
        if 0 <= index < len(self.models):
            del self.models[index]
            del self.weights[index]
            
            # Renormalize weights
            total = sum(self.weights)
            self.weights = [w / total for w in self.weights]

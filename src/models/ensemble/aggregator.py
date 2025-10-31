"""
Model Aggregator
Aggregates predictions from various model types
"""

import numpy as np
from typing import Dict, List
from loguru import logger


class ModelAggregator:
    """Aggregates predictions from multiple model types"""

    def __init__(self):
        self.predictions = {}
        self.weights = {
            'transformer': 0.4,
            'sac': 0.3,
            'traditional': 0.2,
            'llm': 0.1
        }
        logger.info("Model aggregator initialized")

    def add_prediction(self, model_type: str, prediction: float, confidence: float = 1.0):
        """Add a prediction"""
        self.predictions[model_type] = {
            'prediction': prediction,
            'confidence': confidence
        }

    def aggregate(self) -> float:
        """Aggregate all predictions"""
        if not self.predictions:
            return 0.0
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for model_type, data in self.predictions.items():
            weight = self.weights.get(model_type, 0.1) * data['confidence']
            weighted_sum += data['prediction'] * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        return weighted_sum / total_weight

    def get_consensus(self) -> str:
        """Get consensus direction"""
        agg_pred = self.aggregate()
        
        if agg_pred > 0.2:
            return 'buy'
        elif agg_pred < -0.2:
            return 'sell'
        else:
            return 'hold'

    def clear(self):
        """Clear all predictions"""
        self.predictions = {}

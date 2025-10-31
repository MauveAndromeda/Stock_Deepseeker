"""
集成模型系统
组合多个模型进行预测
"""

import torch
import numpy as np
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum


class EnsembleMethod(Enum):
    """集成方法"""
    AVERAGE = "average"
    WEIGHTED_AVERAGE = "weighted_average"
    VOTING = "voting"
    STACKING = "stacking"
    BOOSTING = "boosting"


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    model: Any
    weight: float = 1.0
    enabled: bool = True
    performance_metrics: Dict[str, float] = None


class ModelRegistry:
    """模型注册表"""

    def __init__(self):
        self._models: Dict[str, ModelInfo] = {}

    def register(
        self,
        name: str,
        model: Any,
        weight: float = 1.0,
        performance_metrics: Optional[Dict[str, float]] = None
    ):
        """注册模型"""
        self._models[name] = ModelInfo(
            name=name,
            model=model,
            weight=weight,
            performance_metrics=performance_metrics or {}
        )

    def unregister(self, name: str):
        """注销模型"""
        if name in self._models:
            del self._models[name]

    def get(self, name: str) -> Optional[ModelInfo]:
        """获取模型"""
        return self._models.get(name)

    def get_all(self) -> Dict[str, ModelInfo]:
        """获取所有模型"""
        return self._models.copy()

    def get_enabled(self) -> Dict[str, ModelInfo]:
        """获取启用的模型"""
        return {k: v for k, v in self._models.items() if v.enabled}

    def enable(self, name: str):
        """启用模型"""
        if name in self._models:
            self._models[name].enabled = True

    def disable(self, name: str):
        """禁用模型"""
        if name in self._models:
            self._models[name].enabled = False

    def update_weight(self, name: str, weight: float):
        """更新权重"""
        if name in self._models:
            self._models[name].weight = weight

    def update_performance(self, name: str, metrics: Dict[str, float]):
        """更新性能指标"""
        if name in self._models:
            self._models[name].performance_metrics = metrics


class EnsembleModel:
    """集成模型"""

    def __init__(
        self,
        registry: ModelRegistry,
        method: EnsembleMethod = EnsembleMethod.WEIGHTED_AVERAGE
    ):
        self.registry = registry
        self.method = method

    def predict(self, *args, **kwargs) -> Dict[str, Any]:
        """
        集成预测

        Returns:
            包含预测结果和元数据的字典
        """
        models = self.registry.get_enabled()

        if not models:
            raise ValueError("No enabled models in registry")

        predictions = {}
        weights = {}

        # 收集所有模型的预测
        for name, model_info in models.items():
            try:
                pred = model_info.model.predict(*args, **kwargs)
                predictions[name] = pred
                weights[name] = model_info.weight
            except Exception as e:
                print(f"Error predicting with model {name}: {e}")
                continue

        if not predictions:
            raise RuntimeError("All models failed to predict")

        # 根据方法集成预测
        if self.method == EnsembleMethod.AVERAGE:
            result = self._average(predictions)
        elif self.method == EnsembleMethod.WEIGHTED_AVERAGE:
            result = self._weighted_average(predictions, weights)
        elif self.method == EnsembleMethod.VOTING:
            result = self._voting(predictions)
        else:
            result = self._weighted_average(predictions, weights)

        return {
            "prediction": result,
            "individual_predictions": predictions,
            "weights": weights,
            "method": self.method.value
        }

    def _average(self, predictions: Dict[str, Any]) -> Any:
        """简单平均"""
        # 假设预测是数值型
        values = list(predictions.values())

        if isinstance(values[0], (int, float)):
            return sum(values) / len(values)
        elif isinstance(values[0], np.ndarray):
            return np.mean(values, axis=0)
        elif isinstance(values[0], torch.Tensor):
            return torch.mean(torch.stack(values), dim=0)
        else:
            # 对于其他类型，返回第一个预测
            return values[0]

    def _weighted_average(self, predictions: Dict[str, Any], weights: Dict[str, float]) -> Any:
        """加权平均"""
        total_weight = sum(weights.values())

        if total_weight == 0:
            return self._average(predictions)

        # 归一化权重
        normalized_weights = {k: v / total_weight for k, v in weights.items()}

        # 计算加权和
        result = None
        for name, pred in predictions.items():
            weight = normalized_weights.get(name, 0)

            if isinstance(pred, (int, float)):
                if result is None:
                    result = pred * weight
                else:
                    result += pred * weight
            elif isinstance(pred, np.ndarray):
                if result is None:
                    result = pred * weight
                else:
                    result += pred * weight
            elif isinstance(pred, torch.Tensor):
                if result is None:
                    result = pred * weight
                else:
                    result += pred * weight

        return result

    def _voting(self, predictions: Dict[str, Any]) -> Any:
        """投票法（用于分类）"""
        # 统计每个预测结果的出现次数
        votes = {}

        for pred in predictions.values():
            if isinstance(pred, (list, tuple)):
                pred = tuple(pred)

            votes[pred] = votes.get(pred, 0) + 1

        # 返回票数最多的预测
        return max(votes.items(), key=lambda x: x[1])[0]


# 辅助函数

def adaptive_weighting(
    models: Dict[str, ModelInfo],
    metric: str = "accuracy",
    method: str = "softmax"
) -> Dict[str, float]:
    """
    根据性能指标自适应调整权重

    Args:
        models: 模型字典
        metric: 性能指标名称
        method: 权重计算方法 (softmax, linear, rank)

    Returns:
        权重字典
    """
    scores = {}

    for name, model_info in models.items():
        if model_info.performance_metrics and metric in model_info.performance_metrics:
            scores[name] = model_info.performance_metrics[metric]
        else:
            scores[name] = 0.0

    if not scores or max(scores.values()) == 0:
        # 如果没有性能指标，使用均匀权重
        return {name: 1.0 / len(models) for name in models}

    if method == "softmax":
        # Softmax权重
        exp_scores = {k: np.exp(v) for k, v in scores.items()}
        total = sum(exp_scores.values())
        weights = {k: v / total for k, v in exp_scores.items()}

    elif method == "linear":
        # 线性归一化
        total = sum(scores.values())
        if total > 0:
            weights = {k: v / total for k, v in scores.items()}
        else:
            weights = {name: 1.0 / len(models) for name in models}

    elif method == "rank":
        # 基于排名的权重
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        ranks = {name: i + 1 for i, (name, _) in enumerate(sorted_scores)}
        rank_weights = {name: 1.0 / rank for name, rank in ranks.items()}
        total = sum(rank_weights.values())
        weights = {k: v / total for k, v in rank_weights.items()}

    else:
        weights = {name: 1.0 / len(models) for name in models}

    return weights

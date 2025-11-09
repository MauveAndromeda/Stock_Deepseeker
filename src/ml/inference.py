"""
模型推理模块
用于生产环境的模型预测
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn


@dataclass
class PredictionResult:
    """预测结果"""
    predictions: np.ndarray
    confidence: np.ndarray
    timestamp: datetime = field(default_factory=datetime.now)
    model_version: str = "1.0.0"
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelInference:
    """模型推理"""

    def __init__(
        self,
        model: nn.Module,
        device: str = "cpu",
        model_version: str = "1.0.0"
    ):
        """
        初始化推理引擎

        Args:
            model: PyTorch模型
            device: 设备（cpu或cuda）
            model_version: 模型版本
        """
        self.model = model
        self.device = torch.device(device)
        self.model.to(self.device)
        self.model.eval()
        self.model_version = model_version

        # 推理统计
        self.inference_count = 0
        self.total_inference_time = 0.0

    def predict(
        self,
        X: np.ndarray,
        return_confidence: bool = False
    ) -> PredictionResult:
        """
        批量预测

        Args:
            X: 输入特征
            return_confidence: 是否返回置信度

        Returns:
            预测结果
        """
        start_time = datetime.now()

        X_tensor = torch.FloatTensor(X).to(self.device)

        with torch.no_grad():
            outputs = self.model(X_tensor)
            predictions = outputs.cpu().numpy()

            # 计算置信度
            if return_confidence:
                # 对于分类问题，使用softmax概率作为置信度
                if len(predictions.shape) > 1 and predictions.shape[1] > 1:
                    probas = torch.softmax(outputs, dim=1).cpu().numpy()
                    confidence = np.max(probas, axis=1)
                else:
                    # 对于回归或二分类，使用sigmoid
                    probas = torch.sigmoid(outputs).cpu().numpy()
                    confidence = np.abs(probas - 0.5) * 2  # 映射到[0, 1]
            else:
                confidence = np.ones(len(predictions))

        # 更新统计
        self.inference_count += len(X)
        inference_time = (datetime.now() - start_time).total_seconds()
        self.total_inference_time += inference_time

        return PredictionResult(
            predictions=predictions,
            confidence=confidence.flatten() if confidence.ndim > 1 else confidence,
            model_version=self.model_version,
            metadata={
                "inference_time": inference_time,
                "batch_size": len(X),
                "device": str(self.device)
            }
        )

    def predict_single(self, x: np.ndarray) -> tuple[float, float]:
        """
        单个样本预测

        Args:
            x: 单个样本特征

        Returns:
            (预测值, 置信度)
        """
        # 确保是2D数组
        if x.ndim == 1:
            x = x.reshape(1, -1)

        result = self.predict(x, return_confidence=True)

        return result.predictions[0], result.confidence[0]

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        预测概率（用于分类问题）

        Args:
            X: 输入特征

        Returns:
            概率数组
        """
        X_tensor = torch.FloatTensor(X).to(self.device)

        with torch.no_grad():
            outputs = self.model(X_tensor)

            # 对于多分类
            if len(outputs.shape) > 1 and outputs.shape[1] > 1:
                probas = torch.softmax(outputs, dim=1).cpu().numpy()
            else:
                # 对于二分类
                probas = torch.sigmoid(outputs).cpu().numpy()

        return probas

    def predict_batch_streaming(
        self,
        X: np.ndarray,
        batch_size: int = 32
    ) -> list[PredictionResult]:
        """
        流式批量预测（用于大规模数据）

        Args:
            X: 输入特征
            batch_size: 批大小

        Returns:
            预测结果列表
        """
        results = []

        for i in range(0, len(X), batch_size):
            batch = X[i:i + batch_size]
            result = self.predict(batch, return_confidence=True)
            results.append(result)

        return results

    def get_statistics(self) -> dict[str, Any]:
        """获取推理统计"""
        avg_time = self.total_inference_time / self.inference_count if self.inference_count > 0 else 0

        return {
            "total_inferences": self.inference_count,
            "total_time": self.total_inference_time,
            "avg_inference_time": avg_time,
            "throughput": self.inference_count / self.total_inference_time if self.total_inference_time > 0 else 0,
            "model_version": self.model_version
        }


class EnsembleInference:
    """集成模型推理"""

    def __init__(
        self,
        models: list[nn.Module],
        weights: list[float] | None = None,
        device: str = "cpu",
        aggregation: str = "average"
    ):
        """
        初始化集成推理

        Args:
            models: 模型列表
            weights: 模型权重
            device: 设备
            aggregation: 聚合方法（average, voting, weighted）
        """
        self.models = models
        self.device = torch.device(device)
        self.aggregation = aggregation

        # 设置权重
        if weights is None:
            self.weights = [1.0 / len(models)] * len(models)
        else:
            self.weights = weights

        # 将模型移到设备并设置为评估模式
        for model in self.models:
            model.to(self.device)
            model.eval()

    def predict(
        self,
        X: np.ndarray,
        return_confidence: bool = False
    ) -> PredictionResult:
        """
        集成预测

        Args:
            X: 输入特征
            return_confidence: 是否返回置信度

        Returns:
            预测结果
        """
        X_tensor = torch.FloatTensor(X).to(self.device)

        predictions_list = []

        with torch.no_grad():
            for model in self.models:
                outputs = model(X_tensor)
                predictions = outputs.cpu().numpy()
                predictions_list.append(predictions)

        # 聚合预测
        if self.aggregation in {"average", "weighted"}:
            # 加权平均
            weighted_preds = [p * w for p, w in zip(predictions_list, self.weights)]
            final_predictions = np.sum(weighted_preds, axis=0)

        elif self.aggregation == "voting":
            # 投票（用于分类）
            predictions_array = np.array(predictions_list)
            final_predictions = np.median(predictions_array, axis=0)

        else:
            # 默认简单平均
            final_predictions = np.mean(predictions_list, axis=0)

        # 计算置信度（预测的标准差的倒数）
        if return_confidence:
            predictions_std = np.std(predictions_list, axis=0)
            # 标准差越小，置信度越高
            confidence = 1.0 / (1.0 + predictions_std)
        else:
            confidence = np.ones(len(final_predictions))

        return PredictionResult(
            predictions=final_predictions,
            confidence=confidence.flatten() if confidence.ndim > 1 else confidence,
            model_version="ensemble",
            metadata={
                "num_models": len(self.models),
                "aggregation": self.aggregation
            }
        )


class ModelLoader:
    """模型加载器"""

    @staticmethod
    def load_pytorch_model(
        model_path: str,
        model_class: type,
        model_kwargs: dict | None = None
    ) -> nn.Module:
        """
        加载PyTorch模型

        Args:
            model_path: 模型文件路径
            model_class: 模型类
            model_kwargs: 模型初始化参数

        Returns:
            加载的模型
        """
        model_kwargs = model_kwargs or {}

        # 创建模型实例
        model = model_class(**model_kwargs)

        # 加载权重
        checkpoint = torch.load(model_path, map_location="cpu")

        if isinstance(checkpoint, dict):
            if "model_state_dict" in checkpoint:
                model.load_state_dict(checkpoint["model_state_dict"])
            elif "state_dict" in checkpoint:
                model.load_state_dict(checkpoint["state_dict"])
            else:
                model.load_state_dict(checkpoint)
        else:
            model.load_state_dict(checkpoint)

        model.eval()

        return model

    @staticmethod
    def load_checkpoint(checkpoint_path: str) -> dict:
        """
        加载完整的检查点

        Args:
            checkpoint_path: 检查点路径

        Returns:
            检查点字典
        """
        return torch.load(checkpoint_path, map_location="cpu")

    @staticmethod
    def save_model(
        model: nn.Module,
        save_path: str,
        metadata: dict | None = None
    ) -> None:
        """
        保存模型

        Args:
            model: 模型
            save_path: 保存路径
            metadata: 元数据
        """
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        checkpoint = {
            "model_state_dict": model.state_dict(),
            "timestamp": datetime.now().isoformat()
        }

        if metadata:
            checkpoint["metadata"] = metadata

        torch.save(checkpoint, save_path)


class InferenceCache:
    """推理缓存"""

    def __init__(self, max_size: int = 1000):
        """
        初始化缓存

        Args:
            max_size: 最大缓存大小
        """
        self.max_size = max_size
        self.cache: dict[str, PredictionResult] = {}
        self.access_count: dict[str, int] = {}

    def _get_key(self, X: np.ndarray) -> str:
        """生成缓存键"""
        return str(hash(X.tobytes()))

    def get(self, X: np.ndarray) -> PredictionResult | None:
        """
        获取缓存的预测

        Args:
            X: 输入特征

        Returns:
            预测结果（如果缓存命中）
        """
        key = self._get_key(X)

        if key in self.cache:
            self.access_count[key] = self.access_count.get(key, 0) + 1
            return self.cache[key]

        return None

    def put(self, X: np.ndarray, result: PredictionResult):
        """
        缓存预测结果

        Args:
            X: 输入特征
            result: 预测结果
        """
        key = self._get_key(X)

        # 如果缓存已满，删除最少使用的项
        if len(self.cache) >= self.max_size:
            lru_key = min(self.access_count, key=self.access_count.get)
            del self.cache[lru_key]
            del self.access_count[lru_key]

        self.cache[key] = result
        self.access_count[key] = 1

    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.access_count.clear()

    def get_statistics(self) -> dict[str, int]:
        """获取缓存统计"""
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "total_accesses": sum(self.access_count.values())
        }


class CachedModelInference(ModelInference):
    """带缓存的模型推理"""

    def __init__(
        self,
        model: nn.Module,
        device: str = "cpu",
        model_version: str = "1.0.0",
        cache_size: int = 1000
    ):
        """
        初始化带缓存的推理

        Args:
            model: PyTorch模型
            device: 设备
            model_version: 模型版本
            cache_size: 缓存大小
        """
        super().__init__(model, device, model_version)
        self.cache = InferenceCache(max_size=cache_size)
        self.cache_hits = 0
        self.cache_misses = 0

    def predict(
        self,
        X: np.ndarray,
        return_confidence: bool = False,
        use_cache: bool = True
    ) -> PredictionResult:
        """
        预测（带缓存）

        Args:
            X: 输入特征
            return_confidence: 是否返回置信度
            use_cache: 是否使用缓存

        Returns:
            预测结果
        """
        if use_cache:
            # 尝试从缓存获取
            cached_result = self.cache.get(X)

            if cached_result is not None:
                self.cache_hits += 1
                return cached_result

            self.cache_misses += 1

        # 缓存未命中，执行推理
        result = super().predict(X, return_confidence)

        # 缓存结果
        if use_cache:
            self.cache.put(X, result)

        return result

    def get_cache_statistics(self) -> dict[str, Any]:
        """获取缓存统计"""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0

        return {
            **self.cache.get_statistics(),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": hit_rate
        }

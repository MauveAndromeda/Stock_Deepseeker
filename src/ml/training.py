"""
模型训练模块
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class TrainingConfig:
    """训练配置"""
    batch_size: int = 128
    learning_rate: float = 0.001
    num_epochs: int = 100
    validation_split: float = 0.2
    early_stopping_patience: int = 10
    save_best_only: bool = True
    checkpoint_dir: str = "checkpoints"
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


class ModelTrainer:
    """模型训练器"""
    
    def __init__(self, config: TrainingConfig):
        self.config = config
        self.device = torch.device(config.device)
        self.history: Dict[str, List[float]] = {
            "train_loss": [],
            "val_loss": [],
            "train_acc": [],
            "val_acc": []
        }
        self.best_val_loss = float('inf')
        self.patience_counter = 0
    
    def prepare_data(
        self,
        X: np.ndarray,
        y: np.ndarray
    ) -> Tuple[DataLoader, DataLoader]:
        """准备数据"""
        # 划分训练集和验证集
        split_idx = int(len(X) * (1 - self.config.validation_split))
        
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        # 转换为Tensor
        X_train_tensor = torch.FloatTensor(X_train)
        y_train_tensor = torch.FloatTensor(y_train)
        X_val_tensor = torch.FloatTensor(X_val)
        y_val_tensor = torch.FloatTensor(y_val)
        
        # 创建DataLoader
        train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
        val_dataset = TensorDataset(X_val_tensor, y_val_tensor)
        
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True
        )
        
        val_loader = DataLoader(
            val_dataset,
            batch_size=self.config.batch_size,
            shuffle=False
        )
        
        return train_loader, val_loader
    
    def train(
        self,
        model: nn.Module,
        train_loader: DataLoader,
        val_loader: DataLoader,
        criterion: nn.Module,
        optimizer: optim.Optimizer
    ) -> Dict[str, List[float]]:
        """训练模型"""
        model = model.to(self.device)
        
        for epoch in range(self.config.num_epochs):
            # 训练阶段
            model.train()
            train_loss = 0.0
            train_correct = 0
            train_total = 0
            
            for batch_X, batch_y in train_loader:
                batch_X = batch_X.to(self.device)
                batch_y = batch_y.to(self.device)
                
                # 前向传播
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                
                # 反向传播
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                
                # 统计
                train_loss += loss.item()
                
                # 计算准确率（分类任务）
                if len(batch_y.shape) == 1 or batch_y.shape[1] == 1:
                    predicted = (outputs > 0.5).float()
                else:
                    _, predicted = torch.max(outputs.data, 1)
                    _, labels = torch.max(batch_y.data, 1)
                    batch_y = labels
                
                train_correct += (predicted == batch_y).sum().item()
                train_total += batch_y.size(0)
            
            avg_train_loss = train_loss / len(train_loader)
            train_acc = train_correct / train_total if train_total > 0 else 0
            
            # 验证阶段
            val_loss, val_acc = self.validate(model, val_loader, criterion)
            
            # 记录历史
            self.history["train_loss"].append(avg_train_loss)
            self.history["val_loss"].append(val_loss)
            self.history["train_acc"].append(train_acc)
            self.history["val_acc"].append(val_acc)
            
            # 打印进度
            print(f"Epoch [{epoch+1}/{self.config.num_epochs}] "
                  f"Train Loss: {avg_train_loss:.4f}, Train Acc: {train_acc:.4f}, "
                  f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f}")
            
            # 早停和保存
            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                self.patience_counter = 0
                if self.config.save_best_only:
                    self.save_checkpoint(model, epoch, val_loss)
            else:
                self.patience_counter += 1
                if self.patience_counter >= self.config.early_stopping_patience:
                    print(f"Early stopping at epoch {epoch+1}")
                    break
        
        return self.history
    
    def validate(
        self,
        model: nn.Module,
        val_loader: DataLoader,
        criterion: nn.Module
    ) -> Tuple[float, float]:
        """验证模型"""
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for batch_X, batch_y in val_loader:
                batch_X = batch_X.to(self.device)
                batch_y = batch_y.to(self.device)
                
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                
                val_loss += loss.item()
                
                if len(batch_y.shape) == 1 or batch_y.shape[1] == 1:
                    predicted = (outputs > 0.5).float()
                else:
                    _, predicted = torch.max(outputs.data, 1)
                    _, labels = torch.max(batch_y.data, 1)
                    batch_y = labels
                
                val_correct += (predicted == batch_y).sum().item()
                val_total += batch_y.size(0)
        
        avg_val_loss = val_loss / len(val_loader)
        val_acc = val_correct / val_total if val_total > 0 else 0
        
        return avg_val_loss, val_acc
    
    def save_checkpoint(
        self,
        model: nn.Module,
        epoch: int,
        val_loss: float
    ):
        """保存检查点"""
        checkpoint_dir = Path(self.config.checkpoint_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        checkpoint_path = checkpoint_dir / f"model_epoch_{epoch}_loss_{val_loss:.4f}.pt"
        
        torch.save({
            'epoch': epoch,
            'model_state_dict': model.state_dict(),
            'val_loss': val_loss,
            'history': self.history
        }, checkpoint_path)
        
        print(f"Checkpoint saved: {checkpoint_path}")


class ModelInference:
    """模型推理"""
    
    def __init__(self, model: nn.Module, device: str = "cpu"):
        self.model = model
        self.device = torch.device(device)
        self.model.to(self.device)
        self.model.eval()
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """预测"""
        X_tensor = torch.FloatTensor(X).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(X_tensor)
            predictions = outputs.cpu().numpy()
        
        return predictions
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """预测概率"""
        X_tensor = torch.FloatTensor(X).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(X_tensor)
            probas = torch.sigmoid(outputs).cpu().numpy()
        
        return probas


@dataclass
class PredictionResult:
    """预测结果"""
    predictions: np.ndarray
    confidence: np.ndarray
    timestamp: datetime = field(default_factory=datetime.now)
    model_version: str = "1.0.0"
    metadata: Dict[str, Any] = field(default_factory=dict)

"""
Stock Deepseeker - 机构级AI量化交易系统
================================================

基于最先进的AI技术（2025）的生产级量化交易平台

核心技术栈:
- Transformer架构用于市场预测
- SAC (Soft Actor-Critic) 强化学习
- ChatGPT-5 Nano API 用于市场分析
- 多智能体协作系统
- 高性能执行引擎
- 实时风险管理

版本: 3.0.0
作者: MauveAndromeda
许可: MIT
"""

__version__ = "3.0.0"
__author__ = "MauveAndromeda"

from src.core.config import Config
from src.core.logging import Logger
from src.core.exceptions import *

__all__ = [
    "Config",
    "Logger",
    "__version__",
    "__author__",
]

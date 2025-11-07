"""
Model Unified (MU) Layer
统一的模型调用接口，支持多个LLM提供商

Research-grade implementation (Under Development)
Not ready for production use
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import time
from loguru import logger
import os

# LangChain imports
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic


class ModelProvider(Enum):
    """LLM提供商"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    LOCAL = "local"


class ModelTier(Enum):
    """模型等级（用于成本和性能权衡）"""
    FAST = "fast"  # 快速低成本
    BALANCED = "balanced"  # 平衡
    PREMIUM = "premium"  # 高质量高成本


@dataclass
class ModelConfig:
    """模型配置"""
    provider: ModelProvider
    model_name: str
    tier: ModelTier
    max_tokens: int = 4096
    temperature: float = 0.7
    cost_per_1k_tokens: float = 0.0
    max_retries: int = 3
    timeout: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelResponse:
    """模型响应"""
    content: str
    provider: ModelProvider
    model: str
    tokens_used: int
    cost: float
    latency: float  # seconds
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class RateLimiter:
    """速率限制器"""

    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.calls = []

    async def acquire(self):
        """获取调用许可"""
        now = time.time()
        # 移除1分钟前的调用记录
        self.calls = [t for t in self.calls if now - t < 60]

        if len(self.calls) >= self.calls_per_minute:
            # 需要等待
            sleep_time = 60 - (now - self.calls[0])
            if sleep_time > 0:
                logger.warning(f"Rate limit reached, sleeping {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)

        self.calls.append(time.time())


class ModelUnified(ABC):
    """统一模型接口基类"""

    def __init__(self, config: ModelConfig):
        self.config = config
        self.rate_limiter = RateLimiter(calls_per_minute=60)
        self.total_tokens_used = 0
        self.total_cost = 0.0
        self.call_count = 0

    @abstractmethod
    async def generate(
        self,
        prompt: Union[str, List[Dict[str, str]]],
        **kwargs
    ) -> ModelResponse:
        """生成响应"""
        pass

    def _calculate_cost(self, tokens: int) -> float:
        """计算成本"""
        return (tokens / 1000) * self.config.cost_per_1k_tokens

    async def generate_with_retry(
        self,
        prompt: Union[str, List[Dict[str, str]]],
        **kwargs
    ) -> ModelResponse:
        """带重试的生成"""
        last_error = None

        for attempt in range(self.config.max_retries):
            try:
                await self.rate_limiter.acquire()
                response = await self.generate(prompt, **kwargs)

                # 更新统计
                self.total_tokens_used += response.tokens_used
                self.total_cost += response.cost
                self.call_count += 1

                return response

            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避

        raise Exception(f"Failed after {self.config.max_retries} retries: {last_error}")


class OpenAIModel(ModelUnified):
    """OpenAI模型实现"""

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")

        self.client = ChatOpenAI(
            model=config.model_name,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            api_key=api_key
        )

    async def generate(
        self,
        prompt: Union[str, List[Dict[str, str]]],
        **kwargs
    ) -> ModelResponse:
        """生成响应"""
        start_time = time.time()

        # 转换prompt为消息格式
        if isinstance(prompt, str):
            messages = [HumanMessage(content=prompt)]
        else:
            messages = []
            for msg in prompt:
                if msg['role'] == 'system':
                    messages.append(SystemMessage(content=msg['content']))
                elif msg['role'] == 'user':
                    messages.append(HumanMessage(content=msg['content']))
                elif msg['role'] == 'assistant':
                    messages.append(AIMessage(content=msg['content']))

        # 调用API
        response = await self.client.ainvoke(messages)

        latency = time.time() - start_time
        content = response.content

        # 估算token使用（实际应从response获取）
        tokens_used = len(content.split()) * 1.3  # 粗略估算
        cost = self._calculate_cost(tokens_used)

        return ModelResponse(
            content=content,
            provider=ModelProvider.OPENAI,
            model=self.config.model_name,
            tokens_used=int(tokens_used),
            cost=cost,
            latency=latency,
            metadata={'response_metadata': response.response_metadata}
        )


class AnthropicModel(ModelUnified):
    """Anthropic (Claude) 模型实现"""

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = ChatAnthropic(
            model=config.model_name,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            anthropic_api_key=api_key
        )

    async def generate(
        self,
        prompt: Union[str, List[Dict[str, str]]],
        **kwargs
    ) -> ModelResponse:
        """生成响应"""
        start_time = time.time()

        # 转换prompt
        if isinstance(prompt, str):
            messages = [HumanMessage(content=prompt)]
        else:
            messages = []
            for msg in prompt:
                if msg['role'] == 'system':
                    messages.append(SystemMessage(content=msg['content']))
                elif msg['role'] == 'user':
                    messages.append(HumanMessage(content=msg['content']))
                elif msg['role'] == 'assistant':
                    messages.append(AIMessage(content=msg['content']))

        response = await self.client.ainvoke(messages)
        latency = time.time() - start_time
        content = response.content

        tokens_used = len(content.split()) * 1.3
        cost = self._calculate_cost(tokens_used)

        return ModelResponse(
            content=content,
            provider=ModelProvider.ANTHROPIC,
            model=self.config.model_name,
            tokens_used=int(tokens_used),
            cost=cost,
            latency=latency
        )


class ModelRouter:
    """
    模型路由器
    根据任务类型、成本、延迟自动选择模型
    """

    def __init__(self):
        self.models: Dict[str, ModelUnified] = {}
        self.fallback_order: List[str] = []

        # 预定义的模型配置
        self.configs = {
            "gpt-4o-mini-fast": ModelConfig(
                provider=ModelProvider.OPENAI,
                model_name="gpt-4o-mini",
                tier=ModelTier.FAST,
                cost_per_1k_tokens=0.00015,
                temperature=0.7
            ),
            "gpt-4o-balanced": ModelConfig(
                provider=ModelProvider.OPENAI,
                model_name="gpt-4o",
                tier=ModelTier.BALANCED,
                cost_per_1k_tokens=0.005,
                temperature=0.7
            ),
            "claude-3-5-sonnet": ModelConfig(
                provider=ModelProvider.ANTHROPIC,
                model_name="claude-3-5-sonnet-20241022",
                tier=ModelTier.PREMIUM,
                cost_per_1k_tokens=0.003,
                temperature=0.7
            )
        }

    def register_model(self, name: str, model: ModelUnified):
        """注册模型"""
        self.models[name] = model
        logger.info(f"Registered model: {name}")

    def set_fallback_order(self, order: List[str]):
        """设置降级顺序"""
        self.fallback_order = order

    async def route(
        self,
        prompt: Union[str, List[Dict[str, str]]],
        tier: ModelTier = ModelTier.BALANCED,
        **kwargs
    ) -> ModelResponse:
        """
        路由请求到合适的模型

        Args:
            prompt: 提示词
            tier: 模型等级
            **kwargs: 其他参数

        Returns:
            模型响应
        """
        # 根据tier选择模型
        candidates = [
            name for name, model in self.models.items()
            if model.config.tier == tier
        ]

        if not candidates and self.fallback_order:
            candidates = self.fallback_order

        if not candidates:
            candidates = list(self.models.keys())

        if not candidates:
            raise ValueError("No models available")

        # 尝试调用模型
        for model_name in candidates:
            try:
                model = self.models[model_name]
                response = await model.generate_with_retry(prompt, **kwargs)
                return response
            except Exception as e:
                logger.error(f"Model {model_name} failed: {e}")
                continue

        raise Exception("All models failed")

    async def initialize_default_models(self):
        """初始化默认模型"""
        # 检查API密钥并初始化可用模型
        if os.getenv('OPENAI_API_KEY'):
            try:
                self.register_model(
                    "gpt-4o-mini",
                    OpenAIModel(self.configs["gpt-4o-mini-fast"])
                )
                logger.info("Initialized OpenAI models")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI: {e}")

        if os.getenv('ANTHROPIC_API_KEY'):
            try:
                self.register_model(
                    "claude-3-5-sonnet",
                    AnthropicModel(self.configs["claude-3-5-sonnet"])
                )
                logger.info("Initialized Anthropic models")
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic: {e}")

        # 设置降级顺序
        if self.models:
            self.set_fallback_order(list(self.models.keys()))

    def get_statistics(self) -> Dict[str, Any]:
        """获取使用统计"""
        stats = {}
        for name, model in self.models.items():
            stats[name] = {
                'call_count': model.call_count,
                'total_tokens': model.total_tokens_used,
                'total_cost': model.total_cost,
                'avg_cost_per_call': model.total_cost / model.call_count if model.call_count > 0 else 0
            }
        return stats


# 全局实例
_router = None


async def get_router() -> ModelRouter:
    """获取全局路由器实例"""
    global _router
    if _router is None:
        _router = ModelRouter()
        await _router.initialize_default_models()
    return _router

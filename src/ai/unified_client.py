"""
统一AI API客户端
支持多种AI模型：ChatGPT-5 Nano, Claude 4.5 Sonnet, Gemini等
用于市场分析、情绪分析、信号增强
"""

import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
from typing import Any

import aiohttp


class AIProvider(Enum):
    """AI服务提供商"""
    OPENAI = "openai"           # GPT-4, GPT-5 Nano
    ANTHROPIC = "anthropic"      # Claude 3.5/4.5 Sonnet
    GOOGLE = "google"            # Gemini
    DEEPSEEK = "deepseek"        # DeepSeek


@dataclass
class AIResponse:
    """AI响应数据类"""
    provider: AIProvider
    model: str
    content: str
    confidence: float
    tokens_used: int
    cost: float
    timestamp: datetime
    metadata: dict[str, Any]


class UnifiedAIClient:
    """统一的AI客户端"""

    def __init__(self):
        """初始化客户端"""
        self.api_keys = {
            AIProvider.OPENAI: os.getenv("OPENAI_API_KEY"),
            AIProvider.ANTHROPIC: os.getenv("ANTHROPIC_API_KEY"),
            AIProvider.GOOGLE: os.getenv("GOOGLE_API_KEY"),
            AIProvider.DEEPSEEK: os.getenv("DEEPSEEK_API_KEY")
        }

        # 模型配置
        self.models = {
            AIProvider.OPENAI: {
                "gpt-4o": {"max_tokens": 4096, "cost_per_1k": 0.005},
                "gpt-4o-mini": {"max_tokens": 4096, "cost_per_1k": 0.00015},
                "gpt-5-nano": {"max_tokens": 4096, "cost_per_1k": 0.0001}  # 假设的GPT-5 Nano
            },
            AIProvider.ANTHROPIC: {
                "claude-3-5-sonnet-20241022": {"max_tokens": 8192, "cost_per_1k": 0.003},
                "claude-4-5-sonnet-20250929": {"max_tokens": 8192, "cost_per_1k": 0.003}  # 假设的Claude 4.5
            },
            AIProvider.GOOGLE: {
                "gemini-1.5-pro": {"max_tokens": 8192, "cost_per_1k": 0.00125},
                "gemini-1.5-flash": {"max_tokens": 8192, "cost_per_1k": 0.000075}
            },
            AIProvider.DEEPSEEK: {
                "deepseek-chat": {"max_tokens": 4096, "cost_per_1k": 0.00014}
            }
        }

        # API端点
        self.endpoints = {
            AIProvider.OPENAI: "https://api.openai.com/v1/chat/completions",
            AIProvider.ANTHROPIC: "https://api.anthropic.com/v1/messages",
            AIProvider.GOOGLE: "https://generativelanguage.googleapis.com/v1beta/models",
            AIProvider.DEEPSEEK: "https://api.deepseek.com/v1/chat/completions"
        }

        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()

    async def analyze_market_sentiment(
        self,
        market_data: dict,
        news: list[str],
        provider: AIProvider = AIProvider.OPENAI,
        model: str | None = None
    ) -> AIResponse:
        """
        分析市场情绪

        Args:
            market_data: 市场数据
            news: 新闻列表
            provider: AI提供商
            model: 模型名称

        Returns:
            AI响应
        """
        # 自动选择模型
        if model is None:
            model = self._get_default_model(provider)

        # 构建提示词
        prompt = self._build_sentiment_prompt(market_data, news)

        # 调用API
        response = await self._call_api(provider, model, prompt)

        return response

    async def generate_trading_signal(
        self,
        market_data: dict,
        technical_indicators: dict,
        fundamental_data: dict,
        provider: AIProvider = AIProvider.OPENAI,
        model: str | None = None
    ) -> AIResponse:
        """
        生成交易信号

        Args:
            market_data: 市场数据
            technical_indicators: 技术指标
            fundamental_data: 基本面数据
            provider: AI提供商
            model: 模型名称

        Returns:
            AI响应（包含交易信号和置信度）
        """
        if model is None:
            model = self._get_default_model(provider)

        prompt = self._build_signal_prompt(
            market_data,
            technical_indicators,
            fundamental_data
        )

        response = await self._call_api(provider, model, prompt)

        return response

    async def analyze_risk(
        self,
        portfolio: dict,
        market_conditions: dict,
        provider: AIProvider = AIProvider.ANTHROPIC,
        model: str | None = None
    ) -> AIResponse:
        """
        风险分析

        Args:
            portfolio: 投资组合
            market_conditions: 市场条件
            provider: AI提供商
            model: 模型名称

        Returns:
            风险分析结果
        """
        if model is None:
            model = self._get_default_model(provider)

        prompt = self._build_risk_prompt(portfolio, market_conditions)

        response = await self._call_api(provider, model, prompt)

        return response

    def _get_default_model(self, provider: AIProvider) -> str:
        """获取默认模型"""
        defaults = {
            AIProvider.OPENAI: "gpt-4o-mini",
            AIProvider.ANTHROPIC: "claude-3-5-sonnet-20241022",
            AIProvider.GOOGLE: "gemini-1.5-flash",
            AIProvider.DEEPSEEK: "deepseek-chat"
        }
        return defaults.get(provider, "gpt-4o-mini")

    def _build_sentiment_prompt(
        self,
        market_data: dict,
        news: list[str]
    ) -> str:
        """构建情绪分析提示词"""
        prompt = f"""作为一个专业的金融分析师，分析以下市场数据和新闻，给出市场情绪评估。

市场数据:
- 价格变动: {market_data.get('price_change', 0):.2%}
- 成交量变化: {market_data.get('volume_change', 0):.2%}
- 波动率: {market_data.get('volatility', 0):.2%}

相关新闻:
{chr(10).join(f'- {n}' for n in news[:5])}

请以JSON格式返回分析结果，包含以下字段：
{{
    "sentiment": "bullish/bearish/neutral",
    "confidence": 0.0-1.0,
    "key_factors": ["因素1", "因素2", ...],
    "risk_level": "low/medium/high",
    "recommendation": "具体建议"
}}
"""
        return prompt

    def _build_signal_prompt(
        self,
        market_data: dict,
        technical_indicators: dict,
        fundamental_data: dict
    ) -> str:
        """构建交易信号提示词"""
        prompt = f"""作为量化交易专家，基于以下数据生成交易信号。

市场数据:
{json.dumps(market_data, indent=2, ensure_ascii=False)}

技术指标:
{json.dumps(technical_indicators, indent=2, ensure_ascii=False)}

基本面数据:
{json.dumps(fundamental_data, indent=2, ensure_ascii=False)}

请以JSON格式返回交易信号，包含：
{{
    "action": "BUY/SELL/HOLD",
    "confidence": 0.0-1.0,
    "position_size": 0.0-1.0,
    "stop_loss": 价格,
    "take_profit": 价格,
    "reasoning": "详细理由",
    "timeframe": "持仓时间预期"
}}
"""
        return prompt

    def _build_risk_prompt(
        self,
        portfolio: dict,
        market_conditions: dict
    ) -> str:
        """构建风险分析提示词"""
        prompt = f"""作为风险管理专家，评估当前投资组合的风险状况。

投资组合:
{json.dumps(portfolio, indent=2, ensure_ascii=False)}

市场条件:
{json.dumps(market_conditions, indent=2, ensure_ascii=False)}

请以JSON格式返回风险分析，包含：
{{
    "risk_score": 0-100,
    "main_risks": ["风险1", "风险2", ...],
    "suggested_actions": ["行动1", "行动2", ...],
    "hedging_strategies": ["对冲策略1", ...],
    "max_loss_estimate": 估计最大损失
}}
"""
        return prompt

    async def _call_api(
        self,
        provider: AIProvider,
        model: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> AIResponse:
        """
        调用AI API

        Args:
            provider: 提供商
            model: 模型名称
            prompt: 提示词
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            AI响应
        """
        api_key = self.api_keys.get(provider)
        if not api_key:
            raise ValueError(f"未设置 {provider.value} 的API密钥")

        if not self.session:
            self.session = aiohttp.ClientSession()

        if provider == AIProvider.OPENAI:
            return await self._call_openai(model, prompt, temperature, max_tokens)
        if provider == AIProvider.ANTHROPIC:
            return await self._call_anthropic(model, prompt, temperature, max_tokens)
        if provider == AIProvider.GOOGLE:
            return await self._call_google(model, prompt, temperature, max_tokens)
        if provider == AIProvider.DEEPSEEK:
            return await self._call_deepseek(model, prompt, temperature, max_tokens)
        raise ValueError(f"不支持的提供商: {provider}")

    async def _call_openai(
        self,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int
    ) -> AIResponse:
        """调用OpenAI API"""
        headers = {
            "Authorization": f"Bearer {self.api_keys[AIProvider.OPENAI]}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是一个专业的金融分析AI助手。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        async with self.session.post(
            self.endpoints[AIProvider.OPENAI],
            headers=headers,
            json=payload
        ) as response:
            result = await response.json()

            if "error" in result:
                raise Exception(f"OpenAI API错误: {result['error']}")

            content = result["choices"][0]["message"]["content"]
            tokens_used = result["usage"]["total_tokens"]

            # 计算成本
            cost_per_1k = self.models[AIProvider.OPENAI][model]["cost_per_1k"]
            cost = (tokens_used / 1000) * cost_per_1k

            return AIResponse(
                provider=AIProvider.OPENAI,
                model=model,
                content=content,
                confidence=0.9,  # OpenAI不返回置信度，使用默认值
                tokens_used=tokens_used,
                cost=cost,
                timestamp=datetime.now(),
                metadata=result
            )

    async def _call_anthropic(
        self,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int
    ) -> AIResponse:
        """调用Anthropic API"""
        headers = {
            "x-api-key": self.api_keys[AIProvider.ANTHROPIC],
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        async with self.session.post(
            self.endpoints[AIProvider.ANTHROPIC],
            headers=headers,
            json=payload
        ) as response:
            result = await response.json()

            if "error" in result:
                raise Exception(f"Anthropic API错误: {result['error']}")

            content = result["content"][0]["text"]
            tokens_used = result["usage"]["input_tokens"] + result["usage"]["output_tokens"]

            # 计算成本
            cost_per_1k = self.models[AIProvider.ANTHROPIC][model]["cost_per_1k"]
            cost = (tokens_used / 1000) * cost_per_1k

            return AIResponse(
                provider=AIProvider.ANTHROPIC,
                model=model,
                content=content,
                confidence=0.92,  # Claude通常更保守
                tokens_used=tokens_used,
                cost=cost,
                timestamp=datetime.now(),
                metadata=result
            )

    async def _call_google(
        self,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int
    ) -> AIResponse:
        """调用Google Gemini API"""
        # 简化实现
        raise NotImplementedError("Google Gemini API待实现")

    async def _call_deepseek(
        self,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int
    ) -> AIResponse:
        """调用DeepSeek API"""
        # 与OpenAI兼容的API
        headers = {
            "Authorization": f"Bearer {self.api_keys[AIProvider.DEEPSEEK]}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是一个专业的金融分析AI助手。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        async with self.session.post(
            self.endpoints[AIProvider.DEEPSEEK],
            headers=headers,
            json=payload
        ) as response:
            result = await response.json()

            if "error" in result:
                raise Exception(f"DeepSeek API错误: {result['error']}")

            content = result["choices"][0]["message"]["content"]
            tokens_used = result["usage"]["total_tokens"]

            cost_per_1k = self.models[AIProvider.DEEPSEEK][model]["cost_per_1k"]
            cost = (tokens_used / 1000) * cost_per_1k

            return AIResponse(
                provider=AIProvider.DEEPSEEK,
                model=model,
                content=content,
                confidence=0.88,
                tokens_used=tokens_used,
                cost=cost,
                timestamp=datetime.now(),
                metadata=result
            )

    def parse_json_response(self, content: str) -> dict:
        """
        解析JSON响应

        Args:
            content: AI返回的内容

        Returns:
            解析后的字典
        """
        try:
            # 尝试直接解析
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取JSON部分
            import re
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            raise ValueError("无法从响应中提取JSON")


# 使用示例
async def main():
    """示例用法"""
    async with UnifiedAIClient() as client:
        # 示例1: 市场情绪分析
        market_data = {
            "price_change": 0.025,
            "volume_change": 0.15,
            "volatility": 0.18
        }
        news = [
            "美联储宣布维持利率不变",
            "科技股财报超预期",
            "地缘政治紧张局势缓和"
        ]

        print("=" * 60)
        print("示例1: 市场情绪分析")
        print("=" * 60)

        # 使用GPT-4o-mini
        response = await client.analyze_market_sentiment(
            market_data,
            news,
            provider=AIProvider.OPENAI,
            model="gpt-4o-mini"
        )

        print(f"\n提供商: {response.provider.value}")
        print(f"模型: {response.model}")
        print(f"成本: ${response.cost:.4f}")
        print(f"Token使用: {response.tokens_used}")
        print(f"\n分析结果:\n{response.content}")

        # 解析JSON响应
        try:
            sentiment_data = client.parse_json_response(response.content)
            print(f"\n情绪: {sentiment_data.get('sentiment')}")
            print(f"置信度: {sentiment_data.get('confidence')}")
        except Exception as e:
            print(f"解析失败: {e}")

        # 示例2: 交易信号生成（使用Claude）
        print("\n" + "=" * 60)
        print("示例2: 交易信号生成 (Claude)")
        print("=" * 60)

        technical_indicators = {
            "RSI": 45,
            "MACD": 0.5,
            "SMA_50": 150.2,
            "SMA_200": 145.8
        }

        fundamental_data = {
            "PE_ratio": 18.5,
            "PB_ratio": 2.3,
            "ROE": 0.15
        }

        # 使用Claude
        try:
            response = await client.generate_trading_signal(
                market_data,
                technical_indicators,
                fundamental_data,
                provider=AIProvider.ANTHROPIC,
                model="claude-3-5-sonnet-20241022"
            )

            print(f"\n提供商: {response.provider.value}")
            print(f"模型: {response.model}")
            print(f"成本: ${response.cost:.4f}")
            print(f"\n交易信号:\n{response.content}")
        except ValueError as e:
            print(f"跳过Claude示例（未设置API密钥）: {e}")


if __name__ == "__main__":
    asyncio.run(main())

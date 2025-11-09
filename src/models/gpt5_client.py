"""
ChatGPT-5 Nano API客户端
用于市场分析和决策支持（2025最新）
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
import json
from typing import Any

import openai


class AnalysisType(Enum):
    """分析类型"""
    MARKET_SENTIMENT = "market_sentiment"
    TECHNICAL_ANALYSIS = "technical_analysis"
    FUNDAMENTAL_ANALYSIS = "fundamental_analysis"
    RISK_ASSESSMENT = "risk_assessment"
    TRADE_DECISION = "trade_decision"


@dataclass
class GPT5Config:
    """GPT-5配置"""
    api_key: str
    model: str = "gpt-5-nano"
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 0.9
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    timeout: int = 30
    max_retries: int = 3


class GPT5Client:
    """GPT-5客户端"""

    def __init__(self, config: GPT5Config):
        self.config = config
        openai.api_key = config.api_key
        self.model = config.model

    async def analyze_async(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """
        异步分析

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            **kwargs: 其他参数

        Returns:
            分析结果
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        for attempt in range(self.config.max_retries):
            try:
                response = await openai.ChatCompletion.acreate(
                    model=self.model,
                    messages=messages,
                    max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
                    temperature=kwargs.get("temperature", self.config.temperature),
                    top_p=kwargs.get("top_p", self.config.top_p),
                    frequency_penalty=kwargs.get("frequency_penalty", self.config.frequency_penalty),
                    presence_penalty=kwargs.get("presence_penalty", self.config.presence_penalty),
                    timeout=self.config.timeout
                )

                content = response.choices[0].message.content

                return {
                    "success": True,
                    "content": content,
                    "model": response.model,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }

            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    return {
                        "success": False,
                        "error": str(e)
                    }
                await asyncio.sleep(2 ** attempt)  # 指数退避

    def analyze(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """同步分析"""
        return asyncio.run(self.analyze_async(prompt, system_prompt, **kwargs))


class MarketAnalyzer:
    """市场分析器 - 使用GPT-5进行深度市场分析"""

    def __init__(self, gpt5_client: GPT5Client):
        self.client = gpt5_client

    async def analyze_market_sentiment(
        self,
        symbol: str,
        news: list[str],
        social_media: list[str]
    ) -> dict[str, Any]:
        """
        分析市场情绪

        Args:
            symbol: 股票代码
            news: 新闻列表
            social_media: 社交媒体内容列表

        Returns:
            情绪分析结果
        """
        system_prompt = """You are an expert market sentiment analyst.
        Analyze the provided news and social media content to determine market sentiment.
        Provide a sentiment score (-1 to 1), confidence level, and key insights."""

        prompt = f"""
        Analyze market sentiment for {symbol}:

        Recent News:
        {chr(10).join(f"- {n}" for n in news[:5])}

        Social Media:
        {chr(10).join(f"- {s}" for s in social_media[:10])}

        Provide analysis in JSON format:
        {{
            "sentiment_score": <float between -1 and 1>,
            "confidence": <float between 0 and 1>,
            "sentiment_label": "<bullish/neutral/bearish>",
            "key_insights": [<list of insights>],
            "risk_factors": [<list of risks>]
        }}
        """

        result = await self.client.analyze_async(prompt, system_prompt)

        if result["success"]:
            try:
                analysis = json.loads(result["content"])
                return analysis
            except json.JSONDecodeError:
                return {"error": "Failed to parse response"}
        else:
            return result

    async def analyze_technical_patterns(
        self,
        symbol: str,
        price_data: dict[str, Any],
        indicators: dict[str, float]
    ) -> dict[str, Any]:
        """
        分析技术模式

        Args:
            symbol: 股票代码
            price_data: 价格数据
            indicators: 技术指标

        Returns:
            技术分析结果
        """
        system_prompt = """You are an expert technical analyst.
        Analyze price patterns and technical indicators to identify trading opportunities."""

        prompt = f"""
        Technical Analysis for {symbol}:

        Price Data:
        - Current Price: ${price_data.get('close', 0):.2f}
        - High: ${price_data.get('high', 0):.2f}
        - Low: ${price_data.get('low', 0):.2f}
        - Volume: {price_data.get('volume', 0):,.0f}

        Technical Indicators:
        {json.dumps(indicators, indent=2)}

        Provide analysis in JSON format:
        {{
            "trend": "<uptrend/downtrend/sideways>",
            "strength": <float 0-1>,
            "support_levels": [<list of support prices>],
            "resistance_levels": [<list of resistance prices>],
            "patterns": [<list of identified patterns>],
            "signals": [<list of trading signals>],
            "recommendation": "<buy/hold/sell>",
            "confidence": <float 0-1>
        }}
        """

        result = await self.client.analyze_async(prompt, system_prompt)

        if result["success"]:
            try:
                analysis = json.loads(result["content"])
                return analysis
            except json.JSONDecodeError:
                return {"error": "Failed to parse response"}
        else:
            return result

    async def generate_trade_decision(
        self,
        symbol: str,
        market_data: dict[str, Any],
        portfolio_state: dict[str, Any],
        risk_limits: dict[str, float]
    ) -> dict[str, Any]:
        """
        生成交易决策

        Args:
            symbol: 股票代码
            market_data: 市场数据
            portfolio_state: 投资组合状态
            risk_limits: 风险限制

        Returns:
            交易决策
        """
        system_prompt = """You are an expert portfolio manager and trading strategist.
        Make data-driven trading decisions considering market conditions, portfolio state, and risk management."""

        prompt = f"""
        Generate trading decision for {symbol}:

        Market Data:
        {json.dumps(market_data, indent=2)}

        Portfolio State:
        - Current Position: {portfolio_state.get('position', 0)} shares
        - Available Capital: ${portfolio_state.get('cash', 0):,.2f}
        - Total Value: ${portfolio_state.get('total_value', 0):,.2f}
        - Current P&L: ${portfolio_state.get('pnl', 0):,.2f}

        Risk Limits:
        {json.dumps(risk_limits, indent=2)}

        Provide decision in JSON format:
        {{
            "action": "<buy/sell/hold>",
            "quantity": <number of shares>,
            "confidence": <float 0-1>,
            "reasoning": "<detailed reasoning>",
            "risk_assessment": "<risk level and factors>",
            "entry_price": <suggested entry price>,
            "stop_loss": <stop loss price>,
            "take_profit": <take profit price>,
            "time_horizon": "<short/medium/long>"
        }}
        """

        result = await self.client.analyze_async(prompt, system_prompt)

        if result["success"]:
            try:
                decision = json.loads(result["content"])
                return decision
            except json.JSONDecodeError:
                return {"error": "Failed to parse response"}
        else:
            return result

    async def assess_risk(
        self,
        portfolio: dict[str, Any],
        market_conditions: dict[str, Any]
    ) -> dict[str, Any]:
        """
        评估风险

        Args:
            portfolio: 投资组合
            market_conditions: 市场条件

        Returns:
            风险评估
        """
        system_prompt = """You are an expert risk manager.
        Assess portfolio risks and provide recommendations for risk mitigation."""

        prompt = f"""
        Risk Assessment:

        Portfolio:
        {json.dumps(portfolio, indent=2)}

        Market Conditions:
        {json.dumps(market_conditions, indent=2)}

        Provide risk assessment in JSON format:
        {{
            "overall_risk_score": <float 0-1>,
            "risk_level": "<low/medium/high/critical>",
            "risk_factors": [
                {{
                    "factor": "<risk factor name>",
                    "severity": "<low/medium/high>",
                    "description": "<description>"
                }}
            ],
            "var_95": <Value at Risk 95%>,
            "expected_shortfall": <Expected Shortfall>,
            "recommendations": [<list of risk mitigation recommendations>],
            "required_actions": [<list of required actions>]
        }}
        """

        result = await self.client.analyze_async(prompt, system_prompt)

        if result["success"]:
            try:
                assessment = json.loads(result["content"])
                return assessment
            except json.JSONDecodeError:
                return {"error": "Failed to parse response"}
        else:
            return result


# 示例系统提示模板

SYSTEM_PROMPTS = {
    "market_analyst": """You are a senior market analyst with 20+ years of experience.
    You have deep knowledge of market dynamics, trading strategies, and risk management.
    Provide clear, actionable insights based on data analysis.""",

    "technical_analyst": """You are an expert technical analyst specializing in chart patterns,
    indicators, and price action analysis. You can identify trends, support/resistance levels,
    and trading opportunities with high accuracy.""",

    "risk_manager": """You are a chief risk officer with expertise in portfolio risk management,
    VaR modeling, stress testing, and regulatory compliance. Your priority is protecting capital
    while maximizing risk-adjusted returns.""",

    "portfolio_manager": """You are an institutional portfolio manager managing billions in assets.
    You make disciplined, data-driven decisions with a focus on long-term performance and
    risk-adjusted returns."""
}

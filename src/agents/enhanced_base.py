"""
Enhanced Agent Base Classes
增强的智能体基类，集成LangChain和MU层

Research-grade implementation (Under Development)
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import json
from abc import ABC, abstractmethod

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from src.agents.base import Agent, AgentType, AgentDecision, Action, AgentState
from src.ai.model_unified import ModelRouter, ModelTier, get_router
from loguru import logger


class AgentAnalysisOutput(BaseModel):
    """智能体分析输出结构（用于JSON解析）"""
    action: str = Field(description="Trading action: BUY, SELL, or HOLD")
    confidence: float = Field(description="Confidence level 0-1", ge=0, le=1)
    reasoning: str = Field(description="Explanation for the decision")
    key_factors: List[str] = Field(description="List of key factors considered")
    risk_assessment: str = Field(description="Risk assessment: LOW, MEDIUM, HIGH")


class LLMEnhancedAgent(Agent):
    """
    LLM增强的智能体基类
    使用LangChain和MU层进行决策
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: AgentType,
        initial_capital: float = 100000,
        risk_tolerance: float = 0.5,
        model_tier: ModelTier = ModelTier.FAST,
        use_memory: bool = True,
        **kwargs
    ):
        super().__init__(agent_id, agent_type, initial_capital, risk_tolerance, **kwargs)

        self.model_tier = model_tier
        self.use_memory = use_memory
        self.router: Optional[ModelRouter] = None

        # LangChain组件
        self.prompt_template = self._create_prompt_template()
        self.output_parser = JsonOutputParser(pydantic_object=AgentAnalysisOutput)

        # 会话记忆
        self.conversation_history: List[Dict] = []
        self.max_conversation_history = kwargs.get('max_conversation_history', 10)

    async def _ensure_router(self):
        """确保router已初始化"""
        if self.router is None:
            self.router = await get_router()

    @abstractmethod
    def _create_prompt_template(self) -> ChatPromptTemplate:
        """创建prompt模板（子类实现）"""
        pass

    @abstractmethod
    def _get_personality_traits(self) -> str:
        """获取智能体性格特征（子类实现）"""
        pass

    def _prepare_market_context(self, market_data: Dict[str, Any]) -> str:
        """准备市场数据上下文"""
        context_parts = []

        # 价格信息
        if 'price' in market_data:
            context_parts.append(f"Current Price: ${market_data['price']:.2f}")
        if 'change_pct' in market_data:
            context_parts.append(f"Daily Change: {market_data['change_pct']:.2%}")

        # 技术指标
        if 'indicators' in market_data:
            indicators = market_data['indicators']
            context_parts.append("\nTechnical Indicators:")
            for key, value in indicators.items():
                if isinstance(value, float):
                    context_parts.append(f"  {key}: {value:.2f}")
                else:
                    context_parts.append(f"  {key}: {value}")

        # 基本面
        if 'fundamentals' in market_data:
            fundamentals = market_data['fundamentals']
            context_parts.append("\nFundamentals:")
            for key, value in fundamentals.items():
                context_parts.append(f"  {key}: {value}")

        # 市场情绪
        if 'sentiment' in market_data:
            context_parts.append(f"\nMarket Sentiment: {market_data['sentiment']}")

        return "\n".join(context_parts)

    def _prepare_historical_context(self) -> str:
        """准备历史决策上下文"""
        if not self.conversation_history:
            return "No previous decisions."

        recent_history = self.conversation_history[-3:]  # 最近3次
        history_parts = []

        for i, entry in enumerate(recent_history, 1):
            history_parts.append(
                f"{i}. Action: {entry.get('action')}, "
                f"Confidence: {entry.get('confidence', 0):.2f}, "
                f"Result: {entry.get('result', 'pending')}"
            )

        return "\n".join(history_parts)

    async def analyze(
        self,
        market_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> AgentDecision:
        """
        分析市场并做出决策（使用LLM）

        Args:
            market_data: 市场数据
            context: 额外上下文

        Returns:
            智能体决策
        """
        await self._ensure_router()

        symbol = market_data.get('symbol', 'UNKNOWN')

        try:
            # 准备上下文
            market_context = self._prepare_market_context(market_data)
            historical_context = self._prepare_historical_context() if self.use_memory else "N/A"
            personality = self._get_personality_traits()

            # 构建prompt
            messages = [
                {
                    'role': 'system',
                    'content': f"You are a {self.agent_type.value} trader. {personality}"
                },
                {
                    'role': 'user',
                    'content': self.prompt_template.format(
                        symbol=symbol,
                        market_context=market_context,
                        historical_context=historical_context,
                        risk_tolerance=self.risk_tolerance,
                        current_capital=self.state.capital,
                        format_instructions=self.output_parser.get_format_instructions()
                    )
                }
            ]

            # 调用LLM
            response = await self.router.route(
                messages,
                tier=self.model_tier
            )

            # 解析输出
            parsed = self.output_parser.parse(response.content)

            # 转换为AgentDecision
            action = Action[parsed.action.upper()]
            decision = AgentDecision(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                symbol=symbol,
                action=action,
                confidence=parsed.confidence,
                reasoning=parsed.reasoning,
                metadata={
                    'key_factors': parsed.key_factors,
                    'risk_assessment': parsed.risk_assessment,
                    'llm_cost': response.cost,
                    'llm_tokens': response.tokens_used,
                    'llm_model': response.model
                }
            )

            # 添加到记忆
            if self.use_memory:
                self.conversation_history.append({
                    'timestamp': datetime.now(),
                    'symbol': symbol,
                    'action': action.value,
                    'confidence': parsed.confidence,
                    'reasoning': parsed.reasoning
                })
                # 限制记忆大小
                if len(self.conversation_history) > self.max_conversation_history:
                    self.conversation_history.pop(0)

            return decision

        except Exception as e:
            logger.error(f"Agent {self.agent_id} analysis failed: {e}")
            # 降级为简单决策
            return AgentDecision(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                symbol=symbol,
                action=Action.HOLD,
                confidence=0.5,
                reasoning=f"Analysis failed: {str(e)}",
                metadata={'error': str(e)}
            )

    def _init_parameters(self, **kwargs) -> Dict[str, Any]:
        """初始化参数"""
        return {
            'model_tier': kwargs.get('model_tier', ModelTier.FAST),
            'use_memory': kwargs.get('use_memory', True)
        }


class MomentumChaserAgent(LLMEnhancedAgent):
    """追涨杀跌型智能体"""

    def _create_prompt_template(self) -> ChatPromptTemplate:
        template = """
Analyze {symbol} and make a trading decision as a momentum chaser.

Market Data:
{market_context}

Your Previous Decisions:
{historical_context}

Your Profile:
- Risk Tolerance: {risk_tolerance}
- Current Capital: ${current_capital:.2f}

Focus on:
1. Recent price trends and momentum
2. Volume changes
3. Breaking news or market hype
4. Quick profit opportunities

{format_instructions}
"""
        return PromptTemplate.from_template(template)

    def _get_personality_traits(self) -> str:
        return (
            "You are aggressive and opportunistic. "
            "You love following trends and jumping on hot stocks. "
            "You act quickly when you see momentum building."
        )


class ValueSeekerAgent(LLMEnhancedAgent):
    """价值投资型智能体"""

    def _create_prompt_template(self) -> ChatPromptTemplate:
        template = """
Analyze {symbol} and make a trading decision as a value investor.

Market Data:
{market_context}

Your Previous Decisions:
{historical_context}

Your Profile:
- Risk Tolerance: {risk_tolerance}
- Current Capital: ${current_capital:.2f}

Focus on:
1. Valuation metrics (P/E, P/B, etc.)
2. Financial health and fundamentals
3. Long-term growth potential
4. Margin of safety

{format_instructions}
"""
        return PromptTemplate.from_template(template)

    def _get_personality_traits(self) -> str:
        return (
            "You are patient and analytical. "
            "You seek undervalued stocks with strong fundamentals. "
            "You think long-term and avoid hype."
        )


class TechnicalTraderAgent(LLMEnhancedAgent):
    """技术分析型智能体"""

    def _create_prompt_template(self) -> ChatPromptTemplate:
        template = """
Analyze {symbol} and make a trading decision using technical analysis.

Market Data:
{market_context}

Your Previous Decisions:
{historical_context}

Your Profile:
- Risk Tolerance: {risk_tolerance}
- Current Capital: ${current_capital:.2f}

Focus on:
1. Chart patterns and trends
2. Support and resistance levels
3. Technical indicators (RSI, MACD, etc.)
4. Volume analysis

{format_instructions}
"""
        return PromptTemplate.from_template(template)

    def _get_personality_traits(self) -> str:
        return (
            "You are systematic and disciplined. "
            "You rely on technical indicators and chart patterns. "
            "You follow your rules strictly."
        )


class QuantitativeAgent(LLMEnhancedAgent):
    """量化投资型智能体（机构）"""

    def _create_prompt_template(self) -> ChatPromptTemplate:
        template = """
Analyze {symbol} and make a trading decision as a quantitative hedge fund.

Market Data:
{market_context}

Your Previous Decisions:
{historical_context}

Your Profile:
- Risk Tolerance: {risk_tolerance}
- Current Capital: ${current_capital:.2f}

Focus on:
1. Statistical patterns and anomalies
2. Factor exposures
3. Risk-adjusted returns
4. Portfolio optimization

{format_instructions}
"""
        return PromptTemplate.from_template(template)

    def _get_personality_traits(self) -> str:
        return (
            "You are data-driven and systematic. "
            "You use statistical models and factor analysis. "
            "You prioritize risk management and diversification."
        )

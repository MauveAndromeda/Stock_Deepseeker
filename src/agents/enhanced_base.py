"""
Enhanced Agent Base Classes
增强的智能体基类，集成LangChain和MU层

Research-grade implementation (Under Development)
"""

from abc import abstractmethod
from datetime import datetime
from typing import Any

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from loguru import logger
from pydantic import BaseModel, Field

from src.agents.base import Action, AgentDecision, AgentState, AgentType
from src.agents.unified_interface import (
    ActionType,
    AgentCapability,
    AgentDecisionOutput,
    BaseAgentV2,
    DecisionConfidence,
    MarketContext,
    RiskLevel,
)
from src.ai.model_unified import ModelRouter, ModelTier, get_router


class AgentAnalysisOutput(BaseModel):
    """智能体分析输出结构（用于JSON解析）"""
    action: str = Field(description="Trading action: BUY, SELL, or HOLD")
    confidence: float = Field(description="Confidence level 0-1", ge=0, le=1)
    reasoning: str = Field(description="Explanation for the decision")
    key_factors: list[str] = Field(description="List of key factors considered")
    risk_assessment: str = Field(description="Risk assessment: LOW, MEDIUM, HIGH")


class LLMEnhancedAgent(BaseAgentV2):
    """
    LLM增强的智能体基类
    使用LangChain和MU层进行决策
    Inherits from BaseAgentV2 for unified interface compliance
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: str,  # String type for compatibility
        capabilities: list[AgentCapability],
        initial_capital: float = 100000,
        risk_tolerance: float = 0.5,
        model_tier: ModelTier = ModelTier.FAST,
        use_memory: bool = True,
        **kwargs
    ):
        # Initialize BaseAgentV2
        super().__init__(
            agent_id=agent_id,
            agent_type=agent_type,
            capabilities=capabilities,
            **kwargs
        )

        # Legacy compatibility
        self.initial_capital = initial_capital
        self.risk_tolerance = risk_tolerance
        self.state = AgentState(
            agent_id=agent_id,
            agent_type=AgentType[agent_type.upper()] if isinstance(agent_type, str) else agent_type,
            capital=initial_capital
        )

        self.model_tier = model_tier
        self.use_memory = use_memory
        self.router: ModelRouter | None = None

        # LangChain组件
        self.prompt_template = self._create_prompt_template()
        self.output_parser = PydanticOutputParser(pydantic_object=AgentAnalysisOutput)

        # 会话记忆 (both old and new style)
        self.conversation_history: list[dict] = []
        self.max_conversation_history = kwargs.get("max_conversation_history", 10)

    async def _ensure_router(self):
        """确保router已初始化"""
        if self.router is None:
            self.router = await get_router()

    @abstractmethod
    def _create_prompt_template(self) -> ChatPromptTemplate:
        """创建prompt模板（子类实现）"""

    @abstractmethod
    def _get_personality_traits(self) -> str:
        """获取智能体性格特征（子类实现）"""

    def _prepare_market_context(self, market_data: dict[str, Any]) -> str:
        """准备市场数据上下文"""
        context_parts = []

        # 价格信息
        if "price" in market_data:
            context_parts.append(f"Current Price: ${market_data['price']:.2f}")
        if "change_pct" in market_data:
            context_parts.append(f"Daily Change: {market_data['change_pct']:.2%}")

        # 技术指标
        if "indicators" in market_data:
            indicators = market_data["indicators"]
            context_parts.append("\nTechnical Indicators:")
            for key, value in indicators.items():
                if isinstance(value, float):
                    context_parts.append(f"  {key}: {value:.2f}")
                else:
                    context_parts.append(f"  {key}: {value}")

        # 基本面
        if "fundamentals" in market_data:
            fundamentals = market_data["fundamentals"]
            context_parts.append("\nFundamentals:")
            for key, value in fundamentals.items():
                context_parts.append(f"  {key}: {value}")

        # 市场情绪
        if "sentiment" in market_data:
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

    async def _analyze_internal(
        self,
        context: MarketContext,
        additional_context: dict[str, Any] | None
    ) -> AgentDecisionOutput:
        """
        Internal analysis method (implements BaseAgentV2 interface)

        Args:
            context: Standardized market context
            additional_context: Additional context

        Returns:
            Standardized agent decision output
        """
        await self._ensure_router()

        try:
            # Prepare contexts
            market_context_str = self._prepare_market_context_from_standard(context)
            historical_context = self._prepare_historical_context() if self.use_memory else "N/A"
            personality = self._get_personality_traits()

            # Build prompt
            messages = [
                {
                    "role": "system",
                    "content": f"You are a {self.agent_type} trader. {personality}"
                },
                {
                    "role": "user",
                    "content": self.prompt_template.format(
                        symbol=context.symbol,
                        market_context=market_context_str,
                        historical_context=historical_context,
                        risk_tolerance=self.risk_tolerance,
                        current_capital=self.state.capital,
                        format_instructions=self.output_parser.get_format_instructions()
                    )
                }
            ]

            # Call LLM
            response = await self.router.route(
                messages,
                tier=self.model_tier
            )

            # Parse output
            parsed = self.output_parser.parse(response.content)

            # Convert to standardized output
            action = ActionType[parsed.action.upper()]

            # Map risk assessment string to RiskLevel
            risk_map = {
                "LOW": RiskLevel.LOW,
                "MEDIUM": RiskLevel.MEDIUM,
                "HIGH": RiskLevel.HIGH,
                "VERY_LOW": RiskLevel.VERY_LOW,
                "VERY_HIGH": RiskLevel.VERY_HIGH,
            }
            risk_level = risk_map.get(parsed.risk_assessment.upper(), RiskLevel.MEDIUM)

            decision = AgentDecisionOutput(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                action=action,
                confidence=parsed.confidence,
                confidence_level=DecisionConfidence.MEDIUM,  # Will be auto-computed
                reasoning=parsed.reasoning,
                key_factors=parsed.key_factors,
                risk_level=risk_level,
                concerns=[],
                cost=response.cost,
                metadata={
                    "llm_tokens": response.tokens_used,
                    "llm_model": response.model,
                    "llm_latency": response.latency
                }
            )

            # Add to memory
            if self.use_memory:
                self.conversation_history.append({
                    "timestamp": datetime.now(),
                    "symbol": context.symbol,
                    "action": action.value,
                    "confidence": parsed.confidence,
                    "reasoning": parsed.reasoning
                })
                if len(self.conversation_history) > self.max_conversation_history:
                    self.conversation_history.pop(0)

            return decision

        except Exception as e:
            logger.error(f"Agent {self.agent_id} analysis failed: {e}")
            raise  # Let BaseAgentV2.analyze handle the error

    async def analyze_legacy(
        self,
        market_data: dict[str, Any],
        context: dict[str, Any] | None = None
    ) -> AgentDecision:
        """
        Legacy analyze method for backward compatibility
        Converts dict to MarketContext, calls new interface, converts back
        """
        # Convert to MarketContext
        market_context = self._dict_to_market_context(market_data)

        # Call new interface
        decision_output = await self.analyze(market_context, context)

        # Convert back to AgentDecision
        return self._decision_output_to_legacy(decision_output, market_data.get("symbol", "UNKNOWN"))

    def _init_parameters(self, **kwargs) -> dict[str, Any]:
        """初始化参数"""
        return {
            "model_tier": kwargs.get("model_tier", ModelTier.FAST),
            "use_memory": kwargs.get("use_memory", True)
        }

    def _prepare_market_context_from_standard(self, context: MarketContext) -> str:
        """Prepare market context string from standardized MarketContext"""
        context_parts = []

        # Price information
        context_parts.append(f"Current Price: ${context.current_price:.2f}")
        context_parts.append(f"Daily Change: {context.price_change_pct:.2%}")
        context_parts.append(f"Volume: {context.volume:,}")

        # Technical indicators
        if context.technical_indicators:
            context_parts.append("\nTechnical Indicators:")
            for key, value in context.technical_indicators.items():
                if isinstance(value, float):
                    context_parts.append(f"  {key}: {value:.2f}")
                else:
                    context_parts.append(f"  {key}: {value}")

        # Fundamentals
        if context.fundamentals:
            context_parts.append("\nFundamentals:")
            for key, value in context.fundamentals.items():
                context_parts.append(f"  {key}: {value}")

        # Market sentiment
        if context.sentiment:
            context_parts.append(f"\nMarket Sentiment: {context.sentiment}")

        return "\n".join(context_parts)

    def _dict_to_market_context(self, market_data: dict[str, Any]) -> MarketContext:
        """Convert legacy dict format to MarketContext"""
        return MarketContext(
            symbol=market_data.get("symbol", "UNKNOWN"),
            timestamp=datetime.now(),
            current_price=market_data.get("price", market_data.get("current_price", 0.0)),
            price_change_pct=market_data.get("price_change_pct", market_data.get("change_pct", 0.0)),
            volume=int(market_data.get("volume", 0)),
            technical_indicators=market_data.get("indicators", market_data.get("technical_indicators", {})),
            fundamentals=market_data.get("fundamentals", {}),
            sentiment=market_data.get("sentiment"),
            metadata=market_data.get("metadata", {})
        )

    def _decision_output_to_legacy(self, decision: AgentDecisionOutput, symbol: str) -> AgentDecision:
        """Convert AgentDecisionOutput to legacy AgentDecision"""
        # Map ActionType to Action
        action_map = {
            ActionType.BUY: Action.BUY,
            ActionType.SELL: Action.SELL,
            ActionType.HOLD: Action.HOLD,
            ActionType.EXIT: Action.SELL,
        }

        return AgentDecision(
            agent_id=decision.agent_id,
            agent_type=self.state.agent_type,
            symbol=symbol,
            action=action_map.get(decision.action, Action.HOLD),
            confidence=decision.confidence,
            reasoning=decision.reasoning,
            metadata={
                "key_factors": decision.key_factors,
                "risk_level": decision.risk_level.value,
                "confidence_level": decision.confidence_level.value,
                **decision.metadata
            }
        )


class MomentumChaserAgent(LLMEnhancedAgent):
    """追涨杀跌型智能体"""

    def __init__(self, agent_id: str = "momentum_chaser", **kwargs):
        super().__init__(
            agent_id=agent_id,
            agent_type="momentum_chaser",
            capabilities=[
                AgentCapability.MARKET_ANALYSIS,
                AgentCapability.TECHNICAL_ANALYSIS,
                AgentCapability.TIMING_ANALYSIS
            ],
            **kwargs
        )

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

    def __init__(self, agent_id: str = "value_seeker", **kwargs):
        super().__init__(
            agent_id=agent_id,
            agent_type="value_seeker",
            capabilities=[
                AgentCapability.MARKET_ANALYSIS,
                AgentCapability.FUNDAMENTAL_ANALYSIS,
                AgentCapability.RISK_ASSESSMENT
            ],
            **kwargs
        )

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

    def __init__(self, agent_id: str = "technical_trader", **kwargs):
        super().__init__(
            agent_id=agent_id,
            agent_type="technical_trader",
            capabilities=[
                AgentCapability.MARKET_ANALYSIS,
                AgentCapability.TECHNICAL_ANALYSIS,
                AgentCapability.TIMING_ANALYSIS
            ],
            **kwargs
        )

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

    def __init__(self, agent_id: str = "quantitative", **kwargs):
        super().__init__(
            agent_id=agent_id,
            agent_type="quantitative",
            capabilities=[
                AgentCapability.MARKET_ANALYSIS,
                AgentCapability.TECHNICAL_ANALYSIS,
                AgentCapability.RISK_ASSESSMENT,
                AgentCapability.FUNDAMENTAL_ANALYSIS
            ],
            **kwargs
        )

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

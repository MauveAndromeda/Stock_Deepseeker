"""
Unified Agent Interface
统一的智能体接口定义

Research-grade implementation (Under Development)
Provides standard interfaces for all agent types
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Protocol
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, validator


class AgentCapability(str, Enum):
    """智能体能力"""
    MARKET_ANALYSIS = "market_analysis"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    TECHNICAL_ANALYSIS = "technical_analysis"
    FUNDAMENTAL_ANALYSIS = "fundamental_analysis"
    RISK_ASSESSMENT = "risk_assessment"
    TIMING_ANALYSIS = "timing_analysis"


class DecisionConfidence(str, Enum):
    """决策置信度级别"""
    VERY_LOW = "very_low"      # 0.0-0.3
    LOW = "low"                # 0.3-0.5
    MEDIUM = "medium"          # 0.5-0.7
    HIGH = "high"              # 0.7-0.85
    VERY_HIGH = "very_high"    # 0.85-1.0


class ActionType(str, Enum):
    """统一的动作类型"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    EXIT = "EXIT"  # 平仓
    SHORT = "SHORT"  # 做空 (future)


class RiskLevel(str, Enum):
    """风险级别"""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    EXTREME = "extreme"


class MarketContext(BaseModel):
    """标准化的市场上下文"""
    symbol: str = Field(description="Stock symbol")
    timestamp: datetime = Field(description="Data timestamp")

    # Price data
    current_price: float = Field(description="Current price")
    price_change_pct: float = Field(description="Price change percentage")
    volume: int = Field(description="Trading volume")

    # Technical indicators (optional)
    technical_indicators: Dict[str, float] = Field(default_factory=dict)

    # Fundamental data (optional)
    fundamentals: Dict[str, Any] = Field(default_factory=dict)

    # Market sentiment (optional)
    sentiment: Optional[Dict[str, Any]] = None

    # Additional context
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True


class AgentDecisionOutput(BaseModel):
    """标准化的智能体决策输出"""
    agent_id: str = Field(description="Agent identifier")
    agent_type: str = Field(description="Agent type")

    # Decision
    action: ActionType = Field(description="Recommended action")
    confidence: float = Field(description="Confidence level 0-1", ge=0, le=1)
    confidence_level: DecisionConfidence = Field(description="Confidence category")

    # Reasoning
    reasoning: str = Field(description="Decision reasoning")
    key_factors: List[str] = Field(description="Key factors considered")

    # Risk assessment
    risk_level: RiskLevel = Field(description="Assessed risk level")
    concerns: List[str] = Field(default_factory=list, description="Risk concerns")

    # Position sizing (optional)
    suggested_position_size: Optional[float] = Field(None, ge=0, le=1, description="Suggested position size as % of portfolio")

    # Metadata
    timestamp: datetime = Field(default_factory=datetime.now)
    processing_time_ms: Optional[float] = None
    cost: Optional[float] = None  # API cost if applicable
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('confidence_level', always=True)
    def set_confidence_level(cls, v, values):
        """自动设置置信度级别"""
        if v is not None:
            return v

        confidence = values.get('confidence', 0.5)
        if confidence < 0.3:
            return DecisionConfidence.VERY_LOW
        elif confidence < 0.5:
            return DecisionConfidence.LOW
        elif confidence < 0.7:
            return DecisionConfidence.MEDIUM
        elif confidence < 0.85:
            return DecisionConfidence.HIGH
        else:
            return DecisionConfidence.VERY_HIGH


class AgentPerformanceMetrics(BaseModel):
    """智能体性能指标"""
    agent_id: str

    # Decision metrics
    total_decisions: int = 0
    decisions_acted_on: int = 0

    # Performance metrics
    win_rate: float = 0.0
    avg_confidence: float = 0.0
    avg_processing_time_ms: float = 0.0

    # Cost metrics
    total_api_calls: int = 0
    total_cost: float = 0.0
    avg_cost_per_decision: float = 0.0

    # Quality metrics
    false_signals: int = 0
    missed_opportunities: int = 0

    # Timestamp
    last_updated: datetime = Field(default_factory=datetime.now)


class IAgent(Protocol):
    """
    统一的Agent接口协议
    所有智能体必须实现此接口
    """

    agent_id: str
    agent_type: str
    capabilities: List[AgentCapability]

    async def analyze(
        self,
        context: MarketContext,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> AgentDecisionOutput:
        """
        分析市场并做出决策

        Args:
            context: 标准化的市场上下文
            additional_context: 额外的上下文信息

        Returns:
            标准化的决策输出
        """
        ...

    def get_performance_metrics(self) -> AgentPerformanceMetrics:
        """获取性能指标"""
        ...

    def reset(self) -> None:
        """重置智能体状态"""
        ...


class BaseAgentV2(ABC):
    """
    统一的Agent基类 v2
    实现了标准接口和通用功能
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        capabilities: List[AgentCapability],
        **kwargs
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.capabilities = capabilities

        # Performance tracking
        self.metrics = AgentPerformanceMetrics(agent_id=agent_id)

        # Decision history
        self.decision_history: List[AgentDecisionOutput] = []
        self.max_history_size = kwargs.get('max_history_size', 100)

    @abstractmethod
    async def _analyze_internal(
        self,
        context: MarketContext,
        additional_context: Optional[Dict[str, Any]]
    ) -> AgentDecisionOutput:
        """内部分析逻辑（子类实现）"""
        pass

    async def analyze(
        self,
        context: MarketContext,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> AgentDecisionOutput:
        """
        标准化的分析接口
        包含性能跟踪和历史记录
        """
        import time
        start_time = time.time()

        try:
            # 调用子类实现
            decision = await self._analyze_internal(context, additional_context)

            # 记录处理时间
            processing_time = (time.time() - start_time) * 1000
            decision.processing_time_ms = processing_time

            # 更新指标
            self._update_metrics(decision)

            # 记录历史
            self._add_to_history(decision)

            return decision

        except Exception as e:
            # 错误处理
            from loguru import logger
            logger.error(f"Agent {self.agent_id} analysis failed: {e}")

            # 返回默认决策
            return AgentDecisionOutput(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                action=ActionType.HOLD,
                confidence=0.5,
                confidence_level=DecisionConfidence.MEDIUM,
                reasoning=f"Analysis failed: {str(e)}",
                key_factors=[],
                risk_level=RiskLevel.HIGH,
                concerns=[str(e)],
                processing_time_ms=(time.time() - start_time) * 1000
            )

    def _update_metrics(self, decision: AgentDecisionOutput):
        """更新性能指标"""
        self.metrics.total_decisions += 1

        if decision.processing_time_ms:
            # 更新平均处理时间
            total_time = self.metrics.avg_processing_time_ms * (self.metrics.total_decisions - 1)
            self.metrics.avg_processing_time_ms = (total_time + decision.processing_time_ms) / self.metrics.total_decisions

        if decision.cost:
            self.metrics.total_api_calls += 1
            self.metrics.total_cost += decision.cost
            self.metrics.avg_cost_per_decision = self.metrics.total_cost / self.metrics.total_api_calls

        # 更新平均置信度
        total_conf = self.metrics.avg_confidence * (self.metrics.total_decisions - 1)
        self.metrics.avg_confidence = (total_conf + decision.confidence) / self.metrics.total_decisions

        self.metrics.last_updated = datetime.now()

    def _add_to_history(self, decision: AgentDecisionOutput):
        """添加到历史"""
        self.decision_history.append(decision)
        if len(self.decision_history) > self.max_history_size:
            self.decision_history.pop(0)

    def get_performance_metrics(self) -> AgentPerformanceMetrics:
        """获取性能指标"""
        return self.metrics

    def reset(self):
        """重置智能体状态"""
        self.decision_history.clear()
        self.metrics = AgentPerformanceMetrics(agent_id=self.agent_id)


class ExpertPanelDecision(BaseModel):
    """专家面板决策输出"""
    symbol: str

    # Final decision
    final_action: ActionType
    final_confidence: float = Field(ge=0, le=1)
    final_reasoning: str

    # Expert opinions
    expert_opinions: List[Dict[str, Any]] = Field(default_factory=list)

    # Discussion metadata
    discussion_rounds: int
    consensus_reached: bool
    agreement_level: float = Field(ge=0, le=1)

    # Risk assessment
    aggregated_risk_level: RiskLevel
    key_concerns: List[str] = Field(default_factory=list)

    # Performance
    total_processing_time_ms: float
    total_cost: float = 0.0

    # Timestamp
    timestamp: datetime = Field(default_factory=datetime.now)


class IExpertPanel(Protocol):
    """
    统一的专家面板接口
    """

    async def discuss(
        self,
        context: MarketContext,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExpertPanelDecision:
        """
        进行专家讨论

        Args:
            context: 市场上下文
            metadata: 额外元数据

        Returns:
            专家面板决策
        """
        ...

    def get_discussion_history(self) -> List[ExpertPanelDecision]:
        """获取讨论历史"""
        ...


class AgentRegistry:
    """
    智能体注册表
    管理和发现智能体
    """

    def __init__(self):
        self._agents: Dict[str, IAgent] = {}
        self._agents_by_capability: Dict[AgentCapability, List[str]] = {
            cap: [] for cap in AgentCapability
        }

    def register(self, agent: IAgent):
        """注册智能体"""
        self._agents[agent.agent_id] = agent

        # 按能力索引
        for capability in agent.capabilities:
            if agent.agent_id not in self._agents_by_capability[capability]:
                self._agents_by_capability[capability].append(agent.agent_id)

    def unregister(self, agent_id: str):
        """注销智能体"""
        if agent_id in self._agents:
            agent = self._agents[agent_id]
            # 从能力索引中移除
            for capability in agent.capabilities:
                if agent_id in self._agents_by_capability[capability]:
                    self._agents_by_capability[capability].remove(agent_id)
            del self._agents[agent_id]

    def get_agent(self, agent_id: str) -> Optional[IAgent]:
        """获取智能体"""
        return self._agents.get(agent_id)

    def get_agent_count(self) -> int:
        """获取注册的智能体数量"""
        return len(self._agents)

    def get_agents_by_capability(self, capability: AgentCapability) -> List[IAgent]:
        """根据能力获取智能体"""
        agent_ids = self._agents_by_capability.get(capability, [])
        return [self._agents[aid] for aid in agent_ids if aid in self._agents]

    def get_all_agents(self) -> List[IAgent]:
        """获取所有智能体"""
        return list(self._agents.values())

    def get_performance_summary(self) -> Dict[str, AgentPerformanceMetrics]:
        """获取所有智能体的性能摘要"""
        return {
            agent_id: agent.get_performance_metrics()
            for agent_id, agent in self._agents.items()
        }


# 全局注册表实例
_global_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """获取全局智能体注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = AgentRegistry()
    return _global_registry

"""
多智能体系统
模拟机构和零售投资者
"""

# Legacy agents
# Integration
from src.agents.backtest_integration import (
    MultiAgentStrategy,
    create_default_multi_agent_strategy,
)
from src.agents.base import Agent, AgentDecision, AgentType

# Enhanced LLM agents
from src.agents.enhanced_base import (
    LLMEnhancedAgent,
    MomentumChaserAgent,
    QuantitativeAgent,
    TechnicalTraderAgent,
    ValueSeekerAgent,
)
from src.agents.expert import ExpertPanel
from src.agents.institutional import InstitutionalAgentFactory
from src.agents.retail import RetailAgentFactory

# Unified interface (new system)
from src.agents.unified_interface import (
    ActionType,
    AgentCapability,
    AgentDecisionOutput,
    AgentPerformanceMetrics,
    AgentRegistry,
    BaseAgentV2,
    DecisionConfidence,
    ExpertPanelDecision,
    IAgent,
    IExpertPanel,
    MarketContext,
    RiskLevel,
    get_agent_registry,
)

__all__ = [
    # Legacy
    "Agent",
    "AgentType",
    "AgentDecision",
    "RetailAgentFactory",
    "InstitutionalAgentFactory",
    "ExpertPanel",
    # Unified interface
    "BaseAgentV2",
    "MarketContext",
    "AgentDecisionOutput",
    "ActionType",
    "RiskLevel",
    "AgentCapability",
    "DecisionConfidence",
    "AgentPerformanceMetrics",
    "IAgent",
    "IExpertPanel",
    "ExpertPanelDecision",
    "AgentRegistry",
    "get_agent_registry",
    # Enhanced agents
    "LLMEnhancedAgent",
    "MomentumChaserAgent",
    "ValueSeekerAgent",
    "TechnicalTraderAgent",
    "QuantitativeAgent",
    # Integration
    "MultiAgentStrategy",
    "create_default_multi_agent_strategy",
]

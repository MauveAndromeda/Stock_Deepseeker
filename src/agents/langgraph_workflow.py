"""
LangGraph Workflow System
基于LangGraph的专家讨论工作流

Research-grade implementation (Under Development)
Multi-round expert discussion using graph-based workflow
"""

from typing import Dict, List, Optional, Any, TypedDict, Annotated
from dataclasses import dataclass, field
from datetime import datetime
import operator

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from pydantic import BaseModel, Field

from src.agents.base import AgentDecision, Action
from src.ai.model_unified import ModelRouter, ModelTier, get_router
from loguru import logger


class ExpertRole(str):
    """专家角色"""
    SENTIMENT_ANALYST = "sentiment_analyst"
    INSTITUTIONAL_ANALYST = "institutional_analyst"
    RISK_MANAGER = "risk_manager"
    MARKET_TIMER = "market_timer"
    CHAIRMAN = "chairman"


class DiscussionState(TypedDict):
    """讨论状态（在节点间传递）"""
    symbol: str
    market_data: Dict[str, Any]
    round_number: int
    max_rounds: int
    expert_opinions: Annotated[List[Dict], operator.add]  # 累积专家意见
    chairman_summary: Optional[str]
    final_decision: Optional[Dict]
    metadata: Dict[str, Any]


@dataclass
class ExpertOpinion:
    """专家意见"""
    role: str
    round: int
    opinion: str
    action_recommendation: str  # BUY/SELL/HOLD
    confidence: float
    key_points: List[str]
    concerns: List[str]
    timestamp: datetime = field(default_factory=datetime.now)


class ExpertNode:
    """专家节点（图中的一个节点）"""

    def __init__(
        self,
        role: ExpertRole,
        model_tier: ModelTier = ModelTier.BALANCED
    ):
        self.role = role
        self.model_tier = model_tier
        self.router: Optional[ModelRouter] = None

    async def _ensure_router(self):
        if self.router is None:
            self.router = await get_router()

    def _get_system_prompt(self) -> str:
        """获取角色系统提示"""
        prompts = {
            ExpertRole.SENTIMENT_ANALYST: """
You are a market sentiment analyst expert.
Focus on:
- Social media trends and investor sentiment
- News flow and market psychology
- Fear & Greed indicators
- Retail vs institutional sentiment
Provide your analysis from a sentiment perspective.
""",
            ExpertRole.INSTITUTIONAL_ANALYST: """
You are an institutional trading behavior analyst.
Focus on:
- Large order flows and dark pool activity
- Institutional ownership changes
- Smart money movements
- Options market positioning
Provide insights on institutional behavior.
""",
            ExpertRole.RISK_MANAGER: """
You are a quantitative risk manager.
Focus on:
- Value at Risk (VaR) and tail risks
- Portfolio concentration and diversification
- Stop-loss levels and position sizing
- Correlation risks and hedge effectiveness
Evaluate risks and suggest risk management strategies.
""",
            ExpertRole.MARKET_TIMER: """
You are a market timing and technical analysis expert.
Focus on:
- Market cycles and timing signals
- Technical indicators and chart patterns
- Support/resistance levels
- Optimal entry/exit points
Provide timing recommendations.
""",
            ExpertRole.CHAIRMAN: """
You are the chairman moderating this expert panel discussion.
Your role is to:
- Synthesize all expert opinions
- Identify consensus and disagreements
- Make final recommendation balancing all views
- Assign confidence level to the decision
Provide a balanced final decision.
"""
        }
        return prompts.get(self.role, "You are a financial expert.")

    async def process(self, state: DiscussionState) -> Dict:
        """处理节点逻辑"""
        await self._ensure_router()

        symbol = state['symbol']
        round_num = state['round_number']
        market_data = state['market_data']

        # 准备上下文
        market_context = self._format_market_data(market_data)
        previous_opinions = self._format_previous_opinions(
            state.get('expert_opinions', []),
            round_num
        )

        # 构建prompt
        user_message = f"""
Analyzing: {symbol}
Discussion Round: {round_num}/{state['max_rounds']}

Market Data:
{market_context}

Previous Expert Opinions:
{previous_opinions}

Please provide your analysis and recommendation.
Include:
1. Your perspective on the current situation
2. Action recommendation (BUY/SELL/HOLD)
3. Confidence level (0-1)
4. Key supporting points
5. Main concerns or risks

Format as JSON:
{{
    "opinion": "your detailed analysis",
    "action": "BUY/SELL/HOLD",
    "confidence": 0.0-1.0,
    "key_points": ["point1", "point2", ...],
    "concerns": ["concern1", "concern2", ...]
}}
"""

        messages = [
            {'role': 'system', 'content': self._get_system_prompt()},
            {'role': 'user', 'content': user_message}
        ]

        try:
            # 调用LLM
            response = await self.router.route(messages, tier=self.model_tier)

            # 解析响应
            import json
            try:
                parsed = json.loads(response.content)
            except:
                # 如果解析失败，创建默认响应
                parsed = {
                    "opinion": response.content,
                    "action": "HOLD",
                    "confidence": 0.5,
                    "key_points": [],
                    "concerns": []
                }

            # 创建专家意见
            opinion = {
                'role': self.role,
                'round': round_num,
                'opinion': parsed['opinion'],
                'action': parsed['action'],
                'confidence': parsed['confidence'],
                'key_points': parsed.get('key_points', []),
                'concerns': parsed.get('concerns', []),
                'cost': response.cost,
                'tokens': response.tokens_used
            }

            # 返回更新
            return {
                'expert_opinions': [opinion]
            }

        except Exception as e:
            logger.error(f"Expert {self.role} failed: {e}")
            # 返回默认意见
            return {
                'expert_opinions': [{
                    'role': self.role,
                    'round': round_num,
                    'opinion': f"Analysis failed: {str(e)}",
                    'action': 'HOLD',
                    'confidence': 0.5,
                    'key_points': [],
                    'concerns': [str(e)]
                }]
            }

    def _format_market_data(self, market_data: Dict) -> str:
        """格式化市场数据"""
        parts = []
        for key, value in market_data.items():
            if isinstance(value, dict):
                parts.append(f"{key}:")
                for k, v in value.items():
                    parts.append(f"  {k}: {v}")
            else:
                parts.append(f"{key}: {value}")
        return "\n".join(parts)

    def _format_previous_opinions(self, opinions: List[Dict], current_round: int) -> str:
        """格式化之前的意见"""
        if not opinions:
            return "No previous opinions yet."

        # 只显示上一轮的意见
        previous_round_opinions = [
            op for op in opinions
            if op['round'] == current_round - 1
        ]

        if not previous_round_opinions:
            return "No opinions from previous round."

        formatted = []
        for op in previous_round_opinions:
            formatted.append(
                f"- {op['role']}: {op['action']} (confidence: {op['confidence']:.2f})\n"
                f"  Opinion: {op['opinion'][:200]}..."
            )

        return "\n\n".join(formatted)


class ExpertPanelWorkflow:
    """
    专家面板工作流
    使用LangGraph实现多轮讨论
    """

    def __init__(
        self,
        max_rounds: int = 3,
        model_tier: ModelTier = ModelTier.BALANCED
    ):
        self.max_rounds = max_rounds
        self.model_tier = model_tier
        self.workflow = None
        self._build_workflow()

    def _build_workflow(self):
        """构建LangGraph工作流"""
        # 创建状态图
        workflow = StateGraph(DiscussionState)

        # 创建专家节点
        sentiment_node = ExpertNode(ExpertRole.SENTIMENT_ANALYST, self.model_tier)
        institutional_node = ExpertNode(ExpertRole.INSTITUTIONAL_ANALYST, self.model_tier)
        risk_node = ExpertNode(ExpertRole.RISK_MANAGER, self.model_tier)
        timing_node = ExpertNode(ExpertRole.MARKET_TIMER, self.model_tier)
        chairman_node = ExpertNode(ExpertRole.CHAIRMAN, self.model_tier)

        # 添加节点
        workflow.add_node("sentiment_analyst", sentiment_node.process)
        workflow.add_node("institutional_analyst", institutional_node.process)
        workflow.add_node("risk_manager", risk_node.process)
        workflow.add_node("market_timer", timing_node.process)
        workflow.add_node("chairman", chairman_node.process)
        workflow.add_node("check_rounds", self._check_rounds)

        # 设置入口点
        workflow.set_entry_point("sentiment_analyst")

        # 定义流程（按顺序讨论）
        workflow.add_edge("sentiment_analyst", "institutional_analyst")
        workflow.add_edge("institutional_analyst", "risk_manager")
        workflow.add_edge("risk_manager", "market_timer")
        workflow.add_edge("market_timer", "chairman")
        workflow.add_edge("chairman", "check_rounds")

        # 条件边：检查是否继续下一轮
        workflow.add_conditional_edges(
            "check_rounds",
            self._should_continue,
            {
                "continue": "sentiment_analyst",  # 继续下一轮
                "end": END  # 结束
            }
        )

        self.workflow = workflow.compile()

    def _check_rounds(self, state: DiscussionState) -> Dict:
        """检查轮次并更新状态"""
        return {
            'round_number': state['round_number'] + 1
        }

    def _should_continue(self, state: DiscussionState) -> str:
        """决定是否继续下一轮"""
        if state['round_number'] >= state['max_rounds']:
            return "end"

        # 检查是否达成共识
        last_round_opinions = [
            op for op in state['expert_opinions']
            if op['round'] == state['round_number'] - 1
        ]

        if last_round_opinions:
            actions = [op['action'] for op in last_round_opinions]
            # 如果所有专家意见一致且置信度都很高
            if len(set(actions)) == 1:
                avg_confidence = sum(op['confidence'] for op in last_round_opinions) / len(last_round_opinions)
                if avg_confidence >= 0.8:
                    logger.info(f"Consensus reached with high confidence: {actions[0]}")
                    return "end"

        return "continue"

    async def discuss(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行专家讨论

        Args:
            symbol: 股票代码
            market_data: 市场数据
            metadata: 额外元数据

        Returns:
            讨论结果
        """
        # 初始化状态
        initial_state: DiscussionState = {
            'symbol': symbol,
            'market_data': market_data,
            'round_number': 1,
            'max_rounds': self.max_rounds,
            'expert_opinions': [],
            'chairman_summary': None,
            'final_decision': None,
            'metadata': metadata or {}
        }

        # 运行工作流
        logger.info(f"Starting expert panel discussion for {symbol}")
        final_state = await self.workflow.ainvoke(initial_state)

        # 提取最终决策
        final_decision = self._extract_final_decision(final_state)

        return {
            'symbol': symbol,
            'final_decision': final_decision,
            'discussion_rounds': final_state['round_number'] - 1,
            'all_opinions': final_state['expert_opinions'],
            'metadata': final_state['metadata']
        }

    def _extract_final_decision(self, state: DiscussionState) -> Dict[str, Any]:
        """从状态中提取最终决策"""
        # 获取主席的最后意见
        chairman_opinions = [
            op for op in state['expert_opinions']
            if op['role'] == ExpertRole.CHAIRMAN
        ]

        if chairman_opinions:
            final_chairman = chairman_opinions[-1]
            return {
                'action': final_chairman['action'],
                'confidence': final_chairman['confidence'],
                'reasoning': final_chairman['opinion'],
                'key_points': final_chairman.get('key_points', []),
                'concerns': final_chairman.get('concerns', [])
            }

        # 如果没有主席意见，聚合所有专家意见
        if state['expert_opinions']:
            last_round = max(op['round'] for op in state['expert_opinions'])
            last_opinions = [
                op for op in state['expert_opinions']
                if op['round'] == last_round
            ]

            # 投票
            action_votes = {}
            total_confidence = 0
            for op in last_opinions:
                action = op['action']
                confidence = op['confidence']
                action_votes[action] = action_votes.get(action, 0) + confidence
                total_confidence += confidence

            best_action = max(action_votes, key=action_votes.get)
            avg_confidence = total_confidence / len(last_opinions) if last_opinions else 0.5

            return {
                'action': best_action,
                'confidence': avg_confidence,
                'reasoning': 'Aggregated from expert opinions',
                'key_points': [],
                'concerns': []
            }

        # 默认
        return {
            'action': 'HOLD',
            'confidence': 0.5,
            'reasoning': 'No consensus reached',
            'key_points': [],
            'concerns': ['Insufficient information']
        }

"""
专家系统和决策面板
聚合多个智能体的意见，形成集体决策
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np

from src.agents.base import Action, Agent, AgentDecision


class VotingStrategy(Enum):
    """投票策略"""
    MAJORITY = "majority"  # 多数投票
    WEIGHTED = "weighted"  # 加权投票
    CONFIDENCE_WEIGHTED = "confidence_weighted"  # 置信度加权
    UNANIMOUS = "unanimous"  # 一致通过


@dataclass
class ConsensusDecision:
    """共识决策"""
    symbol: str
    action: Action
    confidence: float
    quantity: int | None
    price: float | None
    reasoning: str
    agent_votes: dict[str, AgentDecision] = field(default_factory=dict)
    voting_details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class ExpertPanel:
    """专家决策面板"""

    def __init__(
        self,
        agents: list[Agent],
        voting_strategy: VotingStrategy = VotingStrategy.CONFIDENCE_WEIGHTED,
        confidence_threshold: float = 0.6,
        min_agreement_ratio: float = 0.5,
    ):
        """
        初始化专家面板

        Args:
            agents: 智能体列表
            voting_strategy: 投票策略
            confidence_threshold: 置信度阈值
            min_agreement_ratio: 最小同意比例
        """
        self.agents = agents
        self.voting_strategy = voting_strategy
        self.confidence_threshold = confidence_threshold
        self.min_agreement_ratio = min_agreement_ratio

        # 智能体权重（可根据历史表现动态调整）
        self.agent_weights = {agent.agent_id: 1.0 for agent in agents}

        # 决策历史
        self.decision_history: list[ConsensusDecision] = []

    def gather_opinions(
        self,
        symbol: str,
        market_data: dict,
        context: dict | None = None
    ) -> dict[str, AgentDecision]:
        """收集所有智能体的意见"""
        opinions = {}

        for agent in self.agents:
            try:
                decision = agent.analyze(market_data, context)
                opinions[agent.agent_id] = decision
            except Exception as e:
                print(f"Error gathering opinion from {agent.agent_id}: {e}")
                continue

        return opinions

    def vote_majority(
        self,
        opinions: dict[str, AgentDecision]
    ) -> tuple[Action, float, dict]:
        """多数投票"""
        action_votes = [decision.action for decision in opinions.values()]
        action_counter = Counter(action_votes)

        # 最多的动作
        most_common_action, vote_count = action_counter.most_common(1)[0]
        total_votes = len(action_votes)
        agreement_ratio = vote_count / total_votes if total_votes > 0 else 0

        # 平均置信度
        relevant_decisions = [d for d in opinions.values() if d.action == most_common_action]
        avg_confidence = np.mean([d.confidence for d in relevant_decisions]) if relevant_decisions else 0

        voting_details = {
            "action_distribution": dict(action_counter),
            "agreement_ratio": agreement_ratio,
            "vote_count": vote_count,
            "total_votes": total_votes
        }

        return most_common_action, avg_confidence, voting_details

    def vote_weighted(
        self,
        opinions: dict[str, AgentDecision]
    ) -> tuple[Action, float, dict]:
        """加权投票（基于智能体权重）"""
        action_weights = {Action.BUY: 0.0, Action.SELL: 0.0, Action.HOLD: 0.0}

        for agent_id, decision in opinions.items():
            weight = self.agent_weights.get(agent_id, 1.0)
            action_weights[decision.action] += weight

        # 选择权重最大的动作
        best_action = max(action_weights, key=action_weights.get)
        total_weight = sum(action_weights.values())
        confidence = action_weights[best_action] / total_weight if total_weight > 0 else 0

        voting_details = {
            "action_weights": {str(k): v for k, v in action_weights.items()},
            "total_weight": total_weight
        }

        return best_action, confidence, voting_details

    def vote_confidence_weighted(
        self,
        opinions: dict[str, AgentDecision]
    ) -> tuple[Action, float, dict]:
        """置信度加权投票"""
        action_scores = {Action.BUY: 0.0, Action.SELL: 0.0, Action.HOLD: 0.0}

        for agent_id, decision in opinions.items():
            agent_weight = self.agent_weights.get(agent_id, 1.0)
            weighted_confidence = decision.confidence * agent_weight
            action_scores[decision.action] += weighted_confidence

        # 选择分数最高的动作
        best_action = max(action_scores, key=action_scores.get)
        total_score = sum(action_scores.values())
        confidence = action_scores[best_action] / total_score if total_score > 0 else 0

        voting_details = {
            "action_scores": {str(k): v for k, v in action_scores.items()},
            "total_score": total_score
        }

        return best_action, confidence, voting_details

    def vote_unanimous(
        self,
        opinions: dict[str, AgentDecision]
    ) -> tuple[Action, float, dict]:
        """一致通过（所有智能体必须同意）"""
        actions = [decision.action for decision in opinions.values()]

        # 检查是否一致
        if len(set(actions)) == 1:
            # 所有智能体同意
            action = actions[0]
            avg_confidence = np.mean([d.confidence for d in opinions.values()])
            voting_details = {"unanimous": True, "action": str(action)}
            return action, avg_confidence, voting_details
        # 不一致，默认持有
        voting_details = {"unanimous": False, "action_distribution": dict(Counter(actions))}
        return Action.HOLD, 0.5, voting_details

    def make_consensus_decision(
        self,
        symbol: str,
        market_data: dict,
        context: dict | None = None
    ) -> ConsensusDecision:
        """形成共识决策"""

        # 收集意见
        opinions = self.gather_opinions(symbol, market_data, context)

        if not opinions:
            # 没有意见，默认持有
            return ConsensusDecision(
                symbol=symbol,
                action=Action.HOLD,
                confidence=0.5,
                quantity=None,
                price=market_data.get("close"),
                reasoning="无智能体意见",
                agent_votes={},
                voting_details={}
            )

        # 根据策略投票
        if self.voting_strategy == VotingStrategy.MAJORITY:
            action, confidence, details = self.vote_majority(opinions)
        elif self.voting_strategy == VotingStrategy.WEIGHTED:
            action, confidence, details = self.vote_weighted(opinions)
        elif self.voting_strategy == VotingStrategy.CONFIDENCE_WEIGHTED:
            action, confidence, details = self.vote_confidence_weighted(opinions)
        elif self.voting_strategy == VotingStrategy.UNANIMOUS:
            action, confidence, details = self.vote_unanimous(opinions)
        else:
            action, confidence, details = self.vote_confidence_weighted(opinions)

        # 检查置信度阈值
        if confidence < self.confidence_threshold and action != Action.HOLD:
            action = Action.HOLD
            reasoning = f"置信度不足：{confidence:.2f} < {self.confidence_threshold}"
        else:
            # 汇总推理
            reasoning = self._aggregate_reasoning(opinions, action)

        # 计算数量（平均）
        relevant_decisions = [d for d in opinions.values() if d.action == action and d.quantity]
        avg_quantity = int(np.mean([d.quantity for d in relevant_decisions])) if relevant_decisions else None

        consensus = ConsensusDecision(
            symbol=symbol,
            action=action,
            confidence=confidence,
            quantity=avg_quantity,
            price=market_data.get("close"),
            reasoning=reasoning,
            agent_votes=opinions,
            voting_details=details
        )

        # 记录决策历史
        self.decision_history.append(consensus)

        return consensus

    def _aggregate_reasoning(
        self,
        opinions: dict[str, AgentDecision],
        chosen_action: Action
    ) -> str:
        """聚合推理"""
        relevant_decisions = [d for d in opinions.values() if d.action == chosen_action]

        if not relevant_decisions:
            return "无相关推理"

        # 提取关键词
        reasoning_texts = [d.reasoning for d in relevant_decisions if d.reasoning]

        if len(reasoning_texts) <= 3:
            return "; ".join(reasoning_texts)
        # 如果太多，只取前3个
        return "; ".join(reasoning_texts[:3]) + f" (共{len(reasoning_texts)}个意见)"

    def update_agent_weights(
        self,
        performance_metrics: dict[str, float]
    ):
        """
        根据表现更新智能体权重

        Args:
            performance_metrics: {agent_id: performance_score}
        """
        for agent_id, score in performance_metrics.items():
            if agent_id in self.agent_weights:
                # 简单的指数移动平均
                alpha = 0.1
                self.agent_weights[agent_id] = (
                    alpha * score + (1 - alpha) * self.agent_weights[agent_id]
                )

        # 归一化权重
        total_weight = sum(self.agent_weights.values())
        if total_weight > 0:
            self.agent_weights = {
                k: v / total_weight for k, v in self.agent_weights.items()
            }

    def get_agent_statistics(self) -> dict[str, Any]:
        """获取智能体统计信息"""
        stats = {
            "total_agents": len(self.agents),
            "agent_types": {},
            "agent_weights": self.agent_weights.copy(),
            "decision_history_count": len(self.decision_history)
        }

        # 统计智能体类型
        type_counter = Counter([agent.agent_type for agent in self.agents])
        stats["agent_types"] = {str(k): v for k, v in dict(type_counter).items()}

        return stats

    def get_decision_history(
        self,
        symbol: str | None = None,
        limit: int = 100
    ) -> list[ConsensusDecision]:
        """获取决策历史"""
        history = self.decision_history

        if symbol:
            history = [d for d in history if d.symbol == symbol]

        return sorted(history, key=lambda x: x.timestamp, reverse=True)[:limit]


class HierarchicalPanel:
    """分层决策面板"""

    def __init__(
        self,
        retail_agents: list[Agent],
        institutional_agents: list[Agent],
        retail_weight: float = 0.3,
        institutional_weight: float = 0.7
    ):
        """
        初始化分层面板

        Args:
            retail_agents: 零售智能体
            institutional_agents: 机构智能体
            retail_weight: 零售权重
            institutional_weight: 机构权重
        """
        self.retail_panel = ExpertPanel(
            retail_agents,
            voting_strategy=VotingStrategy.MAJORITY,
            confidence_threshold=0.5
        )

        self.institutional_panel = ExpertPanel(
            institutional_agents,
            voting_strategy=VotingStrategy.CONFIDENCE_WEIGHTED,
            confidence_threshold=0.7
        )

        self.retail_weight = retail_weight
        self.institutional_weight = institutional_weight

    def make_decision(
        self,
        symbol: str,
        market_data: dict,
        context: dict | None = None
    ) -> ConsensusDecision:
        """分层决策"""

        # 分别获取零售和机构的决策
        retail_decision = self.retail_panel.make_consensus_decision(symbol, market_data, context)
        institutional_decision = self.institutional_panel.make_consensus_decision(symbol, market_data, context)

        # 加权合并
        action_scores = {Action.BUY: 0.0, Action.SELL: 0.0, Action.HOLD: 0.0}

        # 零售投资者影响
        retail_score = retail_decision.confidence * self.retail_weight
        action_scores[retail_decision.action] += retail_score

        # 机构投资者影响
        institutional_score = institutional_decision.confidence * self.institutional_weight
        action_scores[institutional_decision.action] += institutional_score

        # 最终决策
        final_action = max(action_scores, key=action_scores.get)
        total_score = sum(action_scores.values())
        final_confidence = action_scores[final_action] / total_score if total_score > 0 else 0

        # 汇总推理
        reasoning = (
            f"零售: {retail_decision.action.value} ({retail_decision.confidence:.2f}); "
            f"机构: {institutional_decision.action.value} ({institutional_decision.confidence:.2f}); "
            f"最终: {final_action.value} ({final_confidence:.2f})"
        )

        # 计算数量（加权平均）
        quantities = []
        if retail_decision.quantity:
            quantities.append(retail_decision.quantity * self.retail_weight)
        if institutional_decision.quantity:
            quantities.append(institutional_decision.quantity * self.institutional_weight)

        final_quantity = int(sum(quantities)) if quantities else None

        return ConsensusDecision(
            symbol=symbol,
            action=final_action,
            confidence=final_confidence,
            quantity=final_quantity,
            price=market_data.get("close"),
            reasoning=reasoning,
            agent_votes={
                "retail": retail_decision,
                "institutional": institutional_decision
            },
            voting_details={
                "action_scores": {str(k): v for k, v in action_scores.items()},
                "retail_weight": self.retail_weight,
                "institutional_weight": self.institutional_weight
            }
        )

"""
智能体基础类
定义智能体接口和基本行为
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np


class AgentType(Enum):
    """智能体类型"""
    # 零售投资者类型
    MOMENTUM_CHASER = "momentum_chaser"  # 追涨杀跌
    PANIC_SELLER = "panic_seller"  # 恐慌型
    HERD_FOLLOWER = "herd_follower"  # 跟风型
    VALUE_SEEKER = "value_seeker"  # 价值型
    TECHNICAL_TRADER = "technical_trader"  # 技术型

    # 机构投资者类型
    QUANTITATIVE = "quantitative"  # 量化对冲
    VALUE_INVESTOR = "value_investor"  # 价值投资
    TREND_FOLLOWER = "trend_follower"  # 趋势跟踪
    HIGH_FREQUENCY = "high_frequency"  # 高频交易
    INDEX_FUND = "index_fund"  # 指数基金


class Action(Enum):
    """交易动作"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class AgentDecision:
    """智能体决策"""
    agent_id: str
    agent_type: AgentType
    symbol: str
    action: Action
    confidence: float  # 0-1
    quantity: int | None = None
    price: float | None = None
    reasoning: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentState:
    """智能体状态"""
    agent_id: str
    agent_type: AgentType
    capital: float
    positions: dict[str, int] = field(default_factory=dict)
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    last_update: datetime = field(default_factory=datetime.now)


class Agent(ABC):
    """智能体基类"""

    def __init__(
        self,
        agent_id: str,
        agent_type: AgentType,
        initial_capital: float = 100000,
        risk_tolerance: float = 0.5,
        **kwargs
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.initial_capital = initial_capital
        self.risk_tolerance = risk_tolerance  # 0-1

        self.state = AgentState(
            agent_id=agent_id,
            agent_type=agent_type,
            capital=initial_capital
        )

        # 学习参数
        self.learning_rate = kwargs.get("learning_rate", 0.01)
        self.memory = []
        self.max_memory_size = kwargs.get("max_memory_size", 1000)

        # 行为参数
        self.parameters = self._init_parameters(**kwargs)

    @abstractmethod
    def _init_parameters(self, **kwargs) -> dict[str, Any]:
        """初始化智能体参数"""

    @abstractmethod
    def analyze(
        self,
        market_data: dict[str, Any],
        context: dict[str, Any] | None = None
    ) -> AgentDecision:
        """分析市场并做出决策"""

    def update_state(
        self,
        position_change: int = 0,
        capital_change: float = 0,
        realized_pnl: float = 0
    ):
        """更新智能体状态"""
        self.state.capital += capital_change
        self.state.realized_pnl += realized_pnl

        if position_change != 0:
            self.state.trade_count += 1
            if realized_pnl > 0:
                self.state.win_count += 1
            elif realized_pnl < 0:
                self.state.loss_count += 1

        self.state.last_update = datetime.now()

    def add_to_memory(self, experience: dict[str, Any]):
        """添加经验到记忆"""
        self.memory.append(experience)
        if len(self.memory) > self.max_memory_size:
            self.memory.pop(0)

    def learn_from_experience(self):
        """从经验中学习"""
        if len(self.memory) < 10:
            return

        # 简单的强化学习：调整参数基于近期表现
        recent_trades = self.memory[-10:]
        avg_pnl = np.mean([exp.get("pnl", 0) for exp in recent_trades])

        # 如果表现好，保持策略；如果表现差，调整参数
        if avg_pnl < 0:
            # 降低风险容忍度
            self.risk_tolerance *= 0.95
        elif avg_pnl > 0:
            # 略微提高风险容忍度
            self.risk_tolerance = min(1.0, self.risk_tolerance * 1.02)

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息"""
        total_trades = self.state.trade_count
        win_rate = self.state.win_count / total_trades if total_trades > 0 else 0

        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "capital": self.state.capital,
            "initial_capital": self.initial_capital,
            "return_rate": (self.state.capital - self.initial_capital) / self.initial_capital,
            "realized_pnl": self.state.realized_pnl,
            "unrealized_pnl": self.state.unrealized_pnl,
            "total_pnl": self.state.realized_pnl + self.state.unrealized_pnl,
            "trade_count": total_trades,
            "win_count": self.state.win_count,
            "loss_count": self.state.loss_count,
            "win_rate": win_rate,
            "risk_tolerance": self.risk_tolerance,
        }

    def reset(self):
        """重置智能体状态"""
        self.state = AgentState(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            capital=self.initial_capital
        )
        self.memory.clear()


class RetailAgent(Agent):
    """零售投资者基类"""

    def __init__(self, agent_id: str, agent_type: AgentType, **kwargs):
        super().__init__(agent_id, agent_type, **kwargs)
        self.emotion_factor = kwargs.get("emotion_factor", 0.5)  # 情绪因子
        self.herd_mentality = kwargs.get("herd_mentality", 0.5)  # 从众心理

    def _init_parameters(self, **kwargs) -> dict[str, Any]:
        return {
            "emotion_factor": kwargs.get("emotion_factor", 0.5),
            "herd_mentality": kwargs.get("herd_mentality", 0.5),
            "profit_target": kwargs.get("profit_target", 0.1),
            "stop_loss": kwargs.get("stop_loss", 0.05),
        }


class InstitutionalAgent(Agent):
    """机构投资者基类"""

    def __init__(self, agent_id: str, agent_type: AgentType, **kwargs):
        super().__init__(agent_id, agent_type, initial_capital=10000000, **kwargs)
        self.strategy_params = kwargs.get("strategy_params", {})

    def _init_parameters(self, **kwargs) -> dict[str, Any]:
        return {
            "position_sizing": kwargs.get("position_sizing", 0.1),
            "rebalance_threshold": kwargs.get("rebalance_threshold", 0.05),
            "max_drawdown": kwargs.get("max_drawdown", 0.15),
            "target_sharpe": kwargs.get("target_sharpe", 2.0),
        }


class MomentumChaserAgent(RetailAgent):
    """追涨杀跌型智能体"""

    def analyze(
        self,
        market_data: dict[str, Any],
        context: dict[str, Any] | None = None
    ) -> AgentDecision:
        symbol = market_data.get("symbol", "")
        price_change = market_data.get("price_change_pct", 0)
        volume_ratio = market_data.get("volume_ratio", 1.0)

        # 追涨杀跌逻辑
        if price_change > 0.03 and volume_ratio > 1.5:
            # 上涨且放量 -> 买入
            action = Action.BUY
            confidence = min(0.9, abs(price_change) * 10 * self.emotion_factor)
        elif price_change < -0.03:
            # 下跌 -> 卖出
            action = Action.SELL
            confidence = min(0.9, abs(price_change) * 10 * self.emotion_factor)
        else:
            action = Action.HOLD
            confidence = 0.3

        return AgentDecision(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            symbol=symbol,
            action=action,
            confidence=confidence,
            reasoning=f"价格变动{price_change:.2%}，成交量比{volume_ratio:.2f}"
        )


class PanicSellerAgent(RetailAgent):
    """恐慌型智能体"""

    def analyze(
        self,
        market_data: dict[str, Any],
        context: dict[str, Any] | None = None
    ) -> AgentDecision:
        symbol = market_data.get("symbol", "")
        price_change = market_data.get("price_change_pct", 0)
        volatility = market_data.get("volatility", 0)

        # 恐慌性抛售逻辑
        if price_change < -0.02 or volatility > 0.3:
            action = Action.SELL
            confidence = min(0.95, (abs(price_change) + volatility) * 5 * self.emotion_factor)
            reasoning = "市场下跌/波动大，恐慌性抛售"
        elif price_change > 0.05:
            # 反弹时买入
            action = Action.BUY
            confidence = 0.4
            reasoning = "反弹买入"
        else:
            action = Action.HOLD
            confidence = 0.5
            reasoning = "观望"

        return AgentDecision(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            symbol=symbol,
            action=action,
            confidence=confidence,
            reasoning=reasoning
        )


class QuantitativeAgent(InstitutionalAgent):
    """量化对冲基金智能体"""

    def analyze(
        self,
        market_data: dict[str, Any],
        context: dict[str, Any] | None = None
    ) -> AgentDecision:
        symbol = market_data.get("symbol", "")

        # 多因子量化模型
        factors = {
            "momentum": market_data.get("momentum_score", 0),
            "value": market_data.get("value_score", 0),
            "quality": market_data.get("quality_score", 0),
            "volatility": market_data.get("volatility", 0)
        }

        # 因子权重
        weights = {"momentum": 0.3, "value": 0.3, "quality": 0.2, "volatility": 0.2}

        # 计算综合得分
        score = sum(factors.get(k, 0) * w for k, w in weights.items())

        if score > 0.3:
            action = Action.BUY
            confidence = min(0.85, score * 2)
        elif score < -0.3:
            action = Action.SELL
            confidence = min(0.85, abs(score) * 2)
        else:
            action = Action.HOLD
            confidence = 0.6

        return AgentDecision(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            symbol=symbol,
            action=action,
            confidence=confidence,
            reasoning=f"量化得分: {score:.3f}"
        )


class ValueInvestorAgent(InstitutionalAgent):
    """价值投资基金智能体"""

    def analyze(
        self,
        market_data: dict[str, Any],
        context: dict[str, Any] | None = None
    ) -> AgentDecision:
        symbol = market_data.get("symbol", "")

        # 价值投资指标
        pe_ratio = market_data.get("pe_ratio", 20)
        pb_ratio = market_data.get("pb_ratio", 2)
        roe = market_data.get("roe", 0)
        debt_ratio = market_data.get("debt_ratio", 0.5)

        # 价值评估
        is_undervalued = pe_ratio < 15 and pb_ratio < 1.5
        is_quality = roe > 0.15 and debt_ratio < 0.6

        if is_undervalued and is_quality:
            action = Action.BUY
            confidence = 0.8
            reasoning = f"低估优质股: PE={pe_ratio:.1f}, PB={pb_ratio:.2f}, ROE={roe:.2%}"
        elif pe_ratio > 30 or pb_ratio > 3:
            action = Action.SELL
            confidence = 0.7
            reasoning = "估值过高"
        else:
            action = Action.HOLD
            confidence = 0.6
            reasoning = "估值合理"

        return AgentDecision(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            symbol=symbol,
            action=action,
            confidence=confidence,
            reasoning=reasoning
        )

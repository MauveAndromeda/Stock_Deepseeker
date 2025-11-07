"""
Backtest Engine Integration
多智能体系统与回测引擎的集成

Research-grade implementation (Under Development)
Ensures no lookahead bias when using multi-agent decisions
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd
from dataclasses import dataclass, field

from src.backtest.engine_v2 import Strategy, BacktestEngineV2, BacktestConfig
from src.backtest.events import SignalEvent
from src.backtest.portfolio_v2 import PortfolioV2
from src.agents.enhanced_base import LLMEnhancedAgent
from src.agents.langgraph_workflow import ExpertPanelWorkflow
from src.agents.base import Action
from src.agents.unified_interface import (
    MarketContext,
    AgentDecisionOutput,
    ActionType,
    IAgent
)
from loguru import logger


@dataclass
class MultiAgentDecisionRecord:
    """多智能体决策记录"""
    timestamp: datetime
    symbol: str
    agent_decisions: List[Dict]
    expert_panel_decision: Optional[Dict]
    final_action: str
    final_confidence: float
    consensus_method: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class MultiAgentStrategy(Strategy):
    """
    多智能体策略
    整合多个LLM智能体和专家面板的决策
    """

    def __init__(
        self,
        name: str = "MultiAgent",
        agents: Optional[List[LLMEnhancedAgent]] = None,
        use_expert_panel: bool = True,
        expert_panel_rounds: int = 2,
        consensus_threshold: float = 0.7,
        min_confidence: float = 0.6
    ):
        super().__init__(name)

        self.agents = agents or []
        self.use_expert_panel = use_expert_panel
        self.expert_panel_rounds = expert_panel_rounds
        self.consensus_threshold = consensus_threshold
        self.min_confidence = min_confidence

        # 专家面板
        self.expert_panel: Optional[ExpertPanelWorkflow] = None
        if self.use_expert_panel:
            self.expert_panel = ExpertPanelWorkflow(max_rounds=expert_panel_rounds)

        # 决策历史
        self.decision_history: List[MultiAgentDecisionRecord] = []

        # 统计
        self.total_signals = 0
        self.successful_signals = 0
        self.failed_signals = 0

    def generate_signals(
        self,
        date: datetime,
        data: Dict[str, pd.DataFrame],
        portfolio: PortfolioV2
    ) -> List[SignalEvent]:
        """
        生成交易信号（使用多智能体）

        重要：此方法在T日调用，生成的信号将在T+1日执行
        这确保了无前视偏差

        Args:
            date: 当前日期（信号生成日）
            data: 历史数据（到date为止）
            portfolio: 当前组合状态

        Returns:
            信号列表
        """
        # 同步包装器：回测引擎是同步的，但智能体是异步的
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果循环正在运行，创建新任务
                import nest_asyncio
                nest_asyncio.apply()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self._generate_signals_async(date, data, portfolio))

    async def _generate_signals_async(
        self,
        date: datetime,
        data: Dict[str, pd.DataFrame],
        portfolio: PortfolioV2
    ) -> List[SignalEvent]:
        """异步生成信号"""
        signals = []

        for symbol, df in data.items():
            if len(df) < 20:  # 需要足够的历史数据
                continue

            try:
                # 准备市场数据上下文
                market_data = self._prepare_market_data(symbol, df, date)

                # 1. 收集所有智能体的决策
                agent_decisions = await self._gather_agent_decisions(
                    symbol,
                    market_data
                )

                # 2. 如果启用，运行专家面板讨论
                expert_decision = None
                if self.use_expert_panel and self.expert_panel:
                    # Convert MarketContext to dict for workflow compatibility
                    market_data_dict = self._market_context_to_dict(market_data)

                    expert_result = await self.expert_panel.discuss(
                        symbol=symbol,
                        market_data=market_data_dict,
                        metadata={'agent_decisions': agent_decisions}
                    )
                    expert_decision = expert_result['final_decision']

                # 3. 综合决策
                final_action, final_confidence = self._synthesize_decisions(
                    agent_decisions,
                    expert_decision
                )

                # 4. 如果置信度足够，生成信号
                if final_confidence >= self.min_confidence and final_action != 'HOLD':
                    current_price = df['close'].iloc[-1]
                    position_obj = portfolio.get_position(symbol)
                    current_position = 0 if position_obj is None else position_obj.quantity

                    # 只在需要时生成信号
                    should_signal = False
                    signal_type = None

                    if final_action == 'BUY' and current_position == 0:
                        should_signal = True
                        signal_type = 'LONG'
                    elif final_action == 'SELL' and current_position > 0:
                        should_signal = True
                        signal_type = 'EXIT'

                    if should_signal:
                        signal = SignalEvent(
                            timestamp=date,
                            symbol=symbol,
                            signal_type=signal_type,
                            strength=final_confidence,
                            metadata={
                                'agent_count': len(agent_decisions),
                                'expert_panel_used': expert_decision is not None,
                                'consensus_confidence': final_confidence,
                                'price_at_signal': current_price
                            }
                        )
                        signals.append(signal)
                        self.total_signals += 1
                        logger.info(
                            f"Signal generated for {symbol}: {signal_type} "
                            f"(confidence: {final_confidence:.2f})"
                        )

                # 记录决策
                current_pos_for_record = 0
                if 'current_position' in locals():
                    current_pos_for_record = current_position
                else:
                    position_obj = portfolio.get_position(symbol)
                    current_pos_for_record = 0 if position_obj is None else position_obj.quantity

                self.decision_history.append(
                    MultiAgentDecisionRecord(
                        timestamp=date,
                        symbol=symbol,
                        agent_decisions=agent_decisions,
                        expert_panel_decision=expert_decision,
                        final_action=final_action,
                        final_confidence=final_confidence,
                        consensus_method='expert_panel' if expert_decision else 'agent_voting',
                        metadata={
                            'signal_generated': len(signals) > 0,
                            'current_position': current_pos_for_record
                        }
                    )
                )

            except Exception as e:
                logger.error(f"Error generating signals for {symbol}: {e}")
                continue

        return signals

    async def _gather_agent_decisions(
        self,
        symbol: str,
        market_data: MarketContext
    ) -> List[Dict]:
        """
        收集所有智能体的决策
        Uses unified interface (MarketContext -> AgentDecisionOutput)
        """
        decisions = []

        for agent in self.agents:
            try:
                # Use new unified interface
                decision = await agent.analyze(market_data)

                # Convert AgentDecisionOutput to dict for compatibility
                decisions.append({
                    'agent_id': decision.agent_id,
                    'agent_type': decision.agent_type,
                    'action': decision.action.value,
                    'confidence': decision.confidence,
                    'reasoning': decision.reasoning,
                    'metadata': decision.metadata,
                    'risk_level': decision.risk_level.value,
                    'key_factors': decision.key_factors
                })
            except Exception as e:
                logger.warning(f"Agent {agent.agent_id} failed: {e}")
                continue

        return decisions

    def _synthesize_decisions(
        self,
        agent_decisions: List[Dict],
        expert_decision: Optional[Dict]
    ) -> tuple[str, float]:
        """
        综合决策

        如果有专家面板决策，优先使用
        否则基于智能体投票
        """
        if expert_decision:
            return expert_decision['action'], expert_decision['confidence']

        if not agent_decisions:
            return 'HOLD', 0.5

        # 投票
        action_votes = {}
        total_confidence = 0

        for decision in agent_decisions:
            action = decision['action']
            confidence = decision['confidence']

            if action not in action_votes:
                action_votes[action] = {'count': 0, 'confidence_sum': 0}

            action_votes[action]['count'] += 1
            action_votes[action]['confidence_sum'] += confidence
            total_confidence += confidence

        # 选择得票最多的动作
        best_action = max(
            action_votes.items(),
            key=lambda x: (x[1]['count'], x[1]['confidence_sum'])
        )[0]

        # 计算平均置信度
        avg_confidence = action_votes[best_action]['confidence_sum'] / action_votes[best_action]['count']

        # 如果共识不够强，降低置信度
        agreement_ratio = action_votes[best_action]['count'] / len(agent_decisions)
        if agreement_ratio < self.consensus_threshold:
            avg_confidence *= agreement_ratio

        return best_action, avg_confidence

    def _prepare_market_data(
        self,
        symbol: str,
        df: pd.DataFrame,
        date: datetime
    ) -> MarketContext:
        """
        准备市场数据上下文
        Returns standardized MarketContext
        """
        # 获取最新数据
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        # 计算技术指标
        close_prices = df['close'].values
        sma_20 = float(close_prices[-20:].mean() if len(close_prices) >= 20 else close_prices.mean())
        sma_50 = float(close_prices[-50:].mean() if len(close_prices) >= 50 else close_prices.mean())

        # 计算变化
        price_change = (latest['close'] - prev['close']) / prev['close'] if prev['close'] > 0 else 0
        volume_change = (latest['volume'] - prev['volume']) / prev['volume'] if prev['volume'] > 0 else 0

        # Create standardized MarketContext
        return MarketContext(
            symbol=symbol,
            timestamp=date,
            current_price=float(latest['close']),
            price_change_pct=float(price_change),
            volume=int(latest['volume']),
            technical_indicators={
                'SMA_20': sma_20,
                'SMA_50': sma_50,
                'above_sma_20': 1.0 if float(latest['close']) > sma_20 else 0.0,
                'above_sma_50': 1.0 if float(latest['close']) > sma_50 else 0.0,
                'trend_score': 1.0 if sma_20 > sma_50 else -1.0,  # 1.0 = bullish, -1.0 = bearish
                'volume_change_pct': float(volume_change)
            },
            fundamentals={},
            sentiment=None,
            metadata={
                'trend': 'bullish' if sma_20 > sma_50 else 'bearish',  # Move string to metadata
                'ohlc': {
                    'open': float(latest['open']),
                    'high': float(latest['high']),
                    'low': float(latest['low']),
                    'close': float(latest['close'])
                }
            }
        )

    def _market_context_to_dict(self, context: MarketContext) -> Dict[str, Any]:
        """Convert MarketContext to dict for legacy compatibility"""
        return {
            'symbol': context.symbol,
            'date': context.timestamp,
            'price': context.current_price,
            'change_pct': context.price_change_pct,
            'volume': context.volume,
            'indicators': context.technical_indicators,
            'fundamentals': context.fundamentals,
            'sentiment': context.sentiment,
            **context.metadata
        }

    def get_performance_summary(self) -> Dict[str, Any]:
        """获取策略表现总结"""
        if self.total_signals == 0:
            return {
                'total_signals': 0,
                'success_rate': 0,
                'avg_confidence': 0,
                'decision_count': len(self.decision_history)
            }

        # 计算平均置信度
        avg_confidence = sum(
            d.final_confidence for d in self.decision_history
        ) / len(self.decision_history) if self.decision_history else 0

        return {
            'total_signals': self.total_signals,
            'successful_signals': self.successful_signals,
            'failed_signals': self.failed_signals,
            'success_rate': self.successful_signals / self.total_signals if self.total_signals > 0 else 0,
            'avg_confidence': avg_confidence,
            'decision_count': len(self.decision_history),
            'agent_count': len(self.agents)
        }


# 便捷函数

async def create_default_multi_agent_strategy(
    use_expert_panel: bool = True,
    register_agents: bool = True
) -> MultiAgentStrategy:
    """
    创建默认的多智能体策略

    Args:
        use_expert_panel: 是否使用专家面板
        register_agents: 是否将智能体注册到全局注册表

    Returns:
        配置好的多智能体策略
    """
    from src.agents.enhanced_base import (
        MomentumChaserAgent,
        ValueSeekerAgent,
        TechnicalTraderAgent,
        QuantitativeAgent
    )
    from src.agents.unified_interface import get_agent_registry
    from src.ai.model_unified import ModelTier

    # 创建多样化的智能体（使用新的统一接口）
    agents = [
        MomentumChaserAgent(
            agent_id="momentum_1",
            model_tier=ModelTier.FAST
        ),
        ValueSeekerAgent(
            agent_id="value_1",
            model_tier=ModelTier.FAST
        ),
        TechnicalTraderAgent(
            agent_id="technical_1",
            model_tier=ModelTier.FAST
        ),
        QuantitativeAgent(
            agent_id="quant_1",
            model_tier=ModelTier.BALANCED
        )
    ]

    # 注册到全局注册表
    if register_agents:
        registry = get_agent_registry()
        for agent in agents:
            registry.register(agent)
            logger.info(f"Registered agent: {agent.agent_id} with capabilities: {agent.capabilities}")

    strategy = MultiAgentStrategy(
        name="MultiAgent_Default",
        agents=agents,
        use_expert_panel=use_expert_panel,
        expert_panel_rounds=2,
        consensus_threshold=0.6,
        min_confidence=0.65
    )

    return strategy

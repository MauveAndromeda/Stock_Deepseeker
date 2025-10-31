"""
零售投资者智能体实现
模拟散户交易行为
"""

import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime

from src.agents.base import Agent, AgentType, AgentDecision, Action


class MomentumChaserAgent(Agent):
    """追涨杀跌型散户"""

    def _init_parameters(self, **kwargs) -> Dict[str, Any]:
        return {
            'momentum_threshold': kwargs.get('momentum_threshold', 0.02),  # 2%涨幅触发
            'panic_threshold': kwargs.get('panic_threshold', -0.03),  # -3%跌幅恐慌
            'chase_probability': kwargs.get('chase_probability', 0.7),  # 追涨概率
            'holding_period': kwargs.get('holding_period', 3),  # 持仓天数
        }

    def analyze(self, market_data: Dict, context: Optional[Dict] = None) -> AgentDecision:
        """分析市场数据并做出决策"""
        symbol = market_data.get('symbol')
        current_price = market_data.get('close')
        prev_price = market_data.get('prev_close', current_price)

        # 计算涨跌幅
        change_pct = (current_price - prev_price) / prev_price if prev_price > 0 else 0

        # 检查是否持有该股票
        position = self.state.positions.get(symbol, 0)

        # 决策逻辑
        if position == 0:
            # 追涨逻辑
            if change_pct >= self.parameters['momentum_threshold']:
                if np.random.random() < self.parameters['chase_probability']:
                    quantity = int(self.state.capital * self.risk_tolerance * 0.3 / current_price)
                    return AgentDecision(
                        agent_id=self.agent_id,
                        agent_type=self.agent_type,
                        symbol=symbol,
                        action=Action.BUY,
                        confidence=min(0.9, 0.5 + change_pct * 10),
                        quantity=quantity,
                        price=current_price,
                        reasoning=f"追涨：股价上涨{change_pct*100:.2f}%"
                    )
        else:
            # 止损逻辑
            if change_pct <= self.parameters['panic_threshold']:
                return AgentDecision(
                    agent_id=self.agent_id,
                    agent_type=self.agent_type,
                    symbol=symbol,
                    action=Action.SELL,
                    confidence=0.95,
                    quantity=position,
                    price=current_price,
                    reasoning=f"恐慌性止损：下跌{abs(change_pct)*100:.2f}%"
                )

        return AgentDecision(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            symbol=symbol,
            action=Action.HOLD,
            confidence=0.5,
            reasoning="等待追涨机会"
        )


class PanicSellerAgent(Agent):
    """恐慌型散户"""

    def _init_parameters(self, **kwargs) -> Dict[str, Any]:
        return {
            'panic_threshold': kwargs.get('panic_threshold', -0.02),  # -2%触发恐慌
            'panic_intensity': kwargs.get('panic_intensity', 0.8),  # 恐慌强度
            'recovery_time': kwargs.get('recovery_time', 5),  # 恢复时间（天）
        }

    def analyze(self, market_data: Dict, context: Optional[Dict] = None) -> AgentDecision:
        """恐慌型决策"""
        symbol = market_data.get('symbol')
        current_price = market_data.get('close')
        prev_price = market_data.get('prev_close', current_price)
        volume = market_data.get('volume', 0)

        change_pct = (current_price - prev_price) / prev_price if prev_price > 0 else 0
        position = self.state.positions.get(symbol, 0)

        # 恐慌性卖出
        if position > 0 and change_pct <= self.parameters['panic_threshold']:
            sell_ratio = min(1.0, self.parameters['panic_intensity'] * abs(change_pct) * 10)
            quantity = int(position * sell_ratio)

            return AgentDecision(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                symbol=symbol,
                action=Action.SELL,
                confidence=0.9,
                quantity=max(1, quantity),
                price=current_price,
                reasoning=f"恐慌抛售：{abs(change_pct)*100:.2f}%下跌触发恐慌"
            )

        return AgentDecision(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            symbol=symbol,
            action=Action.HOLD,
            confidence=0.6,
            reasoning="观望中"
        )


class HerdFollowerAgent(Agent):
    """跟风型散户"""

    def _init_parameters(self, **kwargs) -> Dict[str, Any]:
        return {
            'follow_threshold': kwargs.get('follow_threshold', 0.6),  # 跟风阈值
            'volume_multiplier': kwargs.get('volume_multiplier', 1.5),  # 成交量倍数
            'confidence_decay': kwargs.get('confidence_decay', 0.9),  # 信心衰减
        }

    def analyze(self, market_data: Dict, context: Optional[Dict] = None) -> AgentDecision:
        """跟风决策"""
        symbol = market_data.get('symbol')
        current_price = market_data.get('close')
        volume = market_data.get('volume', 0)
        avg_volume = market_data.get('avg_volume', volume)

        # 检查成交量是否异常放大
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0

        # 获取社会情绪（如果有）
        social_sentiment = context.get('social_sentiment', 0.5) if context else 0.5

        position = self.state.positions.get(symbol, 0)

        # 跟风买入
        if position == 0 and volume_ratio >= self.parameters['volume_multiplier']:
            if social_sentiment >= self.parameters['follow_threshold']:
                quantity = int(self.state.capital * self.risk_tolerance * 0.2 / current_price)
                return AgentDecision(
                    agent_id=self.agent_id,
                    agent_type=self.agent_type,
                    symbol=symbol,
                    action=Action.BUY,
                    confidence=social_sentiment,
                    quantity=quantity,
                    price=current_price,
                    reasoning=f"跟风买入：成交量{volume_ratio:.1f}倍，情绪{social_sentiment:.2f}"
                )

        return AgentDecision(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            symbol=symbol,
            action=Action.HOLD,
            confidence=0.5,
            reasoning="等待跟风信号"
        )


class ValueSeekerAgent(Agent):
    """价值型散户"""

    def _init_parameters(self, **kwargs) -> Dict[str, Any]:
        return {
            'pe_threshold': kwargs.get('pe_threshold', 15),  # PE阈值
            'pb_threshold': kwargs.get('pb_threshold', 2),  # PB阈值
            'div_yield_min': kwargs.get('div_yield_min', 0.03),  # 最低股息率
            'margin_of_safety': kwargs.get('margin_of_safety', 0.2),  # 安全边际
        }

    def analyze(self, market_data: Dict, context: Optional[Dict] = None) -> AgentDecision:
        """价值投资决策"""
        symbol = market_data.get('symbol')
        current_price = market_data.get('close')

        # 获取估值指标（需要从context传入）
        pe_ratio = context.get('pe_ratio', 20) if context else 20
        pb_ratio = context.get('pb_ratio', 2.5) if context else 2.5
        dividend_yield = context.get('dividend_yield', 0.02) if context else 0.02

        position = self.state.positions.get(symbol, 0)

        # 价值投资逻辑
        is_undervalued = (
            pe_ratio <= self.parameters['pe_threshold'] and
            pb_ratio <= self.parameters['pb_threshold'] and
            dividend_yield >= self.parameters['div_yield_min']
        )

        if position == 0 and is_undervalued:
            quantity = int(self.state.capital * self.risk_tolerance * 0.4 / current_price)
            return AgentDecision(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                symbol=symbol,
                action=Action.BUY,
                confidence=0.8,
                quantity=quantity,
                price=current_price,
                reasoning=f"价值投资：PE={pe_ratio:.1f}, PB={pb_ratio:.1f}, 股息率={dividend_yield:.2%}"
            )

        return AgentDecision(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            symbol=symbol,
            action=Action.HOLD,
            confidence=0.6,
            reasoning="等待低估机会"
        )


class TechnicalTraderAgent(Agent):
    """技术分析型散户"""

    def _init_parameters(self, **kwargs) -> Dict[str, Any]:
        return {
            'rsi_oversold': kwargs.get('rsi_oversold', 30),  # RSI超卖
            'rsi_overbought': kwargs.get('rsi_overbought', 70),  # RSI超买
            'macd_threshold': kwargs.get('macd_threshold', 0),  # MACD阈值
            'volume_confirmation': kwargs.get('volume_confirmation', True),  # 成交量确认
        }

    def analyze(self, market_data: Dict, context: Optional[Dict] = None) -> AgentDecision:
        """技术分析决策"""
        symbol = market_data.get('symbol')
        current_price = market_data.get('close')

        # 技术指标
        rsi = market_data.get('rsi', 50)
        macd = market_data.get('macd', 0)
        macd_signal = market_data.get('macd_signal', 0)
        volume = market_data.get('volume', 0)
        avg_volume = market_data.get('avg_volume', volume)

        position = self.state.positions.get(symbol, 0)

        # 买入信号
        buy_signal = (
            rsi <= self.parameters['rsi_oversold'] and
            macd > macd_signal
        )

        # 卖出信号
        sell_signal = (
            rsi >= self.parameters['rsi_overbought'] and
            macd < macd_signal
        )

        # 成交量确认
        volume_confirmed = volume >= avg_volume * 0.8 if self.parameters['volume_confirmation'] else True

        if position == 0 and buy_signal and volume_confirmed:
            quantity = int(self.state.capital * self.risk_tolerance * 0.35 / current_price)
            return AgentDecision(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                symbol=symbol,
                action=Action.BUY,
                confidence=0.75,
                quantity=quantity,
                price=current_price,
                reasoning=f"技术买入：RSI={rsi:.1f}, MACD金叉"
            )

        if position > 0 and sell_signal and volume_confirmed:
            return AgentDecision(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                symbol=symbol,
                action=Action.SELL,
                confidence=0.75,
                quantity=position,
                price=current_price,
                reasoning=f"技术卖出：RSI={rsi:.1f}, MACD死叉"
            )

        return AgentDecision(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            symbol=symbol,
            action=Action.HOLD,
            confidence=0.5,
            reasoning="技术指标观望"
        )


class RetailAgentFactory:
    """零售投资者工厂类"""

    _agent_classes = {
        AgentType.MOMENTUM_CHASER: MomentumChaserAgent,
        AgentType.PANIC_SELLER: PanicSellerAgent,
        AgentType.HERD_FOLLOWER: HerdFollowerAgent,
        AgentType.VALUE_SEEKER: ValueSeekerAgent,
        AgentType.TECHNICAL_TRADER: TechnicalTraderAgent,
    }

    @classmethod
    def create_agent(
        cls,
        agent_type: AgentType,
        agent_id: Optional[str] = None,
        **kwargs
    ) -> Agent:
        """创建智能体"""
        if agent_type not in cls._agent_classes:
            raise ValueError(f"Unknown retail agent type: {agent_type}")

        if agent_id is None:
            agent_id = f"{agent_type.value}_{datetime.now().timestamp()}"

        agent_class = cls._agent_classes[agent_type]
        return agent_class(agent_id=agent_id, agent_type=agent_type, **kwargs)

    @classmethod
    def create_population(
        cls,
        population_config: Dict[AgentType, int],
        **shared_kwargs
    ) -> List[Agent]:
        """创建智能体群体

        Args:
            population_config: {agent_type: count} 字典
            **shared_kwargs: 共享参数

        Returns:
            智能体列表
        """
        agents = []

        for agent_type, count in population_config.items():
            for i in range(count):
                agent_id = f"{agent_type.value}_{i}"
                agent = cls.create_agent(agent_type, agent_id, **shared_kwargs)
                agents.append(agent)

        return agents

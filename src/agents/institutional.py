"""
机构投资者智能体实现
模拟专业投资机构行为
"""

from datetime import datetime
from typing import Any

from src.agents.base import Action, Agent, AgentDecision, AgentType


class QuantitativeAgent(Agent):
    """量化对冲基金"""

    def _init_parameters(self, **kwargs) -> dict[str, Any]:
        return {
            "sharpe_threshold": kwargs.get("sharpe_threshold", 1.5),  # 夏普率阈值
            "max_position_size": kwargs.get("max_position_size", 0.1),  # 最大持仓比例
            "rebalance_frequency": kwargs.get("rebalance_frequency", 5),  # 调仓频率（天）
            "volatility_target": kwargs.get("volatility_target", 0.15),  # 目标波动率
            "alpha_threshold": kwargs.get("alpha_threshold", 0.01),  # Alpha阈值
        }

    def analyze(self, market_data: dict, context: dict | None = None) -> AgentDecision:
        """量化分析决策"""
        symbol = market_data.get("symbol")
        current_price = market_data.get("close")

        # 量化指标
        alpha = context.get("alpha", 0) if context else 0
        beta = context.get("beta", 1) if context else 1
        sharpe = context.get("sharpe_ratio", 0) if context else 0
        volatility = context.get("volatility", 0.2) if context else 0.2

        position = self.state.positions.get(symbol, 0)
        current_position_value = position * current_price
        total_value = self.state.capital + sum(
            pos * current_price for pos in self.state.positions.values()
        )

        # 目标仓位
        if sharpe >= self.parameters["sharpe_threshold"] and alpha >= self.parameters["alpha_threshold"]:
            # 根据波动率调整仓位
            vol_adjustment = self.parameters["volatility_target"] / max(volatility, 0.01)
            target_weight = min(self.parameters["max_position_size"], vol_adjustment * 0.05)
            target_value = total_value * target_weight
            target_position = int(target_value / current_price)

            # 计算需要调整的数量
            delta = target_position - position

            if abs(delta) > 0:
                action = Action.BUY if delta > 0 else Action.SELL
                quantity = abs(delta)

                return AgentDecision(
                    agent_id=self.agent_id,
                    agent_type=self.agent_type,
                    symbol=symbol,
                    action=action,
                    confidence=min(0.95, 0.6 + sharpe * 0.1),
                    quantity=quantity,
                    price=current_price,
                    reasoning=f"量化调仓：Alpha={alpha:.4f}, Sharpe={sharpe:.2f}, 目标仓位={target_weight:.2%}"
                )

        # 风险控制：波动率过高时减仓
        if position > 0 and volatility > self.parameters["volatility_target"] * 1.5:
            reduce_ratio = 0.3
            quantity = int(position * reduce_ratio)

            return AgentDecision(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                symbol=symbol,
                action=Action.SELL,
                confidence=0.85,
                quantity=quantity,
                price=current_price,
                reasoning=f"波动率风控：当前={volatility:.2%}, 目标={self.parameters['volatility_target']:.2%}"
            )

        return AgentDecision(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            symbol=symbol,
            action=Action.HOLD,
            confidence=0.7,
            reasoning="持仓观察"
        )


class ValueInvestorAgent(Agent):
    """价值投资机构"""

    def _init_parameters(self, **kwargs) -> dict[str, Any]:
        return {
            "dcf_discount": kwargs.get("dcf_discount", 0.3),  # DCF估值折扣
            "roe_threshold": kwargs.get("roe_threshold", 0.15),  # ROE阈值
            "debt_ratio_max": kwargs.get("debt_ratio_max", 0.5),  # 最大负债率
            "fcf_yield_min": kwargs.get("fcf_yield_min", 0.05),  # 最小自由现金流收益率
            "holding_period_min": kwargs.get("holding_period_min", 90),  # 最小持仓天数
        }

    def analyze(self, market_data: dict, context: dict | None = None) -> AgentDecision:
        """价值投资决策"""
        symbol = market_data.get("symbol")
        current_price = market_data.get("close")

        # 基本面指标
        intrinsic_value = context.get("intrinsic_value", current_price) if context else current_price
        roe = context.get("roe", 0.1) if context else 0.1
        debt_ratio = context.get("debt_ratio", 0.3) if context else 0.3
        fcf_yield = context.get("fcf_yield", 0.03) if context else 0.03

        position = self.state.positions.get(symbol, 0)

        # 安全边际
        margin_of_safety = (intrinsic_value - current_price) / intrinsic_value if intrinsic_value > 0 else 0

        # 价值投资标准
        is_quality = (
            roe >= self.parameters["roe_threshold"] and
            debt_ratio <= self.parameters["debt_ratio_max"] and
            fcf_yield >= self.parameters["fcf_yield_min"]
        )

        # 买入逻辑
        if position == 0 and is_quality and margin_of_safety >= self.parameters["dcf_discount"]:
            # 大额建仓
            target_weight = 0.15  # 15%仓位
            total_value = self.state.capital
            target_value = total_value * target_weight
            quantity = int(target_value / current_price)

            return AgentDecision(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                symbol=symbol,
                action=Action.BUY,
                confidence=0.9,
                quantity=quantity,
                price=current_price,
                reasoning=f"价值投资：安全边际={margin_of_safety:.2%}, ROE={roe:.2%}, 内在价值=${intrinsic_value:.2f}"
            )

        # 长期持有，不轻易卖出
        return AgentDecision(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            symbol=symbol,
            action=Action.HOLD,
            confidence=0.8,
            reasoning="长期价值持有"
        )


class TrendFollowerAgent(Agent):
    """趋势跟踪基金"""

    def _init_parameters(self, **kwargs) -> dict[str, Any]:
        return {
            "trend_period": kwargs.get("trend_period", 50),  # 趋势周期
            "breakout_threshold": kwargs.get("breakout_threshold", 0.02),  # 突破阈值
            "atr_multiplier": kwargs.get("atr_multiplier", 2.0),  # ATR止损倍数
            "pyramid_levels": kwargs.get("pyramid_levels", 3),  # 金字塔加仓层数
        }

    def analyze(self, market_data: dict, context: dict | None = None) -> AgentDecision:
        """趋势跟踪决策"""
        symbol = market_data.get("symbol")
        current_price = market_data.get("close")

        # 趋势指标
        ma_50 = market_data.get("ma_50", current_price)
        ma_200 = market_data.get("ma_200", current_price)
        atr = market_data.get("atr", current_price * 0.02)

        # 最高价（用于判断突破）
        high_52w = context.get("high_52w", current_price) if context else current_price

        position = self.state.positions.get(symbol, 0)

        # 趋势判断
        is_uptrend = ma_50 > ma_200 and current_price > ma_50
        is_breakout = current_price >= high_52w * (1 - self.parameters["breakout_threshold"])

        # 买入逻辑
        if is_uptrend and is_breakout:
            if position == 0:
                # 首次建仓
                quantity = int(self.state.capital * 0.1 / current_price)
                return AgentDecision(
                    agent_id=self.agent_id,
                    agent_type=self.agent_type,
                    symbol=symbol,
                    action=Action.BUY,
                    confidence=0.85,
                    quantity=quantity,
                    price=current_price,
                    reasoning=f"趋势建仓：突破52周新高，MA50={ma_50:.2f} > MA200={ma_200:.2f}"
                )
            if position > 0 and current_price > ma_50 * 1.05:
                # 金字塔加仓
                add_quantity = int(position * 0.5)
                return AgentDecision(
                    agent_id=self.agent_id,
                    agent_type=self.agent_type,
                    symbol=symbol,
                    action=Action.BUY,
                    confidence=0.75,
                    quantity=add_quantity,
                    price=current_price,
                    reasoning="趋势加仓：价格持续上涨"
                )

        # 止损逻辑
        if position > 0:
            stop_loss = ma_50 - atr * self.parameters["atr_multiplier"]
            if current_price < stop_loss:
                return AgentDecision(
                    agent_id=self.agent_id,
                    agent_type=self.agent_type,
                    symbol=symbol,
                    action=Action.SELL,
                    confidence=0.95,
                    quantity=position,
                    price=current_price,
                    reasoning=f"趋势止损：价格${current_price:.2f} < 止损位${stop_loss:.2f}"
                )

        return AgentDecision(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            symbol=symbol,
            action=Action.HOLD,
            confidence=0.6,
            reasoning="等待趋势信号"
        )


class HighFrequencyAgent(Agent):
    """高频交易机构"""

    def _init_parameters(self, **kwargs) -> dict[str, Any]:
        return {
            "tick_threshold": kwargs.get("tick_threshold", 0.0005),  # 0.05%价差
            "holding_seconds": kwargs.get("holding_seconds", 60),  # 持仓秒数
            "spread_requirement": kwargs.get("spread_requirement", 0.001),  # 价差要求
            "liquidity_threshold": kwargs.get("liquidity_threshold", 100000),  # 流动性要求
        }

    def analyze(self, market_data: dict, context: dict | None = None) -> AgentDecision:
        """高频交易决策"""
        symbol = market_data.get("symbol")
        current_price = market_data.get("close")

        # 订单簿数据
        bid_price = market_data.get("bid", current_price * 0.999)
        ask_price = market_data.get("ask", current_price * 1.001)
        bid_volume = market_data.get("bid_volume", 1000)
        ask_volume = market_data.get("ask_volume", 1000)

        # 计算价差
        spread = (ask_price - bid_price) / current_price if current_price > 0 else 0

        position = self.state.positions.get(symbol, 0)

        # 高频策略：做市
        if spread >= self.parameters["spread_requirement"]:
            liquidity = min(bid_volume, ask_volume)

            if liquidity >= self.parameters["liquidity_threshold"]:
                if position <= 0:
                    # 在买一价买入
                    quantity = min(100, int(liquidity * 0.1))
                    return AgentDecision(
                        agent_id=self.agent_id,
                        agent_type=self.agent_type,
                        symbol=symbol,
                        action=Action.BUY,
                        confidence=0.7,
                        quantity=quantity,
                        price=bid_price,
                        reasoning=f"HFT做市买入：价差={spread:.4%}"
                    )
                if position > 0:
                    # 在卖一价卖出
                    return AgentDecision(
                        agent_id=self.agent_id,
                        agent_type=self.agent_type,
                        symbol=symbol,
                        action=Action.SELL,
                        confidence=0.7,
                        quantity=position,
                        price=ask_price,
                        reasoning=f"HFT做市卖出：获利={spread:.4%}"
                    )

        return AgentDecision(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            symbol=symbol,
            action=Action.HOLD,
            confidence=0.5,
            reasoning="等待价差机会"
        )


class IndexFundAgent(Agent):
    """指数基金"""

    def _init_parameters(self, **kwargs) -> dict[str, Any]:
        return {
            "index_weights": kwargs.get("index_weights", {}),  # 指数成分权重
            "rebalance_threshold": kwargs.get("rebalance_threshold", 0.05),  # 5%偏差调仓
            "tracking_error_max": kwargs.get("tracking_error_max", 0.02),  # 最大跟踪误差
        }

    def analyze(self, market_data: dict, context: dict | None = None) -> AgentDecision:
        """指数跟踪决策"""
        symbol = market_data.get("symbol")
        current_price = market_data.get("close")

        # 获取目标权重
        target_weight = self.parameters["index_weights"].get(symbol, 0)

        if target_weight == 0:
            return AgentDecision(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                symbol=symbol,
                action=Action.HOLD,
                confidence=0.5,
                reasoning="非指数成分股"
            )

        # 计算当前权重
        position = self.state.positions.get(symbol, 0)
        position_value = position * current_price
        total_value = self.state.capital + sum(
            pos * current_price for pos in self.state.positions.values()
        )
        current_weight = position_value / total_value if total_value > 0 else 0

        # 权重偏差
        weight_deviation = abs(current_weight - target_weight)

        # 调仓逻辑
        if weight_deviation >= self.parameters["rebalance_threshold"]:
            target_value = total_value * target_weight
            target_position = int(target_value / current_price)
            delta = target_position - position

            if abs(delta) > 0:
                action = Action.BUY if delta > 0 else Action.SELL
                quantity = abs(delta)

                return AgentDecision(
                    agent_id=self.agent_id,
                    agent_type=self.agent_type,
                    symbol=symbol,
                    action=action,
                    confidence=0.95,
                    quantity=quantity,
                    price=current_price,
                    reasoning=f"指数调仓：目标权重={target_weight:.2%}, 当前={current_weight:.2%}, 偏差={weight_deviation:.2%}"
                )

        return AgentDecision(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            symbol=symbol,
            action=Action.HOLD,
            confidence=0.9,
            reasoning="权重符合指数"
        )


class InstitutionalAgentFactory:
    """机构投资者工厂类"""

    _agent_classes = {
        AgentType.QUANTITATIVE: QuantitativeAgent,
        AgentType.VALUE_INVESTOR: ValueInvestorAgent,
        AgentType.TREND_FOLLOWER: TrendFollowerAgent,
        AgentType.HIGH_FREQUENCY: HighFrequencyAgent,
        AgentType.INDEX_FUND: IndexFundAgent,
    }

    @classmethod
    def create_agent(
        cls,
        agent_type: AgentType,
        agent_id: str | None = None,
        **kwargs
    ) -> Agent:
        """创建机构智能体"""
        if agent_type not in cls._agent_classes:
            raise ValueError(f"Unknown institutional agent type: {agent_type}")

        if agent_id is None:
            agent_id = f"{agent_type.value}_{datetime.now().timestamp()}"

        agent_class = cls._agent_classes[agent_type]
        return agent_class(agent_id=agent_id, agent_type=agent_type, **kwargs)

    @classmethod
    def create_population(
        cls,
        population_config: dict[AgentType, int],
        **shared_kwargs
    ) -> list[Agent]:
        """创建机构智能体群体"""
        agents = []

        for agent_type, count in population_config.items():
            for i in range(count):
                agent_id = f"{agent_type.value}_{i}"
                agent = cls.create_agent(agent_type, agent_id, **shared_kwargs)
                agents.append(agent)

        return agents
